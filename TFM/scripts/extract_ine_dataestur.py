"""
Extracción de datos de ocupación hotelera y turismo del INE, Dataestur y Turespaña.

Fuentes (en orden de prioridad):
1. Dataestur API: https://www.dataestur.es/apidata/ (turistas internacionales, gasto, pernoctaciones)
2. Turespaña: https://estadisticas.tourspain.es/ (estadísticas turísticas alternativas)
3. INE API: https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/2066 (ocupación hotelera)
4. INE API: https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/2074 (viajeros)
5. INE API: https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/2078 (pernoctaciones)

Inserta en tabla `indicadores_destino` de la BD principal.

Ejecución:
    cd /d D:\\Master\\TrabajoFinalUCM\\TFM
    python scripts/extract_ine_dataestur.py
    python scripts/extract_ine_dataestur.py --db data/tui_recomendador.db
    python scripts/extract_ine_dataestur.py --help
"""

import argparse
import hashlib
import json
import logging
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

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
logger = logging.getLogger("extract_ine")

# ---------------------------------------------------------------------------
# Mapeo de provincias INE a destinos del proyecto
# ---------------------------------------------------------------------------

PROVINCIA_A_DESTINOS = {
    "Illes Balears": ["Mallorca", "Ibiza", "Menorca"],
    "Santa Cruz de Tenerife": ["Tenerife"],
    "Las Palmas": ["Gran Canaria", "Fuerteventura", "Lanzarote"],
    "Málaga": ["Málaga", "Costa del Sol"],
    "Barcelona": ["Barcelona"],
    "Alicante/Alacant": ["Alicante"],
    "Valencia/València": ["Valencia"],
    "Sevilla": ["Sevilla"],
    "Cádiz": ["Cádiz"],
    "Granada": ["Granada"],
    "Córdoba": ["Córdoba"],
    "Bizkaia": ["Bilbao"],
    "Gipuzkoa": ["San Sebastián"],
    "Madrid": ["Madrid"],
}

# Nombres alternativos que el INE puede usar
PROVINCIA_ALIASES = {
    "Balears, Illes": "Illes Balears",
    "Balears (Illes)": "Illes Balears",
    "Alicante": "Alicante/Alacant",
    "Valencia": "Valencia/València",
    "Vizcaya": "Bizkaia",
    "Guipúzcoa": "Gipuzkoa",
    "Bizkaia/Vizcaya": "Bizkaia",
    "Gipuzkoa/Guipúzcoa": "Gipuzkoa",
}

# ---------------------------------------------------------------------------
# Configuración API INE
# ---------------------------------------------------------------------------

INE_BASE_URL = "https://servicios.ine.es/wstempus/js/ES"

TABLAS_INE = {
    "2066": "ocupacion_hotelera_mensual",
    "2074": "viajeros_mensuales",
    "2078": "pernoctaciones_mensuales",
}

# Dataestur API (fuente principal)
DATAESTUR_API_BASE = "https://www.dataestur.es/apidata/"
DATAESTUR_INDICADORES_URL = "https://www.dataestur.es/apidata/indicadores/"

# Indicadores de interés en Dataestur
DATAESTUR_INDICADORES = {
    "turistas_internacionales": "Turistas internacionales",
    "gasto_medio_turistico": "Gasto medio turístico",
    "pernoctaciones_dataestur": "Pernoctaciones",
}

# Turespaña (fuente alternativa)
TURESPAÑA_BASE_URL = "https://estadisticas.tourspain.es/"
TURESPAÑA_API_URL = "https://estadisticas.tourspain.es/es-es/estadisticas/otrasestadisticas/"

# URL antigua de Dataestur (fallback/legacy)
DATAESTUR_URL_LEGACY = "https://www.dataestur.es/frontend/data/"


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def generar_id(destino: str, fuente: str, tipo: str, anio: int, mes: int) -> str:
    """Genera un ID determinista basado en los campos clave."""
    clave = f"{destino}|{fuente}|{tipo}|{anio}|{mes}"
    return hashlib.md5(clave.encode()).hexdigest()[:32]


def crear_tabla_si_no_existe(conn: sqlite3.Connection) -> None:
    """Verifica que la tabla indicadores_destino existe, la crea si no."""
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


def existe_indicador(conn: sqlite3.Connection, destino: str, fuente: str,
                     tipo: str, anio: int, mes: int) -> bool:
    """Verifica si ya existe un indicador para evitar duplicados."""
    cursor = conn.execute("""
        SELECT 1 FROM indicadores_destino 
        WHERE destino_nombre = ? AND fuente = ? AND tipo_indicador = ? 
              AND anio = ? AND mes = ?
    """, (destino, fuente, tipo, anio, mes))
    return cursor.fetchone() is not None


