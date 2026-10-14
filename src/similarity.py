"""Similaridade textual 0-100. Usa RapidFuzz se instalado; senao, difflib (mais lento).

Base: token_sort_ratio (tolera pequenas trocas de ordem), com penalidade quando a ordem das
palavras difere (ratio simples menor): 'BOA VISTA' vs 'VISTA BOA' nao deve valer 100.
"""
from difflib import SequenceMatcher

try:
  from rapidfuzz import fuzz, process
  HAS_RAPIDFUZZ = True
except ImportError: # pragma: no cover
  HAS_RAPIDFUZZ = False

ORDEM_PESO = 0.6


def _sort_tokens(s: str) -> str:
  return " ".join(sorted(s.split()))


def _combinar(ts: float, r: float) -> float:
  return ts - ORDEM_PESO * max(ts - r, 0.0)


def similaridade(a: str, b: str) -> float:
  if not a or not b:
    return 0.0
  if HAS_RAPIDFUZZ:
    return float(_combinar(fuzz.token_sort_ratio(a, b), fuzz.ratio(a, b)))
  ts = 100.0 * SequenceMatcher(None, _sort_tokens(a), _sort_tokens(b)).ratio()
  r = 100.0 * SequenceMatcher(None, a, b).ratio()
  return _combinar(ts, r)


def pontuar(consulta: str, opcoes: list) -> list:
  """Pontua a consulta contra cada opcao. Retorna lista de floats."""
  if not consulta or not opcoes:
    return [0.0] * len(opcoes)
  if HAS_RAPIDFUZZ:
    ts = process.cdist([consulta], opcoes, scorer=fuzz.token_sort_ratio, workers=1)[0]
    r = process.cdist([consulta], opcoes, scorer=fuzz.ratio, workers=1)[0]
    return [float(_combinar(a, b)) for a, b in zip(ts, r)]
  return [similaridade(consulta, o) for o in opcoes]