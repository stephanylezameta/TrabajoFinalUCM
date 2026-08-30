import sqlite3

conn = sqlite3.connect("data/tui_recomendador.db")

cur = conn.execute("PRAGMA table_info(conectividad_destinos)")
print("Columnas de conectividad_destinos:")
for col in cur.fetchall():
    print(f"  {col[1]} ({col[2]})")

print()
cur = conn.execute("SELECT * FROM conectividad_destinos LIMIT 3")
cols = [d[0] for d in cur.description]
print("Primeras 3 filas:")
for row in cur.fetchall():
    print(dict(zip(cols, row)))

conn.close()