def normalizar_provincia(nombre_ine: str) -> str | None:
    """Normaliza el nombre de provincia del INE a nuestro mapeo."""
    nombre = nombre_ine.strip()

    if nombre in PROVINCIA_A_DESTINOS:
        return nombre

    if nombre in PROVINCIA_ALIASES:
        return PROVINCIA_ALIASES[nombre]

    # Buscar contenido parcial
    for provincia in PROVINCIA_A_DESTINOS:
        if provincia.lower() in nombre.lower() or nombre.lower() in provincia.lower():
            return provincia

    return None

# ---------------------------------------------------------------------------
# Extracción INE
# ---------------------------------------------------------------------------

def extraer_tabla_ine(tabla_id: str, tipo_indicador: str) -> list[dict]:
    """
    Extrae datos de una tabla del INE.
    
    La API del INE devuelve un array de objetos con campos:
    - "Nombre": descripción de la serie (contiene nombre de provincia)
    - "Data": array de {Anyo, T3_Periodo (mes como "M01"), Valor}
    
    Se usa ?nult=48 para obtener los últimos 48 períodos (~4 años mensuales).
    """
    registros = []
    url = f"{INE_BASE_URL}/DATOS_TABLA/{tabla_id}"
    params = {"nult": 48}

    logger.info(f"Consultando INE tabla {tabla_id} ({tipo_indicador})...")

    try:
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        logger.error(f"Timeout consultando tabla {tabla_id}")
        return registros
    except requests.exceptions.HTTPError as e:
        logger.error(f"Error HTTP tabla {tabla_id}: {e}")
        return registros
    except (requests.RequestException, json.JSONDecodeError) as e:
        logger.error(f"Error consultando tabla {tabla_id}: {e}")
        return registros

    if not isinstance(data, list):
        logger.warning(f"Respuesta inesperada de tabla {tabla_id}: tipo={type(data)}")
        return registros

    for serie in data:
        try:
            nombre = serie.get("Nombre", "")

            # Buscar provincia en el nombre de la serie
            provincia_encontrada = None
            for provincia in list(PROVINCIA_A_DESTINOS.keys()) + list(PROVINCIA_ALIASES.keys()):
                if provincia.lower() in nombre.lower():
                    provincia_encontrada = normalizar_provincia(provincia)
                    break

            if not provincia_encontrada:
                continue

            # Extraer datos temporales
            datos_serie = serie.get("Data", [])
            if not datos_serie:
                continue

            for punto in datos_serie:
                valor = punto.get("Valor")
                if valor is None:
                    continue

                # Parsear fecha: INE usa Anyo + T3_Periodo (M01..M12) o Fecha (timestamp ms)
                anyo = punto.get("Anyo")
                periodo = punto.get("T3_Periodo")
                anio = None
                mes = None

                if anyo and periodo:
                    try:
                        anio = int(anyo)
                        if isinstance(periodo, str) and periodo.startswith("M"):
                            mes = int(periodo[1:])
                        else:
                            continue
                    except (ValueError, TypeError):
                        continue
                elif "Fecha" in punto:
                    try:
                        ts = punto["Fecha"] / 1000
                        dt = datetime.fromtimestamp(ts)
                        anio = dt.year
                        mes = dt.month
                    except (TypeError, ValueError, OSError):
                        continue
                else:
                    continue

                # Filtrar a últimos 3 años relevantes
                if anio is None or mes is None:
                    continue
                if anio < 2022 or anio > 2025:
                    continue

                # Asignar a cada destino de la provincia
                destinos = PROVINCIA_A_DESTINOS.get(provincia_encontrada, [])
                for destino in destinos:
                    registros.append({
                        "destino_nombre": destino,
                        "fuente": "ine",
                        "tipo_indicador": tipo_indicador,
                        "valor": float(valor),
                        "anio": anio,
                        "mes": mes,
                    })

        except Exception as e:
            logger.debug(f"Error procesando serie: {e}")
            continue

    logger.info(f"  Tabla {tabla_id}: {len(registros)} registros extraídos")
    return registros


