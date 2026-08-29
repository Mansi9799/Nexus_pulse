import duckdb

print("Sessionized Events:")
print(duckdb.query("DESCRIBE SELECT * FROM 'data/processed/sessionized_events.parquet'").df())

print("\nAssignments:")
print(duckdb.query("DESCRIBE SELECT * FROM 'data/raw/assignments.parquet'").df())
