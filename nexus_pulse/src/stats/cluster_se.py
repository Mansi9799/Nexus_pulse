import os
import pandas as pd
import numpy as np
import statsmodels.formula.api as smf

class ClusterRobustInference:
    def fit_and_compare(self, df: pd.DataFrame, outcome_col="post_exp_spend_cuped", treatment_col="is_treatment", cluster_col="user_tier"):
        # The is_treatment col might be boolean, statsmodels will treat True/False as 1/0 but just to be safe
        df = df.copy()
        if df[treatment_col].dtype == bool:
            df[treatment_col] = df[treatment_col].astype(int)
            
        formula = f"{outcome_col} ~ {treatment_col}"
        
        # Fit Naive OLS
        naive_model = smf.ols(formula, data=df).fit()
        
        naive_beta = naive_model.params[treatment_col]
        naive_se = naive_model.bse[treatment_col]
        naive_tstat = naive_model.tvalues[treatment_col]
        naive_pval = naive_model.pvalues[treatment_col]
        naive_ci = naive_model.conf_int().loc[treatment_col]
        
        # Fit Huber-White Clustered OLS
        cluster_model = smf.ols(formula, data=df).fit(cov_type='cluster', cov_kwds={'groups': df[cluster_col]})
        
        cluster_beta = cluster_model.params[treatment_col]
        cluster_se = cluster_model.bse[treatment_col]
        cluster_tstat = cluster_model.tvalues[treatment_col]
        cluster_pval = cluster_model.pvalues[treatment_col]
        cluster_ci = cluster_model.conf_int().loc[treatment_col]
        
        se_inflation = cluster_se / naive_se if naive_se != 0 else np.nan
        
        dof = cluster_model.df_resid
        
        results = {
            "Naive OLS": {
                "Treatment Effect (Beta)": naive_beta,
                "Standard Error": naive_se,
                "t-statistic": naive_tstat,
                "p-value": naive_pval,
                "95% CI Lower": naive_ci[0],
                "95% CI Upper": naive_ci[1],
                "SE Inflation Ratio": 1.0,
                "Degrees of Freedom": naive_model.df_resid
            },
            "Huber-White Clustered": {
                "Treatment Effect (Beta)": cluster_beta,
                "Standard Error": cluster_se,
                "t-statistic": cluster_tstat,
                "p-value": cluster_pval,
                "95% CI Lower": cluster_ci[0],
                "95% CI Upper": cluster_ci[1],
                "SE Inflation Ratio": se_inflation,
                "Degrees of Freedom": dof
            }
        }
        
        return pd.DataFrame(results).T

if __name__ == "__main__":
    # Define paths relative to the current file
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cuped_path = os.path.join(base_dir, "data", "processed", "cuped_metrics.parquet")
    mart_path = os.path.join(base_dir, "data", "processed", "experiment_mart.parquet")
    
    # Load data
    if os.path.exists(cuped_path):
        df = pd.read_parquet(cuped_path)
        print("Loaded cuped_metrics.parquet")
    elif os.path.exists(mart_path):
        df = pd.read_parquet(mart_path)
        print("Loaded experiment_mart.parquet")
    else:
        raise FileNotFoundError(f"Could not find {cuped_path} or {mart_path}")
    
    # Check for the correct outcome column
    outcome_col = "post_exp_spend_cuped" if "post_exp_spend_cuped" in df.columns else "post_exp_spend"
    
    # Handle missing values in cluster_col for statsmodels
    if "user_tier" in df.columns:
        df["user_tier"] = df["user_tier"].fillna("Unknown")
    
    inferencer = ClusterRobustInference()
    comparison_df = inferencer.fit_and_compare(
        df, 
        outcome_col=outcome_col, 
        treatment_col="is_treatment", 
        cluster_col="user_tier"
    )
    
    print("\n--- Cluster-Robust Inference Comparison ---")
    print(comparison_df.to_string())
