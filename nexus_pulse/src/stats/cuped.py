import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
import scipy.stats as stats

def calculate_cuped_adjusted_metric(df: pd.DataFrame, metric_col: str, covariate_col: str, adjusted_metric_name: str = None) -> pd.DataFrame:
    df_copy = df.copy()
    if adjusted_metric_name is None:
        adjusted_metric_name = f"{metric_col}_cuped"
        
    covariance = df_copy[metric_col].cov(df_copy[covariate_col])
    variance = df_copy[covariate_col].var()
    
    if variance == 0:
        theta = 0
    else:
        theta = covariance / variance
        
    covariate_mean = df_copy[covariate_col].mean()
    df_copy[adjusted_metric_name] = df_copy[metric_col] - theta * (df_copy[covariate_col] - covariate_mean)
    
    return df_copy

def perform_ttest(df: pd.DataFrame, metric_col: str, variant_col: str = 'variant', control_name: str = 'control', treatment_name: str = 'treatment'):
    control_data = df[df[variant_col] == control_name][metric_col].dropna()
    treatment_data = df[df[variant_col] == treatment_name][metric_col].dropna()
    
    t_stat, p_value, df_test = sm.stats.ttest_ind(treatment_data, control_data, usevar='unequal')
    
    mean_control = control_data.mean()
    mean_treatment = treatment_data.mean()
    diff = mean_treatment - mean_control
    lift = (diff / mean_control) * 100 if mean_control != 0 else 0
    
    return {
        'metric': metric_col,
        'control_mean': mean_control,
        'treatment_mean': mean_treatment,
        'absolute_diff': diff,
        'relative_lift_pct': lift,
        't_stat': t_stat,
        'p_value': p_value,
        'significant': p_value < 0.05
    }

def perform_ttest_clustered(df: pd.DataFrame, metric_col: str, variant_col: str = 'variant', cluster_col: str = 'user_tier'):
    df_copy = df.copy()
    df_copy['is_treatment'] = (df_copy[variant_col] == 'treatment').astype(int)
    
    model = smf.ols(f"{metric_col} ~ is_treatment", data=df_copy)
    results = model.fit(cov_type='cluster', cov_kwds={'groups': df_copy[cluster_col]})
    
    treatment_coef = results.params['is_treatment']
    p_value = results.pvalues['is_treatment']
    std_err = results.bse['is_treatment']
    
    control_mean = df_copy[df_copy['is_treatment'] == 0][metric_col].mean()
    treatment_mean = df_copy[df_copy['is_treatment'] == 1][metric_col].mean()
    lift = (treatment_coef / control_mean) * 100 if control_mean != 0 else 0
    
    return {
        'metric': metric_col,
        'control_mean': control_mean,
        'treatment_mean': treatment_mean,
        'absolute_diff': treatment_coef,
        'relative_lift_pct': lift,
        'std_err': std_err,
        'p_value': p_value,
        'significant': p_value < 0.05
    }

def check_srm(df: pd.DataFrame, variant_col: str = 'variant', expected_proportions: dict = None):
    if expected_proportions is None:
        expected_proportions = {'control': 0.5, 'treatment': 0.5}
        
    counts = df[variant_col].value_counts()
    observed = [counts.get('control', 0), counts.get('treatment', 0)]
    total = sum(observed)
    expected = [total * expected_proportions['control'], total * expected_proportions['treatment']]
    
    chi2_stat, p_value = stats.chisquare(f_obs=observed, f_exp=expected)
    
    return {
        'chi2_stat': chi2_stat,
        'p_value': p_value,
        'srm_detected': p_value < 0.01,
        'observed_control': observed[0],
        'observed_treatment': observed[1]
    }

