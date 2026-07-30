"""Transformações da camada Silver: tabela fato de questões e respostas."""

from pyspark.sql.dataframe import DataFrame
from pyspark.sql.functions import broadcast, col, concat_ws, sha2

from schemas.silver.fact_qa_schema import build_fact_qa_schema


def create_fact_qa(
    dim_answer_df: DataFrame,
    dim_question_df: DataFrame,
) -> DataFrame:
    """Cria a tabela de fatos de QA a partir das dimensões de questão e resposta.

    A tabela de fatos de QA contém informações sobre cada questão e resposta,
    como o ID da questão, o ID da resposta e se a resposta é correta.
    """
    dim_question_df_reduced = dim_question_df.select("question_id", "exam_id")

    expressions = [
        col(field.name).cast(field.dataType) for field in build_fact_qa_schema()
    ]

    return (
        dim_answer_df.select("question_id", "answer_id")
        .join(broadcast(dim_question_df_reduced), on="question_id", how="inner")
        .withColumn(
            "qa_id", sha2(concat_ws("||", "exam_id", "question_id", "answer_id"), 256)
        )
        .select(*expressions)
        .distinct()
    )
