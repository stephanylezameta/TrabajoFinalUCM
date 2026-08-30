import sqlite3

conn = sqlite3.connect("data/tui_recomendador.db")

destinos_exp = set(r[0] for r in conn.execute(
    "SELECT DISTINCT destination FROM experiencias"
).fetchall())

destinos_conect = set(r[0] for r in conn.execute(
    "SELECT DISTINCT destino_nombre FROM conectividad_destinos"
).fetchall())

conn.close()

print(f"Destinos en 'experiencias': {len(destinos_exp)}")
print(f"Destinos en 'conectividad_destinos': {len(destinos_conect)}")

interseccion = destinos_exp & destinos_conect
print(f"\nCoinciden EXACTO: {len(interseccion)}")

print("\n--- Ejemplos de experiencias.destination ---")
for d in sorted(destinos_exp)[:10]:
    print(f"  {d!r}")

print("\n--- Ejemplos de conectividad_destinos.destino_nombre ---")
for d in sorted(destinos_conect)[:10]:
    print(f"  {d!r}")