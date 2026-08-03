"""
Generador de embeddings semánticos multilingüe.

Usa sentence-transformers para convertir textos en vectores de dimensión fija.
Soporta paraphrase-multilingual-MiniLM-L12-v2 (384 dim) y multilingual-e5-large (1024 dim).
"""
import logging
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class TextEmbedder:
    """Genera embeddings semánticos de textos usando sentence-transformers."""
    
    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2", model_version: str = "1.0.0"):
        """
        Args:
            model_name: Nombre del modelo de HuggingFace.
            model_version: Versión documentada para reproducibilidad.
        """
        self.model_name = model_name
        self.model_version = model_version
        logger.info("TextEmbedder: cargando modelo '%s'...", model_name)
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        logger.info("TextEmbedder: modelo cargado (dim=%d)", self.embedding_dim)
    
    def embed_text(self, text: str) -> np.ndarray:
        """Genera embedding de un texto individual. Retorna array de shape (D,)."""
        return self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    
    def embed_batch(self, texts: list[str], batch_size: int = 64) -> np.ndarray:
        """Genera embeddings en lote. Retorna array de shape (N, D)."""
        return self.model.encode(texts, batch_size=batch_size, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=True)
