"""
Módulo de Embeddings y NLP (Bloque 2).
"""
from src.embeddings.text_embedder import TextEmbedder
from src.embeddings.review_aggregator import ReviewAggregator
from src.embeddings.semantic_fuser import SemanticFuser
from src.embeddings.hybrid_vector_builder import HybridVectorBuilder

__all__ = [
    "TextEmbedder",
    "ReviewAggregator",
    "SemanticFuser",
    "HybridVectorBuilder",
]
