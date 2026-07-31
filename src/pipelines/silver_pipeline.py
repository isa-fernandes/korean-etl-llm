"""Pipeline da camada Silver: processa Bronze e gera tabelas dimensionais."""

from __future__ import annotations

import logging
import os

from pyspark.sql import SparkSession
from pyspark.sql.dataframe import DataFrame
from pyspark.sql.functions import col, concat_ws, sha2

from schemas.bronze.pages_raw_schema import build_pages_raw_schema
from tools.langchain_functions.generative_api import (
    QuestionObject,
    extract_questions,
    filter_reliable,
)
from tools.text_cleaner import preprocess_raw_text
from transformations.silver.dim_answer import create_dim_answer
from transformations.silver.dim_exam import create_dim_exam
from transformations.silver.dim_file import create_dim_file
from transformations.silver.dim_question import create_dim_question
from transformations.silver.fact_download import create_fact_download
from transformations.silver.fact_qa import create_fact_qa
from utils.hadoop_config import configure_windows_hadoop
from utils.parquet_io import read_parquet_data, write_parquet_data
from utils.spark_utils import initialize_spark
from utils.text_utils import concat_ws_sha256

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BRONZE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "bronze")
SILVER_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "data",
    "silver",
    "topik_documents",
)


def build_base_df(df: DataFrame) -> DataFrame:
    """Adiciona colunas computadas (file_id, download_id) ao DataFrame bronze."""
    return (
        df.withColumn(
            "file_id",
            sha2(concat_ws("||", "filename", "source_pdf_path", "source_url"), 256),
        )
        .withColumn(
            "download_id",
            sha2(
                concat_ws(
                    "||", "download_date", "download_status", "exam_id", "file_id"
                ),
                256,
            ),
        )
        .cache()
    )


def build_silver_tables(
    spark: SparkSession,
    df: DataFrame,
    questions_list: list[dict],
    answers_list: list[dict],
) -> tuple[DataFrame, ...]:
    """Cria as tabelas Silver a partir do DataFrame bronze.

    As tabelas Silver são criadas a partir do DataFrame bronze, que contém
    informações sobre cada página de exame. As tabelas Silver são:
    - dim_exam: contém informações únicas sobre cada exame.
    - dim_file: contém informações únicas sobre cada arquivo.
    - dim_question: contém informações únicas sobre cada questão.
    - dim_answer: contém informações únicas sobre cada resposta.
    - fact_download: contém informações sobre cada download realizado.
    - fact_qa: contém informações sobre cada questão e resposta.
    """
    base_df = build_base_df(df)

    dim_exam_df = create_dim_exam(base_df)
    dim_file_df = create_dim_file(base_df)
    dim_question_df = create_dim_question(spark, questions_list)
    dim_answer_df = create_dim_answer(spark, answers_list)
    fact_download_df = create_fact_download(base_df)
    fact_qa_df = create_fact_qa(dim_answer_df, dim_question_df)

    base_df.unpersist()

    return (
        dim_exam_df,
        dim_file_df,
        dim_question_df,
        dim_answer_df,
        fact_download_df,
        fact_qa_df,
    )


def write_silver_parquet(
    dim_exam_df: DataFrame,
    dim_file_df: DataFrame,
    dim_question_df: DataFrame,
    dim_answer_df: DataFrame,
    fact_download_df: DataFrame,
    fact_qa_df: DataFrame,
) -> None:
    """Persiste os dataframes na camada Silver como Parquet."""

    dfs = {
        "dim_exam": dim_exam_df,
        "dim_file": dim_file_df,
        "dim_question": dim_question_df,
        "dim_answer": dim_answer_df,
        "fact_download": fact_download_df,
        "fact_qa": fact_qa_df,
    }
    values_count = {}

    for name, df in dfs.items():
        df_path = os.path.join(SILVER_DIR, name)
        df.cache()
        values_count[df_path] = df.count()
        write_parquet_data(df, df_path)
        df.unpersist()

    logger.info(
        "Silver salvo: "
        + "\n".join(
            [
                f"{df_path} ({df_count} linhas)"
                for df_path, df_count in values_count.items()
            ]
        )
    )


