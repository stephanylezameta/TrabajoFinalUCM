"""
Script para obtener reseñas/posts de Madrid, Málaga y Sevilla
usando la API de Pullpush.io (sucesor de Pushshift para Reddit).

API gratuita, sin autenticación requerida.
"""
import hashlib
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "tui_recomendador.db"
PULLPUSH_URL = "https://api.pullpush.io/reddit/search/submission/"

# Destinos con múltiples queries para obtener variedad
DESTINOS_QUERIES = {
    "Madrid": [
        {"q": "Madrid travel tips", "subreddit": "travel"},
        {"q": "Madrid vacation", "subreddit": "travel"},
        {"q": "Madrid tourism", "subreddit": "solotravel"},
        {"q": "Madrid trip", "subreddit": "solotravel"},
        {"q": "Madrid holiday", "subreddit": "europe"},
        {"q": "Madrid things to do", "subreddit": "travel"},
        {"q": "Madrid itinerary", "subreddit": "travel"},
        {"q": "Madrid spain travel", "subreddit": "backpacking"},
        {"q": "visiting Madrid", "subreddit": "travel"},
        {"q": "Madrid recommendations", "subreddit": "solotravel"},
        {"q": "Madrid food restaurants", "subreddit": "travel"},
        {"q": "Madrid nightlife", "subreddit": "solotravel"},
        {"q": "Madrid neighborhood", "subreddit": "travel"},
        {"q": "Madrid museum art", "subreddit": "travel"},
        {"q": "Madrid day trips", "subreddit": "travel"},
    ],
    "Málaga": [
        {"q": "Malaga travel tips", "subreddit": "travel"},
        {"q": "Malaga vacation beach", "subreddit": "travel"},
        {"q": "Malaga tourism", "subreddit": "solotravel"},
        {"q": "Malaga trip spain", "subreddit": "europe"},
        {"q": "Malaga holiday", "subreddit": "travel"},
        {"q": "Malaga things to do", "subreddit": "travel"},
        {"q": "Malaga itinerary", "subreddit": "solotravel"},
        {"q": "Malaga costa del sol", "subreddit": "travel"},
        {"q": "visiting Malaga", "subreddit": "travel"},
        {"q": "Malaga recommendations", "subreddit": "europe"},
        {"q": "Malaga food tapas", "subreddit": "travel"},
        {"q": "Malaga beach", "subreddit": "travel"},
        {"q": "Malaga day trips", "subreddit": "solotravel"},
        {"q": "Malaga old town", "subreddit": "travel"},
        {"q": "Malaga Picasso", "subreddit": "travel"},
    ],
    "Sevilla": [
        {"q": "Seville travel tips", "subreddit": "travel"},
        {"q": "Seville vacation", "subreddit": "travel"},
        {"q": "Seville tourism", "subreddit": "solotravel"},
        {"q": "Seville trip spain", "subreddit": "europe"},
        {"q": "Seville holiday", "subreddit": "travel"},
        {"q": "Seville things to do", "subreddit": "travel"},
        {"q": "Seville itinerary", "subreddit": "solotravel"},
        {"q": "Seville Sevilla", "subreddit": "travel"},
        {"q": "visiting Seville", "subreddit": "travel"},
        {"q": "Seville recommendations", "subreddit": "europe"},
        {"q": "Seville flamenco", "subreddit": "travel"},
        {"q": "Seville Alcazar", "subreddit": "travel"},
        {"q": "Seville food tapas", "subreddit": "solotravel"},
        {"q": "Seville day trips", "subreddit": "travel"},
        {"q": "Seville neighborhoods", "subreddit": "travel"},
    ],
}

HEADERS = {'User-Agent': 'TFM_UCM_Research/1.0 (academic project)'}


def generar_id_resena(texto: str) -> str:
    """Genera un ID determinista basado en el contenido del texto."""
    return hashlib.md5(texto[:200].encode()).hexdigest()


def buscar_pullpush(query: str, subreddit: str, size: int = 100) -> list[dict]:
    """Busca posts en Pullpush.io API."""
    params = {
        "q": query,
        "subreddit": subreddit,
        "size": size,
        "sort": "desc",
        "sort_type": "score",
    }
    try:
        resp = requests.get(PULLPUSH_URL, params=params, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            return []
        data = resp.json()
        return data.get("data", [])
    except Exception as e:
        print(f"    Error: {e}")
        return []


def main():
    print("=" * 60)
    print("SCRAPING PULLPUSH.IO — Madrid, Málaga, Sevilla")
    print("=" * 60)
    print(f"Base de datos: {DB_PATH}")
    print(f"API: {PULLPUSH_URL}")
    print()

    conn = sqlite3.connect(str(DB_PATH))
    total_insertados = 0
    resumen = {}

    for destino, queries in DESTINOS_QUERIES.items():
        print(f"\n--- {destino} ---")
        insertados_destino = 0
        ids_vistos = set()

        for query_params in queries:
            q = query_params["q"]
            sub = query_params["subreddit"]
            print(f"  Buscando: '{q}' en r/{sub}...")
            
            posts = buscar_pullpush(q, sub, size=100)
            
            insertados_query = 0
            for post in posts:
                titulo = post.get("title", "")
                selftext = post.get("selftext", "")
                texto = (titulo + " " + selftext).strip()
                
                # Filtrar textos muy cortos o eliminados
                if len(texto) < 50:
                    continue
                if "[removed]" in texto or "[deleted]" in texto:
                    continue
                
                id_resena = generar_id_resena(texto)
                
                # Evitar duplicados dentro de la misma ejecución
                if id_resena in ids_vistos:
                    continue
                ids_vistos.add(id_resena)
                
                # Extraer metadata
                fecha_pub = None
                created_utc = post.get("created_utc")
                if created_utc:
                    try:
                        fecha_pub = datetime.fromtimestamp(int(created_utc)).strftime("%Y-%m-%d")
                    except (ValueError, TypeError, OSError):
                        pass
                
                permalink = post.get("permalink", "")
                url_fuente = f"https://reddit.com{permalink}" if permalink else None
                
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO resenas
                        (id_resena, destino_nombre, fuente, texto_original, idioma,
                         fecha_publicacion, url_fuente, fecha_extraccion)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        id_resena, destino, "reddit", texto, "en",
                        fecha_pub, url_fuente, datetime.now().isoformat()
                    ))
                    if conn.total_changes:
                        insertados_query += 1
                except sqlite3.IntegrityError:
                    pass
            
            conn.commit()
            insertados_destino += insertados_query
            print(f"    -> {insertados_query} nuevas resenas")
            time.sleep(3)  # Pausa entre queries para no saturar API

        total_insertados += insertados_destino
        resumen[destino] = insertados_destino
        print(f"  Total {destino}: {insertados_destino} resenas insertadas")

    conn.close()

    print()
    print("=" * 60)
    print("RESUMEN")
    print("=" * 60)
    for dest, n in resumen.items():
        print(f"  {dest}: {n} resenas nuevas")
    print(f"  TOTAL: {total_insertados} resenas nuevas")
    print("=" * 60)


if __name__ == "__main__":
    main()
