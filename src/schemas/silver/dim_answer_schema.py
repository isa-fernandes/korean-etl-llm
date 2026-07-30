from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    BooleanType,
    ArrayType,
)


def build_dim_answer_schema() -> StructType:
    """Schema explicito para manter consistencia do dataset Silver."""
    return StructType(
        [
            StructField("answer_id", StringType(), False), # question_id || raw_answer_text
            StructField("question_id", StringType(), False),
            StructField("raw_answer_text", StringType(), True),
            StructField("is_correct", BooleanType(), True),
            StructField("answer_vocabulary_items", ArrayType(StringType()), True),
            StructField("answer_grammar_patterns", ArrayType(StringType()), True),
        ]
    )
