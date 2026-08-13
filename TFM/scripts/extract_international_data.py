"""
Extracción de indicadores turísticos internacionales y clima faltante.

Fuentes:
1. Eurostat API — pernoctaciones mensuales (Grecia, Italia, Croacia, Portugal)
2. World Bank API — llegadas e ingresos turísticos (Turquía, Egipto, México, EAU, etc.)
3. Open-Meteo Archive API — clima para destinos que fallaron en la primera extracción

Todas las APIs son gratuitas y no requieren API key.

Ejecución:
    cd /d D:\\Master\\TrabajoFinalUCM\\TFM
    python scripts/extract_international_data.py
    python scripts/extract_international_data.py --help
"""

import argparse
import hashlib
import json
import logging
import operator
import sqlite3
import sys
import time
import uuid
from datetime import datetime
from functools import reduce
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# Asegurar imports del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("extract_international")

# ---------------------------------------------------------------------------
# Constantes Eurostat
# ---------------------------------------------------------------------------

EUROSTAT_BASE_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/tour_occ_nim"
)

# Mapeo de código Eurostat (geo) a destinos del proyecto
EUROSTAT_PAIS_A_DESTINOS = {
    "EL": ["Rodas", "Santorini", "Creta"],           # Grecia
    "IT": ["Sicilia", "Cerdeña", "Costa Amalfitana"],  # Italia
    "HR": ["Split"],                                    # Croacia
    "PT": ["Algarve"],                                  # Portugal
    "ES": ["Mallorca", "Tenerife", "Ibiza", "Costa del Sol", "Barcelona"],  # España backup
}

# ---------------------------------------------------------------------------
# Constantes World Bank
# ---------------------------------------------------------------------------

WORLD_BANK_BASE_URL = "https://api.worldbank.org/v2/country"

WORLD_BANK_INDICADORES = {
    "ST.INT.ARVL": "llegadas_internacionales_anual",
    "ST.INT.RCPT.CD": "ingresos_turismo_anual",
    "ST.INT.XPND.CD": "gasto_turismo_anual",
}

# Mapeo de código World Bank (ISO3) a destinos del proyecto
WORLD_BANK_PAIS_A_DESTINOS = {
    "TUR": ["Antalya"],
    "EGY": ["Hurghada"],
    "MEX": ["Cancún", "Riviera Maya"],
    "DOM": ["Punta Cana"],
    "ARE": ["Dubái"],
    "MDV": ["Maldivas"],
    "IDN": ["Bali"],
    "THA": ["Phuket"],
    "MAR": ["Marrakech"],
    "CPV": ["Cabo Verde"],
    "TUN": ["Túnez"],
}

# Patrones de estacionalidad para distribuir datos anuales a mensuales
# Valores normalizados (suman 1.0) — pico verano para Mediterráneo, pico invierno para tropicales
ESTACIONALIDAD_MEDITERRANEO = np.array([
    0.04, 0.04, 0.06, 0.08, 0.10, 0.14, 0.16, 0.16, 0.10, 0.06, 0.04, 0.02
])
ESTACIONALIDAD_TROPICAL = np.array([
    0.12, 0.11, 0.10, 0.07, 0.05, 0.04, 0.05, 0.06, 0.07, 0.09, 0.11, 0.13
])

# Destinos tropicales (pico invierno)
DESTINOS_TROPICALES = {
    "Punta Cana", "Cancún", "Riviera Maya", "Dubái",
    "Maldivas", "Bali", "Phuket", "Cabo Verde",
}

# ---------------------------------------------------------------------------
# Coordenadas de los 39 destinos (mismas que extract_climate_data.py)
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
# Configuración Open-Meteo (re-extracción clima)
# ---------------------------------------------------------------------------

OPEN_METEO_API_URL = "https://archive-api.open-meteo.com/v1/archive"
FECHA_INICIO_CLIMA = "2022-01-01"
FECHA_FIN_CLIMA = "2025-06-30"


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def generar_id(destino: str, fuente: str, tipo: str, anio: int, mes: int) -> str:
    """Genera un ID determinista basado en los campos clave."""
    clave = f"{destino}|{fuente}|{tipo}|{anio}|{mes}"
    return hashlib.md5(clave.encode()).hexdigest()[:32]


