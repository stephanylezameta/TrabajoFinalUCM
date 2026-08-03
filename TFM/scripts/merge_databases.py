"""
Fusiona una base de datos local de scraping con la BD principal del equipo.

Cada miembro del equipo scrapea en su propia BD local. Luego usa este script
para aportar sus registros nuevos a la BD centralizada, sin duplicados.

La deduplicacion se hace por hash MD5 del texto (resenas) y por clave
compuesta (indicadores).

Uso:
    cd TFM
    python scripts/merge_databases.py --origen data/mi_bd_local.db --destino data/tui_recomendador.db
    python scripts/merge_databases.py --origen "C:/Users/Juan/bd_juan.db" --destino data/tui_recomendador.db
"""

import argparse
import hashlib
import logging
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def calcular_hash_texto(texto: str) -> str:
    """Hash MD5 del texto normalizado para comparar duplicados."""
    return hashlib.md5(texto.strip().lower().encode()).hexdigest()


def obtener_hashes_existentes(conn: sqlite3.Connection, tabla: str, columna_texto: str) -> set:
    """Carga los hashes de textos ya existentes en la BD destino."""
    hashes = set()
    try:
        rows = conn.execute(
            f"SELECT {columna_texto} FROM {tabla} WHERE {columna_texto} IS NOT NULL"
        ).fetchall()
        for (texto,) in rows:
            if texto and len(texto.strip()) > 10:
                hashes.add(calcular_hash_texto(texto))
    except Exception as e:
        logger.warning("No se pudieron cargar hashes de %s: %s", tabla, e)
    return hashes


def obtener_claves_indicadores(conn: sqlite3.Connection) -> set:
    """Carga claves unicas de indicadores existentes (destino+fuente+tipo+anio+mes)."""
    claves = set()
    try:
        rows = conn.execute(
            "SELECT destino_nombre, fuente, tipo_indicador, anio, mes FROM indicadores_destino"
        ).fetchall()
        for row in rows:
            clave = (row[0], row[1], row[2], row[3], row[4])
            claves.add(clave)
    except Exception:
        pass
    return claves


def merge_resenas(conn_origen: sqlite3.Connection, conn_destino: sqlite3.Connection) -> int:
    """Fusiona resenas de origen a destino, saltando duplicados por hash de texto."""
    hashes_destino = obtener_hashes_existentes(conn_destino, "resenas", "texto_original")
    logger.info("Resenas ya existentes en destino: %d", len(hashes_destino))

    try:
        resenas_origen = conn_origen.execute(
            "SELECT id_resena, id_paquete, destino_nombre, fuente, texto_original, "
            "idioma, puntuacion, fecha_publicacion, url_fuente, fecha_extraccion "
            "FROM resenas WHERE texto_original IS NOT NULL"
        ).fetchall()
    except Exception as e:
        logger.warning("No se pudo leer tabla resenas del origen: %s", e)
        return 0

    nuevas = 0
    duplicadas = 0

    for row in resenas_origen:
        texto = row[4]
        if not texto or len(texto.strip()) < 10:
            continue

        h = calcular_hash_texto(texto)
        if h in hashes_destino:
            duplicadas += 1
            continue

        # Insertar en destino
        try:
            conn_destino.execute(
                """INSERT OR IGNORE INTO resenas 
                   (id_resena, id_paquete, destino_nombre, fuente, texto_original,
                    idioma, puntuacion, fecha_publicacion, url_fuente, fecha_extraccion)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                row
            )
            hashes_destino.add(h)
            nuevas += 1
        except Exception as e:
            logger.debug("Error insertando resena: %s", e)

    conn_destino.commit()
    logger.info("Resenas: %d nuevas insertadas, %d duplicadas omitidas", nuevas, duplicadas)
    return nuevas


def merge_indicadores(conn_origen: sqlite3.Connection, conn_destino: sqlite3.Connection) -> int:
    """Fusiona indicadores de destino, saltando los que ya existen por clave compuesta."""
    claves_destino = obtener_claves_indicadores(conn_destino)
    logger.info("Indicadores ya existentes en destino: %d", len(claves_destino))

    try:
        indicadores_origen = conn_origen.execute(
            "SELECT id_indicador, destino_nombre, fuente, tipo_indicador, "
            "valor, anio, mes, fecha_extraccion "
            "FROM indicadores_destino"
        ).fetchall()
    except Exception as e:
        logger.warning("No se pudo leer tabla indicadores_destino del origen: %s", e)
        return 0

    nuevos = 0
    duplicados = 0

    for row in indicadores_origen:
        clave = (row[1], row[2], row[3], row[5], row[6])  # destino, fuente, tipo, anio, mes
        if clave in claves_destino:
            duplicados += 1
            continue

        try:
            conn_destino.execute(
                """INSERT OR IGNORE INTO indicadores_destino
                   (id_indicador, destino_nombre, fuente, tipo_indicador,
                    valor, anio, mes, fecha_extraccion)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                row
            )
            claves_destino.add(clave)
            nuevos += 1
        except Exception as e:
            logger.debug("Error insertando indicador: %s", e)

    conn_destino.commit()
    logger.info("Indicadores: %d nuevos insertados, %d duplicados omitidos", nuevos, duplicados)
    return nuevos


