"""Leitura da base de busca e do CNEFE (CSV ou Parquet, inclusive diretorio gerado pelo Spark)."""
import logging
from pathlib import Path

import pandas as pd

from . import config
from .normalize import (chave_comparacao, normalizar_cep, normalizar_municipio,
            normalizar_texto, parse_numero)

log = logging.getLogger(__name__)


def ler_busca(caminho: str) -> pd.DataFrame:
  p = Path(caminho)
  if not p.exists():
    raise FileNotFoundError(f"Base de busca nao encontrada: {p}")
  if p.suffix.lower() in (".xlsx", ".xls"):
    df = pd.read_excel(p, dtype=str)
  elif p.suffix.lower() == ".parquet" or p.is_dir():
    df = pd.read_parquet(p)
  else:
    df = pd.read_csv(p, dtype=str, sep=None, engine="python", na_values=["NULL"])
  df.columns = [c.strip() for c in df.columns]
  df = df.astype(object)
  return df.where(df.notna(), None)


def _abrir_texto(caminho: Path):
  for enc in ("utf-8", "latin1"):
    try:
      with open(caminho, encoding=enc) as f:
        linha = f.readline()
        f.read(2_000_000)
      return enc, linha
    except UnicodeDecodeError:
      continue
  return "latin1", ""


def ler_cnefe_filtrado(caminho: str, municipios6: set, ceps: set,
           sep: str | None = None, encoding: str | None = None,
           chunksize: int = 500_000) -> pd.DataFrame:
  """Le o CNEFE mantendo so linhas dos municipios (6 digitos) OU CEPs da base de busca.
  Isso reduz milhoes de linhas para o que realmente importa."""
  p = Path(caminho)
  if not p.exists():
    raise FileNotFoundError(f"CNEFE nao encontrado: {p}")
  cols = list(config.CNEFE.values())
  c_mun, c_cep = config.CNEFE["municipio"], config.CNEFE["cep"]

  def filtrar(df):
    mun6 = df[c_mun].astype(str).str.replace(r"\D", "", regex=True).str[:6]
    cep = df[c_cep].astype(str).str.replace(r"\D", "", regex=True).str.zfill(8)
    return df[mun6.isin(municipios6) | cep.isin(ceps)]

  if p.is_dir() or p.suffix.lower() == ".parquet":
    log.info("Lendo CNEFE (parquet): %s", p)
    df = pd.read_parquet(p, columns=cols).astype(object)
    df = df.where(df.notna(), None).replace({"NULL": None})
    return filtrar(df)

  enc, linha = _abrir_texto(p)
  encoding = encoding or enc
  if sep is None:
    sep = max([";", ",", "|", "\t"], key=linha.count)
  log.info("Lendo CNEFE (csv) sep=%r encoding=%s: %s", sep, encoding, p)
  partes, total = [], 0
  for chunk in pd.read_csv(p, sep=sep, encoding=encoding, dtype=str, usecols=cols,
              na_values=["NULL"], chunksize=chunksize):
    total += len(chunk)
    partes.append(filtrar(chunk))
  df = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=cols)
  log.info("CNEFE: %d linhas lidas, %d mantidas apos filtro", total, len(df))
  return df


def _mapear_unicos(serie: pd.Series, func) -> pd.Series:
  """Aplica func so nos valores unicos (muito mais rapido em bases grandes)."""
  cache = {v: func(v) for v in serie.dropna().unique()}
  return serie.map(cache)


def preparar_cnefe(df: pd.DataFrame) -> pd.DataFrame:
  """Normaliza o CNEFE e devolve colunas internas prontas para o matching."""
  c = config.CNEFE
  df = df[list(c.values())].drop_duplicates().copy() # COD_UNICO_ENDERECO repete por especie
  out = pd.DataFrame(index=df.index)
  out["mun6"] = _mapear_unicos(df[c["municipio"]], normalizar_municipio)
  out["setor"] = df[c["setor"]].astype(str).str.strip()
  out["cep"] = _mapear_unicos(df[c["cep"]], normalizar_cep)
  out["localidade_key"] = _mapear_unicos(
    df[c["localidade"]], lambda v: chave_comparacao(normalizar_texto(v))).fillna("")
  tipo = _mapear_unicos(df[c["tipo"]], normalizar_texto).fillna("")
  titulo = _mapear_unicos(df[c["titulo"]], lambda v: normalizar_texto(v, False)).fillna("")
  nome = _mapear_unicos(df[c["nome"]], lambda v: normalizar_texto(v, False)).fillna("")
  out["tipo"] = tipo
  padrao_generico = r"^(?:SEM\s+DENO|SEM\s+NOME|PROJETAD|RUA\s+PROJETAD)"
  out["nome_valido"] = ~nome.str.upper().str.contains(padrao_generico, regex=True, na=False) & ~nome.isin(["", "SEM DENOMINACAO", "SEM NOME"])
  nome_completo = (titulo + " " + nome).str.strip()
  out["street_nome_key"] = nome_completo.map(chave_comparacao)
  out["street_full_key"] = (tipo + " " + nome_completo).str.strip().map(chave_comparacao)
  out["numero"] = _mapear_unicos(df[c["numero"]], parse_numero).astype(float)
  out = out.dropna(subset=["mun6", "setor"]).drop_duplicates()
  return out.reset_index(drop=True)
