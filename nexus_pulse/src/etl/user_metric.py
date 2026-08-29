import argparse
import logging
import duckdb
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def aggregate_user_metrics(events_path: str, users_path: str, output_path: str):
    logger.info(f"Ingesting sessionized events and users...")
    
    con = duckdb.connect(database=':memory:')
    
    query = f"""
    WITH aggregated_events AS (
        SELECT 
            user_id,
            ROUND(SUM(COALESCE(revenue_amount, 0)), 2) as post_exp_spend,
            COUNT(DISTINCT session_id) as total_sessions,
            COUNT(event_id) as total_events,
            MAX(CASE WHEN event_type = 'checkout' THEN 1 ELSE 0 END) as converted
        FROM read_parquet('{events_path}')
        GROUP BY user_id
    )
    SELECT 
        u.user_id,
        COALESCE(e.post_exp_spend, 0.0) as post_exp_spend,
        COALESCE(e.total_sessions, 0) as total_sessions,
        COALESCE(e.total_events, 0) as total_events,
        COALESCE(e.converted, 0) as converted
    FROM read_parquet('{users_path}') u
    LEFT JOIN aggregated_events e ON u.user_id = e.user_id
    """
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    logger.info("Aggregating user metrics via DuckDB...")
    con.execute(f"COPY ({query}) TO '{output_path}' (FORMAT PARQUET, COMPRESSION 'snappy');")
    
    logger.info(f"Saved aggregated user metrics to {output_path}")
    
    # Print summary statistics requested by user
    stats = con.execute(f"""
        SELECT 
            COUNT(*) as total_users,
            SUM(post_exp_spend) as total_spend,
            CAST(SUM(converted) AS FLOAT) / COUNT(*) as conversion_rate
        FROM read_parquet('{output_path}')
    """).fetchone()
    
    logger.info(f"Total Users: {stats[0]:,}")
    logger.info(f"Total Post-Spend: ${stats[1]:,.2f}")
    logger.info(f"Conversion Rate: {stats[2]*100:.2f}%")

def main():
    parser = argparse.ArgumentParser(description="NexusPulse User Metrics Aggregator")
    parser.add_argument('--events', type=str, default='data/processed/sessionized_events.parquet', help="Path to sessionized events parquet")
    parser.add_argument('--users', type=str, default='data/raw/users.parquet', help="Path to raw users parquet")
    parser.add_argument('--output', type=str, default='data/processed/user_post_metrics.parquet', help="Path to output user metrics parquet")
    args = parser.parse_args()
    
    aggregate_user_metrics(args.events, args.users, args.output)

if __name__ == "__main__":
    main()
