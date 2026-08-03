"""Fusión ponderada de embedding de paquete y embedding de reputación (reseñas)."""
import numpy as np
import logging

logger = logging.getLogger(__name__)

class SemanticFuser:
    """Fusiona embedding de paquete con embedding de reseñas mediante promedio ponderado."""
    
    def __init__(self, package_weight: float = 0.6, review_weight: float = 0.4):
        """
        Args:
            package_weight: Peso del embedding del paquete (default 0.6).
            review_weight: Peso del embedding de reputación (default 0.4).
        """
        assert abs(package_weight + review_weight - 1.0) < 0.01, "Los pesos deben sumar 1.0"
        self.package_weight = package_weight
        self.review_weight = review_weight
    
    def fuse(self, package_emb: np.ndarray, review_emb: np.ndarray) -> np.ndarray:
        """
        Promedio ponderado de embedding de paquete y embedding de reseñas.
        
        Args:
            package_emb: Embedding del texto del paquete, shape (D,).
            review_emb: Embedding agregado de las reseñas del destino, shape (D,).
            
        Returns:
            Vector fusionado de shape (D,).
        """
        return self.package_weight * package_emb + self.review_weight * review_emb
