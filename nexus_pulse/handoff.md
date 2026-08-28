# NexusPulse Handoff Document

This document summarizes the progress made so far on the NexusPulse (Distributed Product Experimentation, Causal Variance Reduction & Marketplace Analytics Platform) project. It is intended to serve as a checkpoint to easily resume work.

## 1. Accomplished So Far

### Phase 1: Repository Scaffold & Data Generation
- **Repository Structure**: Established the full Python package layout (`src/data_gen`, `src/etl`, `src/analytics`, `src/stats`, `src/api`, and `tests/`) along with `data/raw/` and `data/processed/` directories.
- **Environment**: Created a production-grade `requirements.txt` with pinned dependencies (PySpark, DuckDB, Pandas, PyArrow, FastAPI, Streamlit, etc.) and a comprehensive `.gitignore`.
- **Synthetic Data Generator**: Implemented a highly optimized, vectorized generator (`src/data_gen/generator.py`) using `numpy` and `pandas`.
  - Simulates a two-sided marketplace.
  - Generates `users.parquet` (with gamma-distributed baseline spend and categorical tiers).
  - Generates `assignments.parquet` (with a `--inject-srm` toggle for 52.5/47.5 splits to test Sample Ratio Mismatch).
  - Generates `events.parquet` (simulating realistic Poisson-distributed session lengths, funnel progression from `page_view` -> `search` -> `add_to_cart` -> `checkout`, and a +4.5% treatment lift on revenue).
- **Execution**: Successfully ran and verified the generator locally. It generated 50,000 users and ~160,000 events in ~1.5 seconds. Minor bugs (argparse formatting and DatetimeIndex handling) were identified and resolved.

### Phase 2: PySpark ETL Pipeline
- **ETL Script**: Implemented `src/etl/pyspark_pipeline.py`.
- **Sessionization**: Uses PySpark window functions and `lag` to sessionize clickstream events based on a 30-minute inactivity threshold.
- **Aggregation**: Aggregates raw events into user-level metrics: `post_exp_spend`, `total_sessions`, `total_events`, and `converted` (checkout flag).
- **Output**: Saves the aggregated metrics to `data/processed/user_post_metrics.parquet`.
- **Execution Status**: **Blocked locally**. Attempted to run the PySpark pipeline, but execution failed because **Java is not installed** in the local Windows environment, which is a prerequisite for PySpark.

## 2. Current State of the Workspace
All code is located in the `nexus_pulse/` directory. Raw generated data is currently available in `nexus_pulse/data/raw/`.

## 3. Immediate Next Steps
When resuming work, choose one of the following paths to resolve the ETL roadblock and proceed to Phase 3:
1. **Option A (Keep PySpark)**: Install Java (and set `JAVA_HOME`) on the local machine to allow PySpark to run and verify the ETL pipeline.
2. **Option B (Rewrite ETL)**: Rewrite the ETL pipeline using **DuckDB** or **Polars**. This will completely bypass the JVM overhead and execute natively and extremely fast in the current environment.
3. **Option C (Skip Verification)**: Assume the PySpark ETL works as written and move directly into Phase 3 (Analytics, Causal Variance Reduction (CUPED), and the FastAPI/Streamlit components).
