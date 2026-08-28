import streamlit as st
import pandas as pd
import duckdb
import plotly.graph_objects as go
import plotly.express as px
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.analytics.experiment_analysis import run_analysis
from src.stats.cuped import perform_ttest, perform_ttest_clustered, check_srm

st.set_page_config(page_title="NexusPulse Dashboard", layout="wide")
st.title("NexusPulse Causal Experimentation Platform")

@st.cache_data
def load_data():
    df = run_analysis(
        users_path='data/raw/users.parquet',
        assignments_path='data/raw/assignments.parquet',
        metrics_path='data/processed/user_post_metrics.parquet'
    )
    
    # Load funnel data using DuckDB
    con = duckdb.connect(database=':memory:')
    query = """
    SELECT event_type, COUNT(DISTINCT user_id) as users_count
    FROM read_parquet('data/raw/events.parquet')
    GROUP BY event_type
    """
    funnel_df = con.execute(query).fetchdf()
    
    # Ordering the funnel
    event_order = {'page_view': 1, 'search': 2, 'add_to_cart': 3, 'checkout': 4}
    funnel_df['order'] = funnel_df['event_type'].map(event_order)
    funnel_df = funnel_df.sort_values('order')
    
    return df, funnel_df

with st.spinner("Analyzing experiment..."):
    df, funnel_df = load_data()

tab1, tab2, tab3 = st.tabs(["Funnel Analytics", "CUPED & Causal Stats", "Diagnostics & Robustness"])

with tab1:
    st.header("Conversion Funnel")
    
    fig = go.Figure(go.Funnel(
        y=funnel_df['event_type'],
        x=funnel_df['users_count'],
        textinfo="value+percent initial"
    ))
    fig.update_layout(title="Overall Marketplace Funnel")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("CUPED Variance Reduction")
    
    var_standard = df['post_exp_spend'].var()
    var_cuped = df['post_exp_spend_cuped'].var()
    var_reduction = (1 - (var_cuped / var_standard)) * 100
    
    st.metric("Variance Reduction (pre_exp_spend_14d Covariate)", f"{var_reduction:.2f}%")
    
    standard_results = perform_ttest(df, 'post_exp_spend')
    cuped_results = perform_ttest(df, 'post_exp_spend_cuped')
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Standard T-Test (post_exp_spend)")
        st.write(f"**Lift:** {standard_results['relative_lift_pct']:.2f}%")
        st.write(f"**p-value:** {standard_results['p_value']:.4f}")
        st.write(f"**Significant:** {standard_results['significant']}")
        
    with col2:
        st.subheader("CUPED T-Test (post_exp_spend_cuped)")
        st.write(f"**Lift:** {cuped_results['relative_lift_pct']:.2f}%")
        st.write(f"**p-value:** {cuped_results['p_value']:.4f}")
        st.write(f"**Significant:** {cuped_results['significant']}")
        
    st.subheader("Metric Distributions (Variance Shrinkage)")
    plot_df = pd.DataFrame({
        'Standard': df['post_exp_spend'],
        'CUPED': df['post_exp_spend_cuped']
    }).melt(var_name='Metric', value_name='Spend')
    
    # Filter zeros for better visualization of the spread
    plot_df = plot_df[plot_df['Spend'] > 0]
    
    fig2 = px.histogram(plot_df, x='Spend', color='Metric', barmode='overlay', marginal='box', opacity=0.6,
                        title="Distribution of Spend (excluding $0)")
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    st.header("Diagnostics & Robustness")
    
    st.subheader("Sample Ratio Mismatch (SRM) Check")
    srm_res = check_srm(df)
    
    srm_color = "normal" if not srm_res['srm_detected'] else "inverse"
    col_srm1, col_srm2, col_srm3 = st.columns(3)
    col_srm1.metric("Control Traffic", f"{srm_res['observed_control']:,}")
    col_srm2.metric("Treatment Traffic", f"{srm_res['observed_treatment']:,}")
    col_srm3.metric("p-value", f"{srm_res['p_value']:.4f}", "No SRM detected" if not srm_res['srm_detected'] else "SRM Detected!", delta_color=srm_color)
    
    st.subheader("Standard Error Robustness")
    st.markdown("Comparing Naive standard errors vs Huber-White Sandwich Estimator (Clustered by `user_tier`).")
    
    # We already have standard_results for Naive
    cluster_results = perform_ttest_clustered(df, 'post_exp_spend', cluster_col='user_tier')
    
    compare_df = pd.DataFrame({
        'Method': ['Naive (Welch)', 'Cluster-Robust (user_tier)'],
        'Absolute Lift': [standard_results['absolute_diff'], cluster_results['absolute_diff']],
        'p-value': [standard_results['p_value'], cluster_results['p_value']],
        'Significant (<0.05)': [standard_results['significant'], cluster_results['significant']]
    })
    
    st.dataframe(compare_df, use_container_width=True)
