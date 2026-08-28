import argparse
import logging
import os
import duckdb

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_events(input_path: str, output_path: str):
    """
    Ingest events, sessionize with 30-min threshold, and aggregate user metrics using DuckDB.
    
    Args:
        input_path: Path to the raw events.parquet file or directory.
        output_path: Path to write the aggregated user metrics.
    """
    logger.info(f"Reading raw events from: {input_path}")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Establish a DuckDB connection (in-memory)
    con = duckdb.connect(database=':memory:')
    
    # Run the ETL logic entirely in SQL utilizing DuckDB's fast execution engine
    query = f"""
    WITH lagged_events AS (
        SELECT 
            user_id,
            event_timestamp,
            event_type,
            revenue_amount,
            LAG(event_timestamp) OVER (PARTITION BY user_id ORDER BY event_timestamp) as prev_timestamp
        FROM read_parquet('{input_path}')
    ),
    session_flags AS (
        SELECT
            *,
            CASE 
                WHEN prev_timestamp IS NULL THEN 1
                WHEN date_diff('second', prev_timestamp, event_timestamp) > 1800 THEN 1
                ELSE 0
            END as is_new_session
        FROM lagged_events
    ),
    sessionized AS (
        SELECT
            *,
            SUM(is_new_session) OVER (PARTITION BY user_id ORDER BY event_timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as session_id
        FROM session_flags
    )
    SELECT 
        user_id,
        ROUND(SUM(COALESCE(revenue_amount, 0)), 2) as post_exp_spend,
        MAX(session_id) as total_sessions,
        COUNT(*) as total_events,
        MAX(CASE WHEN event_type = 'checkout' THEN 1 ELSE 0 END) as converted
    FROM sessionized
    GROUP BY user_id
    """
    
    logger.info("Executing DuckDB query for sessionization and aggregation...")
    
    # Execute and directly write the output to a Parquet file
    con.execute(f"COPY ({query}) TO '{output_path}' (FORMAT PARQUET, COMPRESSION 'snappy');")
    
    logger.info(f"Aggregated user metrics successfully written to: {output_path}")
    logger.info("ETL Pipeline completed successfully.")
    
    # Optional: Display a few rows of the final output
    preview = con.execute(f"SELECT * FROM read_parquet('{output_path}') LIMIT 5").fetchdf()
    logger.info(f"Sample data:\n{preview}")

def main():
    parser = argparse.ArgumentParser(description="NexusPulse DuckDB ETL Pipeline")
    parser.add_argument('--input-events', type=str, default='data/raw/events.parquet', help="Path to raw events parquet")
    parser.add_argument('--output-metrics', type=str, default='data/processed/user_post_metrics.parquet', help="Path to output aggregated metrics")
    
    args = parser.parse_args()
    
    process_events(args.input_events, args.output_metrics)

if __name__ == "__main__":
    main()
