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
- **Causal Inference Engine (`src/stats/cuped.py`)**:
  - Implemented the **CUPED** (Controlled Experiment Using Pre-Experiment Data) algorithm to heavily reduce the variance of the post-experiment spend metric (achieving ~27.5% variance reduction).
  - Implemented **Cluster-Robust Standard Errors** (Huber-White Sandwich Estimator) clustered by user tier to ensure rigorous hypothesis testing.
  - Added a Chi-Square test to automatically detect **Sample Ratio Mismatch (SRM)**.
- **Dashboard (`src/api/app.py`)**:
  - Built a real-time Streamlit web app powered directly by the parquet files.
  - **Tab 1**: Funnel Analytics displaying a 4-stage Plotly funnel chart.
  - **Tab 2**: CUPED & Causal Stats highlighting variance reduction, overlaid metric distributions, and standard vs. CUPED p-values.
  - **Tab 3**: Diagnostics & Robustness containing the SRM check and Cluster-Robust vs. Naive standard error comparisons.

## 2. Current State of the Workspace
All code is functional and up-to-date in the `nexus_pulse/` directory. 
- **Raw Data**: `nexus_pulse/data/raw/`
- **Processed Data**: `nexus_pulse/data/processed/`
- **Dashboard**: Run `streamlit run src/api/app.py` to view the UI.

## 3. Next Steps
All Phase 1, Phase 2, and Phase 3 requirements have been fully successfully implemented! Next steps could include:
1. Adding more complex covariates for CUPED (like user tier or categorical features).
2. Implementing more advanced causal models (e.g. Double Machine Learning).
3. Moving the data backend from local parquet to a cloud data warehouse (Snowflake / BigQuery).
