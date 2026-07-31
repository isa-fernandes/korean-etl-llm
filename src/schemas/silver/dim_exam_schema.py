from pyspark.sql.types import (
    StringType,
    StructField,
    StructType,
)


def build_dim_exam_schema() -> StructType:
    """Schema explicito para manter consistencia do dataset Silver."""
    return StructType(
        [
            StructField("exam_id", StringType(), False),
            StructField("exam_name", StringType(), True),
            StructField("exam_edition", StringType(), True),
            StructField("exam_number", StringType(), True),
            StructField("topik_level", StringType(), True),
            StructField("exam_section", StringType(), True),
        ]
    )