def crear_tabla_indicadores(conn: sqlite3.Connection) -> None:
    """Crea la tabla indicadores_destino si no existe."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS indicadores_destino (
            id_indicador TEXT PRIMARY KEY,
            destino_nombre TEXT NOT NULL,
            fuente TEXT NOT NULL,
            tipo_indicador TEXT NOT NULL,
            valor REAL NOT NULL,
            anio INTEGER NOT NULL,
            mes INTEGER,
            fecha_extraccion TEXT
        )
    """)
    conn.commit()


def crear_tabla_clima(conn: sqlite3.Connection) -> None:
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


# ===========================================================================
# PARTE 1: Eurostat API
# ===========================================================================

def extraer_eurostat(conn: sqlite3.Connection) -> dict:
    """
    Extrae pernoctaciones mensuales de Eurostat para países con destinos
    internacionales del proyecto.

    Retorna dict con estadísticas: {insertados, duplicados, errores, destinos_cubiertos}
    """
    stats = {"insertados": 0, "duplicados": 0, "errores": 0, "destinos_cubiertos": set()}

    logger.info("=" * 50)
    logger.info("EUROSTAT — Pernoctaciones mensuales por país")
    logger.info("=" * 50)

    for geo_code, destinos in EUROSTAT_PAIS_A_DESTINOS.items():
        logger.info(f"Consultando Eurostat: geo={geo_code} → {destinos}")

        params = {
            "format": "JSON",
            "lang": "EN",
            "freq": "M",
            "unit": "NR",
            "nace_r2": "I551",
            "geo": geo_code,
        }

        try:
            resp = requests.get(EUROSTAT_BASE_URL, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.Timeout:
            logger.error(f"  Timeout para geo={geo_code}")
            stats["errores"] += 1
            time.sleep(1.0)
            continue
        except requests.exceptions.HTTPError as e:
            logger.error(f"  Error HTTP para geo={geo_code}: {e}")
            stats["errores"] += 1
            time.sleep(1.0)
            continue
        except (requests.RequestException, json.JSONDecodeError) as e:
            logger.error(f"  Error para geo={geo_code}: {e}")
            stats["errores"] += 1
            time.sleep(1.0)
            continue

        # Parsear respuesta JSON de Eurostat (multidimensional)
        # Estructura: data["value"] = {flat_idx: valor}
        # Dimensions: freq x c_resid x unit x nace_r2 x geo x time
        # Time format: "YYYY-MM" (e.g., "2022-01")
        valores = data.get("value", {})
        dims = data.get("dimension", {})
        sizes = data.get("size", [])
        dim_ids = data.get("id", [])

        if not valores or not dims:
            logger.warning(f"  Sin datos para geo={geo_code}")
            stats["errores"] += 1
            time.sleep(1.0)
            continue

        # Get time dimension index
        time_dim_idx = dims.get("time", {}).get("category", {}).get("index", {})
        # Get c_resid index — we want TOTAL (all tourists)
        c_resid_idx = dims.get("c_resid", {}).get("category", {}).get("index", {})
        total_pos = c_resid_idx.get("TOTAL", c_resid_idx.get("FOR", 0))

        registros_pais = 0
        for time_label, time_pos in time_dim_idx.items():
            # Parsear "2022-01" → anio=2022, mes=1
            try:
                parts = time_label.split("-")
                if len(parts) == 2:
                    anio = int(parts[0])
                    mes = int(parts[1])
                elif "M" in time_label:
                    parts = time_label.split("M")
                    anio = int(parts[0])
                    mes = int(parts[1])
                else:
                    continue
            except (ValueError, IndexError):
                continue

            # Filtrar últimos 3 años
            if anio < 2022 or anio > 2025:
                continue

            # Calculate flat index: [freq=0, c_resid=total_pos, unit=0, nace_r2=0, geo=0, time=time_pos]
            positions = [0, total_pos, 0, 0, 0, time_pos]
            flat_idx = 0
            for i, pos in enumerate(positions):
                remaining = sizes[i+1:] if i+1 < len(sizes) else [1]
                stride = reduce(operator.mul, remaining, 1)
                flat_idx += pos * stride

            valor = valores.get(str(flat_idx))
            if valor is None:
                continue

            # Distribuir equitativamente entre destinos del país
            valor_por_destino = float(valor) / len(destinos)

            for destino in destinos:
                id_ind = generar_id(destino, "eurostat", "pernoctaciones_pais_mensual", anio, mes)
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO indicadores_destino
                        (id_indicador, destino_nombre, fuente, tipo_indicador,
                         valor, anio, mes, fecha_extraccion)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        id_ind, destino, "eurostat", "pernoctaciones_pais_mensual",
                        round(valor_por_destino, 2), anio, mes,
                        datetime.now().isoformat()
                    ))
                    if conn.total_changes:
                        stats["insertados"] += 1
                        stats["destinos_cubiertos"].add(destino)
                        registros_pais += 1
                except sqlite3.IntegrityError:
                    stats["duplicados"] += 1

        conn.commit()
        logger.info(f"  → {registros_pais} registros insertados para {geo_code}")

        # Pausa 1s entre llamadas a Eurostat
        time.sleep(1.0)

    return stats


