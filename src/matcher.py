"""Vinculacao em cascata: RUA(+numero) -> LOCALIDADE -> CEP, com checagem de unicidade de setor.

Ideia central: o resultado so e AMBIGUO se os candidatos restantes pertencem a SETORES DIFERENTES.
Varios imoveis empatados no mesmo setor continuam sendo um MATCH valido.
"""
from dataclasses import dataclass

import pandas as pd

from . import config
from .normalize import (chave_comparacao, normalizar_cep, normalizar_municipio,
            normalizar_texto, parse_numero, separar_tipo)
from .similarity import pontuar, similaridade

OK, AMB, NAO = config.STATUS_OK, config.STATUS_AMBIGUO, config.STATUS_NAO


@dataclass
class Consulta:
  mun6: str | None
  cep: str | None
  numero: int | None
  tipo: str
  full_key: str
  nome_key: str
  bairro_key: str


def preparar_consulta(row: dict) -> Consulta:
  b = config.BUSCA
  logr = normalizar_texto(row.get(b["logradouro"]))
  tipo, resto = separar_tipo(logr)
  return Consulta(
    mun6=normalizar_municipio(row.get(b["municipio"])),
    cep=normalizar_cep(row.get(b["cep"])),
    numero=parse_numero(row.get(b["numero"])),
    tipo=tipo,
    full_key=chave_comparacao(logr),
    nome_key=chave_comparacao(resto),
    bairro_key=chave_comparacao(normalizar_texto(row.get(b["bairro"]))),
  )


class IndiceMunicipio:
  """Estruturas pre-computadas de um conjunto de linhas do CNEFE (normalmente 1 municipio)."""

  def __init__(self, rows: pd.DataFrame):
    self.rows = rows
    validas = rows[rows["nome_valido"]]
    self.ruas = (validas[["street_full_key", "street_nome_key", "tipo"]]
          .drop_duplicates("street_full_key").reset_index(drop=True))
    self.grupos = {k: g for k, g in validas.groupby("street_full_key")}
    self.localidades = sorted(l for l in rows["localidade_key"].unique() if l)
    self.setores_por_cep = rows.dropna(subset=["cep"]).groupby("cep")["setor"].agg(set).to_dict()
    self.tipo_da_rua = dict(zip(self.ruas["street_full_key"], self.ruas["tipo"]))


class IndiceCnefe:
  def __init__(self, cnefe: pd.DataFrame):
    self.cnefe = cnefe
    self._mun = {m: IndiceMunicipio(g) for m, g in cnefe.groupby("mun6")}
    self._cep_cache = {}

  def obter(self, q: Consulta):
    if q.mun6:
      return self._mun.get(q.mun6)
    if q.cep: # sem municipio: usa o CEP para localizar as linhas candidatas
      if q.cep not in self._cep_cache:
        sub = self.cnefe[self.cnefe["cep"] == q.cep]
        self._cep_cache[q.cep] = IndiceMunicipio(sub) if len(sub) else None
      return self._cep_cache[q.cep]
    return None


# ---------------------------------------------------------------- helpers
def _resultado(status, nivel, setor=None, setores=(), score=0.0, logr=None, motivo=""):
  setores = sorted(set(setores))
  usar = setor is not None and (status == OK or (status == AMB and config.PREENCHER_SETOR_EM_AMBIGUO))
  return {
    "codigo_setor_censitario": setor if usar else None,
    "codigo_setor_15dig": setor[:15] if usar else None,
    "status_match": status,
    "nivel_match": nivel,
    "score_confianca": round(float(score), 1),
    "n_setores_candidatos": len(setores),
    "setores_candidatos": "|".join(setores[:10]),
    "logradouro_cnefe": logr,
    "motivo": motivo,
  }


def _setor_mais_comum(rows: pd.DataFrame) -> str:
  cont = rows["setor"].value_counts()
  return sorted(cont[cont == cont.max()].index)[0]


def _refinar(rows: pd.DataFrame, q: Consulta, idx: "IndiceMunicipio") -> pd.DataFrame:
  """Reduz candidatos por CEP e bairro, so quando isso ajuda a desempatar setores."""
  r = rows
  if r["setor"].nunique() > 1 and q.cep:
    rc = r[r["cep"] == q.cep]
    if rc.empty: # a rua nao tem esse CEP; usa os setores onde o CEP aparece no municipio
      setores_cep = idx.setores_por_cep.get(q.cep)
      if setores_cep:
        rc = r[r["setor"].isin(setores_cep)]
    if not rc.empty:
      r = rc
  if r["setor"].nunique() > 1 and q.bairro_key:
    bons = [l for l in r["localidade_key"].unique()
        if l and similaridade(q.bairro_key, l) >= config.SCORE_MIN_BAIRRO]
    if bons:
      r = r[r["localidade_key"].isin(bons)]
  return r


def _escolher_setor(rows: pd.DataFrame, q: Consulta, idx: "IndiceMunicipio"):
  """Retorna (rows_finais, nivel). Usa o numero quando existe."""
  if q.numero is not None:
    exato = rows[rows["numero"] == q.numero]
    if not exato.empty:
      return _refinar(exato, q, idx), "LOGRADOURO+NUMERO"
    com_num = rows[rows["numero"].notna()]
    if not com_num.empty and rows["setor"].nunique() > 1:
      dif = com_num["numero"] - q.numero
      custo = dif.abs() + (dif % 2 != 0).astype(int) * 3 # prefere mesma paridade
      return com_num[custo == custo.min()], "LOGRADOURO+NUMERO_APROX"
  return _refinar(rows, q, idx), "LOGRADOURO"


