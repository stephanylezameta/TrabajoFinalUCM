"""
Simulación de impacto territorial con 500 usuarios sintéticos.

Uso:
    cd /d D:\Master\TrabajoFinalUCM\TFM
    python scripts/run_simulation.py
"""
import sys
import time
import logging
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.repository import Repositorio
from src.recommender.affinity.cosine_model import CosineAffinityModel
from src.recommender.tdrs_calculator import TDRSCalculator
from src.recommender.reranking_engine import ReRankingEngine
from src.recommender.territorial_simulator import TerritorialImpactSimulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def main():
    start = time.time()
    
    # Cargar datos
    repo = Repositorio("sqlite:///data/sample_tui.db")
    usuarios = repo.list_usuarios(solo_sinteticos=True)
    paquetes = repo.list_paquetes(page_size=500)
    
    logger.info("Cargados %d usuarios y %d paquetes", len(usuarios), len(paquetes))
    
    # Cargar embeddings
    embeddings = np.load("data/embeddings/hybrid_vectors.npy")
    paquete_ids = np.load("data/embeddings/paquete_ids.npy", allow_pickle=True)
    
    # Inicializar modelos
    affinity = CosineAffinityModel()
    tdrs_calc = TDRSCalculator()
    reranker = ReRankingEngine()
    simulator = TerritorialImpactSimulator()
    
    # Construir mapa de paquetes
    paquete_map = {p.id_paquete: p for p in paquetes}

    # Calcular diversificación por destino (1 - popularidad_relativa)
    destino_count = {}
    for p in paquetes:
        destino_count[p.destino_nombre] = destino_count.get(p.destino_nombre, 0) + 1
    max_count = max(destino_count.values()) if destino_count else 1
    diversificacion_por_destino = {d: 1.0 - (c / max_count) for d, c in destino_count.items()}
    
    # Simular para cada usuario
    rankings_por_escenario = {"tradicional": [], "moderado": [], "intensivo": []}
    
    for i, usuario in enumerate(usuarios[:1000]):
        # Construir vector de usuario
        user_vector = np.zeros(embeddings.shape[1], dtype=np.float32)
        user_vector[0] = usuario.pref_cultura
        user_vector[1] = usuario.pref_gastronomia
        user_vector[2] = usuario.pref_naturaleza
        user_vector[3] = usuario.pref_playa
        user_vector[4] = usuario.pref_bienestar
        user_vector[5] = usuario.pref_aventura
        user_vector[-7] = (usuario.presupuesto_min_eur + usuario.presupuesto_max_eur) / 2 / 3000.0
        user_vector[-1] = usuario.interes_sostenibilidad
        
        # Scores de afinidad
        scores = affinity.score_batch(user_vector, embeddings)
        
        # Construir candidatos con TDRS
        candidates = []
        for j, (score, pkg_id) in enumerate(zip(scores, paquete_ids)):
            pkg = paquete_map.get(str(pkg_id))
            if not pkg:
                continue
            
            temporada_val = {"Baja": 1.0, "Media": 0.5, "Alta": 0.0}.get(pkg.temporada or "Media", 0.5)
            ocupacion = pkg.nivel_ocupacion or 0.5
            
            tdrs = tdrs_calc.calculate(
                afinidad=float(score),
                capacidad=0.5,
                accesibilidad=(pkg.accesibilidad_destino or 2) / 3.0,
                impacto_local=0.5,
                temporada_baja=temporada_val,
                diversificacion=diversificacion_por_destino.get(pkg.destino_nombre, 0.5),
                ocupacion=ocupacion,
                sensibilidad_ambiental=pkg.sensibilidad_ambiental or 0.3,
            )
            
            candidates.append({
                "id_paquete": str(pkg_id),
                "destino_nombre": pkg.destino_nombre,
                "afinidad": float(score),
                "tdrs": tdrs,
                "ocupacion": ocupacion,
                "sostenibilidad": 1.0 if pkg.indicador_sostenibilidad_tui else 0.0,
                "capacidad": 0.5,
            })
        
        # Re-ranking en 3 escenarios
        for escenario in ["tradicional", "moderado", "intensivo"]:
            ranking = reranker.rank(candidates, escenario=escenario, k=10)
            rankings_por_escenario[escenario].append(ranking)
        
        if (i + 1) % 100 == 0:
            logger.info("  Procesados %d/%d usuarios...", i + 1, len(usuarios[:500]))
    
    # Calcular métricas de redistribución
    resultados = simulator.simulate(rankings_por_escenario)
    
    # Exportar CSV
    output_path = "data/processed/simulation_results.csv"
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    simulator.export_csv(resultados, output_path)
    
    elapsed = time.time() - start
    
    # Resumen
    print(f"\n{'='*60}")
    print(f"  SIMULACIÓN DE IMPACTO TERRITORIAL")
    print(f"{'='*60}")
    print(f"  Usuarios simulados: {min(1000, len(usuarios))}")
    print(f"  Paquetes en catálogo: {len(paquetes)}")
    print(f"\n  {'Escenario':<15} {'Gini':<10} {'CR5':<10} {'Destinos':<10}")
    print(f"  {'-'*45}")
    for esc, datos in resultados.items():
        print(f"  {esc:<15} {datos['gini']:.4f}    {datos['cr5']:.4f}    {datos['num_destinos']}")
    
    # Verificar redistribución
    if resultados["moderado"]["gini"] < resultados["tradicional"]["gini"]:
        print(f"\n  ✅ El escenario moderado REDUCE el Gini ({resultados['tradicional']['gini']:.4f} → {resultados['moderado']['gini']:.4f})")
    else:
        print(f"\n  ⚠️ El escenario moderado NO reduce el Gini. Ajustar parámetros.")
    
    print(f"\n  Resultados exportados a: {output_path}")
    print(f"  Tiempo total: {elapsed:.1f} segundos")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
