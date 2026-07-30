from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    DoubleType,
    IntegerType,
)


def build_pages_raw_schema() -> StructType:
    """Schema explicito para manter consistencia do dataset Bronze."""
    return StructType(
        [
            StructField("exam_id", StringType(), False),
            StructField("exam_folder", StringType(), True),
            StructField("exam_edition", StringType(), True),
            StructField("filename", StringType(), True),
            StructField("label", StringType(), True),
            StructField("exam_number", StringType(), True),
            StructField("exam_year", StringType(), True),
            StructField("exam_month", StringType(), True),
            StructField("exam_session", StringType(), True),
            StructField("topik_format", StringType(), True),
            StructField("level", StringType(), True),
            StructField("section", StringType(), True),
            StructField("file_type", StringType(), True),
            StructField("source_url", StringType(), True),
            StructField("page_url", StringType(), True),
            StructField("download_date", StringType(), True),
            StructField("size_kb", DoubleType(), True),
            StructField("download_status", StringType(), True),
            StructField("source_pdf_path", StringType(), True),
            StructField("processed_at", StringType(), True),
            StructField("page_count", IntegerType(), True),
            StructField("page_number", IntegerType(), True),
            StructField("word_count", IntegerType(), True),
            StructField("char_count", IntegerType(), True),
            StructField("raw_text", StringType(), True),
        ]
    )
