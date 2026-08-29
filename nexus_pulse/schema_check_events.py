import duckdb

print("Events:")
print(duckdb.query("DESCRIBE SELECT * FROM 'data/raw/events.parquet'").df())
