"""
Extracción de interés de búsqueda por destino turístico desde Google Trends.

Usa pytrends para extraer el interés mensual de los últimos 5 años como
proxy de demanda turística. Inserta en tabla `indicadores_destino`.

Categoría: 67 (Travel)
Geo: '' (mundial)
Agrupación: 5 destinos por consulta (máximo de pytrends)
Pausa: 65s entre grupos para evitar error 429

Ejecución:
    cd /d D:\\Master\\TrabajoFinalUCM\\TFM
    python scripts/extract_google_trends.py
    python scripts/extract_google_trends.py --db data/tui_recomendador.db
    python scripts/extract_google_trends.py --help
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
logger = logging.getLogger("extract_trends")

# ---------------------------------------------------------------------------
# Destinos y keywords para búsqueda
# ---------------------------------------------------------------------------

# keyword de búsqueda → nombre del destino en nuestra BD
DESTINOS_KEYWORDS = {
    "Mallorca vacaciones": "Mallorca",
    "Tenerife holidays": "Tenerife",
    "Ibiza holidays": "Ibiza",
    "Costa del Sol holidays": "Costa del Sol",
    "Barcelona travel": "Barcelona",
    "Madrid turismo": "Madrid",
    "Malaga holidays": "Málaga",
    "Sevilla turismo": "Sevilla",
    "Valencia turismo": "Valencia",
    "Gran Canaria holidays": "Gran Canaria",
    "Alicante holidays": "Alicante",
    "Bilbao turismo": "Bilbao",
    "San Sebastian travel": "San Sebastián",
    "Cordoba turismo": "Córdoba",
    "Granada turismo": "Granada",
    "Cadiz holidays": "Cádiz",
    "Fuerteventura holidays": "Fuerteventura",
    "Lanzarote holidays": "Lanzarote",
    "Menorca holidays": "Menorca",
    "Antalya holidays": "Antalya",
    "Rhodes holidays": "Rodas",
    "Santorini holidays": "Santorini",
    "Hurghada holidays": "Hurghada",
    "Punta Cana holidays": "Punta Cana",
    "Cancun travel": "Cancún",
    "Riviera Maya travel": "Riviera Maya",
    "Dubai travel": "Dubái",
    "Maldives holidays": "Maldivas",
    "Bali travel": "Bali",
    "Phuket holidays": "Phuket",
    "Marrakech travel": "Marrakech",
    "Cape Verde holidays": "Cabo Verde",
    "Split Croatia holidays": "Split",
    "Crete holidays": "Creta",
    "Sicily holidays": "Sicilia",
    "Sardinia holidays": "Cerdeña",
    "Amalfi Coast travel": "Costa Amalfitana",
    "Algarve holidays": "Algarve",
    "Tunisia holidays": "Túnez",
}


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def generar_id(destino: str, fuente: str, tipo: str, anio: int, mes: int) -> str:
    """Genera un ID determinista basado en los campos clave."""
    clave = f"{destino}|{fuente}|{tipo}|{anio}|{mes}"
    return hashlib.md5(clave.encode()).hexdigest()[:32]


def crear_tabla_si_no_existe(conn: sqlite3.Connection) -> None:
    """Verifica que la tabla indicadores_destino existe."""
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


def chunks(lst: list, n: int) -> list[list]:
    """Divide una lista en chunks de tamaño n."""
    return [lst[i:i + n] for i in range(0, len(lst), n)]


# ---------------------------------------------------------------------------
# Extracción con pytrends
# ---------------------------------------------------------------------------

def extraer_trends_grupo(keywords: list[str], destinos_map: dict,
                         conn: sqlite3.Connection) -> tuple[int, int, list[str]]:
    """
    Extrae datos de Google Trends para un grupo de hasta 5 keywords.
    
    Returns:
        (insertados, duplicados, errores_keywords)
    """
    from pytrends.request import TrendReq

    insertados = 0
    duplicados = 0
    errores = []

    try:
        pytrends = TrendReq(hl='es', tz=360, timeout=(10, 25))
        pytrends.build_payload(
            kw_list=keywords,
            cat=67,              # Travel category
            timeframe='today 5-y',  # Últimos 5 años, datos mensuales
            geo='',              # Mundial
        )

        df = pytrends.interest_over_time()

        if df.empty:
            logger.warning(f"Sin datos para grupo: {keywords}")
            errores.extend(keywords)
            return insertados, duplicados, errores

        # Procesar cada keyword/destino
        for keyword in keywords:
            if keyword not in df.columns:
                errores.append(keyword)
                continue

            destino = destinos_map[keyword]

            for idx, row in df.iterrows():
                valor = row[keyword]
                if valor == 0:
                    continue

                anio = idx.year
                mes = idx.month

                if existe_indicador(conn, destino, "google_trends",
                                  "interes_busqueda_mensual", anio, mes):
                    duplicados += 1
                    continue

                id_indicador = generar_id(destino, "google_trends",
                                        "interes_busqueda_mensual", anio, mes)

                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO indicadores_destino
                        (id_indicador, destino_nombre, fuente, tipo_indicador,
                         valor, anio, mes, fecha_extraccion)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        id_indicador, destino, "google_trends",
                        "interes_busqueda_mensual", float(valor),
                        anio, mes, datetime.now().isoformat()
                    ))
                    insertados += 1
                except sqlite3.IntegrityError:
                    duplicados += 1

        conn.commit()

    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "TooManyRequests" in error_str:
            logger.warning(f"Rate limit (429) para grupo: {keywords}")
            raise  # Re-raise para manejo de reintentos en el caller
        else:
            logger.error(f"Error extrayendo grupo {keywords}: {e}")
            errores.extend(keywords)

    return insertados, duplicados, errores


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extracción de Google Trends (interés de búsqueda por destino turístico)"
    )
    parser.add_argument(
        "--db", type=str, default="data/tui_recomendador.db",
        help="Ruta a la base de datos SQLite (default: data/tui_recomendador.db)"
    )
    parser.add_argument(
        "--pausa", type=int, default=65,
        help="Segundos de pausa entre grupos (default: 65)"
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    db_path = project_root / args.db

    if not db_path.parent.exists():
        logger.error(f"Directorio no encontrado: {db_path.parent}")
        sys.exit(1)

    # Verificar que pytrends está instalado
    try:
        from pytrends.request import TrendReq
    except ImportError:
        print("✗ Error: pytrends no está instalado.")
        print("  Instalar con: pip install pytrends")
        sys.exit(1)

    print("=" * 70)
    print("EXTRACCIÓN DE GOOGLE TRENDS - Interés de búsqueda turístico")
    print("=" * 70)
    print(f"Base de datos: {db_path}")
    print(f"Destinos: {len(DESTINOS_KEYWORDS)}")
    print(f"Pausa entre grupos: {args.pausa}s")
    print(f"Timeframe: últimos 5 años (today 5-y)")
    print(f"Categoría: 67 (Travel)")
    print(f"Registros esperados: ~{len(DESTINOS_KEYWORDS)} × 60 meses = ~{len(DESTINOS_KEYWORDS) * 60}")
    print()

    conn = sqlite3.connect(str(db_path))
    crear_tabla_si_no_existe(conn)

    # Dividir en grupos de 5 (máximo de pytrends)
    all_keywords = list(DESTINOS_KEYWORDS.keys())
    grupos = chunks(all_keywords, 5)

    total_insertados = 0
    total_duplicados = 0
    keywords_fallidos = []

    print(f"Total grupos a consultar: {len(grupos)} (de 5 keywords cada uno)")
    print(f"Tiempo estimado: ~{len(grupos) * args.pausa // 60} minutos")
    print()

    for i, grupo in enumerate(grupos, 1):
        destinos_grupo = [DESTINOS_KEYWORDS[k] for k in grupo]
        print(f"[{i}/{len(grupos)}] Grupo: {', '.join(destinos_grupo)}...")

        try:
            insertados, duplicados, errores = extraer_trends_grupo(
                grupo, DESTINOS_KEYWORDS, conn
            )
            total_insertados += insertados
            total_duplicados += duplicados
            keywords_fallidos.extend(errores)

            if insertados > 0:
                print(f"  ✓ {insertados} insertados, {duplicados} duplicados")
            elif duplicados > 0:
                print(f"  → {duplicados} duplicados (ya existían)")
            else:
                print(f"  ⚠ Sin datos nuevos")

        except Exception as e:
            if "429" in str(e) or "TooManyRequests" in str(e):
                print(f"  ⚠ Rate limit! Guardando datos obtenidos...")
                conn.commit()

                # Espera larga antes de reintentar
                print(f"  Esperando 120s antes de reintentar...")
                time.sleep(120)

                # Reintentar una vez
                try:
                    print(f"  Reintentando grupo {i}...")
                    insertados, duplicados, errores = extraer_trends_grupo(
                        grupo, DESTINOS_KEYWORDS, conn
                    )
                    total_insertados += insertados
                    total_duplicados += duplicados
                    keywords_fallidos.extend(errores)
                    print(f"  ✓ Reintento exitoso: {insertados} insertados")
                except Exception:
                    print(f"  ✗ Reintento fallido, saltando grupo")
                    keywords_fallidos.extend(grupo)
            else:
                logger.error(f"Error inesperado: {e}")
                keywords_fallidos.extend(grupo)

        # Pausa 65s entre grupos (excepto el último)
        if i < len(grupos):
            print(f"  Pausa de {args.pausa}s...")
            time.sleep(args.pausa)

    conn.close()

    # Resumen final
    print()
    print("=" * 70)
    print("RESUMEN FINAL")
    print("=" * 70)
    print(f"✓ Total insertados: {total_insertados} registros en indicadores_destino")
    print(f"  Duplicados descartados: {total_duplicados}")
    print(f"  Fuente: google_trends")
    print(f"  Tipo indicador: interes_busqueda_mensual")

    if keywords_fallidos:
        destinos_fallidos = [DESTINOS_KEYWORDS.get(k, k) for k in keywords_fallidos]
        destinos_unicos = list(set(destinos_fallidos))
        print(f"⚠ Destinos sin datos ({len(destinos_unicos)}):")
        for d in sorted(destinos_unicos):
            print(f"   - {d}")
    else:
        print("✓ Todos los destinos extraídos correctamente")

    if total_insertados > 0:
        print(f"\n✓ Datos guardados en tabla indicadores_destino")
    print("=" * 70)


if __name__ == "__main__":
    main()