def extract_questions_from_bronze(
    spark: SparkSession,
) -> tuple[list[dict], list[dict], list[QuestionObject]]:
    """Lê o bronze consolidado, extrai e limpa questões e respostas por página."""
    bronze_schema = build_pages_raw_schema()
    df = read_parquet_data(spark, BRONZE_DIR, bronze_schema)

    logger.info("Pré-processando e extraindo questões por página...")
    df = (
        df.fillna(value="", subset="raw_text")
        .filter(df.filename.endswith("-Reading-Test-Paper.pdf"))
        .filter(df.page_number >= 3)
        .orderBy(col("filename"), col("page_number"))
    )
    df.cache()

    page_count = df.count()
    if page_count == 0:
        df.unpersist()
        logger.warning("Nenhuma página encontrada para o filtro de leitura TOPIK I.")
        return [], [], []

    logger.info("%d página(s) encontrada(s).", page_count)

    all_questions: list[QuestionObject] = []
    reliable_questions: list[QuestionObject] = []
    questions_list: list[dict] = []
    answers_list: list[dict] = []

    for row in df.toLocalIterator():
        label = f"{row['filename']} p.{row['page_number']}"
        logger.info("Processando %s...", label)
        clean_text = preprocess_raw_text(row["raw_text"])
        if not clean_text.strip():
            logger.warning("%s: página vazia após limpeza, pulando.", label)
            continue

        try:
            wrapper = extract_questions(
                clean_text, model_name="joonoh/HyperCLOVAX-SEED-Text-Instruct-1.5B"
            )
            all_questions.extend(wrapper.questions)
            page_reliable_questions = filter_reliable(wrapper)
            reliable_questions.extend(page_reliable_questions)

            for question in page_reliable_questions:
                question_row = build_question_row(row, question)
                questions_list.append(question_row)

                for answer in question.answer_options:
                    answers_list.append(build_answer_row(question_row, answer))
        except RuntimeError as exc:
            logger.error("%s falhou após retries: %s", label, exc)

    df.unpersist()
    return questions_list, answers_list, reliable_questions


def build_question_row(
    row: dict,
    question: QuestionObject,
) -> dict:
    """Monta uma linha da dimensão de questões a partir de um QuestionObject."""
    return {
        "question_id": concat_ws_sha256(
            "||",
            [
                row["exam_id"],
                row["page_number"],
                question.question_text,
                question.question_stimulus,
            ],
        ),
        "exam_id": row["exam_id"],
        "page_number": row["page_number"],
        "question_type": question.question_type,
        "raw_question_text": question.question_text,
        "question_stimulus": question.question_stimulus,
        "question_vocabulary_items": question.question_vocabulary_items,
        "question_grammar_patterns": question.question_grammar_patterns,
        "topic": question.topic,
        "difficulty_level": question.difficulty_level,
        "confidence": question.confidence,
    }


def build_answer_row(
    question_row: dict,
    answer,
) -> dict:
    """Monta uma linha da dimensão de respostas a partir de uma alternativa."""
    return {
        "answer_id": concat_ws_sha256(
            "||", [question_row["question_id"], answer.answer_text]
        ),
        "question_id": question_row["question_id"],
        "raw_answer_text": answer.answer_text,
        "is_correct": None,
        "answer_vocabulary_items": answer.answer_vocabulary_items,
        "answer_grammar_patterns": answer.answer_grammar_patterns,
    }


def run_silver_pipeline() -> None:
    """Executa o pipeline completo da camada Silver para todos os exames."""
    configure_windows_hadoop()
    spark = None

    try:
        spark = initialize_spark("topik-silver-builder")

        questions_list, answers_list, reliable_questions = (
            extract_questions_from_bronze(spark)
        )

        if not questions_list:
            logger.warning("Nenhuma questão confiável extraída.")
            return

        logger.info("Questões confiáveis extraídas: %d", len(reliable_questions))

        bronze_schema = build_pages_raw_schema()
        full_bronze_df = read_parquet_data(spark, BRONZE_DIR, bronze_schema)

        (
            dim_exam_df,
            dim_file_df,
            dim_question_df,
            dim_answer_df,
            fact_download_df,
            fact_qa_df,
        ) = build_silver_tables(spark, full_bronze_df, questions_list, answers_list)

        write_silver_parquet(
            dim_exam_df,
            dim_file_df,
            dim_question_df,
            dim_answer_df,
            fact_download_df,
            fact_qa_df,
        )
    finally:
        if spark is not None:
            spark.stop()


def main() -> None:
    run_silver_pipeline()


if __name__ == "__main__":
    main()
