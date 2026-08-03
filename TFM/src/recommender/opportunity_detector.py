"""Detección de oportunidades de mercado para TUI."""
import logging
from typing import Any

logger = logging.getLogger(__name__)

class MarketOpportunityDetector:
    """Identifica destinos con potencial de demanda latente."""
    
    def __init__(self, umbral: float = 0.20):
        self.umbral = umbral
    
    def calculate_opportunity_score(self, afinidad_media: float, nivel_ocupacion: float) -> float:
        """indicador_oportunidad = afinidad_media - nivel_ocupacion"""
        return afinidad_media - nivel_ocupacion
    
    def detect_opportunities(self, destinos_stats: list[dict]) -> list[dict]:
        """Detecta destinos con indicador_oportunidad > umbral."""
        oportunidades = []
        for d in destinos_stats:
            score = self.calculate_opportunity_score(
                d.get("afinidad_media", 0), d.get("nivel_ocupacion", 0.5)
            )
            if score > self.umbral:
                oportunidades.append({
                    "destino_nombre": d.get("destino_nombre", ""),
                    "zona_geografica": d.get("zona_geografica", ""),
                    "temporada": d.get("temporada", "Media"),
                    "afinidad_media": d.get("afinidad_media", 0),
                    "nivel_ocupacion": d.get("nivel_ocupacion", 0.5),
                    "indicador_oportunidad": round(score, 4),
                    "perfil_usuario_afin": d.get("perfil_usuario_afin"),
                })
        oportunidades.sort(key=lambda x: -x["indicador_oportunidad"])
        return oportunidades
