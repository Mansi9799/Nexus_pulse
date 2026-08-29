import os
import duckdb
import pandas as pd

def calculate_funnel():
    """
    Ingest parquet files using DuckDB and compute a 4-stage funnel CTE.
    Returns the aggregated DataFrame.
    """
    con = duckdb.connect()

    query = """
    WITH user_funnel AS (
        SELECT
            a.user_id,
            a.variant,
            u.user_tier,
            MAX(CASE WHEN e.event_type = 'page_view' THEN 1 ELSE 0 END) AS stage1_page_view,
            MAX(CASE WHEN e.event_type = 'search' THEN 1 ELSE 0 END) AS stage2_search,
            MAX(CASE WHEN e.event_type = 'add_to_cart' THEN 1 ELSE 0 END) AS stage3_add_to_cart,
            MAX(CASE WHEN e.event_type = 'checkout' THEN 1 ELSE 0 END) AS stage4_checkout
        FROM read_parquet('data/raw/assignments.parquet') a
        JOIN read_parquet('data/raw/users.parquet') u 
            ON a.user_id = u.user_id
        LEFT JOIN read_parquet('data/raw/events.parquet') e 
            ON a.user_id = e.user_id
        GROUP BY a.user_id, a.variant, u.user_tier
    ),
    funnel_aggregated AS (
        SELECT
            variant,
            user_tier,
            COUNT(*) AS total_users,
            SUM(stage1_page_view) AS page_view,
            SUM(stage2_search) AS search,
            SUM(stage3_add_to_cart) AS add_to_cart,
            SUM(stage4_checkout) AS checkout
        FROM user_funnel
        GROUP BY variant, user_tier
    )
    SELECT * FROM funnel_aggregated ORDER BY variant, user_tier;
    """
    
    df = con.execute(query).df()
    return df

def display_funnel_metrics(df):
    """
    Computes and prints conversion rates using the aggregated DataFrame.
    """
    print("=== Raw Funnel Aggregation ===")
    print(df.to_string(index=False))
    print("\n")
    
    # 1. Stage-to-stage drop-off conversion rates
    print("=== Stage-to-Stage Drop-off Conversion Rates ===")
    overall = df.sum(numeric_only=True)
    
    s1 = overall['page_view']
    s2 = overall['search']
    s3 = overall['add_to_cart']
    s4 = overall['checkout']
    
    conv_1_to_2 = (s2 / s1 * 100) if s1 else 0
    conv_2_to_3 = (s3 / s2 * 100) if s2 else 0
    conv_3_to_4 = (s4 / s3 * 100) if s3 else 0
    
    stage_df = pd.DataFrame({
        'Stage Transition': ['Page View -> Search', 'Search -> Add to Cart', 'Add to Cart -> Checkout'],
        'Conversion Rate (%)': [f"{conv_1_to_2:.2f}%", f"{conv_2_to_3:.2f}%", f"{conv_3_to_4:.2f}%"]
    })
    print(stage_df.to_string(index=False))
    print("\n")
    
    # 2. Overall conversion rate per variant ('control' vs 'treatment')
    print("=== Overall Conversion Rate Per Variant ===")
    # Using total_users as the base (Intention-to-Treat)
    variant_grouped = df.groupby('variant')[['total_users', 'checkout']].sum().reset_index()
    variant_grouped['overall_conversion_rate'] = (variant_grouped['checkout'] / variant_grouped['total_users'] * 100)
    variant_grouped['overall_conversion_rate'] = variant_grouped['overall_conversion_rate'].map("{:.2f}%".format)
    print(variant_grouped.to_string(index=False))
    print("\n")
    
    # 3. Segmented conversion rates across user_tier
    print("=== Segmented Conversion Rates Across User Tier ===")
    tier_grouped = df.groupby('user_tier')[['total_users', 'checkout']].sum().reset_index()
    
    # Custom sort for user tier
    tier_grouped['tier_cat'] = pd.Categorical(
        tier_grouped['user_tier'], 
        categories=['bronze', 'silver', 'gold'], 
        ordered=True
    )
    tier_grouped = tier_grouped.sort_values('tier_cat').drop(columns=['tier_cat'])
    
    tier_grouped['conversion_rate'] = (tier_grouped['checkout'] / tier_grouped['total_users'] * 100)
    tier_grouped['conversion_rate'] = tier_grouped['conversion_rate'].map("{:.2f}%".format)
    print(tier_grouped.to_string(index=False))

if __name__ == '__main__':
    # Ensure working directory is the 'nexus_pulse' root so relative data paths work
    script_dir = os.path.dirname(os.path.abspath(__file__))
    nexus_pulse_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))
    os.chdir(nexus_pulse_dir)
    
    df = calculate_funnel()
    display_funnel_metrics(df)
