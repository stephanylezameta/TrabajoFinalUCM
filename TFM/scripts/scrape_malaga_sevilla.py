"""
Script para obtener reseñas de Málaga y Sevilla con pausas más largas
para evitar rate limiting de Pullpush.io API.
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

# Queries con variaciones para evitar duplicados
DESTINOS_QUERIES = {
    "Málaga": [
        {"q": "Malaga Spain travel", "subreddit": "travel", "size": 100},
        {"q": "Malaga beach vacation", "subreddit": "solotravel", "size": 100},
        {"q": "Malaga tourism guide", "subreddit": "europe", "size": 100},
        {"q": "Malaga food culture", "subreddit": "travel", "size": 100},
        {"q": "Costa del Sol Malaga", "subreddit": "travel", "size": 100},
        {"q": "Malaga Andalucia trip", "subreddit": "solotravel", "size": 100},
        {"q": "Malaga Picasso museum", "subreddit": "europe", "size": 100},
        {"q": "Malaga nightlife bars", "subreddit": "travel", "size": 100},
    ],
    "Sevilla": [
        {"q": "Seville Spain travel", "subreddit": "travel", "size": 100},
        {"q": "Sevilla turismo", "subreddit": "europe", "size": 100},
        {"q": "Seville flamenco culture", "subreddit": "solotravel", "size": 100},
        {"q": "Seville Alcazar cathedral", "subreddit": "travel", "size": 100},
        {"q": "Seville Andalusia trip", "subreddit": "travel", "size": 100},
        {"q": "Seville food tapas bars", "subreddit": "solotravel", "size": 100},
        {"q": "Seville Spain itinerary", "subreddit": "europe", "size": 100},
        {"q": "Seville weather summer", "subreddit": "travel", "size": 100},
    ],
}

HEADERS = {'User-Agent': 'TFM_UCM_Academic_Research/1.0'}
PAUSA_ENTRE_QUERIES = 8  # Longer pause to avoid rate limiting


def generar_id_resena(texto):
    return hashlib.md5(texto[:200].encode()).hexdigest()


def buscar_pullpush(query, subreddit, size=100):
    params = {
        "q": query,
        "subreddit": subreddit,
        "size": size,
        "sort": "desc",
        "sort_type": "score",
    }
    try:
        resp = requests.get(PULLPUSH_URL, params=params, headers=HEADERS, timeout=30)
        if resp.status_code == 429:
            print(f"    Rate limited! Esperando 30s...")
            time.sleep(30)
            resp = requests.get(PULLPUSH_URL, params=params, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            print(f"    HTTP {resp.status_code}")
            return []
        data = resp.json()
        return data.get("data", [])
    except Exception as e:
        print(f"    Error: {e}")
        return []


def main():
    print("=" * 60)
    print("SCRAPING PULLPUSH.IO — Malaga y Sevilla (con pausas largas)")
    print("=" * 60)

    conn = sqlite3.connect(str(DB_PATH))
    total_insertados = 0
    resumen = {}

    for destino, queries in DESTINOS_QUERIES.items():
        print(f"\n--- {destino} ---")
        insertados_destino = 0
        ids_vistos = set()

        # Load existing IDs for this destination to avoid re-inserts
        existing = conn.execute(
            "SELECT id_resena FROM resenas WHERE destino_nombre = ?", (destino,)
        ).fetchall()
        ids_vistos = {r[0] for r in existing}
        print(f"  IDs existentes: {len(ids_vistos)}")

        for query_params in queries:
            q = query_params["q"]
            sub = query_params["subreddit"]
            size = query_params.get("size", 100)
            
            print(f"  Buscando: '{q}' en r/{sub}...")
            posts = buscar_pullpush(q, sub, size)
            
            insertados_query = 0
            for post in posts:
                titulo = post.get("title", "")
                selftext = post.get("selftext", "")
                texto = (titulo + " " + selftext).strip()
                
                if len(texto) < 50:
                    continue
                if "[removed]" in texto or "[deleted]" in texto:
                    continue
                
                id_resena = generar_id_resena(texto)
                if id_resena in ids_vistos:
                    continue
                ids_vistos.add(id_resena)
                
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
                    insertados_query += 1
                except sqlite3.IntegrityError:
                    pass
            
            conn.commit()
            insertados_destino += insertados_query
            print(f"    -> {insertados_query} nuevas resenas")
            
            # Long pause between queries
            print(f"    Pausa {PAUSA_ENTRE_QUERIES}s...")
            time.sleep(PAUSA_ENTRE_QUERIES)

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
