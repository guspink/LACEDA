"""Padronizacao de texto de endereco. Aplicada IGUALMENTE ao CNEFE e a base de busca."""
import re
import unicodedata

NULOS = {"", "NULL", "NONE", "NAN", "NA", "N/A", "NULO", "<NA>"}

# Abreviacoes aceitas apenas na PRIMEIRA palavra (tipo de logradouro)
TIPOS = {
  "R": "RUA", "AV": "AVENIDA", "AVE": "AVENIDA", "TV": "TRAVESSA", "TRAV": "TRAVESSA",
  "TRV": "TRAVESSA", "AL": "ALAMEDA", "PC": "PRACA", "PCA": "PRACA", "PRC": "PRACA",
  "ROD": "RODOVIA", "EST": "ESTRADA", "ESTR": "ESTRADA", "LGO": "LARGO", "LRG": "LARGO",
  "VL": "VILA", "VLA": "VILA", "LOT": "LOTEAMENTO", "CJ": "CONJUNTO", "FAZ": "FAZENDA",
  "POV": "POVOADO", "DIST": "DISTRITO", "BC": "BECO", "SIT": "SITIO", "LAD": "LADEIRA",
}
# Tipos de logradouro conhecidos (para separar tipo do nome)
TIPOS_CONHECIDOS = set(TIPOS.values()) | {
  "BAIXA", "CHACARA", "CONDOMINIO", "VIADUTO", "PARQUE", "JARDIM", "LOCALIDADE",
  "QUADRA", "ACESSO", "CAMINHO", "VIA", "RESIDENCIAL", "CORREGO",
}
# Titulos/abreviacoes em qualquer posicao
TITULOS = {
  "DR": "DOUTOR", "DRA": "DOUTORA", "PROF": "PROFESSOR", "PROFA": "PROFESSORA",
  "STA": "SANTA", "STO": "SANTO", "CEL": "CORONEL", "ENG": "ENGENHEIRO",
  "CAP": "CAPITAO", "GAL": "GENERAL", "PRES": "PRESIDENTE", "GOV": "GOVERNADOR",
  "DEP": "DEPUTADO", "VER": "VEREADOR", "MAL": "MARECHAL", "SGT": "SARGENTO",
  "TEN": "TENENTE", "JD": "JARDIM", "PQ": "PARQUE", "COM": "COMENDADOR",
}
STOPWORDS = {"DE", "DA", "DO", "DAS", "DOS", "E"}


def sem_acentos(texto: str) -> str:
  n = unicodedata.normalize("NFKD", texto)
  return "".join(c for c in n if not unicodedata.combining(c))


def normalizar_texto(valor, expandir_tipo: bool = True) -> str:
  """Maiuscula, sem acento/pontuacao, separa letra de digito (BR101 -> BR 101),
  expande abreviacoes. Valores nulos viram string vazia."""
  if valor is None:
    return ""
  t = str(valor)
  for ch in ("\u00ba", "\u00b0", "\u00aa"):
    t = t.replace(ch, " ")
  t = sem_acentos(t).upper().strip()
  if t in NULOS:
    return ""
  t = re.sub(r"\bS\s*/\s*N\b", "SN", t)
  t = re.sub(r"[^A-Z0-9 ]", " ", t)
  t = re.sub(r"(?<=[A-Z])(?=[0-9])|(?<=[0-9])(?=[A-Z])", " ", t)
  toks = [x for x in t.split() if x not in {"NONE", "NULL", "NAN"}]
  if expandir_tipo and toks and toks[0] in TIPOS:
    toks[0] = TIPOS[toks[0]]
  toks = [TITULOS.get(x, x) for x in toks]
  return " ".join(toks)


def chave_comparacao(texto: str) -> str:
  """Versao usada para comparar (remove DE/DA/DO...)."""
  return " ".join(t for t in texto.split() if t not in STOPWORDS)


def separar_tipo(texto_norm: str):
  """Retorna (tipo, resto). tipo = '' se a 1a palavra nao for tipo conhecido."""
  toks = texto_norm.split()
  if toks and toks[0] in TIPOS_CONHECIDOS and len(toks) > 1:
    return toks[0], " ".join(toks[1:])
  return "", texto_norm


def parse_numero(valor):
  """Retorna int ou None. 'SN', 'S/N', vazio e 0 significam sem numero."""
  t = normalizar_texto(valor, expandir_tipo=False)
  if t in ("", "SN", "SEM NUMERO"):
    return None
  m = re.search(r"\d+", t)
  if not m:
    return None
  n = int(m.group())
  return n if n > 0 else None


def normalizar_municipio(valor):
  """Codigo IBGE com 6 digitos (aceita 6 ou 7 digitos)."""
  if valor is None:
    return None
  s = re.sub(r"\.0+$", "", str(valor).strip())
  d = re.sub(r"\D", "", s)
  return d[:6] if len(d) >= 6 else None


def normalizar_cep(valor):
  if valor is None:
    return None
  s = re.sub(r"\.0+$", "", str(valor).strip())
  d = re.sub(r"\D", "", s)
  if not d or set(d) == {"0"} or len(d) > 8:
    return None
  return d.zfill(8)