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


def cargar_sentimiento_por_destino(conn: sqlite3.Connection) -> dict:
    """Sentimiento real agregado por destino (media del score de resenas_sentimiento)."""
    try:
        rows = conn.execute("""
            SELECT r.destino_nombre, AVG(s.sentiment_score)
            FROM resenas r
            JOIN resenas_sentimiento s ON r.id_resena = s.id_resena
            GROUP BY r.destino_nombre
        """).fetchall()
        return {destino: score for destino, score in rows}
    except Exception as e:
        logger.warning("No se pudo cargar sentimiento por destino: %s", e)
        return {}


def cargar_ocupacion_por_destino(conn: sqlite3.Connection) -> dict:
    """Ocupación real agregada por destino (indicadores_destino, Eurostat/INE)."""
    try:
        rows = conn.execute("""
            SELECT destino_nombre, AVG(valor)
            FROM indicadores_destino
            WHERE tipo_indicador = 'ocupacion_hotelera_mensual'
            GROUP BY destino_nombre
        """).fetchall()
        valores = {destino: val for destino, val in rows}
        if valores:
            vmin, vmax = min(valores.values()), max(valores.values())
            if vmax > vmin:
                valores = {d: (v - vmin) / (vmax - vmin) for d, v in valores.items()}
        return valores
    except Exception as e:
        logger.warning("No se pudo cargar ocupación por destino: %s", e)
        return {}


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
    parser.add_argument("--modelo", default="intfloat/multilingual-e5-large",
                         choices=["paraphrase-multilingual-MiniLM-L12-v2",
                                  "intfloat/multilingual-e5-large"],
                         help="Modelo de embeddings a usar")
    parser.add_argument("--sufijo", default=None,
                         help="Sufijo para los archivos de salida (ej. '_e5large'). "
                              "Si no se especifica, sobreescribe los archivos por defecto "
                              "(hybrid_vectors.npy, etc.) -- usar con cuidado.")
    args = parser.parse_args()

    start = time.time()

    output_dir = Path("data/embeddings")
    output_dir.mkdir(parents=True, exist_ok=True)
    sufijo = args.sufijo or ""

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

    logger.info("Cargando sentimiento real y ocupación real por destino...")
    sentimiento_por_destino = cargar_sentimiento_por_destino(conn)
    ocupacion_por_destino = cargar_ocupacion_por_destino(conn)
    logger.info("  -> sentimiento real: %d destinos | ocupación real: %d destinos",
                len(sentimiento_por_destino), len(ocupacion_por_destino))
    conn.close()

    logger.info("Inicializando TextEmbedder (%s)...", args.modelo)
    embedder = TextEmbedder(model_name=args.modelo)
    es_e5 = "e5" in args.modelo.lower()
    prefijo_e5 = "query: " if es_e5 else ""
    # e5-large es mucho más pesado que MiniLM; reducimos el batch interno
    # para no saturar la memoria RAM en textos largos (hasta 2000 caracteres).
    batch_size = 8 if es_e5 else 64
    aggregator = ReviewAggregator()
    fuser = SemanticFuser(package_weight=0.6, review_weight=0.4)
    builder = HybridVectorBuilder()

    logger.info("Generando embeddings de reseñas por destino...")
    review_embeddings_by_destino = {}
    for destino, textos in resenas_por_destino.items():
        textos_batch = [f"{prefijo_e5}{t}" for t in textos[:50]] if prefijo_e5 else textos[:50]
        embs = embedder.embed_batch(textos_batch, batch_size=batch_size)
        review_embeddings_by_destino[destino] = aggregator.aggregate(embs)
    logger.info("  -> %d destinos con embeddings de reseñas", len(review_embeddings_by_destino))

    all_review_embs = list(review_embeddings_by_destino.values())
    default_review_emb = np.mean(all_review_embs, axis=0) if all_review_embs else np.zeros(embedder.embedding_dim)

    logger.info("Generando embeddings de experiencias...")
    textos_experiencias = [
        f"{prefijo_e5}{e['activity_name']} {e['destination']} {e['category']}"
        for e in experiencias
    ]
    package_embeddings = embedder.embed_batch(textos_experiencias, batch_size=batch_size)
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

        # nivel_ocupacion: real cuando hay dato de indicadores_destino
        # (Eurostat/INE), si no, neutro (0.5).
        # estrellas_hotel_norm: mezcla 50/50 entre el rating sintético de
        # 'experiencias' y el sentimiento real agregado de reseñas reales
        # del destino (cuando existe). Sustituye el placeholder anterior.
        rating_sintetico = norm(e["rating"], rating_min, rating_max)
        sentimiento_real = sentimiento_por_destino.get(e["destination"])
        if sentimiento_real is not None:
            estrellas_final = 0.5 * rating_sintetico + 0.5 * sentimiento_real
        else:
            estrellas_final = rating_sintetico

        attrs = {
            "precio_base_eur_norm": norm(e["price_eur"], precio_min, precio_max),
            "duracion_dias_norm": norm(e["duration_hrs"], dur_min, dur_max),
            "nivel_ocupacion": ocupacion_por_destino.get(e["destination"], 0.5),
            "accesibilidad_destino_norm": 0.5,
            "estrellas_hotel_norm": estrellas_final,
            "num_valoraciones_hotel_norm": norm(e["review_count"], rc_min, rc_max),
            "indicador_sostenibilidad_tui": 0.0,
        }

        hybrid = builder.build(fused, attrs)
        hybrid_vectors.append(hybrid)
        experiencia_ids.append(e["experience_id"])

    hybrid_matrix = np.array(hybrid_vectors, dtype=np.float32)

    np.save(output_dir / f"hybrid_vectors{sufijo}.npy", hybrid_matrix)
    np.save(output_dir / f"paquete_ids{sufijo}.npy", np.array(experiencia_ids))
    np.save(output_dir / f"package_embeddings{sufijo}.npy", package_embeddings)

    elapsed = time.time() - start

    print(f"\n{'='*60}")
    print(f"  EMBEDDINGS GENERADOS ({args.modelo})")
    print(f"{'='*60}")
    print(f"  Experiencias procesadas: {len(experiencias)}")
    print(f"  Destinos con reseñas:    {len(review_embeddings_by_destino)}")
    print(f"  Dimensión embedding:     {embedder.embedding_dim}")
    print(f"  Dimensión híbrido:       {hybrid_matrix.shape[1]} (={embedder.embedding_dim}+7)")
    print(f"  Ficheros guardados:      hybrid_vectors{sufijo}.npy, paquete_ids{sufijo}.npy, package_embeddings{sufijo}.npy")
    print(f"  Tiempo total:            {elapsed:.1f} segundos")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()