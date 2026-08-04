"""
Scraping masivo con rotación de destinos y deduplicación.

Estrategia:
- Rota entre destinos para no hacer muchas peticiones seguidas al mismo
- Espera entre rondas para evitar rate limiting
- Verifica si el texto ya existe en la BD antes de guardar
- Ejecuta múltiples rondas hasta alcanzar el objetivo

Uso:
    cd /d D:\Master\TrabajoFinalUCM\TFM
    python scripts/run_bulk_scraping.py --objetivo 5000 --rondas 10
"""
import sys
import time
import random
import hashlib
import logging
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Destinos organizados por grupos (se rota entre grupos para no repetir fuente)
DESTINOS_GRUPOS = [
    # Grupo 1 - España
    ["Mallorca", "Tenerife", "Ibiza", "Costa del Sol", "Lanzarote", "Fuerteventura"],
    # Grupo 2 - Grecia/Turquía/Egipto
    ["Creta", "Santorini", "Rodas", "Antalya", "Hurghada"],
    # Grupo 3 - Caribe
    ["Cancun", "Riviera Maya", "Punta Cana", "Cuba", "Jamaica"],
    # Grupo 4 - Variantes de búsqueda (mismos destinos, diferente query)
    ["Mallorca hotel", "Tenerife resort", "Cancun all inclusive", "Creta vacaciones", "Ibiza playa"],
    # Grupo 5 - Destinos adicionales para más variedad
    ["Maldivas", "Bali", "Tailandia", "Sicilia", "Cerdeña", "Croacia"],
    # Grupo 6 - Queries en inglés
    ["Mallorca beach holiday", "Tenerife travel", "Cancun vacation", "Crete tourism", "Punta Cana resort"],
]

DATABASE_URL = "data/tui_recomendador.db"


def get_existing_hashes(db_path: str) -> set:
    """Carga los hashes de textos ya guardados para evitar duplicados."""
    hashes = set()
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT texto_original FROM resenas WHERE texto_original IS NOT NULL").fetchall()
        for (texto,) in rows:
            if texto:
                h = hashlib.md5(texto.strip().lower().encode()).hexdigest()
                hashes.add(h)
        conn.close()
        logger.info("Cargados %d hashes de reseñas existentes", len(hashes))
    except Exception as e:
        logger.warning("No se pudieron cargar hashes existentes: %s", e)
    return hashes


def get_total_resenas(db_path: str) -> int:
    """Cuenta total de reseñas en la BD."""
    try:
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM resenas").fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def texto_es_duplicado(texto: str, hashes_existentes: set) -> bool:
    """Verifica si un texto ya fue guardado (por hash MD5)."""
    if not texto or len(texto.strip()) < 20:
        return True
    h = hashlib.md5(texto.strip().lower().encode()).hexdigest()
    return h in hashes_existentes


