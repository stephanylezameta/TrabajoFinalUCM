"""Simulación de impacto territorial del motor redistributivo."""
import logging
import numpy as np
from typing import Any

logger = logging.getLogger(__name__)

class TerritorialImpactSimulator:
    """Simula distribución de demanda bajo distintas estrategias de recomendación."""
    
    def simulate(self, rankings_por_escenario: dict[str, list[list[dict]]]) -> dict[str, dict]:
        """
        Calcula métricas de redistribución para cada escenario.
        
        Args:
            rankings_por_escenario: {escenario: [ranking_usuario1, ranking_usuario2, ...]}
            Cada ranking es una lista de dicts con "destino_nombre".
        
        Returns:
            {escenario: {"gini": float, "cr5": float, "pct_baja_saturacion": float}}
        """
        resultados = {}
        for escenario, rankings in rankings_por_escenario.items():
            # Contar demanda por destino
            demanda = {}
            for ranking in rankings:
                for paq in ranking[:10]:  # Top-10 por usuario
                    destino = paq.get("destino_nombre", "unknown")
                    demanda[destino] = demanda.get(destino, 0) + 1
            
            valores = list(demanda.values()) if demanda else [1]
            total = sum(valores)
            
            resultados[escenario] = {
                "gini": self.calcular_gini(valores),
                "cr5": self.calcular_cr5(demanda),
                "pct_baja_saturacion": 0.0,  # Se calculará con datos reales de ocupación
                "num_destinos": len(demanda),
                "total_recomendaciones": total,
            }
        
        return resultados
    
    def calcular_gini(self, distribution: list[float]) -> float:
        """Coeficiente de Gini de una distribución."""
        arr = np.array(sorted(distribution), dtype=np.float64)
        n = len(arr)
        if n == 0 or arr.sum() == 0:
            return 0.0
        index = np.arange(1, n + 1)
        return float((2 * np.sum(index * arr) - (n + 1) * np.sum(arr)) / (n * np.sum(arr)))
    
    def calcular_cr5(self, demand_distribution: dict[str, float]) -> float:
        """Concentración en los 5 destinos más demandados."""
        if not demand_distribution:
            return 0.0
        total = sum(demand_distribution.values())
        if total == 0:
            return 0.0
        top5 = sorted(demand_distribution.values(), reverse=True)[:5]
        return float(sum(top5) / total)
    
    def export_csv(self, results: dict[str, dict], path: str) -> None:
        """Exporta resultados en CSV."""
        import csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["escenario", "gini", "cr5", "num_destinos", "total_recomendaciones"])
            for esc, datos in results.items():
                writer.writerow([esc, datos["gini"], datos["cr5"], datos["num_destinos"], datos["total_recomendaciones"]])
        logger.info("Resultados exportados a %s", path)
