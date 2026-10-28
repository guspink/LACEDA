"""Pipeline: leitura -> filtro do CNEFE -> normalizacao -> vinculacao -> saida + metricas.

Uso:
  python -m src.main --cnefe data/cnefe_bahia.csv --busca data/base_busca.csv \
           --saida output/resultado_final.csv
"""
import argparse
import logging
import sys

import pandas as pd

from . import config
from .ingest import ler_busca, ler_cnefe_filtrado, preparar_cnefe
from .matcher import IndiceCnefe, casar, preparar_consulta

log = logging.getLogger("geocoding")


def executar(cnefe_path, busca_path, sep=None, encoding=None, engine="pandas",
      cache_dir="data/cache", force=False) -> pd.DataFrame:
  busca = ler_busca(busca_path)
  log.info("Base de busca: %d registros", len(busca))
  faltantes = [c for c in config.BUSCA.values() if c not in busca.columns]
  if faltantes:
    log.warning("Colunas esperadas ausentes na busca (ajuste config.BUSCA): %s", faltantes)

  consultas = [preparar_consulta(r) for r in busca.to_dict("records")]
  municipios = {c.mun6 for c in consultas if c.mun6}
  ceps = {c.cep for c in consultas if c.cep}

  if engine == "spark":
    from .spark_prep import filtrar_com_spark
    cnefe_path = filtrar_com_spark(cnefe_path, municipios, ceps, cache_dir=cache_dir,
                   sep=sep, encoding=encoding, force=force)
    sep = encoding = None # a partir daqui o CNEFE e um parquet
  bruto = ler_cnefe_filtrado(cnefe_path, municipios, ceps, sep=sep, encoding=encoding)
  cnefe = preparar_cnefe(bruto)
  log.info("CNEFE preparado: %d enderecos unicos em %d municipios",
      len(cnefe), cnefe["mun6"].nunique())
  indice = IndiceCnefe(cnefe)

  resultados = [casar(c, indice) for c in consultas]
  bruto_df = pd.concat([busca.reset_index(drop=True), pd.DataFrame(resultados)], axis=1)
  return formatar_saida(bruto_df, list(busca.columns))


def formatar_saida(df: pd.DataFrame, colunas_busca, minimo: bool = False) -> pd.DataFrame:
  """Formato do enunciado: base de busca original + `setor_censitario_encontrado` (15 digitos).

  Casos sem setor ficam com `config.MARCADOR_NAO_ENCONTRADO` e `status_match = NAO_ENCONTRADO`.
  As colunas de apoio vem depois; com minimo=True so fica o status.
  """
  out = df[list(colunas_busca)].copy()
  setor = df["codigo_setor_15dig"].astype("string")
  out[config.COLUNA_SAIDA] = setor.fillna(config.MARCADOR_NAO_ENCONTRADO)
  apoio = ["status_match"] if minimo else [
    "status_match", "codigo_setor_censitario", "nivel_match", "score_confianca",
    "n_setores_candidatos", "setores_candidatos", "logradouro_cnefe", "motivo"]
  for k in apoio:
    out[k] = df[k].values
  return out


def resumo(df: pd.DataFrame) -> str:
  n = len(df)
  linhas = [f"Total: {n}"]
  for s in (config.STATUS_OK, config.STATUS_AMBIGUO, config.STATUS_NAO):
    q = int((df["status_match"] == s).sum())
    linhas.append(f" {s}: {q} ({100 * q / n:.1f}%)" if n else f" {s}: 0")
  linhas.append("Por nivel de match:")
  for k, v in df["nivel_match"].value_counts().items():
    linhas.append(f" {k}: {v}")
  return "\n".join(linhas)


def salvar(df: pd.DataFrame, caminho: str):
  c = caminho.lower()
  if c.endswith(".parquet"):
    df.to_parquet(caminho, index=False)
  elif c.endswith(".xlsx"):
    df.to_excel(caminho, index=False)
  else:
    df.to_csv(caminho, index=False, encoding="utf-8-sig")


def main(argv=None):
  ap = argparse.ArgumentParser(description="Vinculacao de enderecos ao setor censitario (CNEFE BA).")
  ap.add_argument("--cnefe", required=True, help="CSV, parquet ou diretorio parquet do CNEFE")
  ap.add_argument("--busca", required=True, help="Base de busca (.csv/.xlsx/.parquet)")
  ap.add_argument("--saida", default="output/resultado_final.csv")
  ap.add_argument("--sep", default=None, help="Separador do CSV do CNEFE (auto se omitido)")
  ap.add_argument("--encoding", default=None)
  ap.add_argument("--engine", choices=["pandas", "spark"], default="pandas",
          help="spark: preparo paralelo do CSV grande (requer pyspark+Java); pandas: leitura em blocos")
  ap.add_argument("--cache-dir", default="data/cache", help="Cache do parquet filtrado (engine spark)")
  ap.add_argument("--minimo", action="store_true",
          help="Saida enxuta: base original + setor_censitario_encontrado + status_match")
  ap.add_argument("--preencher-ambiguo", action=argparse.BooleanOptionalAction,
          default=config.PREENCHER_SETOR_EM_AMBIGUO,
          help="Se True, preenche o melhor palpite em casos ambiguos; se False, deixa vazio.")
  ap.add_argument("--force", action="store_true", help="Refaz o cache mesmo se existir")
  a = ap.parse_args(argv)
  logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
  if a.preencher_ambiguo is not None:
    config.PREENCHER_SETOR_EM_AMBIGUO = a.preencher_ambiguo
  try:
    df = executar(a.cnefe, a.busca, a.sep, a.encoding, a.engine, a.cache_dir, a.force)
  except (FileNotFoundError, RuntimeError) as e:
    log.error("%s", e)
    sys.exit(1)
  if a.minimo:
    df = df[[c for c in df.columns if c not in
        ("codigo_setor_censitario", "nivel_match", "score_confianca", "n_setores_candidatos",
         "setores_candidatos", "logradouro_cnefe", "motivo")]]
  salvar(df, a.saida)
  log.info("Resultado salvo em %s", a.saida)
  print(resumo(df))


if __name__ == "__main__":
  main()
