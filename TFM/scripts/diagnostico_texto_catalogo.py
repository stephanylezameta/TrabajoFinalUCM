import sqlite3

conn = sqlite3.connect("data/tui_recomendador.db")

# Los items que dominan el top en las 3 consultas
ids_dominantes = ["EXP_103936", "EXP_103995", "EXP_103958", "EXP_104159", "EXP_105516"]

for eid in ids_dominantes:
    row = conn.execute(
        "SELECT activity_name, destination, category FROM experiencias WHERE experience_id = ?",
        (eid,)
    ).fetchone()
    print(f"{eid}: {row}")

print("\n--- Muestra aleatoria de 10 items cualquiera, para comparar ---")
rows = conn.execute(
    "SELECT experience_id, activity_name, destination, category FROM experiencias ORDER BY RANDOM() LIMIT 10"
).fetchall()
for r in rows:
    print(r)

conn.close()