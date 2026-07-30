"""Transformações da camada Silver: tabela fato de downloads."""

from pyspark.sql.dataframe import DataFrame
from pyspark.sql.functions import col, current_date

from schemas.silver.fact_download_schema import build_fact_download_schema


def create_fact_download(df: DataFrame) -> DataFrame:
    """Cria a tabela de fatos de downloads a partir do DataFrame bronze.

    A tabela de fatos de downloads contém informações sobre cada download
    realizado, como o ID do exame, o nome do arquivo e a data do download.
    """
    expressions = [
        col(field.name).cast(field.dataType) for field in build_fact_download_schema()
    ]
    return (
        df.select(
            "download_id",
            "exam_id",
            "file_id",
            "download_date",
            "download_status",
            col("processed_at").alias("bronze_processed_at"),
        )
        .withColumn("silver_processed_at", current_date())
        .select(*expressions)
        .distinct()
    )
