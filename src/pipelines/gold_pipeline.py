"""Pipeline da camada Gold: produz datasets analíticos a partir da Silver."""

from __future__ import annotations

import logging
import os

from pyspark.sql.dataframe import DataFrame

from schemas.silver.dim_answer_schema import build_dim_answer_schema
from schemas.silver.dim_exam_schema import build_dim_exam_schema
from schemas.silver.dim_question_schema import build_dim_question_schema
from transformations.gold.vw_llm_training import create_vw_llm_training
from utils.hadoop_config import configure_windows_hadoop
from utils.parquet_io import read_parquet_data, write_parquet_data
from utils.spark_utils import initialize_spark

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

SILVER_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "data",
    "silver",
    "topik_documents",
)
GOLD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "gold")


def write_gold_parquet(vw_llm_training_df: DataFrame) -> None:
    """Escreve o dataset Gold em formato Parquet."""
    output_path = os.path.join(GOLD_DIR, "vw_llm_training")
    write_parquet_data(vw_llm_training_df, output_path)
    logger.info("Dataset Gold gravado em: %s", output_path)


def run_gold_pipeline() -> None:
    """Executa o pipeline completo da camada Gold."""
    configure_windows_hadoop()

    spark = None

    try:
        spark = initialize_spark("topik-gold-builder")

        dim_exam_df = read_parquet_data(
            spark, os.path.join(SILVER_DIR, "dim_exam"), build_dim_exam_schema()
        )
        dim_question_df = read_parquet_data(
            spark,
            os.path.join(SILVER_DIR, "dim_question"),
            build_dim_question_schema(),
        )
        dim_answer_df = read_parquet_data(
            spark,
            os.path.join(SILVER_DIR, "dim_answer"),
            build_dim_answer_schema(),
        )

        vw_llm_training_df = create_vw_llm_training(
            dim_exam_df, dim_question_df, dim_answer_df
        )

        vw_llm_training_df.cache()
        logger.info("Dados de treinamento: %d", vw_llm_training_df.count())
        write_gold_parquet(vw_llm_training_df)
        vw_llm_training_df.unpersist()

    finally:
        if spark is not None:
            spark.stop()


def main() -> None:
    run_gold_pipeline()


if __name__ == "__main__":
    main()
