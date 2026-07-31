from pyspark.sql.types import DateType, StringType, StructField, StructType


def build_fact_download_schema() -> StructType:
    """Schema explicito para manter consistencia do dataset Silver."""
    return StructType(
        [
            StructField(
                "download_id", StringType(), False
            ),  # download_date || download_status || exam_id || file_id
            StructField("exam_id", StringType(), False),
            StructField("file_id", StringType(), False),
            StructField("download_date", DateType(), True),
            StructField("download_status", StringType(), True),
            StructField("bronze_processed_at", DateType(), True),
            StructField("silver_processed_at", DateType(), True),
        ]
    )
