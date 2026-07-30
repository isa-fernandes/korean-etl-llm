"""Transformações da camada Silver: dimensão de exames."""

from pyspark.sql.dataframe import DataFrame
from pyspark.sql.functions import col

from schemas.silver.dim_exam_schema import build_dim_exam_schema


def create_dim_exam(df: DataFrame) -> DataFrame:
    """Cria a dimensão de exames a partir do DataFrame bronze.

    A dimensão de exames contém informações únicas sobre cada exame,
    como o ID do exame, o nome do exame e a data de realização.
    """
    expressions = [
        col(field.name).cast(field.dataType) for field in build_dim_exam_schema()
    ]
    return (
        df.withColumnRenamed("label", "exam_name")
        .withColumnRenamed("level", "topik_level")
        .withColumnRenamed("section", "exam_section")
        .select(*expressions)
        .distinct()
    )
