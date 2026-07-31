import os
import sys

from pyspark.sql import SparkSession


def initialize_spark(app_name: str):
    spark = (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.pyspark.python", sys.executable)
        .config("spark.pyspark.driver.python", sys.executable)
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark
