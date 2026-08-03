"""Agregador de embeddings de reseñas por destino (mean pooling)."""
import numpy as np
import logging

logger = logging.getLogger(__name__)

class ReviewAggregator:
    """Agrega embeddings de múltiples reseñas de un destino mediante mean pooling."""
    
    def aggregate(self, review_embeddings: np.ndarray) -> np.ndarray:
        """
        Calcula el embedding promedio de las reseñas de un destino.
        
        Args:
            review_embeddings: Array de shape (N, D) con embeddings de N reseñas.
            
        Returns:
            Array de shape (D,) con el embedding promedio.
        """
        if review_embeddings.ndim == 1:
            return review_embeddings
        if len(review_embeddings) == 0:
            raise ValueError("No se pueden agregar 0 embeddings de reseñas")
        resultado = np.mean(review_embeddings, axis=0)
        logger.debug("ReviewAggregator: agregados %d embeddings → vector (D=%d)", len(review_embeddings), len(resultado))
        return resultado
