"""
Compara paraphrase-multilingual-MiniLM-L12-v2 vs multilingual-e5-large
sobre un corpus piloto, segun el criterio de DECISION-006 del informe
tecnico: el modelo que produzca mayor similitud coseno promedio entre
experiencias del MISMO destino y categoria (coherencia de clusters) gana.

Uso:
    cd TFM
    python scripts/comparar_modelos_embeddings.py
    python scripts/comparar_modelos_embeddings.py --n-muestra 100
"""
import argparse
import sqlite3
import sys
import time
import logging
import random
import numpy as np
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MODELOS = {
    "MiniLM": "paraphrase-multilingual-MiniLM-L12-v2",
    "e5-large": "intfloat/multilingual-e5-large",
}


def cargar_muestra(conn: sqlite3.Connection, n: int) -> list[dict]:
    rows = conn.execute("""
        SELECT experience_id, activity_name, category, destination
        FROM experiencias
        ORDER BY RANDOM()
        LIMIT ?
    """, (n,)).fetchall()
    return [
        {"id": r[0], "texto": f"{r[1]} {r[3]} {r[2]}", "destino": r[3], "categoria": r[2]}
        for r in rows
    ]


def coherencia_clusters(embeddings: np.ndarray, items: list[dict]) -> float:
    """Similitud coseno promedio entre pares del mismo (destino, categoria)."""
    grupos = defaultdict(list)
    for i, item in enumerate(items):
        grupos[(item["destino"], item["categoria"])].append(i)

    # Normalizar para que el coseno sea un simple producto punto
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    emb_norm = embeddings / norms

    similitudes = []
    for indices in grupos.values():
        if len(indices) < 2:
            continue
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                sim = float(np.dot(emb_norm[indices[i]], emb_norm[indices[j]]))
                similitudes.append(sim)

    return float(np.mean(similitudes)) if similitudes else 0.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/tui_recomendador.db")
    parser.add_argument("--n-muestra", type=int, default=100,
                         help="Tamaño del corpus piloto (default: 100, según informe)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)

    db_path = Path(args.db)
    if not db_path.exists():
        logger.error("No se encontró la base de datos en %s", db_path)
        return

    conn = sqlite3.connect(str(db_path))
    muestra = cargar_muestra(conn, args.n_muestra)
    conn.close()

    if not muestra:
        logger.error("No se pudo cargar la muestra desde 'experiencias'.")
        return

    logger.info("Corpus piloto: %d experiencias", len(muestra))
    n_grupos = len(set((m["destino"], m["categoria"]) for m in muestra))
    logger.info("Grupos (destino+categoria) distintos: %d", n_grupos)

    from sentence_transformers import SentenceTransformer

    resultados = {}
    for nombre, model_id in MODELOS.items():
        logger.info("Cargando modelo %s (%s)...", nombre, model_id)
        t0 = time.time()
        model = SentenceTransformer(model_id)

        textos = [m["texto"] for m in muestra]
        if nombre == "e5-large":
            # e5 requiere el prefijo "query: " para embeddings de buena calidad
            # (documentado por el autor del modelo). Sin esto, el rendimiento
            # de e5 se ve artificialmente peor, no por ser el modelo inferior.
            textos = [f"query: {t}" for t in textos]
        embeddings = model.encode(textos, show_progress_bar=False, convert_to_numpy=True)

        coherencia = coherencia_clusters(embeddings, muestra)
        elapsed = time.time() - t0

        resultados[nombre] = {
            "coherencia": coherencia,
            "dim": embeddings.shape[1],
            "tiempo_s": elapsed,
        }
        logger.info("  -> %s: coherencia=%.4f, dim=%d, tiempo=%.1fs",
                    nombre, coherencia, embeddings.shape[1], elapsed)

        del model  # liberar memoria antes de cargar el siguiente

    ganador = max(resultados, key=lambda k: resultados[k]["coherencia"])

    print(f"\n{'='*60}")
    print(f"  COMPARACIÓN DE MODELOS DE EMBEDDINGS (DECISIÓN-006)")
    print(f"{'='*60}")
    for nombre, r in resultados.items():
        marca = " <-- GANADOR" if nombre == ganador else ""
        print(f"  {nombre}: coherencia={r['coherencia']:.4f} | dim={r['dim']} | "
              f"tiempo={r['tiempo_s']:.1f}s{marca}")
    print(f"{'='*60}")
    print(f"  Criterio (informe): mayor similitud coseno intra-cluster gana.")
    print(f"  Modelo recomendado: {ganador}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
