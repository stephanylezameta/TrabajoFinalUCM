"""
Carga los precios reales de paquetes de TUI y, para los destinos sin dato
real, estima un precio de paquete usando la razon tipica entre precio de
actividad suelta y precio de paquete completo (calculada con los destinos
que SI tienen dato real) -- nunca un numero inventado sin base.

Uso:
    cd TFM
    python scripts/cargar_precios_reales.py
"""
import csv
import sqlite3
import statistics
from pathlib import Path

DB_PATH = "data/tui_recomendador.db"
CSV_PATH = "data/precio_real_por_destino.csv"


def main():
    if not Path(CSV_PATH).exists():
        print(f"ERROR: no se encontro {CSV_PATH}.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS paquetes_reales_tui")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS paquetes_reales_tui (
            destino_nombre TEXT PRIMARY KEY,
            precio_persona REAL NOT NULL,
            n_paquetes INTEGER,
            es_real INTEGER NOT NULL,
            fuente TEXT
        )
    """)
    conn.execute("DELETE FROM paquetes_reales_tui")

    # 1) Cargar los reales
    precios_reales = {}
    with open(CSV_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            precios_reales[row["destino"]] = {
                "precio": float(row["precio_mediano_persona"]),
                "n": int(row["n_paquetes"]),
            }
            conn.execute(
                "INSERT INTO paquetes_reales_tui VALUES (?, ?, ?, 1, ?)",
                (row["destino"], float(row["precio_mediano_persona"]),
                 int(row["n_paquetes"]), "TUI real (recoleccion manual verificada)"),
            )

    # 2) Precio mediano de ACTIVIDAD (item) por destino, desde experiencias
    destinos_todos = [r[0] for r in conn.execute(
        "SELECT DISTINCT destination FROM experiencias"
    ).fetchall()]

    def mediana_item(destino):
        precios = [r[0] for r in conn.execute(
            "SELECT price_eur FROM experiencias WHERE destination = ? AND price_eur IS NOT NULL",
            (destino,),
        ).fetchall()]
        return statistics.median(precios) if precios else None

    # 3) Razon tipica paquete/actividad, calculada SOLO con destinos reales
    razones = []
    for destino, info in precios_reales.items():
        m_item = mediana_item(destino)
        if m_item and m_item > 0:
            razones.append(info["precio"] / m_item)

    if not razones:
        print("ERROR: no se pudo calcular ninguna razon (sin datos de actividades).")
        conn.commit()
        conn.close()
        return

    razon_global = statistics.median(razones)
    print(f"Razon tipica paquete/actividad (mediana de {len(razones)} destinos reales): {razon_global:.2f}")

    # 4) Estimar para los que faltan
    faltantes = [d for d in destinos_todos if d not in precios_reales]
    estimados = 0
    for destino in faltantes:
        m_item = mediana_item(destino)
        if m_item is None:
            continue
        precio_estimado = round(m_item * razon_global, 0)
        conn.execute(
            "INSERT INTO paquetes_reales_tui VALUES (?, ?, NULL, 0, ?)",
            (destino, precio_estimado,
             f"Estimado: mediana de actividad x razon tipica ({razon_global:.2f})"),
        )
        estimados += 1

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM paquetes_reales_tui").fetchone()[0]
    reales = conn.execute("SELECT COUNT(*) FROM paquetes_reales_tui WHERE es_real=1").fetchone()[0]
    conn.close()
    print(f"Cargados: {reales} reales + {estimados} estimados = {total} destinos con precio de referencia.")


if __name__ == "__main__":
    main()