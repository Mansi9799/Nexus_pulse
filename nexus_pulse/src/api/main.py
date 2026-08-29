import os
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import time

from src.stats.cuped import check_srm, CUPEDAnalyzer
from src.stats.cluster_se import ClusterRobustInference
from src.analytics.funnel import calculate_funnel

app = FastAPI(title="NexusPulse API")

# 1. Build a production-grade FastAPI app with CORS middleware.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base Path definition
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MART_PATH = os.path.join(BASE_DIR, "data", "processed", "experiment_mart.parquet")

# 2. Define Pydantic v2 Models

class ExperimentEvalRequest(BaseModel):
    experiment_id: str = "EXP_CHECKOUT_V2"
    alpha: float = 0.05
    expected_control_ratio: float = 0.50
    cluster_col: str = "user_tier"
    metric_col: str = "post_exp_spend"
    covariate_col: str = "pre_exp_spend_14d"

class HealthResponse(BaseModel):
    status: str
    total_records: int
    service_uptime: str

class ExperimentEvalResponse(BaseModel):
    experiment_id: str
    srm_diagnostics: dict
    cuped_inference: dict
    clustered_inference: dict
    business_decision: str
    decision_rationale: str

class SRMDetector:
    @staticmethod
    def check(df: pd.DataFrame, expected_control_ratio: float) -> dict:
        expected_proportions = {
            'control': expected_control_ratio,
            'treatment': 1.0 - expected_control_ratio
        }
        return check_srm(df, variant_col='variant', expected_proportions=expected_proportions)


# Track start time for uptime
START_TIME = time.time()

# 3. Implement Endpoints

@app.get("/health", response_model=HealthResponse)
def health_check():
    """
    Checks if data/processed/experiment_mart.parquet exists and returns row counts.
    """
    if not os.path.exists(MART_PATH):
        raise HTTPException(status_code=503, detail="Data mart not found")
    
    try:
        # Load just the user_id column to get the row count quickly
        df = pd.read_parquet(MART_PATH, columns=['user_id'])
        total_records = len(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read data mart: {str(e)}")
        
    uptime_seconds = int(time.time() - START_TIME)
    
    return HealthResponse(
        status="healthy",
        total_records=total_records,
        service_uptime=f"{uptime_seconds}s"
    )

@app.post("/api/v1/experiment/evaluate", response_model=ExperimentEvalResponse)
def evaluate_experiment(req: ExperimentEvalRequest):
    """
    Evaluates the experiment results using SRM, CUPED, and Cluster-Robust Standard Errors.
    """
    if not os.path.exists(MART_PATH):
        raise HTTPException(status_code=500, detail="Data mart not found")
        
    try:
        df = pd.read_parquet(MART_PATH)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read data mart: {str(e)}")
    
    # Step 1: Runs SRM check via SRMDetector
    srm_diagnostics = SRMDetector.check(df, req.expected_control_ratio)
    
    if srm_diagnostics.get('srm_detected', False):
        return ExperimentEvalResponse(
            experiment_id=req.experiment_id,
            srm_diagnostics=srm_diagnostics,
            cuped_inference={},
            clustered_inference={},
            business_decision="INVALID_SRM",
            decision_rationale="Sample Ratio Mismatch detected. Experiment data is invalid and cannot be evaluated."
        )
        
    # Step 2: Executes CUPEDAnalyzer on target metric & covariate
    analyzer = CUPEDAnalyzer()
    
    # Handle missing column checks
    if req.metric_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Metric column '{req.metric_col}' not found in dataset.")
    if req.covariate_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Covariate column '{req.covariate_col}' not found in dataset.")
        
    df_cuped, meta = analyzer.fit_transform(df, target=req.metric_col, covariate=req.covariate_col)
    
    cuped_metric_name = f"{req.metric_col}_cuped"
    cuped_inference = analyzer.run_ttest(df_cuped, metric_col=cuped_metric_name, alpha=req.alpha)
    cuped_inference['metadata'] = meta  # Enrich with variance reduction metrics
    
    # Step 3: Runs ClusterRobustInference on the CUPED-adjusted metric clustered by req.cluster_col
    if req.cluster_col not in df_cuped.columns:
        raise HTTPException(status_code=400, detail=f"Cluster column '{req.cluster_col}' not found in dataset.")
        
    # Ensure no NaNs in cluster column for statsmodels
    df_cuped[req.cluster_col] = df_cuped[req.cluster_col].fillna("Unknown")
    
    inferencer = ClusterRobustInference()
    comparison_df = inferencer.fit_and_compare(
        df_cuped,
        outcome_col=cuped_metric_name,
        treatment_col="is_treatment",
        cluster_col=req.cluster_col
    )
    
    clustered_stats = comparison_df.loc["Huber-White Clustered"].to_dict()
    
    # Convert clustered_stats scalar types (e.g., numpy float/int) to native Python types for JSON serialization
    clustered_stats = {k: float(v) if pd.api.types.is_numeric_dtype(type(v)) else v for k, v in clustered_stats.items()}
    
    # Step 4: Decision Rule
    clustered_p_value = clustered_stats.get("p-value", 1.0)
    clustered_lift = clustered_stats.get("Treatment Effect (Beta)", 0.0)
    
    if pd.isna(clustered_p_value):
        decision = "REJECT"
        rationale = "Clustered p-value could not be computed (NaN)."
    elif clustered_p_value < req.alpha and clustered_lift > 0:
        decision = "ROLLOUT"
        rationale = f"Significant positive lift detected (p={clustered_p_value:.4f} < {req.alpha})."
    else:
        decision = "REJECT"
        rationale = f"No significant positive lift detected (p={clustered_p_value:.4f}, lift={clustered_lift:.4f})."
        
    return ExperimentEvalResponse(
        experiment_id=req.experiment_id,
        srm_diagnostics=srm_diagnostics,
        cuped_inference=cuped_inference,
        clustered_inference=clustered_stats,
        business_decision=decision,
        decision_rationale=rationale
    )


@app.get("/api/v1/analytics/funnel")
def get_funnel():
    """
    Queries data/processed/experiment_mart.parquet (or raw via duckdb) and returns 4-stage funnel conversion JSON.
    """
    orig_dir = os.getcwd()
    try:
        # Change directory so DuckDB inside calculate_funnel() can find 'data/raw/...'
        os.chdir(BASE_DIR)
        
        df = calculate_funnel()
        # Convert all numeric values to standard Python types for JSON serialization
        # df may contain int64 or float64 which FastAPI/Pydantic might struggle with natively if not defined explicitly
        json_friendly_df = df.astype(object).where(pd.notnull(df), None)
        return json_friendly_df.to_dict(orient="records")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Revert back to original working directory
        os.chdir(orig_dir)


# 4. Add a verification block under if __name__ == '__main__':
if __name__ == '__main__':
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
