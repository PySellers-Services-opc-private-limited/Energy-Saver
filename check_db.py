import sqlite3

# Backend DB (used by running server)
print("=== BACKEND DB (backend/energy_saver_ai.db) ===")
conn1 = sqlite3.connect("backend/energy_saver_ai.db")
c1 = conn1.cursor()
tables = c1.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"Tables: {[t[0] for t in tables]}")
for tbl in ["users", "tenants"]:
    try:
        cols = c1.execute(f"PRAGMA table_info({tbl})").fetchall()
        print(f"{tbl} columns: {[c[1] for c in cols]}")
        rows = c1.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()
        print(f"{tbl} rows: {rows[0]}")
    except Exception as e:
        print(f"{tbl}: {e}")
conn1.close()

print()
print("=== ROOT DB (energy_saver_ai.db) ===")
conn2 = sqlite3.connect("energy_saver_ai.db")
c2 = conn2.cursor()
tables = c2.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"Tables: {[t[0] for t in tables]}")
for tbl in ["users", "tenants"]:
    try:
        cols = c2.execute(f"PRAGMA table_info({tbl})").fetchall()
        print(f"{tbl} columns: {[c[1] for c in cols]}")
        rows = c2.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()
        print(f"{tbl} rows: {rows[0]}")
    except Exception as e:
        print(f"{tbl}: {e}")
conn2.close()
