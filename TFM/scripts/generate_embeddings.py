"""
Script para generar embeddings del catalogo completo.

Fix (15/08): el script apuntaba a la tabla 'paquetes' (nunca poblada,
el scraping real de TUI esta bloqueado por CloudFront) y a una ruta
hardcodeada de un usuario especifico. Ahora usa la tabla 'experiencias'
(poblada por el dataset sintetico compartido por TUI, 5850 registros)
y una ruta de base de datos configurable via argumento.

Uso:
    cd TFM
    python scripts/generate_embeddings.py
    python scripts/generate_embeddings.py --db data/tui_recomendador.db
"""
import argparse
import sys
import time
import sqlite3
import logging
import numpy as np
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.embeddings.text_embedder import TextEmbedder
from src.embeddings.review_aggregator import ReviewAggregator
from src.embeddings.semantic_fuser import SemanticFuser
from src.embeddings.hybrid_vector_builder import HybridVectorBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def cargar_experiencias(conn: sqlite3.Connection) -> list[dict]:
    """Carga el catalogo de experiencias (reemplaza a la vieja tabla paquetes)."""
    rows = conn.execute(
        "SELECT experience_id, activity_name, category, destination, "
        "duration_hrs, price_eur, rating, review_count "
        "FROM experiencias"
    ).fetchall()
    cols = ["experience_id", "activity_name", "category", "destination",
            "duration_hrs", "price_eur", "rating", "review_count"]
    return [dict(zip(cols, r)) for r in rows]


def cargar_resenas_reales(conn: sqlite3.Connection) -> dict:
    """Reseñas reales scrapeadas (tabla resenas), agrupadas por destino."""
    resenas_por_destino = defaultdict(list)
    try:
        rows = conn.execute(
            "SELECT destino_nombre, texto_original FROM resenas "
            "WHERE texto_original IS NOT NULL"
        ).fetchall()
        for destino, texto in rows:
            if texto and len(texto.strip()) > 20:
                resenas_por_destino[destino].append(texto)
        logger.info("  -> %d reseñas reales cargadas (%d destinos)",
                    sum(len(v) for v in resenas_por_destino.values()),
                    len(resenas_por_destino))
    except Exception as e:
        logger.warning("No se pudieron cargar reseñas reales: %s", e)
    return resenas_por_destino


