"""
Scraping masivo con rotación de destinos, 5 fuentes y deduplicación.

Usa: TripAdvisor, Reddit (Selenium), Reddit Arctic Shift (API), Google Maps, YouTube.
No elimina datos existentes, solo inserta nuevos (sin duplicados).

Uso:
    cd /d D:\Master\TrabajoFinalUCM\TFM
    python scripts/run_bulk_scraping.py --objetivo 5000 --rondas 30 --pausa-ronda 15
"""
import sys
import time
import random
import hashlib
import logging
import sqlite3
import uuid
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 5 fuentes disponibles
FUENTES = ["tripadvisor", "reddit", "reddit_arctic", "google_maps", "youtube"]

# Destinos reales TUI + destinos seguros potenciales — NUEVOS PRIMERO
DESTINOS_GRUPOS = [
    # --- NUEVOS PRIMERO (nunca buscados) ---
    # Grupo 1 - Emergentes Mediterráneo seguro
    ["Georgia Batumi", "Eslovenia Portoroz", "Croacia islas", "Grecia Lefkada", "Grecia Thassos", "Italia Tropea"],
    # Grupo 2 - Asia segura
    ["Tailandia Phuket", "Tailandia Koh Samui", "Bali", "Vietnam Da Nang", "Sri Lanka", "Maldivas"],
    # Grupo 3 - Océano Índico
    ["Mauricio", "Seychelles", "Reunión", "Zanzíbar", "Maldivas atolón"],
    # Grupo 4 - Caribe ampliado seguro
    ["Antigua", "Santa Lucía", "Granada Caribe", "Dominica", "Bonaire", "Turks and Caicos"],
    # Grupo 5 - Naturaleza seguros
    ["Islandia", "Noruega fiordos", "Azores senderismo", "Madeira trekking", "Canarias volcanes", "Escocia Highlands"],
    # Grupo 6 - Oriente Medio seguro
    ["Dubái", "Abu Dhabi", "Omán Muscat", "Omán Salalah", "Jordania Mar Muerto", "Jordania Aqaba"],
    # Grupo 7 - México y Centroamérica
    ["Playa del Carmen", "Tulum", "Los Cabos", "Puerto Vallarta", "Costa Rica", "Panamá"],
    # Grupo 8 - Cabo Verde
    ["Cabo Verde Sal", "Cabo Verde Boa Vista", "Cabo Verde Santiago", "Cabo Verde Santo Antão"],
    # Grupo 9 - Marruecos
    ["Marrakech", "Agadir", "Essaouira", "Fez", "Tánger"],
    # Grupo 10 - Italia ampliada
    ["Sicilia", "Cerdeña", "Calabria", "Puglia", "Costa Amalfitana", "Toscana", "Cinque Terre", "Lago de Garda"],
    # Grupo 11 - Croacia y Adriático
    ["Dubrovnik", "Split", "Istria", "Hvar", "Montenegro Budva", "Albania Saranda", "Albania Ksamil"],
    # Grupo 12 - Turquía ampliada
    ["Antalya", "Bodrum", "Dalaman", "Fethiye", "Cesme", "Kusadasi", "Marmaris", "Alanya"],
    # Grupo 13 - Egipto ampliado
    ["Hurghada", "Sharm el Sheikh", "Marsa Alam", "El Gouna", "Luxor"],
    # Grupo 14 - Grecia continental
    ["Atenas", "Salónica", "Pelión", "Halkidiki", "Peloponeso"],
    # Grupo 15 - Europa otros seguros
    ["Malta", "Chipre", "Chipre Norte", "Eslovenia costa", "Bulgaria Sunny Beach"],
    # Grupo 16 - Portugal atlántico
    ["Algarve", "Madeira", "Azores", "Lisboa costa", "Porto"],
    # Grupo 17 - Temporadas y ofertas (nuevo)
    ["vacaciones verano 2025 oferta", "viaje invierno sol barato", "Semana Santa playa",
     "Navidad Caribe", "puente mayo destino", "última hora vacaciones playa"],
    # Grupo 18 - Comparativas (nuevo)
    ["Mallorca vs Creta", "Cancún vs Punta Cana", "Tenerife vs Gran Canaria",
     "Antalya vs Hurghada", "Maldivas vs Mauricio", "Costa del Sol vs Algarve", "Bali vs Tailandia"],
    # Grupo 19 - Temáticas (nuevo)
    ["vacaciones playa familia Europa", "mejor destino luna de miel", "todo incluido barato",
     "mejor isla griega parejas", "destino sostenible Europa", "viaje aventura seguro"],
    # Grupo 20 - Marcas TUI
    ["TUI Blue Mallorca", "TUI Magic Life Bodrum", "TUI Sensatori Tenerife",
     "Robinson Club Fuerteventura", "RIU Cancún", "Iberostar Creta", "Barceló Bávaro"],


    # Grupo 21 - Baleares
    ["Mallorca", "Ibiza", "Menorca", "Formentera"],
    # Grupo 22 - Canarias
    ["Tenerife", "Gran Canaria", "Lanzarote", "Fuerteventura", "La Palma", "La Gomera"],
    # Grupo 23 - Costas España
    ["Costa del Sol", "Costa Brava", "Costa Blanca", "Costa Dorada", "Almería", "Cádiz", "Huelva"],
    # Grupo 24 - Grecia islas
    ["Creta", "Santorini", "Rodas", "Kos", "Corfu", "Zante", "Mykonos", "Kefalonia", "Skiathos", "Paros", "Naxos"],
    # Grupo 25 - Caribe clásico
    ["Cancún", "Riviera Maya", "Punta Cana", "Cuba Varadero", "Jamaica Montego Bay", "Aruba", "Curaçao", "Barbados"],
    # Grupo 26 - Opiniones español
    ["Mallorca vacaciones opiniones", "Tenerife hotel todo incluido", "Cancún experiencia viaje",
     "Creta playa familiar", "Punta Cana resort opiniones", "Antalya all inclusive"],
    # Grupo 27 - Reviews inglés
    ["Mallorca holiday review", "Tenerife all inclusive", "Cancun resort review",
     "Crete family holiday", "Rhodes travel tips", "Maldives overwater villa review"],
    # Grupo 28 - Bewertungen alemán
    ["Mallorca Urlaub Erfahrung", "Teneriffa Hotel Bewertung", "Kreta Familienurlaub",
     "Antalya All Inclusive", "Hurghada Reise Tipps", "Fuerteventura Strand"],
]

