import sys, sqlite3
sys.stdout.reconfigure(encoding="utf-8")

db_path = "data/portal.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

query = "SELECT name FROM sqlite_master WHERE type='table'"
c.execute(query)
tables = [r[0] for r in c.fetchall()]
print("Tables found:", tables)

for t in tables:
    c.execute("SELECT COUNT(*) FROM " + t)
    count = c.fetchone()[0]
    print("  " + t + ": " + str(count) + " rows")

conn.close()
print("\nDB verification done.")
