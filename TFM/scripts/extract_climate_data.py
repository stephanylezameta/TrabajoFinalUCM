"""
Extracción de datos climáticos históricos desde Open-Meteo Archive API.

Obtiene temperatura media, máxima, mínima, precipitación y horas de sol
por mes y destino para el período 2022-01-01 a 2025-06-30.

API: https://archive-api.open-meteo.com/v1/archive (gratuita, sin API key)

Ejecución:
    cd /d D:\\Master\\TrabajoFinalUCM\\TFM
    python scripts/extract_climate_data.py
    python scripts/extract_climate_data.py --db data/tui_recomendador.db
    python scripts/extract_climate_data.py --help
"""

import argparse
import json
import sqlite3
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

# Asegurar imports del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Coordenadas de los destinos (lat, lon)
# ---------------------------------------------------------------------------

DESTINOS_COORDS = {
    # España peninsular e islas
    "Mallorca": (39.5696, 2.6502),
    "Tenerife": (28.2916, -16.6291),
    "Ibiza": (38.9067, 1.4206),
    "Costa del Sol": (36.7213, -4.4214),
    "Barcelona": (41.3874, 2.1686),
    "Madrid": (40.4168, -3.7038),
    "Málaga": (36.7213, -4.4214),
    "Sevilla": (37.3891, -5.9845),
    "Valencia": (39.4699, -0.3763),
    "Gran Canaria": (27.9202, -15.5474),
    "Alicante": (38.3452, -0.4810),
    "Bilbao": (43.2630, -2.9350),
    "San Sebastián": (43.3183, -1.9812),
    "Córdoba": (37.8882, -4.7794),
    "Granada": (37.1773, -3.5986),
    "Cádiz": (36.5271, -6.2886),
    "Fuerteventura": (28.3587, -14.0538),
    "Lanzarote": (29.0469, -13.5900),
    "Menorca": (39.9496, 4.1104),
    # Internacional - Mediterráneo
    "Antalya": (36.8969, 30.7133),
    "Rodas": (36.4349, 28.2176),
    "Santorini": (36.3932, 25.4615),
    "Hurghada": (27.2579, 33.8116),
    "Split": (43.5081, 16.4402),
    "Creta": (35.2401, 24.4691),
    "Sicilia": (37.5994, 14.0154),
    "Cerdeña": (40.1209, 9.0129),
    "Costa Amalfitana": (40.6333, 14.6029),
    "Algarve": (37.0179, -7.9304),
    "Túnez": (36.8065, 10.1815),
    # Caribe y largo radio
    "Punta Cana": (18.5601, -68.3725),
    "Cancún": (21.1619, -86.8515),
    "Riviera Maya": (20.6296, -87.0739),
    "Dubái": (25.2048, 55.2708),
    "Maldivas": (3.2028, 73.2207),
    "Bali": (-8.3405, 115.0920),
    "Phuket": (7.8804, 98.3923),
    "Marrakech": (31.6295, -7.9811),
    "Cabo Verde": (14.9330, -23.5133),
}

# ---------------------------------------------------------------------------
# Configuración API
# ---------------------------------------------------------------------------

API_BASE_URL = "https://archive-api.open-meteo.com/v1/archive"
FECHA_INICIO = "2022-01-01"
FECHA_FIN = "2025-06-30"


# ---------------------------------------------------------------------------
# Funciones
# ---------------------------------------------------------------------------

def crear_tabla(conn: sqlite3.Connection) -> None:
    """Crea la tabla clima_destinos si no existe."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS clima_destinos (
            id TEXT PRIMARY KEY,
            destino_nombre TEXT NOT NULL,
            latitud REAL NOT NULL,
            longitud REAL NOT NULL,
            anio INTEGER NOT NULL,
            mes INTEGER NOT NULL,
            temp_media REAL,
            temp_max REAL,
            temp_min REAL,
            precipitacion_mm REAL,
            horas_sol REAL,
            fecha_extraccion TEXT NOT NULL,
            UNIQUE(destino_nombre, anio, mes)
        )
    """)
    conn.commit()


def existe_registro(conn: sqlite3.Connection, destino: str, anio: int, mes: int) -> bool:
    """Verifica si ya existe un registro para ese destino/año/mes."""
    cursor = conn.execute(
        "SELECT 1 FROM clima_destinos WHERE destino_nombre = ? AND anio = ? AND mes = ?",
        (destino, anio, mes)
    )
    return cursor.fetchone() is not None