DATABASE_PATH = "data/tui_recomendador.db"


def get_existing_hashes(db_path: str) -> set:
    """Carga hashes MD5 de textos ya guardados."""
    hashes = set()
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT texto_original FROM resenas WHERE texto_original IS NOT NULL").fetchall()
        for (texto,) in rows:
            if texto:
                hashes.add(hashlib.md5(texto.strip().lower().encode()).hexdigest())
        conn.close()
        logger.info("Cargados %d hashes existentes", len(hashes))
    except Exception as e:
        logger.warning("Error cargando hashes: %s", e)
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


def guardar_resenas(resenas: list, db_path: str, hashes: set) -> int:
    """Guarda reseñas no duplicadas. Retorna cuantas se guardaron."""
    nuevas = []
    for r in resenas:
        texto = r.get("texto_original", "")
        if not texto or len(texto.strip()) < 20:
            continue
        h = hashlib.md5(texto.strip().lower().encode()).hexdigest()
        if h in hashes:
            continue
        hashes.add(h)
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
                    r.get("id_resena", str(uuid.uuid4())),
                    r.get("destino_nombre", ""),
                    r.get("fuente", ""),
                    r.get("texto_original", ""),
                    r.get("idioma", "unknown"),
                    r.get("puntuacion"),
                    str(r.get("fecha_publicacion")) if r.get("fecha_publicacion") else None,
                    r.get("url_fuente", ""),
                    r.get("fecha_extraccion", datetime.utcnow().isoformat()),
                )
            )
        except Exception:
            pass
    conn.commit()
    conn.close()
    return len(nuevas)


def ejecutar_scraper(fuente: str, destino: str, hashes: set) -> int:
    """Ejecuta un scraper para un destino. Retorna reseñas nuevas guardadas."""
    try:
        resenas = []

        if fuente == "tripadvisor":
            from src.scraping.tripadvisor_scraper import TripAdvisorScraper
            resenas = TripAdvisorScraper(timeout=15).extraer_resenas(destino, limite=40)

        elif fuente == "reddit":
            from src.scraping.reddit_collector import RedditCollector
            resenas = RedditCollector(timeout=15).collect_posts(destino, limite=40)

        elif fuente == "reddit_arctic":
            from src.scraping.reddit_collector_arctic_shift import RedditCollectorArcticShift
            collector = RedditCollectorArcticShift(timeout=20, pausa_entre_requests=2.0)
            resenas = collector.collect_posts(destino, limite=100)

        elif fuente == "google_maps":
            from src.scraping.google_maps_scraper import GoogleMapsScraper
            resenas = GoogleMapsScraper(timeout=15).extraer_resenas(destino, limite=40)

        elif fuente == "youtube":
            from src.scraping.youtube_scraper import YouTubeScraper
            resenas = YouTubeScraper(timeout=15).extraer_comentarios(destino, limite=40)

        guardadas = guardar_resenas(resenas, DATABASE_PATH, hashes)
        return guardadas

    except Exception as e:
        logger.warning("  Error [%s] %s: %s", fuente, destino, e)
        return 0


