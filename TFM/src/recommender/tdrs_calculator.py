"""
Cálculo del Tourism Demand Redistribution Score (TDRS).

TDRS = w1*Afinidad + w2*Capacidad + w3*Accesibilidad + w4*Impacto_Local
     + w5*Temporada_Baja + w6*Diversificación - w7*Ocupación - w8*Sensibilidad_Ambiental
"""
import logging
import numpy as np

logger = logging.getLogger(__name__)

class TDRSCalculator:
    """Calcula el índice TDRS para paquetes turísticos."""
    
    # Pesos por defecto (config.yml)
    DEFAULT_WEIGHTS = {
        "w1_afinidad": 0.20,
        "w2_capacidad": 0.15,
        "w3_accesibilidad": 0.10,
        "w4_impacto_local": 0.10,
        "w5_temporada_baja": 0.15,
        "w6_diversificacion": 0.10,
        "w7_ocupacion": 0.15,
        "w8_sensibilidad_ambiental": 0.05,
    }
    
    def __init__(
        self,
        weights: dict[str, float] | None = None,
        umbral_ocupacion_maxima: float = 0.85,
        aplicar_umbral_ocupacion: bool = False,
    ):
        """
        aplicar_umbral_ocupacion: por defecto False (desactivado).

        Hallazgo (revision de arquitectura, 31/08): la regla RF-6.4
        ("si ocupacion > 0.85, forzar a 1.0 = penalizacion maxima") fue
        diseñada asumiendo que 'ocupacion' es un porcentaje real de
        ocupacion hotelera (ej. 85% de habitaciones ocupadas = destino
        saturado). En la practica, 'ocupacion' llega normalizada por
        min-max SOLO entre los 19 de 39 destinos que tienen dato real
        (ver cargar_ocupacion_por_destino en run_recommendation.py) --
        eso significa que el destino con mayor ocupacion de esos 19
        SIEMPRE da exactamente 1.0, sea cual sea su valor real (podria
        ser 55% de ocupacion real y aun asi "ganar" el maximo relativo),
        mientras que los 20 destinos sin dato (fallback neutro 0.5)
        nunca pueden activar la regla, sin importar si estan realmente
        mas saturados. Es decir: la regla hoy mide ranking relativo
        dentro de una muestra parcial, no saturacion absoluta -- lo
        contrario de para lo que fue diseñada. Se desactiva por defecto
        hasta que la cobertura de ocupacion real sea mas completa y en
        una escala verdaderamente absoluta (no normalizada por min-max
        sobre un subconjunto). Reactivar pasando
        aplicar_umbral_ocupacion=True una vez resuelto eso.
        """
        self.weights = weights or self.DEFAULT_WEIGHTS
        self.umbral_ocupacion_maxima = umbral_ocupacion_maxima
        self.aplicar_umbral_ocupacion = aplicar_umbral_ocupacion
        # Verificar que suma de |pesos| = 1.0
        suma = sum(abs(v) for v in self.weights.values())
        assert abs(suma - 1.0) < 0.01, f"Suma de |pesos| debe ser 1.0, es {suma}"
    
    def calculate(
        self,
        afinidad: float,
        capacidad: float = 0.5,
        accesibilidad: float = 0.5,
        impacto_local: float = 0.5,
        temporada_baja: float = 0.5,
        diversificacion: float = 0.5,
        ocupacion: float = 0.5,
        sensibilidad_ambiental: float = 0.3,
    ) -> float:
        """
        Calcula TDRS. Todos los inputs deben estar en [0, 1].
        Postcondición: resultado ∈ [-1, 1].
        """
        # Validaciones
        assert 0 <= afinidad <= 1, f"Afinidad fuera de rango: {afinidad}"
        assert 0 <= ocupacion <= 1, f"Ocupación fuera de rango: {ocupacion}"
        
        # RF-6.4: si ocupacion > umbral, forzar a 1.0. Desactivado por
        # defecto (ver docstring del __init__) -- reactivar cuando la
        # cobertura de datos reales de ocupacion sea completa y este en
        # una escala absoluta, no normalizada por min-max sobre una
        # muestra parcial de destinos.
        if self.aplicar_umbral_ocupacion and ocupacion > self.umbral_ocupacion_maxima:
            ocupacion = 1.0
        
        w = self.weights
        tdrs = (
            w["w1_afinidad"] * afinidad
            + w["w2_capacidad"] * capacidad
            + w["w3_accesibilidad"] * accesibilidad
            + w["w4_impacto_local"] * impacto_local
            + w["w5_temporada_baja"] * temporada_baja
            + w["w6_diversificacion"] * diversificacion
            - w["w7_ocupacion"] * ocupacion
            - w["w8_sensibilidad_ambiental"] * sensibilidad_ambiental
        )
        return max(-1.0, min(1.0, float(tdrs)))
    
    def calculate_for_package(self, afinidad: float, paquete_attrs: dict) -> float:
        """Calcula TDRS usando atributos del paquete directamente."""
        temporada = paquete_attrs.get("temporada", "Media")
        temporada_val = {"Baja": 1.0, "Media": 0.5, "Alta": 0.0}.get(temporada, 0.5)
        
        return self.calculate(
            afinidad=afinidad,
            capacidad=paquete_attrs.get("capacidad_norm", 0.5),
            accesibilidad=paquete_attrs.get("accesibilidad_norm", 0.5),
            impacto_local=paquete_attrs.get("impacto_local", 0.5),
            temporada_baja=temporada_val,
            diversificacion=paquete_attrs.get("diversificacion", 0.5),
            ocupacion=paquete_attrs.get("nivel_ocupacion", 0.5),
            sensibilidad_ambiental=paquete_attrs.get("sensibilidad_ambiental", 0.3),
        )