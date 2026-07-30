"""Transformações da camada Silver: dimensão de respostas."""

from pyspark.sql import SparkSession
from pyspark.sql.dataframe import DataFrame
from pyspark.sql.functions import col

from schemas.silver.dim_answer_schema import build_dim_answer_schema


def create_dim_answer(
    spark: SparkSession,
    answers_list: list[dict],
) -> DataFrame:
    """Cria a dimensão de respostas a partir da lista de respostas.

    A dimensão de respostas contém informações únicas sobre cada resposta,
    como o ID da questão, o texto da resposta e se é a resposta correta.
    """
    expressions = [
        col(field.name).cast(field.dataType) for field in build_dim_answer_schema()
    ]
    return (
        spark.createDataFrame(answers_list, schema=build_dim_answer_schema())
        .select(*expressions)
        .distinct()
    )
