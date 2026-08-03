"""Generador de explicaciones para las recomendaciones."""
import logging

logger = logging.getLogger(__name__)

class ExplainabilityBuilder:
    """Construye explicaciones de por qué un paquete está en cierta posición."""
    
    def build(self, paquete: dict, ranking_tradicional: list[str], ranking_redistributivo: list[str]) -> dict:
        """Genera explicación con desglose de factores y cambio de posición."""
        id_paq = paquete.get("id_paquete", "")
        
        pos_trad = (ranking_tradicional.index(id_paq) + 1) if id_paq in ranking_tradicional else None
        pos_redis = (ranking_redistributivo.index(id_paq) + 1) if id_paq in ranking_redistributivo else None
        
        motivo = None
        if pos_trad and pos_redis and pos_trad != pos_redis:
            if pos_redis < pos_trad:
                motivo = f"Ascendió {pos_trad - pos_redis} posiciones por bajo nivel de saturación y temporada favorable"
            else:
                motivo = f"Descendió {pos_redis - pos_trad} posiciones por alta ocupación del destino"
        
        return {
            "afinidad": round(paquete.get("afinidad", 0), 4),
            "tdrs": round(paquete.get("tdrs", 0), 4),
            "saturacion": round(paquete.get("ocupacion", 0.5), 4),
            "posicion_ranking_tradicional": pos_trad,
            "posicion_ranking_redistributivo": pos_redis,
            "motivo_cambio_posicion": motivo,
        }
