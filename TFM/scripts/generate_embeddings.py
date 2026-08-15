"""
Script para generar embeddings del catálogo completo.

Uso:
    cd /d D:/Master/TrabajoFinalUCM/TFM
    python scripts/generate_embeddings.py
"""
import sys
import time
import logging
import numpy as np
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.repository import Repositorio
from src.embeddings.text_embedder import TextEmbedder
from src.embeddings.review_aggregator import ReviewAggregator
from src.embeddings.semantic_fuser import SemanticFuser
from src.embeddings.hybrid_vector_builder import HybridVectorBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def main():
    start = time.time()
    
    # Directorio de salida
    output_dir = Path("data/embeddings")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Cargar datos

    db_path = Path("C:/Users/mtkyg/Downloads/tui_recomendador.db")
    db_url = f"sqlite:///{db_path.as_posix()}"

    logger.info("Cargando paquetes de %s...", db_path)
    repo_paquetes = Repositorio(db_url)
    paquetes = repo_paquetes.list_paquetes(page_size=500)

    # 🛡️ AQUÍ AGREGAS LA PRIMERA PROTECCIÓN:
    if not paquetes:
        logger.error("⚠️ La tabla 'paquetes' está vacía. No se pueden generar embeddings.")
        return  # Sale sin romper todo de golpe
    logger.info("  -> %d paquetes cargados", len(paquetes))
    
    # Cargar reseñas de ambas BDs
    logger.info("Cargando reseñas...")
    import sqlite3
    
    resenas_por_destino = defaultdict(list)
    
    # Reseñas reales
    resenas_por_destino = defaultdict(list)
    db_path_str = "C:/Users/mtkyg/Downloads/tui_recomendador.db"

    try:
        conn = sqlite3.connect(db_path_str)
        rows = conn.execute("SELECT destino_nombre, texto_original FROM resenas WHERE texto_original IS NOT NULL").fetchall()
        for destino, texto in rows:
            if texto and len(texto.strip()) > 20:
                resenas_por_destino[destino].append(texto)
        conn.close()
        logger.info("  -> %d reseñas reales cargadas", sum(len(v) for v in resenas_por_destino.values()))
    except Exception as e:
        logger.warning("No se pudieron cargar reseñas reales: %s", e)
    
    # Reseñas sintéticas
    try:
        conn = sqlite3.connect("data/sample_tui.db")
        rows = conn.execute("SELECT destino_nombre, texto_original FROM resenas WHERE texto_original IS NOT NULL").fetchall()
        for destino, texto in rows:
            if texto and len(texto.strip()) > 20:
                resenas_por_destino[destino].append(texto)
        conn.close()
        logger.info("  -> %d destinos con reseñas en total", len(resenas_por_destino))
    except Exception as e:
        logger.warning("No se pudieron cargar reseñas sintéticas: %s", e)
    
    # Inicializar componentes del Bloque 2
    logger.info("Inicializando TextEmbedder (MiniLM)...")
    embedder = TextEmbedder()
    aggregator = ReviewAggregator()
    fuser = SemanticFuser(package_weight=0.6, review_weight=0.4)
    builder = HybridVectorBuilder()
    
    # Generar embeddings de reseñas por destino
    logger.info("Generando embeddings de reseñas por destino...")
    review_embeddings_by_destino = {}
    for destino, textos in resenas_por_destino.items():
        embs = embedder.embed_batch(textos[:50])  # Max 50 reseñas por destino
        review_embeddings_by_destino[destino] = aggregator.aggregate(embs)
    logger.info("  -> %d destinos con embeddings de reseñas", len(review_embeddings_by_destino))
    
    # Vector de reseña genérico para destinos sin reseñas
    all_review_embs = list(review_embeddings_by_destino.values())
    default_review_emb = np.mean(all_review_embs, axis=0) if all_review_embs else np.zeros(embedder.embedding_dim)
    
    # Generar embeddings de paquetes
    logger.info("Generando embeddings de paquetes...")
    textos_paquetes = []
    for p in paquetes:
        texto = p.descripcion_texto or f"{p.nombre_paquete} {p.destino_nombre} {p.categoria}"
        textos_paquetes.append(texto)
    
    package_embeddings = embedder.embed_batch(textos_paquetes)
    if len(package_embeddings) > 0:
        logger.info("  -> %d embeddings de paquetes generados (dim=%d)", len(package_embeddings), package_embeddings.shape[1])
    else:
        logger.warning("⚠️ No hay embeddings de paquetes disponibles para medir su dimensión.")
        return
    # Fusionar y construir vectores híbridos
    logger.info("Fusionando embeddings y construyendo vectores híbridos...")
    
    # Calcular min/max para normalización
    precios = [p.precio_base_eur for p in paquetes if p.precio_base_eur]
    duraciones = [p.duracion_dias for p in paquetes if p.duracion_dias]
    estrellas = [p.estrellas_hotel for p in paquetes if p.estrellas_hotel]
    valoraciones = [p.num_valoraciones_hotel for p in paquetes if p.num_valoraciones_hotel]
    
    precio_min, precio_max = min(precios) if precios else 0, max(precios) if precios else 1
    dur_min, dur_max = min(duraciones) if duraciones else 1, max(duraciones) if duraciones else 14
    est_min, est_max = 1.0, 5.0
    val_min, val_max = min(valoraciones) if valoraciones else 0, max(valoraciones) if valoraciones else 1
    
    def norm(val, vmin, vmax):
        if vmax == vmin:
            return 0.5
        return (val - vmin) / (vmax - vmin) if val is not None else 0.5
    
    hybrid_vectors = []
    paquete_ids = []
    
    for i, p in enumerate(paquetes):
        # Embedding del paquete
        pkg_emb = package_embeddings[i]
        
        # Embedding de reseñas del destino
        review_emb = review_embeddings_by_destino.get(p.destino_nombre, default_review_emb)
        
        # Fusión semántica
        fused = fuser.fuse(pkg_emb, review_emb)
        
        # Atributos estructurados normalizados
        attrs = {
            "precio_base_eur_norm": norm(p.precio_base_eur, precio_min, precio_max),
            "duracion_dias_norm": norm(p.duracion_dias, dur_min, dur_max),
            "nivel_ocupacion": p.nivel_ocupacion or 0.5,
            "accesibilidad_destino_norm": norm(p.accesibilidad_destino, 1, 3) if p.accesibilidad_destino else 0.5,
            "estrellas_hotel_norm": norm(p.estrellas_hotel, est_min, est_max) if p.estrellas_hotel else 0.5,
            "num_valoraciones_hotel_norm": norm(p.num_valoraciones_hotel, val_min, val_max) if p.num_valoraciones_hotel else 0.5,
            "indicador_sostenibilidad_tui": 1.0 if p.indicador_sostenibilidad_tui else 0.0,
        }
        
        # Vector híbrido final
        hybrid = builder.build(fused, attrs)
        hybrid_vectors.append(hybrid)
        paquete_ids.append(p.id_paquete)
    
    # Guardar vectores
    hybrid_matrix = np.array(hybrid_vectors, dtype=np.float32)
    
    np.save(output_dir / "hybrid_vectors.npy", hybrid_matrix)
    np.save(output_dir / "paquete_ids.npy", np.array(paquete_ids))
    np.save(output_dir / "package_embeddings.npy", package_embeddings)
    
    elapsed = time.time() - start
    
    # Resumen
    print(f"\n{'='*60}")
    print(f"  EMBEDDINGS GENERADOS")
    print(f"{'='*60}")
    print(f"  Paquetes procesados:    {len(paquetes)}")
    print(f"  Destinos con reseñas:   {len(review_embeddings_by_destino)}")
    print(f"  Dimensión embedding:    {embedder.embedding_dim}")
    print(f"  Dimensión híbrido:      {hybrid_matrix.shape[1]} (={embedder.embedding_dim}+7)")
    print(f"  Ficheros guardados:")
    print(f"    - data/embeddings/hybrid_vectors.npy  ({hybrid_matrix.nbytes/1024:.1f} KB)")
    print(f"    - data/embeddings/paquete_ids.npy")
    print(f"    - data/embeddings/package_embeddings.npy")
    print(f"  Tiempo total:           {elapsed:.1f} segundos")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
