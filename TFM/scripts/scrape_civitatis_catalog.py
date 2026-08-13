"""
Scraping del catálogo REAL de experiencias de Civitatis.

Extrae actividades/experiencias de la web pública de Civitatis para los 39 destinos TUI.
Usa requests + BeautifulSoup (NO Selenium). Maneja bloqueos con gracia.

Uso:
    cd /d D:\Master\TrabajoFinalUCM\TFM
    python scripts/scrape_civitatis_catalog.py
    python scripts/scrape_civitatis_catalog.py --destinos Mallorca Barcelona
    python scripts/scrape_civitatis_catalog.py --max-paginas 5
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

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- Configuración ---
DATABASE_PATH = "data/tui_recomendador.db"
BASE_URL = "https://www.civitatis.com/es"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# Mapeo de destinos TUI a slugs de Civitatis
DESTINOS_CIVITATIS = {
    "Mallorca": "mallorca",
    "Tenerife": "tenerife",
    "Ibiza": "ibiza",
    "Costa del Sol": "malaga",
    "Barcelona": "barcelona",
    "Madrid": "madrid",
    "Málaga": "malaga",
    "Sevilla": "sevilla",
    "Valencia": "valencia",
    "Gran Canaria": "gran-canaria",
    "Alicante": "alicante",
    "Bilbao": "bilbao",
    "San Sebastián": "san-sebastian",
    "Córdoba": "cordoba",
    "Granada": "granada",
    "Cádiz": "cadiz",
    "Fuerteventura": "fuerteventura",
    "Lanzarote": "lanzarote",
    "Menorca": "menorca",
    "Antalya": "antalya",
    "Rodas": "rodas",
    "Santorini": "santorini",
    "Hurghada": "hurghada",
    "Split": "split",
    "Creta": "creta",
    "Sicilia": "sicilia",
    "Cerdeña": "cerdena",
    "Costa Amalfitana": "costa-amalfitana",
    "Algarve": "algarve",
    "Túnez": "tunez",
    "Punta Cana": "punta-cana",
    "Cancún": "cancun",
    "Riviera Maya": "riviera-maya",
    "Dubái": "dubai",
    "Maldivas": "maldivas",
    "Bali": "bali",
    "Phuket": "phuket",
    "Marrakech": "marrakech",
    "Cabo Verde": "cabo-verde",
}


def crear_tabla(db_path: str):
    """Crea la tabla experiencias_reales si no existe."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS experiencias_reales (
            id TEXT PRIMARY KEY,
            destino_nombre TEXT NOT NULL,
            titulo TEXT NOT NULL,
            url TEXT,
            precio_eur REAL,
            rating REAL,
            review_count INTEGER,
            duracion_texto TEXT,
            fuente TEXT NOT NULL DEFAULT 'civitatis',
            fecha_extraccion TEXT NOT NULL,
            UNIQUE(destino_nombre, titulo, fuente)
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Tabla 'experiencias_reales' verificada/creada.")


def generar_id(destino: str, titulo: str, fuente: str) -> str:
    """Genera un ID determinístico basado en destino + título + fuente."""
    texto = f"{destino}|{titulo}|{fuente}".lower().strip()
    return hashlib.md5(texto.encode()).hexdigest()


