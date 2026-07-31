"""Transformações da camada Gold: view de treino para LLM."""

from __future__ import annotations

from pyspark.sql.dataframe import DataFrame
from pyspark.sql.functions import (
    array,
    broadcast,
    coalesce,
    col,
    concat,
    first,
    lit,
    row_number,
    struct,
)
from pyspark.sql.window import Window

from schemas.gold.vw_llm_training import build_vw_llm_training_schema


def create_vw_llm_training(
    dim_exam: DataFrame,
    dim_question: DataFrame,
    dim_answer: DataFrame,
) -> DataFrame:
    """Cria a view de treino para LLM a partir das tabelas de fatos e dimensões.

    A view de treino para LLM contém informações sobre cada questão e resposta,
    como o ID da questão, o ID da resposta, se a resposta é correta, o texto da
    questão e o texto da resposta.
    """
    expressions = [
        col(field.name).cast(field.dataType) for field in build_vw_llm_training_schema()
    ]

    system_prompt = (
        "You are a Korean language expert and TOPIK exam question generator.\n\n"
        "Your task is to create new TOPIK exam questions that follow the official exam format and style.\n\n"
        "Output format:\n"
        "Question stimulus: <optional context shown before the question, or leave blank if none>\n"
        "Question text: <the main question in Korean>\n"
        "Option 1. <first answer choice>\n"
        "Option 2. <second answer choice>\n"
        "Option 3. <third answer choice>\n"
        "Option 4. <fourth answer choice>\n\n"
        "Rules:\n"
        "- All content must be written in Korean.\n"
        "- The question must be original and not copied from existing questions.\n"
        "- The question must be grammatically correct and meaningful.\n"
        "- There must be exactly four answer choices with only one correct answer.\n"
        "- The question must match the requested TOPIK level, topic, difficulty, and question type."
    )

    window_rule = Window.partitionBy("question_id").orderBy("answer_id")

    return (
        dim_question.join(broadcast(dim_exam), on="exam_id", how="inner")
        .join(dim_answer, on="question_id", how="inner")
        .withColumn("answer_order", row_number().over(window_rule))
        .withColumn("temp_col_name", concat(lit("answer_"), col("answer_order")))
        .select(
            "exam_id",
            "question_id",
            "topik_level",
            "topic",
            "difficulty_level",
            "question_type",
            "question_stimulus",
            "raw_question_text",
            "raw_answer_text",
            "confidence",
            "answer_order",
            "temp_col_name",
        )
        .groupBy(
            "exam_id",
            "question_id",
            "topik_level",
            "topic",
            "difficulty_level",
            "question_type",
            "question_stimulus",
            "raw_question_text",
            "confidence",
        )
        .pivot("temp_col_name", ["answer_1", "answer_2", "answer_3", "answer_4"])
        .agg(first("raw_answer_text"))
        .withColumn("training_id", col("question_id"))
        .withColumn(
            "messages",
            array(
                struct(
                    lit("system").alias("role"), lit(system_prompt).alias("content")
                ),
                struct(
                    lit("user").alias("role"),
                    concat(
                        lit("Generate a "),
                        col("topik_level"),
                        lit(' multiple-choice question about the topic "'),
                        col("topic"),
                        lit('", with difficulty level "'),
                        col("difficulty_level"),
                        lit('" and question type "'),
                        col("question_type"),
                        lit(
                            '". Follow the output format specified in the system prompt.'
                        ),
                    ).alias("content"),
                ),
                struct(
                    lit("assistant").alias("role"),
                    concat(
                        lit("Question stimulus: "),
                        coalesce(col("question_stimulus"), lit("")),
                        lit("\nQuestion text: "),
                        col("raw_question_text"),
                        lit("\nOption 1. "),
                        col("answer_1"),
                        lit("\nOption 2. "),
                        col("answer_2"),
                        lit("\nOption 3. "),
                        col("answer_3"),
                        lit("\nOption 4. "),
                        col("answer_4"),
                    ).alias("content"),
                ),
            ),
        )
        .select(*expressions)
        .distinct()
    )
