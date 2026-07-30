"""Transformações da camada Silver: dimensão de questões."""

from pyspark.sql import SparkSession
from pyspark.sql.dataframe import DataFrame
from pyspark.sql.functions import col

from schemas.silver.dim_question_schema import build_dim_question_schema


def create_dim_question(
    spark: SparkSession,
    questions_list: list[dict],
) -> DataFrame:
    """Cria a dimensão de questões a partir da lista de questões.

    A dimensão de questões contém informações únicas sobre cada questão,
    como o ID do exame, o tipo de questão, o vocabulário e a gramática
    frequentes.
    """
    expressions = [
        col(field.name).cast(field.dataType) for field in build_dim_question_schema()
    ]
    return (
        spark.createDataFrame(questions_list, schema=build_dim_question_schema())
        .select(*expressions)
        .distinct()
    )
