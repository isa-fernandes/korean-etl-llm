"""Transformações da camada Gold: view de treino para LLM."""

from __future__ import annotations

from pyspark.sql.dataframe import DataFrame
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, broadcast, sha2, array, struct, lit

from src.schemas.gold.vw_llm_training import build_vw_llm_training_schema


# TODO: implementar montagem do campo messages a partir de dim_question + dim_answer
def create_vw_llm_training(fact_qa: DataFrame, dim_exam: DataFrame, dim_question: DataFrame, dim_answer: DataFrame) -> DataFrame:
    """Cria a view de treino para LLM a partir das tabelas de fatos e dimensões.

    A view de treino para LLM contém informações sobre cada questão e resposta,
    como o ID da questão, o ID da resposta, se a resposta é correta, o texto da
    questão e o texto da resposta.
    """
    expressions = [
        col(field.name).cast(field.dataType) for field in build_vw_llm_training_schema()
    ]

    system_prompt = """
    You are a Korean language expert and TOPIK exam analyst.

    Generate new TOPIK questions based on TOPIK Level (which may be TOPIK I or TOPIK II), based on topic (if any given), based on difficulty (if any given).
    Also consider question type if given.

    Rules:
    - The question must be in Korean language.
    - The question must be unique and not a copy of any existing question.
    - The question must be grammatically correct and make sense.
    - The question must be relevant to the topic and difficulty level if given.
    - The question must be relevant to the question type if given.
    - The question must be relevant to the TOPIK exam format and style.
    - The question must have only one correct answer.
    """

    return (
        fact_qa.join(broadcast(dim_exam), on="exam_id", how="inner")
        .join(broadcast(dim_question), on="question_id", how="inner")
        .join(dim_answer, on="answer_id", how="inner")
        .withColumn("training_id", sha2(col("question_id"),256))
        .withColumn("messages",array(struct(lit("system").alias("role"), lit(system_prompt).alias("content"))))
        .select(*expressions)
        .distinct()
    )