# ===========================================================================
# PARTE 2: World Bank API
# ===========================================================================

def extraer_world_bank(conn: sqlite3.Connection) -> dict:
    """
    Extrae indicadores turísticos anuales del World Bank para países
    con destinos fuera de Europa.

    Retorna dict con estadísticas: {insertados, duplicados, errores, destinos_cubiertos}
    """
    stats = {"insertados": 0, "duplicados": 0, "errores": 0, "destinos_cubiertos": set()}

    logger.info("")
    logger.info("=" * 50)
    logger.info("WORLD BANK — Indicadores turísticos anuales")
    logger.info("=" * 50)

    for pais_code, destinos in WORLD_BANK_PAIS_A_DESTINOS.items():
        for wb_indicator, tipo_indicador in WORLD_BANK_INDICADORES.items():
            logger.info(f"  {pais_code} / {wb_indicator} → {destinos}")

            url = f"{WORLD_BANK_BASE_URL}/{pais_code}/indicator/{wb_indicator}"
            params = {
                "format": "json",
                "per_page": 100,
                "date": "2019:2024",
            }

            try:
                resp = requests.get(url, params=params, timeout=30)
                resp.raise_for_status()
                payload = resp.json()
            except requests.exceptions.Timeout:
                logger.error(f"    Timeout: {pais_code}/{wb_indicator}")
                stats["errores"] += 1
                time.sleep(0.5)
                continue
            except requests.exceptions.HTTPError as e:
                logger.error(f"    Error HTTP: {pais_code}/{wb_indicator}: {e}")
                stats["errores"] += 1
                time.sleep(0.5)
                continue
            except (requests.RequestException, json.JSONDecodeError) as e:
                logger.error(f"    Error: {pais_code}/{wb_indicator}: {e}")
                stats["errores"] += 1
                time.sleep(0.5)
                continue

            # World Bank devuelve: [{page info}, [{indicator, country, date, value}, ...]]
            if not isinstance(payload, list) or len(payload) < 2:
                logger.warning(f"    Respuesta inesperada para {pais_code}/{wb_indicator}")
                stats["errores"] += 1
                time.sleep(0.5)
                continue

            datos = payload[1]
            if not datos:
                logger.info(f"    Sin datos para {pais_code}/{wb_indicator}")
                time.sleep(0.5)
                continue

            for entry in datos:
                valor = entry.get("value")
                date_str = entry.get("date")

                if valor is None or date_str is None:
                    continue

                try:
                    anio = int(date_str)
                except (ValueError, TypeError):
                    continue

                # Determinar patrón de estacionalidad para distribución mensual
                es_tropical = any(d in DESTINOS_TROPICALES for d in destinos)
                estacionalidad = ESTACIONALIDAD_TROPICAL if es_tropical else ESTACIONALIDAD_MEDITERRANEO

                # Distribuir valor anual a 12 meses según estacionalidad
                for mes in range(1, 13):
                    valor_mensual = float(valor) * estacionalidad[mes - 1]
                    valor_por_destino = valor_mensual / len(destinos)

                    for destino in destinos:
                        id_ind = generar_id(destino, "world_bank", tipo_indicador, anio, mes)
                        try:
                            conn.execute("""
                                INSERT OR IGNORE INTO indicadores_destino
                                (id_indicador, destino_nombre, fuente, tipo_indicador,
                                 valor, anio, mes, fecha_extraccion)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                id_ind, destino, "world_bank", tipo_indicador,
                                round(valor_por_destino, 2), anio, mes,
                                datetime.now().isoformat()
                            ))
                            stats["insertados"] += 1
                            stats["destinos_cubiertos"].add(destino)
                        except sqlite3.IntegrityError:
                            stats["duplicados"] += 1

            conn.commit()

            # Pausa 0.5s entre llamadas a World Bank
            time.sleep(0.5)

    return stats


# ===========================================================================
# PARTE 3: Re-extracción clima Open-Meteo
# ===========================================================================

def obtener_destinos_clima_faltantes(conn: sqlite3.Connection) -> list[str]:
    """
    Identifica destinos que NO tienen datos en clima_destinos (de los 39 esperados).
    """
    cursor = conn.execute("SELECT DISTINCT destino_nombre FROM clima_destinos")
    existentes = {row[0] for row in cursor.fetchall()}
    esperados = set(DESTINOS_COORDS.keys())
    faltantes = esperados - existentes
    return sorted(faltantes)


def extraer_clima_destino(destino: str, lat: float, lon: float) -> list[dict]:
    """
    Extrae datos climáticos diarios de Open-Meteo y los agrega a mensual con pandas.
    Misma lógica que extract_climate_data.py.
    """
    registros = []

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": FECHA_INICIO_CLIMA,
        "end_date": FECHA_FIN_CLIMA,
        "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min,precipitation_sum,sunshine_duration",
        "timezone": "auto",
    }

    try:
        resp = requests.get(OPEN_METEO_API_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        logger.error(f"  [ERROR] {destino}: {e}")
        return registros

    if "daily" not in data:
        logger.warning(f"  [WARN] {destino}: sin datos diarios en respuesta")
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


def reextraer_clima_faltante(conn: sqlite3.Connection) -> dict:
    """
    Re-intenta la extracción de clima para destinos que fallaron la primera vez.

    Retorna dict con estadísticas: {insertados, duplicados, errores, destinos_cubiertos}
    """
    stats = {"insertados": 0, "duplicados": 0, "errores": 0, "destinos_cubiertos": set()}

    logger.info("")
    logger.info("=" * 50)
    logger.info("OPEN-METEO — Re-extracción clima faltante")
    logger.info("=" * 50)

    faltantes = obtener_destinos_clima_faltantes(conn)

    if not faltantes:
        logger.info("  Todos los 39 destinos ya tienen datos de clima. Sin re-extracción necesaria.")
        return stats

    logger.info(f"  Destinos sin clima: {len(faltantes)} de {len(DESTINOS_COORDS)}")
    for d in faltantes:
        logger.info(f"    - {d}")

    for idx, destino in enumerate(faltantes, 1):
        coords = DESTINOS_COORDS.get(destino)
        if not coords:
            logger.warning(f"  {destino}: coordenadas no encontradas, saltando")
            stats["errores"] += 1
            continue

        lat, lon = coords
        logger.info(f"  [{idx}/{len(faltantes)}] {destino} ({lat}, {lon})...")

        try:
            registros = extraer_clima_destino(destino, lat, lon)
        except Exception as e:
            logger.error(f"  [ERROR] Excepción inesperada para {destino}: {e}")
            stats["errores"] += 1
            continue

        insertados = 0
        for reg in registros:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO clima_destinos
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
                stats["duplicados"] += 1

        conn.commit()
        stats["insertados"] += insertados
        if insertados > 0:
            stats["destinos_cubiertos"].add(destino)
            logger.info(f"    → {insertados} registros insertados")
        else:
            logger.warning(f"    → Sin datos obtenidos")
            stats["errores"] += 1

        # Pausa 0.5s entre llamadas a Open-Meteo
        time.sleep(0.5)

    return stats


# ===========================================================================
# MAIN
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Extracción de indicadores turísticos internacionales y clima faltante"
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
        logger.error(f"Directorio no encontrado: {db_path.parent}")
        sys.exit(1)

    print("=" * 70)
    print("EXTRACCIÓN DE INDICADORES TURÍSTICOS INTERNACIONALES")
    print("=" * 70)
    print(f"Base de datos: {db_path}")
    print(f"Fuentes: Eurostat, World Bank, Open-Meteo (clima faltante)")
    print(f"Eurostat — países: {list(EUROSTAT_PAIS_A_DESTINOS.keys())}")
    print(f"World Bank — países: {list(WORLD_BANK_PAIS_A_DESTINOS.keys())}")
    print(f"Clima — destinos totales: {len(DESTINOS_COORDS)}")
    print()

    conn = sqlite3.connect(str(db_path))
    crear_tabla_indicadores(conn)
    crear_tabla_clima(conn)

    # -----------------------------------------------------------------------
    # PARTE 1: Eurostat
    # -----------------------------------------------------------------------
    print(f"\n{'─' * 70}")
    print("PARTE 1: EUROSTAT — Pernoctaciones mensuales")
    print(f"{'─' * 70}")

    try:
        stats_eurostat = extraer_eurostat(conn)
    except Exception as e:
        logger.error(f"Error crítico en Eurostat: {e}")
        stats_eurostat = {"insertados": 0, "duplicados": 0, "errores": 1, "destinos_cubiertos": set()}

    print(f"  ✓ Eurostat: {stats_eurostat['insertados']} insertados, "
          f"{stats_eurostat['duplicados']} duplicados, "
          f"{stats_eurostat['errores']} errores")

    # -----------------------------------------------------------------------
    # PARTE 2: World Bank
    # -----------------------------------------------------------------------
    print(f"\n{'─' * 70}")
    print("PARTE 2: WORLD BANK — Llegadas e ingresos turísticos")
    print(f"{'─' * 70}")

    try:
        stats_wb = extraer_world_bank(conn)
    except Exception as e:
        logger.error(f"Error crítico en World Bank: {e}")
        stats_wb = {"insertados": 0, "duplicados": 0, "errores": 1, "destinos_cubiertos": set()}

    print(f"  ✓ World Bank: {stats_wb['insertados']} insertados, "
          f"{stats_wb['duplicados']} duplicados, "
          f"{stats_wb['errores']} errores")

    # -----------------------------------------------------------------------
    # PARTE 3: Re-extracción clima
    # -----------------------------------------------------------------------
    print(f"\n{'─' * 70}")
    print("PARTE 3: OPEN-METEO — Re-extracción clima faltante")
    print(f"{'─' * 70}")

    try:
        stats_clima = reextraer_clima_faltante(conn)
    except Exception as e:
        logger.error(f"Error crítico en Open-Meteo: {e}")
        stats_clima = {"insertados": 0, "duplicados": 0, "errores": 1, "destinos_cubiertos": set()}

    print(f"  ✓ Open-Meteo: {stats_clima['insertados']} insertados, "
          f"{stats_clima['duplicados']} duplicados, "
          f"{stats_clima['errores']} errores")

    conn.close()

    # -----------------------------------------------------------------------
    # Resumen final
    # -----------------------------------------------------------------------
    total_insertados = (
        stats_eurostat["insertados"] + stats_wb["insertados"] + stats_clima["insertados"]
    )
    total_errores = (
        stats_eurostat["errores"] + stats_wb["errores"] + stats_clima["errores"]
    )
    todos_destinos = (
        stats_eurostat["destinos_cubiertos"]
        | stats_wb["destinos_cubiertos"]
        | stats_clima["destinos_cubiertos"]
    )

    print()
    print("=" * 70)
    print("RESUMEN FINAL")
    print("=" * 70)
    print(f"✓ Total insertados: {total_insertados} registros")
    print(f"  - Eurostat (pernoctaciones): {stats_eurostat['insertados']}")
    print(f"  - World Bank (llegadas/ingresos): {stats_wb['insertados']}")
    print(f"  - Open-Meteo (clima faltante): {stats_clima['insertados']}")
    print(f"  Destinos cubiertos: {len(todos_destinos)}")
    if total_errores > 0:
        print(f"⚠ Errores totales: {total_errores}")
    if total_insertados == 0:
        print()
        print("⚠ No se obtuvieron datos. Posibles causas:")
        print("  - Eurostat puede estar en mantenimiento (timeout 60s)")
        print("  - World Bank puede no tener datos recientes")
        print("  - Reintentar más tarde")
    print("=" * 70)


if __name__ == "__main__":
    main()
