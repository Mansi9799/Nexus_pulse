"""
Synthetic Data Generator for NexusPulse.
Simulates a two-sided marketplace experimentation log.
"""

import argparse
import os
import time
import uuid
import logging
from typing import Tuple

import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_users(num_users: int) -> pd.DataFrame:
    """
    Generate synthetic users for the marketplace.
    
    Args:
        num_users: Number of users to generate.
        
    Returns:
        pd.DataFrame containing user profiles.
    """
    logger.info(f"Generating {num_users} users...")
    user_ids = np.arange(1, num_users + 1)
    
    # 60% bronze, 30% silver, 10% gold
    tiers = np.random.choice(['bronze', 'silver', 'gold'], size=num_users, p=[0.6, 0.3, 0.1])
    
    # Pre-experiment spend (Gamma distribution)
    pre_exp_spend = np.round(np.random.gamma(shape=2.0, scale=35.0, size=num_users), 2)
    
    # Signup dates
    start_date = pd.to_datetime('2025-01-01')
    end_date = pd.to_datetime('2026-06-01')
    days_between = (end_date - start_date).days
    random_days = np.random.randint(0, days_between, size=num_users)
    signup_dates = start_date + pd.to_timedelta(random_days, unit='D')
    
    return pd.DataFrame({
        'user_id': user_ids,
        'user_tier': tiers,
        'pre_exp_spend_14d': pre_exp_spend,
        'signup_date': signup_dates.strftime('%Y-%m-%d')
    })

def generate_assignments(user_ids: np.ndarray, inject_srm: bool) -> pd.DataFrame:
    """
    Generate experiment assignments.
    
    Args:
        user_ids: Array of user IDs.
        inject_srm: Whether to inject Sample Ratio Mismatch (52.5% Control).
        
    Returns:
        pd.DataFrame containing experiment assignments.
    """
    num_users = len(user_ids)
    logger.info(f"Generating assignments for {num_users} users (SRM={inject_srm})...")
    
    if inject_srm:
        p_control, p_treatment = 0.525, 0.475
    else:
        p_control, p_treatment = 0.5, 0.5
        
    variants = np.random.choice(['control', 'treatment'], size=num_users, p=[p_control, p_treatment])
    
    # Assigned across 2026-08-01
    start_ts = pd.to_datetime('2026-08-01 00:00:00')
    end_ts = pd.to_datetime('2026-08-01 23:59:59')
    seconds_between = int((end_ts - start_ts).total_seconds())
    random_seconds = np.random.randint(0, seconds_between, size=num_users)
    assigned_timestamps = start_ts + pd.to_timedelta(random_seconds, unit='s')
    
    return pd.DataFrame({
        'experiment_id': "EXP_CHECKOUT_V2",
        'user_id': user_ids,
        'variant': variants,
        'assigned_timestamp': assigned_timestamps
    })

def generate_events(users_df: pd.DataFrame, assignments_df: pd.DataFrame, num_active_users: int) -> pd.DataFrame:
    """
    Generate clickstream events for active users.
    
    Args:
        users_df: Users DataFrame.
        assignments_df: Assignments DataFrame.
        num_active_users: Number of active users to simulate events for.
        
    Returns:
        pd.DataFrame containing clickstream events.
    """
    logger.info(f"Generating events for {num_active_users} active users...")
    
    # Select active users
    active_user_ids = np.random.choice(users_df['user_id'], size=num_active_users, replace=False)
    
    active_users_info = users_df[users_df['user_id'].isin(active_user_ids)][['user_id', 'pre_exp_spend_14d']]
    active_assignments = assignments_df[assignments_df['user_id'].isin(active_user_ids)][['user_id', 'variant', 'assigned_timestamp']]
    
    merged = pd.merge(active_users_info, active_assignments, on='user_id')
    
    # Number of sessions per user: Poisson(4) + 1
    sessions_per_user = np.random.poisson(lam=4, size=num_active_users) + 1
    
    session_user_ids = np.repeat(merged['user_id'].values, sessions_per_user)
    session_spend = np.repeat(merged['pre_exp_spend_14d'].values, sessions_per_user)
    session_variant = np.repeat(merged['variant'].values, sessions_per_user)
    session_assigned_ts = np.repeat(merged['assigned_timestamp'].values, sessions_per_user)
    
    num_sessions = len(session_user_ids)
    
    # Initial page_view
    random_offsets = np.random.randint(1, 14 * 24 * 3600, size=num_sessions)
    page_view_ts = session_assigned_ts + pd.to_timedelta(random_offsets, unit='s')
    
    # search (+15s to 45s)
    search_conv = np.random.rand(num_sessions) < 0.70
    search_ts = page_view_ts + pd.to_timedelta(np.random.randint(15, 46, size=num_sessions), unit='s')
    
    # add_to_cart (+30s to 90s)
    atc_conv = search_conv & (np.random.rand(num_sessions) < 0.45)
    atc_ts = search_ts + pd.to_timedelta(np.random.randint(30, 91, size=num_sessions), unit='s')
    
    # checkout (+60s to 180s)
    checkout_conv = atc_conv & (np.random.rand(num_sessions) < 0.35)
    checkout_ts = atc_ts + pd.to_timedelta(np.random.randint(60, 181, size=num_sessions), unit='s')
    
    # Revenue logic explicitly requested by user
    gamma_noise = np.random.gamma(2.0, 6.0, size=num_sessions)
    base_revenue = (session_spend * 0.75) + gamma_noise
    
    treatment_mask = (session_variant == 'treatment')
    revenue = base_revenue.copy()
    revenue[treatment_mask] = revenue[treatment_mask] * 1.06
    revenue = np.round(revenue, 2)
    
    # Construct event DataFrames
    df_pv = pd.DataFrame({
        'user_id': session_user_ids,
        'event_timestamp': page_view_ts,
        'event_type': 'page_view',
        'revenue_amount': 0.0
    })
    
    df_search = pd.DataFrame({
        'user_id': session_user_ids[search_conv],
        'event_timestamp': search_ts[search_conv],
        'event_type': 'search',
        'revenue_amount': 0.0
    })
    
    df_atc = pd.DataFrame({
        'user_id': session_user_ids[atc_conv],
        'event_timestamp': atc_ts[atc_conv],
        'event_type': 'add_to_cart',
        'revenue_amount': 0.0
    })
    
    df_checkout = pd.DataFrame({
        'user_id': session_user_ids[checkout_conv],
        'event_timestamp': checkout_ts[checkout_conv],
        'event_type': 'checkout',
        'revenue_amount': revenue[checkout_conv]
    })
    
    events_df = pd.concat([df_pv, df_search, df_atc, df_checkout], ignore_index=True)
    events_df['event_id'] = [str(uuid.uuid4()) for _ in range(len(events_df))]
    
    events_df = events_df[['event_id', 'user_id', 'event_timestamp', 'event_type', 'revenue_amount']]
    events_df = events_df.sort_values(['user_id', 'event_timestamp']).reset_index(drop=True)
    
    return events_df

