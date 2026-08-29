import os
import pandas as pd
import numpy as np
import pytest

from src.stats.cuped import CUPEDAnalyzer
from src.stats.cluster_se import ClusterRobustInference
from src.api.main import SRMDetector

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MART_PATH = os.path.join(BASE_DIR, "data", "processed", "experiment_mart.parquet")

def load_mart():
    if not os.path.exists(MART_PATH):
        pytest.skip("Data mart not found")
    return pd.read_parquet(MART_PATH)

def test_cuped_variance_reduction_bound():
    df = load_mart()
    analyzer = CUPEDAnalyzer()
    df_cuped, meta = analyzer.fit_transform(df, target='post_exp_spend', covariate='pre_exp_spend_14d')
    
    var_raw = df['post_exp_spend'].var()
    var_cuped = df_cuped['post_exp_spend_cuped'].var()
    
    assert var_cuped < var_raw
    assert 25.0 <= meta['variance_reduction_percentage'] <= 65.0

def test_cuped_unbiased_treatment_effect():
    df = load_mart()
    analyzer = CUPEDAnalyzer()
    df_cuped, meta = analyzer.fit_transform(df, target='post_exp_spend', covariate='pre_exp_spend_14d')
    
    res_raw = analyzer.run_ttest(df_cuped, metric_col='post_exp_spend')
    res_cuped = analyzer.run_ttest(df_cuped, metric_col='post_exp_spend_cuped')
    
    raw_lift = res_raw['absolute_lift']
    cuped_lift = res_cuped['absolute_lift']
    
    assert np.isclose(raw_lift, cuped_lift, atol=0.08)

def test_srm_detector_true_negative():
    df = load_mart()
    srm_diagnostics = SRMDetector.check(df, expected_control_ratio=0.50)
    assert srm_diagnostics['srm_detected'] is False
    assert srm_diagnostics['p_value'] > 0.01

def test_srm_detector_true_positive():
    # Construct a synthetic dataframe with an intentional 56:44 allocation split
    control_count = 5600
    treatment_count = 4400
    df = pd.DataFrame({
        'variant': ['control'] * control_count + ['treatment'] * treatment_count
    })
    
    srm_diagnostics = SRMDetector.check(df, expected_control_ratio=0.50)
    assert srm_diagnostics['srm_detected'] is True
    assert srm_diagnostics['p_value'] < 0.001

def test_cluster_robust_se_inflation():
    df = load_mart()
    
    analyzer = CUPEDAnalyzer()
    df_cuped, meta = analyzer.fit_transform(df, target='post_exp_spend', covariate='pre_exp_spend_14d')
    
    if 'user_tier' in df_cuped.columns:
        df_cuped['user_tier'] = df_cuped['user_tier'].fillna("Unknown")
        
    inferencer = ClusterRobustInference()
    comparison_df = inferencer.fit_and_compare(
        df_cuped,
        outcome_col='post_exp_spend_cuped',
        treatment_col='is_treatment',
        cluster_col='user_tier'
    )
    
    cluster_stats = comparison_df.loc["Huber-White Clustered"]
    assert 'Standard Error' in cluster_stats
    assert not np.isnan(cluster_stats['Standard Error'])
    assert cluster_stats['Standard Error'] > 0
    assert cluster_stats['Degrees of Freedom'] > 0