class CUPEDAnalyzer:
    def __init__(self):
        pass

    def fit_transform(self, df, target='post_exp_spend', covariate='pre_exp_spend_14d'):
        cov_val = df[target].cov(df[covariate])
        var_x = df[covariate].var()
        
        if var_x == 0:
            theta = 0
        else:
            theta = cov_val / var_x
            
        mean_x = df[covariate].mean()
        y_cuped = df[target] - theta * (df[covariate] - mean_x)
        
        df = df.copy()
        df[f'{target}_cuped'] = y_cuped
        
        var_y = df[target].var()
        var_y_cuped = y_cuped.var()
        delta_var = (1 - var_y_cuped / var_y) * 100 if var_y != 0 else 0
        
        metadata = {
            'theta': theta,
            'variance_reduction_percentage': delta_var,
            'target': target,
            'covariate': covariate
        }
        
        return df, metadata

    def run_ttest(self, df, metric_col='post_exp_spend_cuped', alpha=0.05):
        control_data = df[df['variant'] == 'control'][metric_col].dropna()
        treatment_data = df[df['variant'] == 'treatment'][metric_col].dropna()
        
        t_stat, p_value = stats.ttest_ind(treatment_data, control_data, equal_var=False)
        
        mean_control = control_data.mean()
        mean_treatment = treatment_data.mean()
        abs_lift = mean_treatment - mean_control
        rel_lift_pct = (abs_lift / mean_control) * 100 if mean_control != 0 else 0
        
        return {
            'control_mean': mean_control,
            'treatment_mean': mean_treatment,
            'absolute_lift': abs_lift,
            'relative_lift_pct': rel_lift_pct,
            't_stat': t_stat,
            'p_value': p_value,
            'significant': p_value < alpha
        }

if __name__ == '__main__':
    import os
    
    # Read experiment_mart.parquet
    mart_path = 'data/processed/experiment_mart.parquet'
    
    # Assume script run from nexus_pulse root, fallback to relative 
    file_path = mart_path
    if not os.path.exists(file_path):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        file_path = os.path.join(base_dir, mart_path)
        
    df = pd.read_parquet(file_path)
    
    analyzer = CUPEDAnalyzer()
    
    # Fit transform
    df_cuped, meta = analyzer.fit_transform(df, target='post_exp_spend', covariate='pre_exp_spend_14d')
    
    # run t-test for raw
    res_raw = analyzer.run_ttest(df_cuped, metric_col='post_exp_spend')
    
    # run t-test for cuped
    res_cuped = analyzer.run_ttest(df_cuped, metric_col='post_exp_spend_cuped')
    
    print(f"Optimal Theta: {meta['theta']:.4f}")
    print(f"Variance Reduction: {meta['variance_reduction_percentage']:.2f}%\n")
    
    # Print comparison table
    print(f"{'-'*100}")
    print(f"{'Metric':<25} | {'Control Mean':<15} | {'Treatment Mean':<15} | {'Lift %':<10} | {'p-value':<10} | {'Significance'}")
    print(f"{'-'*100}")
    print(f"{'Raw Spend':<25} | {res_raw['control_mean']:<15.4f} | {res_raw['treatment_mean']:<15.4f} | {res_raw['relative_lift_pct']:<10.2f} | {res_raw['p_value']:<10.4f} | {res_raw['significant']}")
    print(f"{'CUPED Spend':<25} | {res_cuped['control_mean']:<15.4f} | {res_cuped['treatment_mean']:<15.4f} | {res_cuped['relative_lift_pct']:<10.2f} | {res_cuped['p_value']:<10.4f} | {res_cuped['significant']}")
    print(f"{'-'*100}\n")
    
    # Save the CUPED-enriched dataset
    out_path = 'data/processed/cuped_metrics.parquet'
    if not os.path.exists('data/processed'):
        out_path = os.path.join(base_dir, 'data/processed/cuped_metrics.parquet')
    
    df_cuped.to_parquet(out_path, engine='pyarrow', compression='snappy')
    print(f"Saved CUPED-enriched dataset to {out_path}")
