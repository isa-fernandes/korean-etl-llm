from pyspark.sql.types import ArrayType, FloatType, StringType, StructField, StructType


def build_vw_llm_training_schema():
    """Schema explicito para manter consistencia do dataset gold."""
    return StructType(
        [
            StructField("training_id", StringType(), False),  # question_id
            StructField("exam_id", StringType(), True),
            StructField("question_id", StringType(), True),
            StructField(
                "messages",
                ArrayType(
                    StructType(
                        [
                            StructField("role", StringType(), True),
                            StructField("content", StringType(), True),
                        ]
                    )
                ),
                True,
            ),
            StructField("topik_level", StringType(), True),
            StructField("topic", StringType(), True),
            StructField("difficulty_level", StringType(), True),
            StructField("question_type", StringType(), True),
            StructField("confidence", FloatType(), True),
            # TODO: adicionar vocabulários/gramáticas
        ]
    )
