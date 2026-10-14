"""Compara o resultado com um gabarito (amostra rotulada) para calibrar limiares.

Uso:
  python -m src.evaluate --resultado output/resultado_final.csv --gabarito gabarito.csv --col-gabarito setor
Alinhamento por posicao (mesma ordem) ou por --chave (coluna comum). Compara os 15 primeiros
caracteres do setor (ignora o sufixo de letra).
"""
import argparse

import pandas as pd


def _c15(s):
  return None if pd.isna(s) else str(s).strip()[:15]


def avaliar(res: pd.DataFrame, gold: pd.DataFrame, col_gold: str, chave: str | None = None) -> dict:
  if chave:
    df = res.merge(gold[[chave, col_gold]].rename(columns={col_gold: "_gold"}), on=chave, how="left")
  else:
    assert len(res) == len(gold), "tamanhos diferentes: use --chave"
    df = res.copy()
    df["_gold"] = gold[col_gold].values
  df["_ok"] = df["codigo_setor_censitario"].map(_c15) == df["_gold"].map(_c15)
  out = {"acuracia_geral": float(df["_ok"].mean())}
  for s, g in df.groupby("status_match"):
    out[f"acuracia_{s}"] = float(g["_ok"].mean())
    out[f"n_{s}"] = int(len(g))
  return out


if __name__ == "__main__":
  ap = argparse.ArgumentParser()
  ap.add_argument("--resultado", required=True)
  ap.add_argument("--gabarito", required=True)
  ap.add_argument("--col-gabarito", required=True)
  ap.add_argument("--chave", default=None)
  a = ap.parse_args()
  r = pd.read_csv(a.resultado, dtype=str)
  g = pd.read_csv(a.gabarito, dtype=str)
  for k, v in avaliar(r, g, a.col_gabarito, a.chave).items():
    print(f"{k}: {v:.3f}" if isinstance(v, float) else f"{k}: {v}")