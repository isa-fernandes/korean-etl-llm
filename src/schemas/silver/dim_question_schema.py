from pyspark.sql.types import (
    ArrayType,
    FloatType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)


def build_dim_question_schema() -> StructType:
    """Schema explicito para manter consistencia do dataset Silver."""
    return StructType(
        [
            StructField(
                "question_id", StringType(), False
            ),  # exam_id || page_number || raw_question_text || question_stimulus
            StructField("exam_id", StringType(), False),
            StructField("page_number", IntegerType(), True),
            StructField("question_type", StringType(), True),
            StructField("raw_question_text", StringType(), True),
            StructField("question_stimulus", StringType(), True),
            StructField("question_vocabulary_items", ArrayType(StringType()), True),
            StructField("question_grammar_patterns", ArrayType(StringType()), True),
            StructField("topic", StringType(), True),
            StructField("difficulty_level", StringType(), True),
            StructField("confidence", FloatType(), True),
        ]
    )
