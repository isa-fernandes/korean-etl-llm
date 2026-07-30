from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    DoubleType,
    IntegerType,
)


def build_dim_file_schema() -> StructType:
    """Schema explicito para manter consistencia do dataset Silver."""
    return StructType(
        [
            StructField("file_id", StringType(), False), # filename || source_pdf_path || source_url
            StructField("filename", StringType(), True),
            StructField("file_type", StringType(), True),
            StructField("size_kb", DoubleType(), True),
            StructField("page_count", IntegerType(), True),
            StructField("source_pdf_path", StringType(), True),
            StructField("source_url", StringType(), True),
        ]
    )