def contar_registros(conn: sqlite3.Connection) -> dict:
    """Cuenta registros en las tablas principales."""
    conteos = {}
    for tabla in ["resenas", "indicadores_destino", "paquetes"]:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
            conteos[tabla] = count
        except Exception:
            conteos[tabla] = 0
    return conteos


def main():
    parser = argparse.ArgumentParser(
        description="Fusiona una BD local de scraping con la BD principal del equipo."
    )
    parser.add_argument(
        "--origen",
        required=True,
        help="Ruta a la BD local del compañero (ej: data/bd_juan.db)"
    )
    parser.add_argument(
        "--destino",
        default="data/tui_recomendador.db",
        help="Ruta a la BD principal/centralizada (default: data/tui_recomendador.db)"
    )
    args = parser.parse_args()

    # Validar que los archivos existen
    if not Path(args.origen).exists():
        logger.error("La BD de origen no existe: %s", args.origen)
        sys.exit(1)

    if not Path(args.destino).exists():
        logger.error("La BD de destino no existe: %s", args.destino)
        logger.info("Crea primero las tablas con: python -c \"import sys; sys.path.insert(0,'.'); "
                    "from src.data.repository import Repositorio; "
                    "Repositorio('sqlite:///data/tui_recomendador.db').crear_tablas()\"")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  MERGE DE BASES DE DATOS")
    print(f"{'='*60}")
    print(f"  Origen:  {args.origen}")
    print(f"  Destino: {args.destino}")
    print(f"{'='*60}\n")

    conn_origen = sqlite3.connect(args.origen)
    conn_destino = sqlite3.connect(args.destino)

    # Mostrar estado antes del merge
    conteos_origen = contar_registros(conn_origen)
    conteos_destino_antes = contar_registros(conn_destino)

    print(f"  Estado ANTES del merge:")
    print(f"    Origen  -> resenas: {conteos_origen['resenas']}, "
          f"indicadores: {conteos_origen['indicadores_destino']}")
    print(f"    Destino -> resenas: {conteos_destino_antes['resenas']}, "
          f"indicadores: {conteos_destino_antes['indicadores_destino']}")
    print()

    # Ejecutar merge
    nuevas_resenas = merge_resenas(conn_origen, conn_destino)
    nuevos_indicadores = merge_indicadores(conn_origen, conn_destino)

    # Mostrar estado despues
    conteos_destino_despues = contar_registros(conn_destino)

    print(f"\n{'='*60}")
    print(f"  RESULTADO")
    print(f"{'='*60}")
    print(f"  Resenas nuevas aportadas:     {nuevas_resenas}")
    print(f"  Indicadores nuevos aportados: {nuevos_indicadores}")
    print(f"  Total resenas en destino:     {conteos_destino_despues['resenas']}")
    print(f"  Total indicadores en destino: {conteos_destino_despues['indicadores_destino']}")
    print(f"{'='*60}\n")

    conn_origen.close()
    conn_destino.close()


if __name__ == "__main__":
    main()