def guardar_resenas(resenas: list, db_path: str, hashes_existentes: set) -> int:
    """Guarda reseñas nuevas (no duplicadas) en la BD. Retorna cuántas se guardaron."""
    import uuid

    nuevas = []
    for r in resenas:
        texto = r.get("texto_original", "")
        if texto_es_duplicado(texto, hashes_existentes):
            continue
        # Marcar como vista
        h = hashlib.md5(texto.strip().lower().encode()).hexdigest()
        hashes_existentes.add(h)
        nuevas.append(r)

    if not nuevas:
        return 0

    conn = sqlite3.connect(db_path)
    for r in nuevas:
        try:
            conn.execute(
                """INSERT INTO resenas (id_resena, destino_nombre, fuente, texto_original, 
                   idioma, puntuacion, fecha_publicacion, url_fuente, fecha_extraccion)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    r.get("destino_nombre", ""),
                    r.get("fuente", ""),
                    r.get("texto_original", ""),
                    r.get("idioma", "unknown"),
                    r.get("puntuacion"),
                    r.get("fecha_publicacion"),
                    r.get("url_fuente", ""),
                    r.get("fecha_extraccion", datetime.utcnow().isoformat()),
                )
            )
        except Exception as e:
            logger.debug("Error insertando reseña: %s", e)
    conn.commit()
    conn.close()
    return len(nuevas)


def ejecutar_ronda(grupo_destinos: list, fuente: str, hashes: set) -> int:
    """Ejecuta scraping de un grupo de destinos con una fuente. Retorna reseñas nuevas."""
    total_nuevas = 0

    if fuente == "tripadvisor":
        from src.scraping.tripadvisor_scraper import TripAdvisorScraper
        scraper = TripAdvisorScraper(timeout=15)
        for destino in grupo_destinos:
            try:
                resenas = scraper.extraer_resenas(destino, limite=30)
                guardadas = guardar_resenas(resenas, DATABASE_URL, hashes)
                total_nuevas += guardadas
                logger.info("  [TA] %s: %d extraídas, %d nuevas guardadas", destino, len(resenas), guardadas)
                time.sleep(random.uniform(2, 5))  # Pausa entre destinos
            except Exception as e:
                logger.warning("  [TA] Error en %s: %s", destino, e)

    elif fuente == "reddit":
        from src.scraping.reddit_collector import RedditCollector
        collector = RedditCollector(timeout=15)
        for destino in grupo_destinos:
            try:
                posts = collector.collect_posts(destino, limite=30)
                guardadas = guardar_resenas(posts, DATABASE_URL, hashes)
                total_nuevas += guardadas
                logger.info("  [RD] %s: %d extraídos, %d nuevos guardados", destino, len(posts), guardadas)
                time.sleep(random.uniform(2, 5))
            except Exception as e:
                logger.warning("  [RD] Error en %s: %s", destino, e)

    elif fuente == "reddit_arctic":
        from src.scraping.reddit_collector_arctic_shift import RedditCollectorArcticShift
        collector = RedditCollectorArcticShift(pausa_entre_requests=2.0)
        for destino in grupo_destinos:
            try:
                posts = collector.collect_posts(destino, limite=30)
                guardadas = guardar_resenas(posts, DATABASE_URL, hashes)
                total_nuevas += guardadas
                logger.info("  [RA] %s: %d extraídos, %d nuevos guardados", destino, len(posts), guardadas)
                time.sleep(random.uniform(3, 7))
            except Exception as e:
                logger.warning("  [RA] Error en %s: %s", destino, e)

    return total_nuevas


def main():
    parser = argparse.ArgumentParser(description="Scraping masivo con rotación de destinos")
    parser.add_argument("--objetivo", type=int, default=5000, help="Número objetivo de reseñas totales")
    parser.add_argument("--rondas", type=int, default=10, help="Número máximo de rondas")
    parser.add_argument("--pausa-ronda", type=int, default=30, help="Segundos de pausa entre rondas")
    parser.add_argument(
        "--fuentes", nargs="+", default=["reddit_arctic"],
        choices=["tripadvisor", "reddit", "reddit_arctic"],
        help="Fuentes a rotar durante el scraping masivo",
    )
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  SCRAPING MASIVO CON ROTACIÓN")
    print(f"{'='*60}")
    print(f"  Objetivo: {args.objetivo} reseñas totales")
    print(f"  Rondas máximas: {args.rondas}")
    print(f"  Pausa entre rondas: {args.pausa_ronda}s")
    print(f"{'='*60}\n")

    # Cargar hashes existentes
    hashes = get_existing_hashes(DATABASE_URL)
    total_actual = get_total_resenas(DATABASE_URL)
    print(f"Reseñas actuales en BD: {total_actual}")

    if total_actual >= args.objetivo:
        print(f"Ya se alcanzó el objetivo ({total_actual} >= {args.objetivo}). Nada que hacer.")
        return

    total_nuevas_global = 0
    fuentes = args.fuentes
    start_time = time.time()

    for ronda in range(1, args.rondas + 1):
        total_actual = get_total_resenas(DATABASE_URL)
        if total_actual >= args.objetivo:
            print(f"\n✅ Objetivo alcanzado: {total_actual} reseñas")
            break

        # Seleccionar grupo de destinos (rotar)
        grupo_idx = (ronda - 1) % len(DESTINOS_GRUPOS)
        grupo = DESTINOS_GRUPOS[grupo_idx]
        random.shuffle(grupo)  # Aleatorizar orden dentro del grupo

        # Alternar fuente
        fuente = fuentes[(ronda - 1) % len(fuentes)]

        print(f"\n--- Ronda {ronda}/{args.rondas} | Fuente: {fuente} | Grupo: {grupo[:3]}... ---")

        try:
            nuevas = ejecutar_ronda(grupo, fuente, hashes)
        except Exception as e:
            logger.error("Ronda %d falló por completo: %s. Continuando con la siguiente.", ronda, e)
            nuevas = 0

        total_nuevas_global += nuevas
        total_actual = get_total_resenas(DATABASE_URL)

        print(f"  Nuevas esta ronda: {nuevas} | Total en BD: {total_actual} | Objetivo: {args.objetivo}")

        if ronda < args.rondas and total_actual < args.objetivo:
            pausa = args.pausa_ronda + random.randint(0, 10)
            print(f"  Esperando {pausa}s antes de siguiente ronda...")
            time.sleep(pausa)

    elapsed = time.time() - start_time
    total_final = get_total_resenas(DATABASE_URL)

    print(f"\n{'='*60}")
    print(f"  RESUMEN SCRAPING MASIVO")
    print(f"{'='*60}")
    print(f"  Reseñas nuevas: {total_nuevas_global}")
    print(f"  Total en BD: {total_final}")
    print(f"  Duplicados omitidos: verificación por hash MD5")
    print(f"  Tiempo total: {elapsed/60:.1f} minutos")
    print(f"  Objetivo {'ALCANZADO ✅' if total_final >= args.objetivo else 'NO alcanzado ⚠️'}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
