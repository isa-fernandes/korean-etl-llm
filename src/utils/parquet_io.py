"""Funções reutilizáveis de leitura e escrita de Parquet."""

from __future__ import annotations

import os
import shutil

from pyspark.sql import SparkSession
from pyspark.sql.dataframe import DataFrame
from pyspark.sql.types import StructType


def ensure_dir(path: str) -> None:
    """Cria o diretório pai se não existir."""
    os.makedirs(os.path.dirname(path), exist_ok=True)


def clear_directory(path: str) -> None:
    """Remove e recria um diretório, garantindo estado limpo para escrita."""
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


def read_parquet_data(
    spark: SparkSession,
    path: str,
    schema: StructType | None = None,
) -> DataFrame:
    """Lê Parquet de um caminho, opcionalmente aplicando schema fixo."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Parquet não encontrado: {path}")

    reader = spark.read
    if schema is not None:
        reader = reader.schema(schema)

    return reader.parquet(path)


def read_parquet_by_edition(
    spark: SparkSession,
    base_dir: str,
    edition: str,
    schema: StructType | None = None,
) -> DataFrame:
    """Lê Parquet de uma edição específica dentro de uma base de dados."""
    edition_path = os.path.join(base_dir, str(edition))
    return read_parquet_data(spark, edition_path, schema)


def write_parquet_data(
    df: DataFrame,
    path: str,
    mode: str = "overwrite",
    clear_before_write: bool = True,
) -> None:
    """Persiste um DataFrame em Parquet."""
    if clear_before_write:
        clear_directory(path)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.write.mode(mode).parquet(path)
