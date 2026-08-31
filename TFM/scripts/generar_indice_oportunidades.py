"""
Construye un indice de embeddings sobre las reseñas reales de destinos
que NO estan en el catalogo vendible (experiencias, 39 destinos), para
poder detectar "destinos oportunidad" por contenido semantico real de
la consulta, en vez de solo por coincidencia literal del nombre
(version v1 actual en detectar_oportunidades(), documentada como
limitada en la memoria tecnica).

No se conecta todavia al flujo de recomendar() -- este script solo
construye el indice (tarea larga, pensada para dejar corriendo sin
supervision). Conectarlo es un paso rapido para la proxima sesion.

Uso:
    cd TFM
    python scripts/generar_indice_oportunidades.py
"""
import re
import sqlite3
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, ".")
from src.embeddings.text_embedder import TextEmbedder

DB_PATH = "data/tui_recomendador.db"
OUTPUT_DIR = Path("data/oportunidades")
MIN_RESENAS_POR_DESTINO = 5
MAX_RESENAS_POR_DESTINO = 50  # tope para no eternizar el embebido de un destino con muchas reseñas

# Palabras que indican que el "destino_nombre" en realidad es un
# resto de termino de busqueda del scraping (ver hallazgo documentado
# en la memoria tecnica, seccion 10.16), no un destino real -- se
# descartan para no ensuciar el indice.
PALABRAS_SOSPECHOSAS = [
    "opiniones", "review", "holiday", "vacation", "experience", "experiencia",
    "hotel", "beach", "family", "resort", " vs ", "mejor ", "todo incluido",
    "barato", "turismo", "travel", "tips", "guide", "reise", "urlaub",
]


def es_destino_sospechoso(nombre: str) -> bool:
    nombre_lower = nombre.lower()
    return any(p in nombre_lower for p in PALABRAS_SOSPECHOSAS)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    conn = sqlite3.connect(DB_PATH)
    destinos_catalogo = {
        r[0] for r in conn.execute("SELECT DISTINCT destination FROM experiencias").fetchall()
    }
    rows = conn.execute(
        "SELECT destino_nombre, texto_original FROM resenas WHERE texto_original IS NOT NULL"
    ).fetchall()
    conn.close()

    print(f"1) Filtrando destinos fuera del catalogo (de {len(rows)} reseñas totales)...")
    resenas_por_destino = defaultdict(list)
    for destino, texto in rows:
        if not destino or destino in destinos_catalogo:
            continue
        if es_destino_sospechoso(destino):
            continue
        if texto and len(texto.strip()) > 20:
            resenas_por_destino[destino].append(texto)

    destinos_validos = {
        d: textos for d, textos in resenas_por_destino.items()
        if len(textos) >= MIN_RESENAS_POR_DESTINO
    }
    print(f"   -> {len(destinos_validos)} destinos con al menos {MIN_RESENAS_POR_DESTINO} "
          f"reseñas reales, fuera del catalogo y sin nombre sospechoso")

    print("2) Cargando modelo de embeddings (e5-large, mismo del catalogo)...")
    embedder = TextEmbedder(model_name="intfloat/multilingual-e5-large")

    print("3) Generando embeddings agregados por destino...")
    nombres_destinos = []
    embeddings_destinos = []
    for i, (destino, textos) in enumerate(destinos_validos.items(), 1):
        textos_batch = [f"passage: {t[:2000]}" for t in textos[:MAX_RESENAS_POR_DESTINO]]
        embs = embedder.embed_batch(textos_batch, batch_size=8)
        embedding_promedio = embs.mean(axis=0)
        nombres_destinos.append(destino)
        embeddings_destinos.append(embedding_promedio)
        if i % 20 == 0:
            print(f"   -> {i}/{len(destinos_validos)} destinos procesados")

    matriz = np.array(embeddings_destinos, dtype=np.float32)
    np.save(OUTPUT_DIR / "oportunidades_embeddings.npy", matriz)
    np.save(OUTPUT_DIR / "oportunidades_nombres.npy", np.array(nombres_destinos))

    elapsed = time.time() - t0
    print(f"\n{'='*55}")
    print(f"  INDICE DE OPORTUNIDADES GENERADO")
    print(f"{'='*55}")
    print(f"  Destinos indexados: {len(nombres_destinos)}")
    print(f"  Dimension: {matriz.shape[1]}")
    print(f"  Guardado en: {OUTPUT_DIR}/")
    print(f"  Tiempo total: {elapsed/60:.1f} minutos")
    print(f"{'='*55}\n")
    print("Pendiente para la proxima sesion: conectar este indice a")
    print("detectar_oportunidades() en run_recommendation.py, comparando")
    print("el embedding de la consulta (con prefijo 'query: ') contra")
    print("esta matriz por similitud de coseno, en vez de la coincidencia")
    print("literal de nombre que usa la version v1 actual.")


if __name__ == "__main__":
    main()