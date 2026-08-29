import duckdb

print("Users:")
print(duckdb.query("DESCRIBE SELECT * FROM 'data/raw/users.parquet'").df())