def extraer_clima_destino(destino: str, lat: float, lon: float) -> list[dict]:
    """
    Extrae datos climáticos diarios de Open-Meteo y los agrega a mensual con pandas.
    Devuelve lista de dicts con los datos agregados por mes.
    """
    registros = []

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": FECHA_INICIO,
        "end_date": FECHA_FIN,
        "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min,precipitation_sum,sunshine_duration",
        "timezone": "auto",
    }

    try:
        resp = requests.get(API_BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"  [ERROR] {destino}: {e}")
        return registros

    if "daily" not in data:
        print(f"  [WARN] {destino}: sin datos diarios en respuesta")
        return registros

    daily = data["daily"]

    # Construir DataFrame con pandas para agregar a mensual
    df = pd.DataFrame({
        "fecha": pd.to_datetime(daily.get("time", [])),
        "temp_mean": daily.get("temperature_2m_mean", []),
        "temp_max": daily.get("temperature_2m_max", []),
        "temp_min": daily.get("temperature_2m_min", []),
        "precipitation": daily.get("precipitation_sum", []),
        "sunshine_s": daily.get("sunshine_duration", []),  # en segundos
    })

    if df.empty:
        return registros

    # Agregar por año-mes
    df["anio"] = df["fecha"].dt.year
    df["mes"] = df["fecha"].dt.month

    mensual = df.groupby(["anio", "mes"]).agg(
        temp_media=("temp_mean", "mean"),
        temp_max=("temp_max", "mean"),
        temp_min=("temp_min", "mean"),
        precipitacion_mm=("precipitation", "sum"),
        sunshine_total_s=("sunshine_s", "sum"),
    ).reset_index()

    for _, row in mensual.iterrows():
        # Convertir sunshine_duration de segundos a horas
        horas_sol = round(row["sunshine_total_s"] / 3600.0, 1) if pd.notna(row["sunshine_total_s"]) else None

        registros.append({
            "id": str(uuid.uuid4()),
            "destino_nombre": destino,
            "latitud": lat,
            "longitud": lon,
            "anio": int(row["anio"]),
            "mes": int(row["mes"]),
            "temp_media": round(row["temp_media"], 1) if pd.notna(row["temp_media"]) else None,
            "temp_max": round(row["temp_max"], 1) if pd.notna(row["temp_max"]) else None,
            "temp_min": round(row["temp_min"], 1) if pd.notna(row["temp_min"]) else None,
            "precipitacion_mm": round(row["precipitacion_mm"], 1) if pd.notna(row["precipitacion_mm"]) else None,
            "horas_sol": horas_sol,
            "fecha_extraccion": datetime.now().isoformat(),
        })

    return registros


def main():
    parser = argparse.ArgumentParser(
        description="Extracción de datos climáticos históricos desde Open-Meteo Archive API"
    )
    parser.add_argument(
        "--db", type=str, default="data/tui_recomendador.db",
        help="Ruta a la base de datos SQLite (default: data/tui_recomendador.db)"
    )
    args = parser.parse_args()

    # Resolver ruta relativa al proyecto
    project_root = Path(__file__).resolve().parent.parent
    db_path = project_root / args.db

    if not db_path.parent.exists():
        print(f"[ERROR] Directorio no encontrado: {db_path.parent}")
        sys.exit(1)

    print("=" * 70)
    print("EXTRACCIÓN DE DATOS CLIMÁTICOS - Open-Meteo Archive API")
    print("=" * 70)
    print(f"Base de datos: {db_path}")
    print(f"Período: {FECHA_INICIO} a {FECHA_FIN}")
    print(f"Destinos: {len(DESTINOS_COORDS)}")
    print(f"Registros esperados: ~{len(DESTINOS_COORDS)} × 42 meses = ~{len(DESTINOS_COORDS) * 42}")
    print()

    conn = sqlite3.connect(str(db_path))
    crear_tabla(conn)

    total_insertados = 0
    total_duplicados = 0
    total_errores = 0

    for idx, (destino, (lat, lon)) in enumerate(DESTINOS_COORDS.items(), 1):
        print(f"[{idx}/{len(DESTINOS_COORDS)}] {destino} ({lat}, {lon})...")

        try:
            registros = extraer_clima_destino(destino, lat, lon)
        except Exception as e:
            print(f"  [ERROR] Excepción inesperada: {e}")
            total_errores += 1
            continue

        insertados = 0
        duplicados = 0
        for reg in registros:
            if existe_registro(conn, reg["destino_nombre"], reg["anio"], reg["mes"]):
                duplicados += 1
                continue

            try:
                conn.execute("""
                    INSERT INTO clima_destinos 
                    (id, destino_nombre, latitud, longitud, anio, mes, temp_media, temp_max, 
                     temp_min, precipitacion_mm, horas_sol, fecha_extraccion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    reg["id"], reg["destino_nombre"], reg["latitud"], reg["longitud"],
                    reg["anio"], reg["mes"], reg["temp_media"], reg["temp_max"],
                    reg["temp_min"], reg["precipitacion_mm"], reg["horas_sol"],
                    reg["fecha_extraccion"]
                ))
                insertados += 1
            except sqlite3.IntegrityError:
                duplicados += 1

        conn.commit()
        total_insertados += insertados
        total_duplicados += duplicados

        if insertados > 0 or duplicados > 0:
            print(f"  -> {insertados} insertados, {duplicados} duplicados")
        else:
            print(f"  -> Sin datos obtenidos")
            total_errores += 1

        # Pausa 0.5s entre llamadas para no saturar la API
        time.sleep(0.5)

    conn.close()

    # Resumen final
    print()
    print("=" * 70)
    print("RESUMEN FINAL")
    print("=" * 70)
    print(f"✓ Total insertados: {total_insertados} registros en tabla clima_destinos")
    print(f"  Duplicados descartados: {total_duplicados}")
    print(f"  Destinos procesados: {len(DESTINOS_COORDS)}")
    if total_errores > 0:
        print(f"⚠ {total_errores} destinos con errores de extracción")
    print("=" * 70)


if __name__ == "__main__":
    main()
