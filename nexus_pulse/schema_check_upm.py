import duckdb

print("User post metrics:")
print(duckdb.query("DESCRIBE SELECT * FROM 'data/processed/user_post_metrics.parquet'").df())
