import argparse
import logging
import duckdb
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def sessionize_events(input_path: str, output_path: str):
    logger.info(f"Ingesting raw events from {input_path}")
    
    con = duckdb.connect(database=':memory:')
    
    query = f"""
    WITH lagged AS (
        SELECT 
            *,
            LAG(event_timestamp) OVER (PARTITION BY user_id ORDER BY event_timestamp) as prev_ts
        FROM read_parquet('{input_path}')
    ),
    flags AS (
        SELECT 
            *,
            CASE 
                WHEN prev_ts IS NULL THEN 1
                WHEN epoch(event_timestamp) - epoch(prev_ts) > 1800 THEN 1
                ELSE 0
            END as is_new_session
        FROM lagged
    ),
    indexed AS (
        SELECT 
            *,
            SUM(is_new_session) OVER (PARTITION BY user_id ORDER BY event_timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as session_index
        FROM flags
    )
    SELECT 
        event_id,
        user_id,
        event_timestamp,
        event_type,
        revenue_amount,
        CAST(user_id AS VARCHAR) || '_s' || CAST(session_index AS VARCHAR) as session_id
    FROM indexed
    ORDER BY user_id, event_timestamp
    """
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    logger.info("Executing sessionization logic via DuckDB...")
    con.execute(f"COPY ({query}) TO '{output_path}' (FORMAT PARQUET, COMPRESSION 'snappy');")
    
    logger.info(f"Saved sessionized events to {output_path}")
    
    # Print total records and distinct session count
    stats = con.execute(f"""
        SELECT 
            COUNT(*) as total_records, 
            COUNT(DISTINCT session_id) as distinct_sessions 
        FROM read_parquet('{output_path}')
    """).fetchone()
    
    logger.info(f"Total Records: {stats[0]:,}")
    logger.info(f"Distinct Sessions: {stats[1]:,}")

def main():
    parser = argparse.ArgumentParser(description="NexusPulse Event Sessionizer")
    parser.add_argument('--input', type=str, default='data/raw/events.parquet', help="Path to raw events parquet")
    parser.add_argument('--output', type=str, default='data/processed/sessionized_events.parquet', help="Path to output sessionized events")
    args = parser.parse_args()
    
    sessionize_events(args.input, args.output)

if __name__ == "__main__":
    main()
