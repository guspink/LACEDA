"""Preparacao do CNEFE com Spark (modo local).

Le o CSV grande em paralelo, mantem so os municipios/CEPs da base de busca, remove duplicatas
e grava um parquet pequeno em cache. O matcher (pandas + RapidFuzz) le esse parquet.

A gravacao e feita pelo pandas/pyarrow (nao pelo Spark) para nao depender do winutils.exe/Hadoop
no Windows. O cache e identificado por hash (arquivo + tamanho + data + municipios + CEPs).
"""
import hashlib
import logging
import os
from pathlib import Path

from . import config
from .ingest import _abrir_texto

log = logging.getLogger(__name__)


def chave_cache(caminho, municipios6, ceps) -> str:
  p = Path(caminho)
  st = p.stat()
  base = f"{p.resolve()}|{st.st_size}|{int(st.st_mtime)}|{sorted(municipios6)}|{sorted(ceps)}"
  return hashlib.md5(base.encode()).hexdigest()[:12]


def filtrar_com_spark(caminho, municipios6, ceps, cache_dir="data/cache",
           sep=None, encoding=None, force=False) -> str:
  """Retorna o caminho do arquivo parquet filtrado (cache)."""
  p = Path(caminho)
  if not p.exists():
    raise FileNotFoundError(f"CNEFE nao encontrado: {p}")
  destino = Path(cache_dir) / f"cnefe_{chave_cache(caminho, municipios6, ceps)}.parquet"
  if destino.exists() and not force:
    log.info("Cache do CNEFE encontrado, pulando Spark: %s", destino)
    return str(destino)

  try:
    from pyspark.sql import SparkSession, functions as F
  except ImportError as e:
    raise RuntimeError("PySpark nao instalado. Use 'pip install pyspark' (requer Java 11+) "
             "ou rode com --engine pandas.") from e

  enc, linha = _abrir_texto(p)
  encoding = encoding or enc
  if sep is None:
    sep = max([";", ",", "|", "\t"], key=linha.count)
  enc_spark = {"latin1": "ISO-8859-1", "utf-8": "UTF-8"}.get(encoding.lower(), encoding)

  spark = (SparkSession.builder.master("local[*]").appName("cnefe_prep")
      .config("spark.driver.memory", os.environ.get("SPARK_DRIVER_MEMORY", "4g"))
      .config("spark.sql.shuffle.partitions", "8")
      .config("spark.ui.enabled", "false")
      .getOrCreate())
  spark.sparkContext.setLogLevel("ERROR")
  try:
    cols = list(config.CNEFE.values())
    df = (spark.read.option("header", True).option("sep", sep).option("encoding", enc_spark)
       .option("nullValue", "NULL").option("inferSchema", False)
       .csv(str(p)).select(*cols))
    c_mun, c_cep = config.CNEFE["municipio"], config.CNEFE["cep"]
    mun6 = F.substring(F.regexp_replace(F.col(c_mun), r"\D", ""), 1, 6)
    cep8 = F.lpad(F.regexp_replace(F.col(c_cep), r"\D", ""), 8, "0")
    cond_mun = mun6.isin(list(municipios6)) if municipios6 else F.lit(False)
    cond_cep = cep8.isin(list(ceps)) if ceps else F.lit(False)
    filtrado = df.filter(cond_mun | cond_cep).dropDuplicates()

   # Traz o resultado (pequeno) para o pandas e grava aqui: evita o winutils/Hadoop no Windows.
    pdf = filtrado.toPandas()
    log.info("Spark: %d linhas apos filtro/deduplicacao", len(pdf))
  finally:
    spark.stop()

  destino.parent.mkdir(parents=True, exist_ok=True)
  tmp = destino.with_suffix(".tmp")
  pdf.to_parquet(tmp, index=False)
  os.replace(tmp, destino)
  log.info("Cache gravado em %s", destino)
  return str(destino)