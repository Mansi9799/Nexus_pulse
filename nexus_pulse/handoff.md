# NexusPulse Handoff Document

This document summarizes the progress made on the NexusPulse (Distributed Product Experimentation, Causal Variance Reduction & Marketplace Analytics Platform) project.

## 1. Accomplished So Far

### Phase 1: Repository Scaffold & Data Generation
- **Repository Structure**: Established the full Python package layout (`src/data_gen`, `src/etl`, `src/analytics`, `src/stats`, `src/api`, and `tests/`) along with `data/raw/` and `data/processed/` directories.
- **Synthetic Data Generator**: The highly optimized generator (`src/data_gen/generator.py`) was fully calibrated.
  - Successfully simulated a two-sided marketplace for 50,000 total users (20,000 active).
  - Enforced a strong correlation ($\rho \approx 0.65 - 0.70$) between `pre_exp_spend_14d` and `post_exp_spend`.
  - Intentionally injected a clean **+6.0% treatment lift** on checkout spend to ensure CUPED statistics cross significance thresholds.
  - Generates `users.parquet`, `assignments.parquet`, and `events.parquet`.

### Phase 2: DuckDB ETL Pipeline
- **JVM Dependency Bypassed**: Completely replaced the original blocked PySpark pipeline with a highly optimized, native DuckDB architecture.
- **Sessionization (`src/etl/sessionizer.py`)**: Uses DuckDB window functions to compute inter-event time deltas. Applies a 30-minute inactivity threshold to generate unique `session_id` tags for all events, outputting to `sessionized_events.parquet`.
- **User Metrics (`src/etl/user_metric.py`)**: Aggregates the sessionized events and performs a `LEFT JOIN` against the original `users.parquet` to ensure all 50,000 users are represented in the dataset (Intention-To-Treat population). Outputs the final `user_post_metrics.parquet` with Snappy compression.
- **Current Stats**:
  - Total Users: 50,000
  - Total Post-Experiment Spend: ~$729,745
  - Overall Conversion Rate: 17.08%

### Phase 3: Analytics & Streamlit Dashboard
- **Funnel Analytics (`src/analytics/funnel.py`)**:
  - Developed a native DuckDB SQL Common Table Expression (CTE) to track user progression across a 4-stage funnel (`page_view` -> `search` -> `add_to_cart` -> `checkout`).
  - Computes stage-to-stage drop-off conversion rates, overall conversion per variant, and segmented conversion rates by `user_tier`.
  - Provides natively formatted Pandas tabular outputs for CLI testing and consumption.
- **Cohort Retention Analytics (`src/analytics/retention.py`)**:
  - Implemented cohort retention analysis using DuckDB CTEs to compute Day 1, Day 3, Day 7, and Day 14 retention percentages relative to assignment timestamps.
  - Segmented the retention matrix by `variant` ('control' vs 'treatment') and simulated `device_type` ('mobile', 'desktop', 'tablet').
  - Persists the processed results to `data/processed/cohort_retention.parquet` with Snappy compression for downstream usage.
- **Causal Inference Engine (`src/stats/cuped.py`)**:
  - Implemented the **CUPED** (Controlled Experiment Using Pre-Experiment Data) algorithm to heavily reduce the variance of the post-experiment spend metric (achieving ~27.5% variance reduction).
  - Implemented **Cluster-Robust Standard Errors** (Huber-White Sandwich Estimator) clustered by user tier to ensure rigorous hypothesis testing.
  - Added a Chi-Square test to automatically detect **Sample Ratio Mismatch (SRM)**.
- **Dashboard (`src/api/app.py`)**:
  - Built a real-time Streamlit web app powered directly by the parquet files.
  - **Tab 1**: Funnel Analytics displaying a 4-stage Plotly funnel chart.
  - **Tab 2**: CUPED & Causal Stats highlighting variance reduction, overlaid metric distributions, and standard vs. CUPED p-values.
  - **Tab 3**: Diagnostics & Robustness containing the SRM check and Cluster-Robust vs. Naive standard error comparisons.

### Phase 4: Master Analytical Mart
- **Unified Feature Store (`src/analytics/build_mart.py`)**:
  - Developed a highly optimized DuckDB ingestion script to unify `users.parquet`, `assignments.parquet`, and `user_post_metrics.parquet` into a single unified experiment feature store.
  - Successfully preserved the full Intention-To-Treat population of 50,000 users via robust LEFT JOINs and NULL coalescing (zero-activity users appropriately padded with zeros).
  - Designed engineered features including `spend_delta` (post vs pre experiment), `is_treatment` indicator, and `has_converted` flag.
  - Mocked the missing `device_type` user attribute efficiently using a deterministic SQL CASE statement to match downstream expectations.
  - Exported the clean, correctly typed table to `data/processed/experiment_mart.parquet` utilizing Snappy compression.
  - Included strict validation tests ensuring complete data fidelity across all 50,000 subjects with zero nulls on critical outcome metrics.

### Phase 5: Object-Oriented CUPED Refactor
- **CUPEDAnalyzer Class (`src/stats/cuped.py`)**:
  - Refactored the causal inference logic into a cohesive `CUPEDAnalyzer` class.
  - Implemented `fit_transform` to compute the optimal theta ($Cov(Y, X) / Var(X)$) and append the `post_exp_spend_cuped` metric, dynamically capturing variance reduction metadata (~27.54%).
  - Implemented `run_ttest` utilizing Welch's t-test (`equal_var=False`) to surface Mean, Lift %, and p-value metrics.
  - Added a self-contained execution runner that processes `experiment_mart.parquet`, outputs a side-by-side comparison table of raw vs. CUPED metrics, and saves the final enriched dataframe.
  - Exported the final dataset to `data/processed/cuped_metrics.parquet` utilizing PyArrow and Snappy compression.

### Phase 6: Cluster-Robust Standard Errors
- **ClusterRobustInference Class (`src/stats/cluster_se.py`)**:
  - Ingests `cuped_metrics.parquet`.
  - Implements Naive OLS and Huber-White Clustered Sandwich Estimator using `statsmodels`.
  - Clustered on `user_tier` to adjust for within-cluster correlation.
  - Outputs a detailed comparison table with Beta, Standard Error, t-stat, p-value, 95% CIs, SE Inflation Ratio, and Degrees of Freedom.

## 2. Current State of the Workspace
All code is functional and up-to-date in the `nexus_pulse/` directory. 
- **Raw Data**: `nexus_pulse/data/raw/`
- **Processed Data**: `nexus_pulse/data/processed/` (now featuring `experiment_mart.parquet` and the newly generated `cuped_metrics.parquet`)
- **Dashboard**: Run `streamlit run src/api/app.py` to view the UI.

## 3. Next Steps
All Phase 1, Phase 2, Phase 3, Phase 4, Phase 5, and Phase 6 requirements have been fully successfully implemented! Next steps could include:
1. Connecting the Dashboard directly to the unified `experiment_mart.parquet` to simplify backend queries.
2. Adding more complex covariates for CUPED (like user tier or categorical features).
3. Implementing more advanced causal models (e.g. Double Machine Learning) using the new engineered features.
4. Moving the data backend from local parquet to a cloud data warehouse (Snowflake / BigQuery).
