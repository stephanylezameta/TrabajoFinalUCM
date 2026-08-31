"""Motor de re-ranking con 3 escenarios de redistribución y diversificación."""
import logging
from typing import Any
from collections import Counter

logger = logging.getLogger(__name__)

class ReRankingEngine:
    """Produce rankings finales en 3 escenarios: tradicional, moderado, intensivo.
    
    El escenario tradicional usa solo afinidad.
    Los escenarios moderado e intensivo aplican redistribución + diversificación
    para asegurar que los destinos menos saturados Y menos repetidos suben en el ranking.
    """
    
    SCENARIOS = {
        "tradicional": {"alpha": 1.0, "beta": 0.0, "gamma": 0.0, "delta": 0.0, "lambda_": 0.0},
        # Pesos ajustados (28/08) tras busqueda contra Gini/CR5 reales
        # sobre 20 consultas de muestra, con piso de afinidad minima
        # (90%/70% del tradicional) e intensivo forzado a ser mas
        # agresivo en redistribucion que moderado (margen real, no solo
        # igualdad en el limite). Reemplazan los valores originales del
        # informe, nunca antes validados contra metricas de concentracion.
        "moderado": {"alpha": 0.1453, "beta": 0.4913, "gamma": 0.2126, "delta": 0.1507, "lambda_": 0.0292},
        "intensivo": {"alpha": 0.0287, "beta": 0.6490, "gamma": 0.2281, "delta": 0.0942, "lambda_": 0.0418},
    }
    
    def score_final(
        self,
        score_base: float,
        redistribucion: float = 0.0,
        sostenibilidad: float = 0.0,
        capacidad: float = 0.5,
        saturacion: float = 0.5,
        escenario: str = "moderado",
    ) -> float:
        """Score_Final = α·Base + β·Redistrib + γ·Sostenib + δ·Capacidad − λ·Saturación"""
        c = self.SCENARIOS[escenario]
        return (
            c["alpha"] * score_base
            + c["beta"] * redistribucion
            + c["gamma"] * sostenibilidad
            + c["delta"] * capacidad
            - c["lambda_"] * saturacion
        )
    
    def rank(self, candidates: list[dict], escenario: str = "moderado", k: int = 10) -> list[dict]:
        """
        Ordena candidatos por Score_Final con diversificación de destinos.
        
        Para escenarios moderado/intensivo: aplica selección greedy que penaliza
        destinos ya seleccionados (inspirado en MMR - Maximal Marginal Relevance).
        Para escenario tradicional: orden puro por score sin diversificación.
        """
        # Calcular scores base
        scored = []
        for c in candidates:
            sf = self.score_final(
                score_base=c.get("afinidad", 0),
                redistribucion=max(0, c.get("tdrs", 0)),
                sostenibilidad=c.get("sostenibilidad", 0),
                capacidad=c.get("capacidad", 0.5),
                saturacion=c.get("ocupacion", 0.5),
                escenario=escenario,
            )
            scored.append({**c, "score_final": sf})
        
        if escenario == "tradicional":
            # Ranking puro por score
            scored.sort(key=lambda x: (-x["score_final"], x.get("id_paquete", "")))
            return scored[:k]
        
        # Selección greedy con diversificación de destinos
        return self._select_diverse(scored, k=k, escenario=escenario)
    
    def _select_diverse(self, scored: list[dict], k: int, escenario: str) -> list[dict]:
        """
        Selección greedy con penalización por repetición de destino.
        
        Penalización: cada vez que un destino ya está en el ranking seleccionado,
        su score efectivo se reduce un % (30% para moderado, 50% para intensivo).
        Esto fuerza la diversificación de destinos en el ranking.
        """
        # Factor de penalización por repetición
        penalty_factor = 0.12 if escenario == "moderado" else 0.20
        
        selected = []
        destino_count = Counter()
        remaining = list(scored)
        
        for _ in range(min(k, len(remaining))):
            # Calcular score efectivo con penalización
            best_idx = -1
            best_score = -float("inf")
            
            for idx, candidate in enumerate(remaining):
                destino = candidate.get("destino_nombre", "")
                repeticiones = destino_count.get(destino, 0)
                
                # Penalizar por cada aparición previa del mismo destino
                effective_score = candidate["score_final"] * (1 - penalty_factor * repeticiones)
                
                if effective_score > best_score:
                    best_score = effective_score
                    best_idx = idx
            
            if best_idx >= 0:
                elegido = remaining.pop(best_idx)
                selected.append(elegido)
                destino_count[elegido.get("destino_nombre", "")] += 1
        
        return selected
    
    def rank_all_scenarios(self, candidates: list[dict], k: int = 10) -> dict[str, list[dict]]:
        """Retorna los 3 rankings en una sola llamada."""
        return {esc: self.rank(candidates, esc, k) for esc in self.SCENARIOS}
