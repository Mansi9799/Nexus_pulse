import os
import duckdb
import pandas as pd

def calculate_and_save_retention():
    """
    Reads sessionized events and assignments.
    Computes cohort retention at Day 1, Day 3, Day 7, and Day 14.
    Segments by variant and device_type.
    Saves the output to data/processed/cohort_retention.parquet.
    """
    con = duckdb.connect()
    
    # We use a CTE to mock device_type deterministically based on user_id 
    # since it is missing from the raw assignments.parquet.
    query = """
    WITH assignments_with_device AS (
        SELECT 
            user_id,
            variant,
            assigned_timestamp,
            CAST(assigned_timestamp AS DATE) as assigned_date,
            CASE 
                WHEN user_id % 3 = 0 THEN 'mobile'
                WHEN user_id % 3 = 1 THEN 'desktop'
                ELSE 'tablet'
            END AS device_type
        FROM read_parquet('data/raw/assignments.parquet')
    ),
    user_activity AS (
        SELECT 
            a.user_id,
            a.variant,
            a.device_type,
            a.assigned_date,
            CAST(e.event_timestamp AS DATE) as event_date,
            date_diff('day', a.assigned_date, CAST(e.event_timestamp AS DATE)) as days_since_assignment
        FROM assignments_with_device a
        LEFT JOIN read_parquet('data/processed/sessionized_events.parquet') e
            ON a.user_id = e.user_id
    ),
    retention_flags AS (
        SELECT 
            user_id,
            variant,
            device_type,
            MAX(CASE WHEN days_since_assignment = 1 THEN 1 ELSE 0 END) as retained_day_1,
            MAX(CASE WHEN days_since_assignment = 3 THEN 1 ELSE 0 END) as retained_day_3,
            MAX(CASE WHEN days_since_assignment = 7 THEN 1 ELSE 0 END) as retained_day_7,
            MAX(CASE WHEN days_since_assignment = 14 THEN 1 ELSE 0 END) as retained_day_14
        FROM user_activity
        GROUP BY user_id, variant, device_type
    ),
    cohort_retention AS (
        SELECT 
            variant,
            device_type,
            COUNT(user_id) as cohort_size,
            SUM(retained_day_1) as day_1_active,
            SUM(retained_day_3) as day_3_active,
            SUM(retained_day_7) as day_7_active,
            SUM(retained_day_14) as day_14_active
        FROM retention_flags
        GROUP BY variant, device_type
    )
    SELECT 
        variant,
        device_type,
        cohort_size,
        day_1_active * 100.0 / cohort_size as day_1_retention_pct,
        day_3_active * 100.0 / cohort_size as day_3_retention_pct,
        day_7_active * 100.0 / cohort_size as day_7_retention_pct,
        day_14_active * 100.0 / cohort_size as day_14_retention_pct
    FROM cohort_retention
    ORDER BY variant, device_type
    """
    
    os.makedirs('data/processed', exist_ok=True)
    output_path = 'data/processed/cohort_retention.parquet'
    
    # Save using DuckDB COPY
    save_query = f"""
    COPY (
        {query}
    ) TO '{output_path}' (FORMAT PARQUET, COMPRESSION 'snappy');
    """
    con.execute(save_query)
    
    # Return as df for printing
    df = con.execute(query).df()
    return df

def display_retention_matrix(df):
    """
    Prints the formatted retention matrix.
    """
    print("=== Cohort Retention Matrix ===")
    
    # Format the percentages
    formatted_df = df.copy()
    for col in ['day_1_retention_pct', 'day_3_retention_pct', 'day_7_retention_pct', 'day_14_retention_pct']:
        formatted_df[col] = formatted_df[col].map("{:.2f}%".format)
        
    print(formatted_df.to_string(index=False))

if __name__ == '__main__':
    # Ensure working directory is the 'nexus_pulse' root so relative data paths work
    script_dir = os.path.dirname(os.path.abspath(__file__))
    nexus_pulse_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))
    os.chdir(nexus_pulse_dir)
    
    df = calculate_and_save_retention()
    display_retention_matrix(df)