def cargar_reviews_sinteticas(conn: sqlite3.Connection) -> dict:
    """Reviews sintéticas (reviews_dataset), agrupadas por destino via experiencias."""
    resenas_por_destino = defaultdict(list)
    try:
        rows = conn.execute(
            "SELECT e.destination, r.review_text "
            "FROM reviews_dataset r "
            "JOIN experiencias e ON r.experience_id = e.experience_id "
            "WHERE r.review_text IS NOT NULL"
        ).fetchall()
        for destino, texto in rows:
            if texto and len(texto.strip()) > 20:
                resenas_por_destino[destino].append(texto)
        logger.info("  -> %d reviews sintéticas cargadas (%d destinos)",
                    sum(len(v) for v in resenas_por_destino.values()),
                    len(resenas_por_destino))
    except Exception as e:
        logger.warning("No se pudieron cargar reviews sintéticas: %s", e)
    return resenas_por_destino


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/tui_recomendador.db",
                         help="Ruta a la base de datos unificada")
    args = parser.parse_args()

    start = time.time()

    output_dir = Path("data/embeddings")
    output_dir.mkdir(parents=True, exist_ok=True)

    db_path = Path(args.db)
    if not db_path.exists():
        logger.error("No se encontró la base de datos en %s", db_path)
        return

    conn = sqlite3.connect(str(db_path))

    logger.info("Cargando experiencias de %s...", db_path)
    experiencias = cargar_experiencias(conn)
    if not experiencias:
        logger.error("⚠️ La tabla 'experiencias' está vacía. No se pueden generar embeddings.")
        conn.close()
        return
    logger.info("  -> %d experiencias cargadas", len(experiencias))

    logger.info("Cargando reseñas...")
    resenas_por_destino = defaultdict(list)
    for destino, textos in cargar_resenas_reales(conn).items():
        resenas_por_destino[destino].extend(textos)
    for destino, textos in cargar_reviews_sinteticas(conn).items():
        resenas_por_destino[destino].extend(textos)
    conn.close()

    logger.info("Inicializando TextEmbedder (MiniLM)...")
    embedder = TextEmbedder()
    aggregator = ReviewAggregator()
    fuser = SemanticFuser(package_weight=0.6, review_weight=0.4)
    builder = HybridVectorBuilder()

    logger.info("Generando embeddings de reseñas por destino...")
    review_embeddings_by_destino = {}
    for destino, textos in resenas_por_destino.items():
        embs = embedder.embed_batch(textos[:50])
        review_embeddings_by_destino[destino] = aggregator.aggregate(embs)
    logger.info("  -> %d destinos con embeddings de reseñas", len(review_embeddings_by_destino))

    all_review_embs = list(review_embeddings_by_destino.values())
    default_review_emb = np.mean(all_review_embs, axis=0) if all_review_embs else np.zeros(embedder.embedding_dim)

    logger.info("Generando embeddings de experiencias...")
    textos_experiencias = [
        f"{e['activity_name']} {e['destination']} {e['category']}"
        for e in experiencias
    ]
    package_embeddings = embedder.embed_batch(textos_experiencias)
    if len(package_embeddings) == 0:
        logger.warning("⚠️ No hay embeddings de experiencias disponibles.")
        return
    logger.info("  -> %d embeddings generados (dim=%d)", len(package_embeddings), package_embeddings.shape[1])

    logger.info("Fusionando embeddings y construyendo vectores híbridos...")

    precios = [e["price_eur"] for e in experiencias if e["price_eur"]]
    duraciones = [e["duration_hrs"] for e in experiencias if e["duration_hrs"]]
    ratings = [e["rating"] for e in experiencias if e["rating"]]
    reviews_count = [e["review_count"] for e in experiencias if e["review_count"]]

    precio_min, precio_max = (min(precios), max(precios)) if precios else (0, 1)
    dur_min, dur_max = (min(duraciones), max(duraciones)) if duraciones else (1, 14)
    rating_min, rating_max = 1.0, 5.0
    rc_min, rc_max = (min(reviews_count), max(reviews_count)) if reviews_count else (0, 1)

    def norm(val, vmin, vmax):
        if vmax == vmin or val is None:
            return 0.5
        return (val - vmin) / (vmax - vmin)

    hybrid_vectors = []
    experiencia_ids = []

    for i, e in enumerate(experiencias):
        pkg_emb = package_embeddings[i]
        review_emb = review_embeddings_by_destino.get(e["destination"], default_review_emb)
        fused = fuser.fuse(pkg_emb, review_emb)

        # NOTA: nivel_ocupacion / accesibilidad / sostenibilidad no existen aun
        # en 'experiencias'; quedan en 0.5 (neutro) hasta cruzar con
        # indicadores_destino (ya poblado, 3342 registros) - pendiente.
        attrs = {
            "precio_base_eur_norm": norm(e["price_eur"], precio_min, precio_max),
            "duracion_dias_norm": norm(e["duration_hrs"], dur_min, dur_max),
            "nivel_ocupacion": 0.5,
            "accesibilidad_destino_norm": 0.5,
            "estrellas_hotel_norm": norm(e["rating"], rating_min, rating_max),
            "num_valoraciones_hotel_norm": norm(e["review_count"], rc_min, rc_max),
            "indicador_sostenibilidad_tui": 0.0,
        }

        hybrid = builder.build(fused, attrs)
        hybrid_vectors.append(hybrid)
        experiencia_ids.append(e["experience_id"])

    hybrid_matrix = np.array(hybrid_vectors, dtype=np.float32)

    np.save(output_dir / "hybrid_vectors.npy", hybrid_matrix)
    np.save(output_dir / "paquete_ids.npy", np.array(experiencia_ids))
    np.save(output_dir / "package_embeddings.npy", package_embeddings)

    elapsed = time.time() - start

    print(f"\n{'='*60}")
    print(f"  EMBEDDINGS GENERADOS")
    print(f"{'='*60}")
    print(f"  Experiencias procesadas: {len(experiencias)}")
    print(f"  Destinos con reseñas:    {len(review_embeddings_by_destino)}")
    print(f"  Dimensión embedding:     {embedder.embedding_dim}")
    print(f"  Dimensión híbrido:       {hybrid_matrix.shape[1]} (={embedder.embedding_dim}+7)")
    print(f"  Ficheros guardados en data/embeddings/")
    print(f"  Tiempo total:            {elapsed:.1f} segundos")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()