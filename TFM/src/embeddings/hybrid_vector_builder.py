"""
Construye el vector híbrido final: embedding semántico + atributos numéricos ponderados.
Dimensión final: D + 7 (donde D es la dimensión del embedding semántico).
"""
import numpy as np
import logging

logger = logging.getLogger(__name__)

class HybridVectorBuilder:
    """Concatena embedding semántico con 7 atributos numéricos ponderados."""
    
    # Pesos por defecto (DECISIÓN-008)
    DEFAULT_WEIGHTS = {
        "w1_precio": 1.0,
        "w2_duracion": 0.5,
        "w3_ocupacion": 1.5,
        "w4_accesibilidad": 0.8,
        "w5_estrellas": 0.7,
        "w6_valoraciones": 0.6,
        "w7_sostenibilidad": 1.0,
    }
    
    def __init__(self, weights: dict[str, float] | None = None):
        """
        Args:
            weights: Diccionario con los 7 pesos. Si None, usa los defaults de DECISIÓN-008.
        """
        self.weights = weights or self.DEFAULT_WEIGHTS
    
    def build(self, semantic_vector: np.ndarray, structured_attrs: dict[str, float]) -> np.ndarray:
        """
        Construye el vector híbrido final.
        
        Args:
            semantic_vector: Embedding semántico fusionado, shape (D,).
            structured_attrs: Diccionario con los 7 atributos normalizados [0,1]:
                - precio_base_eur_norm
                - duracion_dias_norm
                - nivel_ocupacion
                - accesibilidad_destino_norm
                - estrellas_hotel_norm
                - num_valoraciones_hotel_norm
                - indicador_sostenibilidad_tui (0.0 o 1.0)
                
        Returns:
            Vector de shape (D+7,).
        """
        numeric_part = np.array([
            self.weights["w1_precio"] * structured_attrs.get("precio_base_eur_norm", 0.0),
            self.weights["w2_duracion"] * structured_attrs.get("duracion_dias_norm", 0.0),
            self.weights["w3_ocupacion"] * structured_attrs.get("nivel_ocupacion", 0.0),
            self.weights["w4_accesibilidad"] * structured_attrs.get("accesibilidad_destino_norm", 0.0),
            self.weights["w5_estrellas"] * structured_attrs.get("estrellas_hotel_norm", 0.0),
            self.weights["w6_valoraciones"] * structured_attrs.get("num_valoraciones_hotel_norm", 0.0),
            self.weights["w7_sostenibilidad"] * structured_attrs.get("indicador_sostenibilidad_tui", 0.0),
        ], dtype=np.float32)
        
        return np.concatenate([semantic_vector, numeric_part])
