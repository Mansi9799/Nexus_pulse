# NexusPulse

Distributed Product Experimentation, Causal Variance Reduction & Marketplace Analytics Platform.

## Architecture & Structure
- `data/`: Contains raw and processed data pipelines.
- `src/`: Core Python source code for data generation, ETL, analytics, statistics, and API.
- `tests/`: Automated test suites.

## Setup
Install dependencies:
```bash
pip install -r requirements.txt
```

## Data Generation
You can run the synthetic data generator as follows:
```bash
python src/data_gen/generator.py --num-users 50000 --active-users 15000
```
