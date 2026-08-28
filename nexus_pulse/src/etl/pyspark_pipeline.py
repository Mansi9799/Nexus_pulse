"""
PySpark ETL Pipeline for NexusPulse.
Sessionizes raw clickstream events and aggregates user-level metrics.
"""

import argparse
import logging
import os
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_spark_session() -> SparkSession:
    """Initialize and return a SparkSession."""
    return SparkSession.builder \
        .appName("NexusPulse_ETL") \
        .config("spark.sql.session.timeZone", "UTC") \
        .config("spark.driver.memory", "4g") \
        .getOrCreate()

def process_events(spark: SparkSession, input_path: str, output_path: str):
    """
    Ingest events, sessionize with 30-min threshold, and aggregate user metrics.
    
    Args:
        spark: SparkSession instance.
        input_path: Path to the raw events.parquet file or directory.
        output_path: Path to write the aggregated user metrics.
    """
    logger.info(f"Reading raw events from: {input_path}")
    
    # 1. Ingest Data
    events_df = spark.read.parquet(input_path)
    
    # 2. Sessionize Events
    # Define window spec partitioned by user_id and ordered by event_timestamp
    window_spec = Window.partitionBy("user_id").orderBy("event_timestamp")
    
    # Calculate difference in seconds from previous event
    events_with_lag = events_df.withColumn(
        "prev_timestamp",
        F.lag("event_timestamp", 1).over(window_spec)
    )
    
    # Calculate time difference in seconds
    events_with_diff = events_with_lag.withColumn(
        "time_diff_sec",
        F.col("event_timestamp").cast("long") - F.col("prev_timestamp").cast("long")
    )
    
    # Identify new sessions: > 30 mins (1800 seconds) inactivity or first event
    events_with_new_session = events_with_diff.withColumn(
        "is_new_session",
        F.when(F.col("prev_timestamp").isNull() | (F.col("time_diff_sec") > 1800), 1).otherwise(0)
    )
    
    # Create unique session ID per user via cumulative sum
    sessionized_events = events_with_new_session.withColumn(
        "session_id",
        F.sum("is_new_session").over(window_spec)
    )
    
    logger.info("Sessionization complete. Proceeding with user-level aggregation...")
    
    # 3. Aggregate User Metrics
    user_metrics = sessionized_events.groupBy("user_id").agg(
        F.round(F.sum("revenue_amount"), 2).alias("post_exp_spend"),
        F.max("session_id").alias("total_sessions"),
        F.count("*").alias("total_events"),
        F.max(F.when(F.col("event_type") == "checkout", 1).otherwise(0)).alias("converted")
    )
    
    # 4. Save Aggregated Output
    logger.info(f"Writing aggregated user metrics to: {output_path}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Coalesce to a single partition for simplicity if it's a small output, 
    # but for a true distributed pipeline we might let it write multiple part files.
    # We will let PySpark write naturally based on its shuffle partitions.
    user_metrics.write.mode("overwrite").parquet(output_path, compression="snappy")
    
    logger.info("ETL Pipeline completed successfully.")
    
    # Show a sample of the aggregated data
    user_metrics.show(5, truncate=False)

def main():
    parser = argparse.ArgumentParser(description="NexusPulse PySpark ETL Pipeline")
    parser.add_argument('--input-events', type=str, default='data/raw/events.parquet', help="Path to raw events parquet")
    parser.add_argument('--output-metrics', type=str, default='data/processed/user_post_metrics.parquet', help="Path to output aggregated metrics")
    
    args = parser.parse_args()
    
    spark = create_spark_session()
    
    try:
        process_events(spark, args.input_events, args.output_metrics)
    finally:
        spark.stop()

if __name__ == "__main__":
    main()