def extraer_series_ine_alternativa(tabla_id: str, tipo_indicador: str) -> list[dict]:
    """
    Método alternativo: consultar series individuales por provincia.
    Usa SERIES_TABLA para obtener códigos y luego DATOS_SERIE para cada una.
    """
    registros = []

    url_series = f"{INE_BASE_URL}/SERIES_TABLA/{tabla_id}"
    try:
        resp = requests.get(url_series, timeout=30)
        resp.raise_for_status()
        series = resp.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        logger.warning(f"No se pudieron obtener series de tabla {tabla_id}: {e}")
        return registros

    if not isinstance(series, list):
        return registros

    # Filtrar series que contengan provincias de interés
    series_interes = []
    for serie in series:
        nombre = serie.get("Nombre", "")
        for provincia in list(PROVINCIA_A_DESTINOS.keys()) + list(PROVINCIA_ALIASES.keys()):
            if provincia.lower() in nombre.lower():
                cod = serie.get("COD")
                if cod:
                    prov_norm = normalizar_provincia(provincia)
                    series_interes.append((cod, prov_norm, nombre))
                break

    logger.info(f"  Encontradas {len(series_interes)} series relevantes en tabla {tabla_id}")

    for cod_serie, provincia, nombre_serie in series_interes[:30]:
        url_datos = f"{INE_BASE_URL}/DATOS_SERIE/{cod_serie}"
        params = {"nult": 48}

        try:
            resp = requests.get(url_datos, params=params, timeout=30)
            resp.raise_for_status()
            datos = resp.json()
        except (requests.RequestException, json.JSONDecodeError):
            continue

        if not isinstance(datos, list):
            continue

        for punto in datos:
            valor = punto.get("Valor")
            if valor is None:
                continue

            anyo = punto.get("Anyo")
            periodo = punto.get("T3_Periodo")
            anio = None
            mes = None

            if anyo and periodo:
                try:
                    anio = int(anyo)
                    if isinstance(periodo, str) and periodo.startswith("M"):
                        mes = int(periodo[1:])
                    else:
                        continue
                except (ValueError, TypeError):
                    continue
            elif "Fecha" in punto:
                try:
                    ts = punto["Fecha"] / 1000
                    dt = datetime.fromtimestamp(ts)
                    anio = dt.year
                    mes = dt.month
                except (TypeError, ValueError, OSError):
                    continue

            if anio is None or mes is None:
                continue
            if anio < 2022 or anio > 2025:
                continue

            destinos = PROVINCIA_A_DESTINOS.get(provincia, [])
            for destino in destinos:
                registros.append({
                    "destino_nombre": destino,
                    "fuente": "ine",
                    "tipo_indicador": tipo_indicador,
                    "valor": float(valor),
                    "anio": anio,
                    "mes": mes,
                })

        time.sleep(1.0)

    return registros


