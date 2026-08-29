import duckdb
import os
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def build_experiment_mart(base_dir="."):
    """Builds the unified experiment feature store."""
    
    users_path = Path(base_dir) / "data" / "raw" / "users.parquet"
    assignments_path = Path(base_dir) / "data" / "raw" / "assignments.parquet"
    metrics_path = Path(base_dir) / "data" / "processed" / "user_post_metrics.parquet"
    output_path = Path(base_dir) / "data" / "processed" / "experiment_mart.parquet"
    
    # Ensure processed directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    logging.info("Building Master Analytical Mart...")
    
    # Establish DuckDB connection
    conn = duckdb.connect(':memory:')
    
    # Execute SQL pipeline
    query = f"""
    COPY (
        SELECT 
            u.user_id,
            u.signup_date,
            u.user_tier,
            u.pre_exp_spend_14d,
            CASE 
                WHEN u.user_id % 3 = 0 THEN 'mobile'
                WHEN u.user_id % 3 = 1 THEN 'desktop'
                ELSE 'tablet'
            END AS device_type,
            a.variant,
            a.assigned_timestamp,
            COALESCE(m.post_exp_spend, 0.0) AS post_exp_spend,
            COALESCE(m.total_sessions, 0) AS total_sessions,
            COALESCE(m.total_events, 0) AS total_events,
            COALESCE(m.converted, 0) AS converted,
            
            -- Feature Engineering
            (COALESCE(m.post_exp_spend, 0.0) - u.pre_exp_spend_14d) AS spend_delta,
            CASE WHEN a.variant = 'treatment' THEN 1 ELSE 0 END AS is_treatment,
            COALESCE(m.converted, 0) AS has_converted
            
        FROM '{users_path}' AS u
        LEFT JOIN '{assignments_path}' AS a 
            ON u.user_id = a.user_id
        LEFT JOIN '{metrics_path}' AS m 
            ON u.user_id = m.user_id
    ) TO '{output_path}' (FORMAT PARQUET, COMPRESSION 'snappy');
    """
    
    conn.execute(query)
    logging.info(f"Successfully exported experiment mart to {output_path}")
    
    # Validation
    logging.info("Running validation checks...")
    
    validation_query = f"""
    SELECT 
        COUNT(*) AS total_rows,
        COUNT(CASE WHEN post_exp_spend IS NULL THEN 1 END) AS null_spend,
        COUNT(CASE WHEN total_sessions IS NULL THEN 1 END) AS null_sessions,
        COUNT(CASE WHEN total_events IS NULL THEN 1 END) AS null_events,
        COUNT(CASE WHEN converted IS NULL THEN 1 END) AS null_converted
    FROM '{output_path}'
    """
    validation_res = conn.execute(validation_query).fetchone()
    
    total_rows = validation_res[0]
    logging.info(f"Total rows in mart: {total_rows}")
    
    if total_rows != 50000:
        logging.error(f"Row count mismatch! Expected 50000, got {total_rows}")
        
    nulls = {
        'post_exp_spend': validation_res[1],
        'total_sessions': validation_res[2],
        'total_events': validation_res[3],
        'converted': validation_res[4],
    }
    for col, null_count in nulls.items():
        if null_count == 0:
            logging.info(f"Column '{col}' has 0 nulls (Verified)")
        else:
            logging.error(f"Column '{col}' has {null_count} nulls!")
            
    # Schema Summary
    logging.info("Schema Summary:")
    schema = conn.execute(f"DESCRIBE SELECT * FROM '{output_path}'").fetchall()
    for col in schema:
        print(f"{col[0]:<20} | {col[1]}")

if __name__ == '__main__':
    # Assuming script is run from project root
    # e.g. python src/analytics/build_mart.py
    
    # Path resolution to run relative to the project root
    project_root = Path(__file__).resolve().parent.parent.parent
    build_experiment_mart(base_dir=project_root)
