"""Transformações da camada Silver: dimensão de arquivos."""

from pyspark.sql.dataframe import DataFrame
from pyspark.sql.functions import col

from schemas.silver.dim_file_schema import build_dim_file_schema


def create_dim_file(df: DataFrame) -> DataFrame:
    """Cria a dimensão de arquivos a partir do DataFrame bronze.

    A dimensão de arquivos contém informações únicas sobre cada arquivo,
    como o ID do exame, o nome do arquivo, o tipo de arquivo e o caminho
    para o arquivo PDF original.
    """
    expressions = [
        col(field.name).cast(field.dataType) for field in build_dim_file_schema()
    ]
    return df.select(*expressions).distinct()