def _casar_rua(q: Consulta, idx: IndiceMunicipio):
  ruas = idx.ruas
  if ruas.empty or not q.nome_key:
    return None
  tipos = ruas["tipo"].tolist()
 # Compara o NOME (sem o tipo): comparar com o tipo junto inflava o score
 # (FAZENDA BICO x FAZENDA ANGICO compartilham 'FAZENDA').
  pontos = pontuar(q.nome_key, ruas["street_nome_key"].tolist())
  if not q.tipo: # tipo desconhecido na consulta: o nome pode incluir o tipo
    p_full = pontuar(q.full_key, ruas["street_full_key"].tolist())
    pontos = [max(a, b) for a, b in zip(pontos, p_full)]
  curto = len(q.nome_key.replace(" ", "")) <= config.TAM_NOME_CURTO
  minimo = config.SCORE_MIN_RUA_CURTA if curto else config.SCORE_MIN_RUA

  base = []
  for i, s in enumerate(pontos):
    if q.tipo and tipos[i] and q.tipo != tipos[i]:
      s -= config.PENALIDADE_TIPO_DIFERENTE
    base.append(s)
  top = sorted(range(len(ruas)), key=lambda i: base[i], reverse=True)[:config.TOP_K_RUAS]
  finais = {}
  for i in top:
    if base[i] < minimo:
      continue
    chave = ruas.at[i, "street_full_key"]
    g = idx.grupos[chave]
    bonus = 0.0
    if q.cep and (g["cep"] == q.cep).any():
      bonus += config.BONUS_CEP
    if q.bairro_key and any(similaridade(q.bairro_key, l) >= config.SCORE_MIN_BAIRRO
                for l in g["localidade_key"].unique() if l):
      bonus += config.BONUS_BAIRRO
    finais[chave] = min(100.0, base[i] + bonus)
  if not finais:
    return None
  melhor = max(finais.values())
  empatadas = [k for k, v in finais.items() if v >= melhor - config.MARGEM_EMPATE]
  if q.tipo: # entre empatadas, prefere as do mesmo tipo da consulta
    mesmas = [k for k in empatadas if idx.tipo_da_rua.get(k) == q.tipo]
    if mesmas:
      empatadas = mesmas
  rows = pd.concat([idx.grupos[k] for k in empatadas])
  return rows, melhor, empatadas


def _fallback_localidade(q: Consulta, idx: IndiceMunicipio):
  if not idx.localidades:
    return None
  textos = [t for t in (q.full_key, q.nome_key, q.bairro_key) if t]
  melhor, loc_ok = 0.0, []
  for loc in idx.localidades:
    s = 0.0
    for t in textos:
      lim = (config.SCORE_MIN_LOCALIDADE_CURTA
         if len(t.replace(" ", "")) <= config.TAM_NOME_CURTO
         else config.SCORE_MIN_LOCALIDADE)
      v = similaridade(t, loc)
      if v >= lim:
        s = max(s, v)
    if s > melhor + 1e-9:
      melhor, loc_ok = s, [loc]
    elif s > 0 and abs(s - melhor) < 1e-9:
      loc_ok.append(loc)
  if melhor <= 0:
    return None
  return idx.rows[idx.rows["localidade_key"].isin(loc_ok)], melhor


# ---------------------------------------------------------------- API
def casar(q: Consulta, indice: IndiceCnefe) -> dict:
  idx = indice.obter(q)
  if idx is None:
    return _resultado(NAO, "-", motivo="municipio/CEP sem registros no CNEFE")

 # 1) Rua (+ numero)
  achado = _casar_rua(q, idx)
  if achado:
    rows, score, chaves = achado
    finais, nivel = _escolher_setor(rows, q, idx)
    setores = finais["setor"].unique().tolist()
    logr = " | ".join(chaves[:3])
    if len(setores) == 1 and score >= config.SCORE_MATCH_RUA:
      return _resultado(OK, nivel, setores[0], setores, score, logr)
    motivo = ("similaridade de rua baixa" if len(setores) == 1
         else f"{len(setores)} setores possiveis para o endereco")
    return _resultado(AMB, nivel, _setor_mais_comum(finais), setores, score, logr, motivo)

 # 2) Localidade (povoado, distrito, fazenda...)
  loc = _fallback_localidade(q, idx)
  if loc:
    rows, score = loc
    finais = _refinar(rows, q, idx)
    setores = finais["setor"].unique().tolist()
    nome_loc = finais["localidade_key"].iloc[0]
    if len(setores) == 1:
      return _resultado(OK, "LOCALIDADE", setores[0], setores, score, nome_loc)
    return _resultado(AMB, "LOCALIDADE", _setor_mais_comum(finais), setores, score,
             nome_loc, f"{len(setores)} setores na localidade")

 # 3) Somente CEP
  if q.cep:
    rows = idx.rows[idx.rows["cep"] == q.cep]
    if not rows.empty:
      setores = rows["setor"].unique().tolist()
      if len(setores) == 1:
        return _resultado(OK, "CEP", setores[0], setores, 60.0, None, "casado apenas pelo CEP")
      if config.CEP_MAX_SETORES is not None and len(setores) > config.CEP_MAX_SETORES:
        return _resultado(NAO, "CEP", None, setores, 0.0, None,
                 f"CEP cobre {len(setores)} setores: palpite sem base")
      return _resultado(AMB, "CEP", _setor_mais_comum(rows), setores, 40.0, None,
               f"CEP cobre {len(setores)} setores")

  return _resultado(NAO, "-", motivo="nenhum candidato acima dos limiares")