def extraer_experiencias_pagina(soup: BeautifulSoup, destino_nombre: str, slug: str) -> list:
    """Extrae experiencias de una página parseada de Civitatis."""
    experiencias = []

    # Civitatis usa diferentes estructuras; intentamos varias
    # Buscar tarjetas de actividades
    tarjetas = soup.select("article.comfort-card") or \
               soup.select("div.o-search-list__item") or \
               soup.select("article") or \
               soup.select("div[class*='activity']")

    for tarjeta in tarjetas:
        try:
            # Título
            titulo_elem = tarjeta.select_one("h2 a") or \
                          tarjeta.select_one("h3 a") or \
                          tarjeta.select_one("a[class*='title']") or \
                          tarjeta.select_one(".comfort-card__title a") or \
                          tarjeta.select_one("a")
            if not titulo_elem:
                continue

            titulo = titulo_elem.get_text(strip=True)
            if not titulo or len(titulo) < 5:
                continue

            # URL
            url = titulo_elem.get("href", "")
            if url and not url.startswith("http"):
                url = f"https://www.civitatis.com{url}"

            # Precio
            precio = None
            precio_elem = tarjeta.select_one("span.comfort-card__price__text") or \
                          tarjeta.select_one("span[class*='price']") or \
                          tarjeta.select_one("div[class*='price'] span") or \
                          tarjeta.select_one(".price")
            if precio_elem:
                precio_texto = precio_elem.get_text(strip=True)
                # Extraer número del precio (ej: "25 €", "Desde 25€", "25,50 €")
                import re
                match = re.search(r"(\d+[.,]?\d*)", precio_texto.replace(".", "").replace(",", "."))
                if match:
                    try:
                        precio = float(match.group(1))
                    except ValueError:
                        pass

            # Rating
            rating = None
            rating_elem = tarjeta.select_one("span.comfort-card__rating__average") or \
                          tarjeta.select_one("span[class*='rating']") or \
                          tarjeta.select_one("div[class*='rating'] span")
            if rating_elem:
                import re
                match = re.search(r"(\d+[.,]?\d*)", rating_elem.get_text(strip=True).replace(",", "."))
                if match:
                    try:
                        rating = float(match.group(1))
                        if rating > 10:
                            rating = rating / 2  # Normalizar si viene en escala 1-10
                    except ValueError:
                        pass

            # Review count
            review_count = None
            reviews_elem = tarjeta.select_one("span.comfort-card__rating__total") or \
                           tarjeta.select_one("span[class*='reviews']") or \
                           tarjeta.select_one("span[class*='opinions']")
            if reviews_elem:
                import re
                match = re.search(r"(\d+[\d.]*)", reviews_elem.get_text(strip=True).replace(".", ""))
                if match:
                    try:
                        review_count = int(match.group(1))
                    except ValueError:
                        pass

            # Duración
            duracion = None
            duracion_elem = tarjeta.select_one("span[class*='duration']") or \
                            tarjeta.select_one("div[class*='duration']") or \
                            tarjeta.select_one(".comfort-card__duration")
            if duracion_elem:
                duracion = duracion_elem.get_text(strip=True)

            experiencia = {
                "id": generar_id(destino_nombre, titulo, "civitatis"),
                "destino_nombre": destino_nombre,
                "titulo": titulo,
                "url": url,
                "precio_eur": precio,
                "rating": rating,
                "review_count": review_count,
                "duracion_texto": duracion,
                "fuente": "civitatis",
                "fecha_extraccion": datetime.utcnow().isoformat(),
            }
            experiencias.append(experiencia)

        except Exception as e:
            logger.debug("Error parseando tarjeta: %s", e)
            continue

    return experiencias


def scrape_destino(destino_nombre: str, slug: str, max_paginas: int = 10, session: requests.Session = None) -> list:
    """Scrapea todas las experiencias de un destino (con paginación)."""
    if session is None:
        session = requests.Session()
        session.headers.update(HEADERS)

    todas_experiencias = []

    for pagina in range(1, max_paginas + 1):
        url = f"{BASE_URL}/{slug}/"
        if pagina > 1:
            url = f"{BASE_URL}/{slug}/?page={pagina}"

        try:
            response = session.get(url, timeout=15)

            # Manejar bloqueos
            if response.status_code == 403:
                logger.warning("  [%s] Bloqueado (403) en página %d. Saltando destino.", destino_nombre, pagina)
                break
            if response.status_code == 429:
                logger.warning("  [%s] Rate limited (429). Esperando 30s...", destino_nombre)
                time.sleep(30)
                break
            if response.status_code == 404:
                if pagina == 1:
                    logger.warning("  [%s] No encontrado (404). Slug '%s' podría ser incorrecto.", destino_nombre, slug)
                break  # No hay más páginas
            if response.status_code != 200:
                logger.warning("  [%s] HTTP %d en página %d.", destino_nombre, response.status_code, pagina)
                break

            soup = BeautifulSoup(response.text, "html.parser")

            # Detectar captcha
            if "captcha" in response.text.lower() or "recaptcha" in response.text.lower():
                logger.warning("  [%s] Captcha detectado. Saltando destino.", destino_nombre)
                break

            experiencias = extraer_experiencias_pagina(soup, destino_nombre, slug)

            if not experiencias:
                # No hay más resultados en esta página
                if pagina == 1:
                    logger.info("  [%s] Sin experiencias encontradas (estructura HTML puede haber cambiado).", destino_nombre)
                break

            todas_experiencias.extend(experiencias)
            logger.info("  [%s] Página %d: %d experiencias", destino_nombre, pagina, len(experiencias))

            # Verificar si hay siguiente página
            next_link = soup.select_one("a[rel='next']") or \
                        soup.select_one("a.next") or \
                        soup.select_one("li.next a")
            if not next_link and pagina > 1:
                break

            # Pausa entre páginas
            time.sleep(random.uniform(2, 4))

        except requests.exceptions.Timeout:
            logger.warning("  [%s] Timeout en página %d.", destino_nombre, pagina)
            break
        except requests.exceptions.ConnectionError as e:
            logger.warning("  [%s] Error de conexión: %s", destino_nombre, e)
            break
        except Exception as e:
            logger.error("  [%s] Error inesperado: %s", destino_nombre, e)
            break

    return todas_experiencias