def deduplicar_bd_final(db_path: str) -> int:
    """Deduplicacion final: elimina solo registros duplicados (conserva el mas reciente)."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT id_resena, texto_original FROM resenas
        WHERE texto_original IS NOT NULL
        ORDER BY fecha_extraccion DESC
    """).fetchall()

    hashes_vistos = set()
    ids_a_eliminar = []

    for id_resena, texto in rows:
        if not texto:
            continue
        h = hashlib.md5(texto.strip().lower().encode()).hexdigest()
        if h in hashes_vistos:
            ids_a_eliminar.append(id_resena)
        else:
            hashes_vistos.add(h)

    if ids_a_eliminar:
        for i in range(0, len(ids_a_eliminar), 500):
            batch = ids_a_eliminar[i:i+500]
            placeholders = ",".join("?" * len(batch))
            conn.execute(f"DELETE FROM resenas WHERE id_resena IN ({placeholders})", batch)
        conn.commit()

    conn.close()
    return len(ids_a_eliminar)


def main():
    parser = argparse.ArgumentParser(description="Scraping masivo con 5 fuentes y deduplicacion")
    parser.add_argument("--objetivo", type=int, default=5000, help="Numero objetivo de reseñas totales")
    parser.add_argument("--rondas", type=int, default=30, help="Numero maximo de rondas")
    parser.add_argument("--pausa-ronda", type=int, default=15, help="Segundos de pausa entre rondas")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  SCRAPING MASIVO — 5 FUENTES")
    print(f"{'='*60}")
    print(f"  Objetivo: {args.objetivo} reseñas totales")
    print(f"  Rondas maximas: {args.rondas}")
    print(f"  Pausa entre rondas: {args.pausa_ronda}s")
    print(f"  Fuentes: {', '.join(FUENTES)}")
    print(f"{'='*60}\n")

    # Estado
    hashes = get_existing_hashes(DATABASE_PATH)
    total_inicio = get_total_resenas(DATABASE_PATH)
    ejecutados = set()  # (fuente, destino) ya procesados
    total_nuevas = 0
    start_time = time.time()

    print(f"Reseñas al inicio: {total_inicio}")

    if total_inicio >= args.objetivo:
        print(f"Ya se alcanzo el objetivo ({total_inicio} >= {args.objetivo}).")
        return

    for ronda in range(1, args.rondas + 1):
        total_actual = get_total_resenas(DATABASE_PATH)
        if total_actual >= args.objetivo:
            print(f"\n✅ Objetivo alcanzado: {total_actual} reseñas")
            break

        # Rotar grupo y fuente
        grupo_idx = (ronda - 1) % len(DESTINOS_GRUPOS)
        fuente_idx = (ronda - 1) % len(FUENTES)
        grupo = list(DESTINOS_GRUPOS[grupo_idx])
        fuente = FUENTES[fuente_idx]
        random.shuffle(grupo)

        print(f"\n--- Ronda {ronda}/{args.rondas} | {fuente.upper()} | {grupo[:3]}... ---")

        nuevas_ronda = 0
        for destino in grupo:
            # No repetir fuente+destino
            clave = (fuente, destino.lower())
            if clave in ejecutados:
                continue
            ejecutados.add(clave)

            guardadas = ejecutar_scraper(fuente, destino, hashes)
            nuevas_ronda += guardadas
            total_nuevas += guardadas

            if guardadas > 0:
                logger.info("  [%s] %s: +%d nuevas", fuente[:2].upper(), destino, guardadas)

            time.sleep(random.uniform(2, 4))

        total_actual = get_total_resenas(DATABASE_PATH)
        print(f"  Ronda {ronda}: +{nuevas_ronda} | Total: {total_actual} | Objetivo: {args.objetivo}")

        # Pausa entre rondas
        if ronda < args.rondas and total_actual < args.objetivo:
            time.sleep(args.pausa_ronda + random.randint(0, 5))

    # Deduplicacion final (solo elimina duplicados, no datos originales)
    print(f"\n--- Deduplicacion final ---")
    eliminados = deduplicar_bd_final(DATABASE_PATH)
    print(f"  Duplicados eliminados: {eliminados}")

    total_final = get_total_resenas(DATABASE_PATH)
    elapsed = time.time() - start_time

    print(f"\n{'='*60}")
    print(f"  RESUMEN SCRAPING MASIVO")
    print(f"{'='*60}")
    print(f"  Reseñas al inicio: {total_inicio}")
    print(f"  Reseñas nuevas: {total_nuevas}")
    print(f"  Duplicados eliminados: {eliminados}")
    print(f"  Total final en BD: {total_final}")
    print(f"  Combinaciones ejecutadas: {len(ejecutados)}")
    print(f"  Rondas completadas: {ronda}")
    print(f"  Tiempo total: {elapsed/60:.1f} minutos")
    print(f"  Objetivo {'ALCANZADO' if total_final >= args.objetivo else 'NO alcanzado'}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
