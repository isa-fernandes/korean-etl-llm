import os
import sys

from pyspark.sql import SparkSession
from pyspark.sql.types import StructType

def initialize_spark(app_name:str):
    spark = (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.pyspark.python", sys.executable)
        .config("spark.pyspark.driver.python", sys.executable)
        .getOrCreate()
        )
    spark.sparkContext.setLogLevel("ERROR")
    return spark

def read_parquet(spark: SparkSession, folder: str, edition: str, schema: StructType | None):
    folder_path = os.path.join(folder, f"{edition}")
    if os.path.exists(folder_path):
        if schema is not None:
            df = spark.read.schema(schema).parquet(folder_path)
        else:
            df = spark.read.parquet(folder_path, inferSchema=True)
    else:
        raise FileNotFoundError(f"Arquivo não encontrado no caminho {folder_path}")
    return df