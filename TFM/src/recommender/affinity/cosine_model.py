"""Modelo baseline de afinidad usuario-paquete por similitud del coseno."""
import numpy as np
import logging

logger = logging.getLogger(__name__)

class CosineAffinityModel:
    """Calcula afinidad usuario-paquete mediante similitud del coseno normalizada a [0,1]."""
    
    def score(self, user_vector: np.ndarray, package_vector: np.ndarray) -> float:
        """
        Afinidad(u, e) = (coseno(user, package) + 1) / 2 → [0, 1]
        """
        cos = np.dot(user_vector, package_vector) / (
            np.linalg.norm(user_vector) * np.linalg.norm(package_vector) + 1e-8
        )
        return float((cos + 1.0) / 2.0)
    
    def top_k(self, user_vector: np.ndarray, catalog_vectors: np.ndarray, k: int = 10) -> list[int]:
        """Retorna índices de los K paquetes más afines."""
        norms = np.linalg.norm(catalog_vectors, axis=1) + 1e-8
        norm_user = np.linalg.norm(user_vector) + 1e-8
        scores = np.dot(catalog_vectors, user_vector) / (norms * norm_user)
        scores = (scores + 1.0) / 2.0
        return np.argsort(scores)[::-1][:k].tolist()
    
    def score_batch(self, user_vector: np.ndarray, catalog_vectors: np.ndarray) -> np.ndarray:
        """Calcula scores de afinidad para todo el catálogo. Retorna array de scores [0,1]."""
        norms = np.linalg.norm(catalog_vectors, axis=1) + 1e-8
        norm_user = np.linalg.norm(user_vector) + 1e-8
        scores = np.dot(catalog_vectors, user_vector) / (norms * norm_user)
        return (scores + 1.0) / 2.0
