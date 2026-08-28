import pandas as pd
import duckdb
import argparse
import logging
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.stats.cuped import calculate_cuped_adjusted_metric, perform_ttest, perform_ttest_clustered, check_srm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_analysis(users_path: str, assignments_path: str, metrics_path: str):
    logger.info("Loading datasets...")
    
    con = duckdb.connect(database=':memory:')
    
    query = f"""
    SELECT 
        a.user_id,
        a.variant,
        u.pre_exp_spend_14d,
        u.user_tier,
        COALESCE(m.post_exp_spend, 0) AS post_exp_spend,
        COALESCE(m.total_sessions, 0) AS total_sessions,
        COALESCE(m.total_events, 0) AS total_events,
        COALESCE(m.converted, 0) AS converted
    FROM read_parquet('{assignments_path}') a
    JOIN read_parquet('{users_path}') u ON a.user_id = u.user_id
    LEFT JOIN read_parquet('{metrics_path}') m ON a.user_id = m.user_id
    """
    
    df = con.execute(query).fetchdf()
    logger.info(f"Loaded merged data with {len(df)} rows.")
    
    # SRM Check
    srm_res = check_srm(df)
    logger.info(f"SRM Check: p_value={srm_res['p_value']:.4f}, Detected={srm_res['srm_detected']}")
    
    # Apply CUPED
    df = calculate_cuped_adjusted_metric(
        df=df, 
        metric_col='post_exp_spend', 
        covariate_col='pre_exp_spend_14d', 
        adjusted_metric_name='post_exp_spend_cuped'
    )
    
    var_standard = df['post_exp_spend'].var()
    var_cuped = df['post_exp_spend_cuped'].var()
    var_reduction = (1 - (var_cuped / var_standard)) * 100
    
    logger.info(f"Variance Reduction: {var_reduction:.2f}%")
    
    return df

def main():
    parser = argparse.ArgumentParser(description="NexusPulse Experiment Analysis")
    parser.add_argument('--users', type=str, default='data/raw/users.parquet')
    parser.add_argument('--assignments', type=str, default='data/raw/assignments.parquet')
    parser.add_argument('--metrics', type=str, default='data/processed/user_post_metrics.parquet')
    
    args = parser.parse_args()
    run_analysis(args.users, args.assignments, args.metrics)

if __name__ == "__main__":
    main()
