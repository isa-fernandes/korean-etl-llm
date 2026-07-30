from pyspark.sql.types import StructType, StructField, StringType


def build_fact_qa_schema() -> StructType:
    """Schema explicito para manter consistencia do dataset Silver."""
    return StructType(
        [
            StructField("qa_id", StringType(), False),
            StructField("exam_id", StringType(), False),
            StructField("question_id", StringType(), False),
            StructField("answer_id", StringType(), False),
        ]
    )
