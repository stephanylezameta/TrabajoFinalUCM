"""
Scraping dirigido y puntual solo para 'Sevilla' -- el unico destino de
'experiencias' sin reseñas reales (38/39 cubiertos, ver DECISION-021).
Reutiliza las funciones ya probadas de run_bulk_scraping.py.

Se incluyen variantes de busqueda para maximizar cobertura, ya que
"Sevilla" nunca se habia scrapeado antes en ninguna corrida previa.

Uso:
    cd TFM
    python scripts/scrape_sevilla.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_bulk_scraping import (
    ejecutar_scraper, get_existing_hashes, get_total_resenas,
    deduplicar_bd_final, DATABASE_PATH,
)

# Sin google_maps: pausado por bajo rendimiento (ver sesion anterior)
FUENTES_SEVILLA = ["tripadvisor", "reddit", "reddit_arctic", "youtube"]

TERMINOS_SEVILLA = ["Sevilla", "Sevilla España", "Sevilla turismo", "Sevilla Andalucia"]

def main():
    hashes = get_existing_hashes(DATABASE_PATH)
    total_inicio = get_total_resenas(DATABASE_PATH)
    print(f"Reseñas al inicio: {total_inicio}")

    total_nuevas = 0
    for termino in TERMINOS_SEVILLA:
        for fuente in FUENTES_SEVILLA:
            print(f"\n--- {fuente.upper()} | '{termino}' ---")
            try:
                nuevas = ejecutar_scraper(fuente, termino, hashes)
                total_nuevas += nuevas
                print(f"  +{nuevas} nuevas")
            except Exception as e:
                print(f"  Error en {fuente}: {e}")

    eliminados = deduplicar_bd_final(DATABASE_PATH)

    print(f"\n--- Normalizando destino_nombre a 'Sevilla' ---")
    import sqlite3
    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()
    normalizados = 0
    for termino in TERMINOS_SEVILLA:
        if termino == "Sevilla":
            continue
        cur.execute(
            "UPDATE resenas SET destino_nombre = 'Sevilla' WHERE destino_nombre = ?",
            (termino,),
        )
        normalizados += cur.rowcount
    conn.commit()
    conn.close()
    print(f"  {normalizados} reseñas normalizadas a 'Sevilla'")

    total_final = get_total_resenas(DATABASE_PATH)

    print(f"\n{'='*50}")
    print(f"  SCRAPING SEVILLA COMPLETADO")
    print(f"{'='*50}")
    print(f"  Nuevas: {total_nuevas} | Duplicados eliminados: {eliminados}")
    print(f"  Total en BD: {total_final}")
    print(f"{'='*50}\n")

if __name__ == "__main__":
    main()