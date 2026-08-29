import duckdb
import pandas as pd

# Connect to in-memory DuckDB
con = duckdb.connect()

# Read and fetch a sample
query = "SELECT * FROM read_parquet('data/processed/sessionized_events.parquet') LIMIT 10"
df = con.execute(query).fetchdf()

# Display the dataframe nicely
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
print(df)