def guardar_experiencias(experiencias: list, db_path: str) -> int:
    """Guarda experiencias en la BD. Retorna cuántas se insertaron."""
    if not experiencias:
        return 0

    conn = sqlite3.connect(db_path)
    insertadas = 0

    for exp in experiencias:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO experiencias_reales
                   (id, destino_nombre, titulo, url, precio_eur, rating, review_count, duracion_texto, fuente, fecha_extraccion)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    exp["id"],
                    exp["destino_nombre"],
                    exp["titulo"],
                    exp["url"],
                    exp["precio_eur"],
                    exp["rating"],
                    exp["review_count"],
                    exp["duracion_texto"],
                    exp["fuente"],
                    exp["fecha_extraccion"],
                )
            )
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                insertadas += 1
        except Exception as e:
            logger.debug("Error insertando experiencia: %s", e)
            continue

    conn.commit()
    conn.close()
    return insertadas


def main():
    parser = argparse.ArgumentParser(
        description="Scraping del catálogo de experiencias de Civitatis (web pública)"
    )
    parser.add_argument(
        "--destinos", nargs="*", default=None,
        help="Lista de destinos específicos a scrapear (por defecto todos)"
    )
    parser.add_argument(
        "--max-paginas", type=int, default=10,
        help="Máximo de páginas por destino (default: 10)"
    )
    parser.add_argument(
        "--db", type=str, default=DATABASE_PATH,
        help="Ruta a la base de datos SQLite"
    )
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  SCRAPING CATÁLOGO CIVITATIS")
    print(f"{'='*60}")
    print(f"  Fuente: Civitatis (web pública)")
    print(f"  Método: requests + BeautifulSoup (sin Selenium)")
    print(f"  Max páginas por destino: {args.max_paginas}")
    print(f"{'='*60}\n")

    # Crear tabla
    crear_tabla(args.db)

    # Seleccionar destinos
    if args.destinos:
        destinos = {d: DESTINOS_CIVITATIS[d] for d in args.destinos if d in DESTINOS_CIVITATIS}
        if not destinos:
            print(f"ERROR: Ningún destino válido. Disponibles: {list(DESTINOS_CIVITATIS.keys())}")
            return
    else:
        destinos = DESTINOS_CIVITATIS

    # Sesión persistente
    session = requests.Session()
    session.headers.update(HEADERS)

    # Estadísticas
    total_experiencias = 0
    destinos_ok = 0
    destinos_error = 0
    start_time = time.time()

    print(f"Destinos a procesar: {len(destinos)}\n")

    for i, (destino_nombre, slug) in enumerate(destinos.items(), 1):
        print(f"[{i}/{len(destinos)}] {destino_nombre} (/{slug}/) ...", end=" ", flush=True)

        try:
            experiencias = scrape_destino(destino_nombre, slug, args.max_paginas, session)
            insertadas = guardar_experiencias(experiencias, args.db)
            total_experiencias += insertadas
            destinos_ok += 1
            print(f"✓ {len(experiencias)} encontradas, {insertadas} nuevas")
        except Exception as e:
            destinos_error += 1
            print(f"✗ Error: {e}")
            logger.error("Error procesando %s: %s", destino_nombre, e)

        # Pausa entre destinos
        if i < len(destinos):
            pausa = random.uniform(2, 4)
            time.sleep(pausa)

    # Resumen
    elapsed = time.time() - start_time

    # Contar total en BD
    try:
        conn = sqlite3.connect(args.db)
        total_bd = conn.execute("SELECT COUNT(*) FROM experiencias_reales").fetchone()[0]
        conn.close()
    except Exception:
        total_bd = "?"

    print(f"\n{'='*60}")
    print(f"  RESUMEN SCRAPING CIVITATIS")
    print(f"{'='*60}")
    print(f"  Destinos procesados: {destinos_ok}/{len(destinos)}")
    print(f"  Destinos con error: {destinos_error}")
    print(f"  Experiencias nuevas insertadas: {total_experiencias}")
    print(f"  Total en tabla experiencias_reales: {total_bd}")
    print(f"  Tiempo total: {elapsed/60:.1f} minutos")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