def main():
    parser = argparse.ArgumentParser(description="NexusPulse Synthetic Data Generator")
    parser.add_argument('--num-users', type=int, default=100000, help="Total number of users to generate")
    parser.add_argument('--active-users', type=int, default=30000, help="Number of active users generating events")
    parser.add_argument('--inject-srm', action='store_true', help="Inject SRM (52.5%% Control / 47.5%% Treatment)")
    parser.add_argument('--output-dir', type=str, default='data/raw', help="Output directory for parquet files")
    
    args = parser.parse_args()
    
    if args.active_users > args.num_users:
        logger.warning("active_users > num_users. Clamping active_users to num_users.")
        args.active_users = args.num_users
        
    os.makedirs(args.output_dir, exist_ok=True)
    
    start_time = time.time()
    
    # Seed for reproducibility
    np.random.seed(42)
    
    # 1. Users
    users_df = generate_users(args.num_users)
    users_path = os.path.join(args.output_dir, 'users.parquet')
    users_df.to_parquet(users_path, compression='snappy', index=False)
    
    # 2. Assignments
    assignments_df = generate_assignments(users_df['user_id'].values, args.inject_srm)
    assignments_path = os.path.join(args.output_dir, 'assignments.parquet')
    assignments_df.to_parquet(assignments_path, compression='snappy', index=False)
    
    # 3. Events
    events_df = generate_events(users_df, assignments_df, args.active_users)
    
    # Zero out pre_exp_spend for inactive users so correlation holds for the overall ITT population
    active_user_ids = events_df['user_id'].unique()
    users_df.loc[~users_df['user_id'].isin(active_user_ids), 'pre_exp_spend_14d'] = 0.0
    
    # Save Users again
    users_df.to_parquet(users_path, compression='snappy', index=False)
    
    # Save Events
    events_path = os.path.join(args.output_dir, 'events.parquet')
    events_df.to_parquet(events_path, compression='snappy', index=False)
    
    duration = time.time() - start_time
    
    # Print metrics
    logger.info("==================================================")
    logger.info("DATA GENERATION COMPLETE")
    logger.info("==================================================")
    logger.info(f"Execution Time: {duration:.2f} seconds")
    logger.info(f"Total Users Generated: {args.num_users:,}")
    logger.info(f"Active Users Simulated: {args.active_users:,}")
    logger.info(f"Total Events Generated: {len(events_df):,}")
    logger.info("\nFile Sizes:")
    logger.info(f" - users.parquet:      {os.path.getsize(users_path) / (1024*1024):.2f} MB")
    logger.info(f" - assignments.parquet: {os.path.getsize(assignments_path) / (1024*1024):.2f} MB")
    logger.info(f" - events.parquet:     {os.path.getsize(events_path) / (1024*1024):.2f} MB")
    logger.info("==================================================")

if __name__ == "__main__":
    main()
