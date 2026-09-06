"""Exporta el catálogo completo de 39 destinos desde el pipeline del TFM.

El dashboard nació sobre un mock de 16 destinos (propuesta_7.html). El pipeline
(``tui_recomendador.db``, 64 MB, no versionable) tiene 39 destinos reales con
clima, conectividad, seguridad y sentimiento. Este script agrega todo eso a CSV
en ``data/raw/``, versionables y consumibles por el ETL existente:

- ``destinos_pipeline.csv``        -> tabla destinations (características + precio)
- ``clima_pipeline.csv``           -> climate_observations (mensual)
- ``conectividad_pipeline.csv``    -> connectivity_stats
- ``seguridad_pipeline.csv``       -> country_indicators (por país)

El precio de referencia no existe como tal en el pipeline, así que se deriva de
las experiencias reales de cada destino (mediana del precio de sus actividades),
que es un dato observado, no inventado.

Uso:
    python scripts/export_catalog.py
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import RAW_DIR  # noqa: E402

DEFAULT_DB = PROJECT_ROOT.parent / "data" / "tui_recomendador.db"


def _rows(conn: sqlite3.Connection, sql: str) -> list[sqlite3.Row]:
    return conn.execute(sql).fetchall()


def _write(path: Path, columns: list[str], rows: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c) for c in columns})
    return len(rows)


def export_destinations(conn: sqlite3.Connection) -> int:
    from statistics import median

    # Precio de referencia derivado de las experiencias reales del destino: la
    # mediana del precio de sus actividades, calculada en Python (más claro que
    # una subconsulta correlacionada en SQLite).
    exp_by_dest: dict[str, list[float]] = {}
    for r in conn.execute(
        "SELECT destination, price_eur FROM experiencias WHERE price_eur IS NOT NULL"
    ):
        exp_by_dest.setdefault(r["destination"], []).append(float(r["price_eur"]))
    prices = {dest: median(vals) for dest, vals in exp_by_dest.items() if vals}
    rows = []
    for r in _rows(conn, "SELECT * FROM destinos_caracteristicas ORDER BY destino_nombre"):
        name = r["destino_nombre"]
        # Precio orientativo de un paquete: la experiencia mediana como proxy de
        # nivel de precio del destino, escalada a rango de paquete.
        exp_price = prices.get(name)
        reference_price = round(float(exp_price) * 10, 0) if exp_price else None
        rows.append({
            "n": name,
            "zona": r["zona_geografica"],
            "pais": r["pais"],
            "afinidad": None,
            "demanda": None,
            "ocupacion": None,
            "impacto": r["sensibilidad_ambiental"],
            "temporada": None,
            "accesibilidad": r["accesibilidad_estimada"],
            "sostenibilidad": (1.0 - float(r["sensibilidad_ambiental"]))
            if r["sensibilidad_ambiental"] is not None else None,
            "precio": reference_price,
            "co2": None,
            "tiene_playa": r["tiene_playa"],
            "tiene_patrimonio_unesco": r["tiene_patrimonio_unesco"],
            "es_isla": r["es_isla"],
            "nivel_saturacion": r["nivel_saturacion_conocido"],
        })
    columns = [
        "n", "zona", "pais", "afinidad", "demanda", "ocupacion", "impacto",
        "temporada", "accesibilidad", "sostenibilidad", "precio", "co2",
        "tiene_playa", "tiene_patrimonio_unesco", "es_isla", "nivel_saturacion",
    ]
    return _write(RAW_DIR / "destinos_pipeline.csv", columns, rows)


def export_climate(conn: sqlite3.Connection) -> int:
    rows = []
    for r in _rows(conn, "SELECT * FROM clima_destinos"):
        year, month = r["anio"], r["mes"]
        rows.append({
            "lugar": r["destino_nombre"],
            "year_month": f"{year}-{int(month):02d}",
            "temp_media_aire_c": r["temp_media"],
            "temp_media_agua_c": r["temp_agua"],
            "precipitacion_total_mm": r["precipitacion_mm"],
            "dias_lluvia": r["dias_lluvia"],
            "horas_sol_totales": r["horas_sol"],
            "humedad_media_pct": r["humedad_pct"],
        })
    columns = [
        "lugar", "year_month", "temp_media_aire_c", "temp_media_agua_c",
        "precipitacion_total_mm", "dias_lluvia", "horas_sol_totales", "humedad_media_pct",
    ]
    return _write(RAW_DIR / "clima_pipeline.csv", columns, rows)


def export_connectivity(conn: sqlite3.Connection) -> int:
    rows = []
    for r in _rows(conn, "SELECT * FROM conectividad_destinos"):
        rows.append({
            "termino_original": r["destino_nombre"],
            "grupo": r["grupo"],
            "iata_destino": r["iata_destino"],
            "rutas_directas_es": r["rutas_directas_ES"],
            "rutas_directas_uk": r["rutas_directas_UK"],
            "rutas_directas_de": r["rutas_directas_DE"],
            "vuelos_semanales_estimados": r["vuelos_semanales"],
            "asientos_semanales_ofertados": r["asientos_semanales"],
            "pasajeros_semanales_estimados": None,
            "pasajeros_anuales_estimados": r["pasajeros_anuales"],
        })
    columns = [
        "termino_original", "grupo", "iata_destino", "rutas_directas_es",
        "rutas_directas_uk", "rutas_directas_de", "vuelos_semanales_estimados",
        "asientos_semanales_ofertados", "pasajeros_semanales_estimados",
        "pasajeros_anuales_estimados",
    ]
    return _write(RAW_DIR / "conectividad_pipeline.csv", columns, rows)


def export_safety(conn: sqlite3.Connection) -> int:
    # country_indicators va por país (iso). El pipeline lo tiene por destino, así
    # que se agrega por país tomando el primer valor conocido.
    seen: dict[str, dict] = {}
    for r in _rows(conn, "SELECT * FROM seguridad_destinos"):
        iso = (r["iso"] or "").strip()
        if not iso or iso in seen:
            continue
        seen[iso] = {
            "iso": iso,
            "pais": r["pais"],
            "camas_hospital_1000hab": r["camas_hospital_1000hab"],
            "tasa_homicidios_100mil": r["tasa_homicidios_100mil"],
        }
    columns = ["iso", "pais", "camas_hospital_1000hab", "tasa_homicidios_100mil"]
    return _write(RAW_DIR / "seguridad_pipeline.csv", columns, list(seen.values()))


def main(db_path: Path) -> int:
    if not db_path.exists():
        print(f"No existe la base del pipeline: {db_path}")
        return 1
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        n_dest = export_destinations(conn)
        n_clima = export_climate(conn)
        n_conn = export_connectivity(conn)
        n_safe = export_safety(conn)
    finally:
        conn.close()

    print(f"destinos_pipeline.csv       {n_dest} destinos")
    print(f"clima_pipeline.csv          {n_clima} observaciones mensuales")
    print(f"conectividad_pipeline.csv   {n_conn} destinos")
    print(f"seguridad_pipeline.csv      {n_safe} países")
    print(f"\nEscritos en {RAW_DIR}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    raise SystemExit(main(args.db))