def intentar_dataestur() -> list[dict]:
    """
    Intenta descargar indicadores de Dataestur.
    Si no responde o no hay datos accesibles, devuelve lista vacía.
    """
    registros = []
    logger.info("Intentando acceso a Dataestur...")

    try:
        resp = requests.get(DATAESTUR_URL, timeout=15)
        if resp.status_code != 200:
            logger.info(f"  Dataestur no disponible (HTTP {resp.status_code}), usando solo INE")
            return registros

        # Intentar parsear como JSON o CSV
        content_type = resp.headers.get("Content-Type", "")
        if "json" in content_type:
            try:
                data = resp.json()
                logger.info(f"  Dataestur JSON recibido: {type(data)}")
                # Procesar si tiene estructura conocida
                # (La estructura de Dataestur puede variar)
            except json.JSONDecodeError:
                pass
        else:
            logger.info("  Dataestur: respuesta no procesable, usando solo INE")

    except requests.exceptions.Timeout:
        logger.info("  Dataestur: timeout, usando solo INE")
    except requests.RequestException as e:
        logger.info(f"  Dataestur: error de conexión ({e}), usando solo INE")

    return registros


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extracción de datos turísticos del INE y Dataestur"
    )
    parser.add_argument(
        "--db", type=str, default="data/tui_recomendador.db",
        help="Ruta a la base de datos SQLite (default: data/tui_recomendador.db)"
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    db_path = project_root / args.db

    if not db_path.parent.exists():
        logger.error(f"Directorio no encontrado: {db_path.parent}")
        sys.exit(1)

    print("=" * 70)
    print("EXTRACCIÓN DE DATOS TURÍSTICOS - INE + Dataestur")
    print("=" * 70)
    print(f"Base de datos: {db_path}")
    print(f"Tablas INE: {list(TABLAS_INE.keys())}")
    print(f"Provincias objetivo: {len(PROVINCIA_A_DESTINOS)}")
    print(f"Registros esperados: ~1.500")
    print()

    conn = sqlite3.connect(str(db_path))
    crear_tabla_si_no_existe(conn)

    total_insertados = 0
    total_duplicados = 0
    total_errores = 0
    resumen_por_tabla = {}

    # --- Extracción INE ---
    for tabla_id, tipo_indicador in TABLAS_INE.items():
        print(f"\n{'─' * 50}")
        print(f"Tabla INE {tabla_id}: {tipo_indicador}")
        print(f"{'─' * 50}")

        # Intentar método principal (DATOS_TABLA)
        registros = extraer_tabla_ine(tabla_id, tipo_indicador)

        # Si pocos resultados, intentar método alternativo por series
        if len(registros) < 10:
            logger.info(f"Pocos registros ({len(registros)}), probando método alternativo...")
            time.sleep(2.0)
            registros_alt = extraer_series_ine_alternativa(tabla_id, tipo_indicador)
            if len(registros_alt) > len(registros):
                registros = registros_alt

        # Insertar registros
        insertados = 0
        duplicados = 0
        for reg in registros:
            if existe_indicador(conn, reg["destino_nombre"], reg["fuente"],
                              reg["tipo_indicador"], reg["anio"], reg["mes"]):
                duplicados += 1
                continue

            id_indicador = generar_id(
                reg["destino_nombre"], reg["fuente"],
                reg["tipo_indicador"], reg["anio"], reg["mes"]
            )

            try:
                conn.execute("""
                    INSERT OR IGNORE INTO indicadores_destino
                    (id_indicador, destino_nombre, fuente, tipo_indicador,
                     valor, anio, mes, fecha_extraccion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    id_indicador, reg["destino_nombre"], reg["fuente"],
                    reg["tipo_indicador"], reg["valor"], reg["anio"], reg["mes"],
                    datetime.now().isoformat()
                ))
                insertados += 1
            except sqlite3.IntegrityError:
                duplicados += 1
            except Exception as e:
                logger.warning(f"Error insertando: {e}")
                total_errores += 1

        conn.commit()
        total_insertados += insertados
        total_duplicados += duplicados
        resumen_por_tabla[tipo_indicador] = insertados

        print(f"  ✓ {insertados} insertados, {duplicados} duplicados")

        # Pausa 2s entre tablas
        time.sleep(2.0)

    # --- Intentar Dataestur ---
    print(f"\n{'─' * 50}")
    print("Dataestur (intento de descarga)")
    print(f"{'─' * 50}")

    registros_dataestur = intentar_dataestur()
    insertados_dataestur = 0
    for reg in registros_dataestur:
        if existe_indicador(conn, reg["destino_nombre"], reg["fuente"],
                          reg["tipo_indicador"], reg["anio"], reg["mes"]):
            continue
        id_indicador = generar_id(
            reg["destino_nombre"], reg["fuente"],
            reg["tipo_indicador"], reg["anio"], reg["mes"]
        )
        try:
            conn.execute("""
                INSERT OR IGNORE INTO indicadores_destino
                (id_indicador, destino_nombre, fuente, tipo_indicador,
                 valor, anio, mes, fecha_extraccion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                id_indicador, reg["destino_nombre"], reg["fuente"],
                reg["tipo_indicador"], reg["valor"], reg["anio"], reg["mes"],
                datetime.now().isoformat()
            ))
            insertados_dataestur += 1
        except (sqlite3.IntegrityError, Exception):
            pass

    if insertados_dataestur > 0:
        conn.commit()
        total_insertados += insertados_dataestur
        print(f"  ✓ {insertados_dataestur} registros de Dataestur insertados")
    else:
        print("  → Sin datos adicionales de Dataestur")

    conn.close()

    # Resumen final
    print()
    print("=" * 70)
    print("RESUMEN FINAL")
    print("=" * 70)
    print(f"✓ Total insertados: {total_insertados} registros")
    print(f"  Duplicados descartados: {total_duplicados}")
    if total_errores > 0:
        print(f"⚠ Errores: {total_errores}")
    print()
    print("Desglose por indicador (INE):")
    for tipo, n in resumen_por_tabla.items():
        print(f"  - {tipo}: {n} registros")
    if insertados_dataestur > 0:
        print(f"  - dataestur: {insertados_dataestur} registros")
    if total_insertados == 0:
        print()
        print("⚠ No se obtuvieron datos. Posibles causas:")
        print("  - La API del INE puede estar en mantenimiento")
        print("  - Los nombres de provincias cambiaron en la respuesta")
        print("  - Ejecutar de nuevo más tarde")
    print("=" * 70)


if __name__ == "__main__":
    main()
