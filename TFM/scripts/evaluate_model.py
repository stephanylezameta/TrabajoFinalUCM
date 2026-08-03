"""
Evaluación completa del modelo recomendador.

Calcula métricas de calidad (Precision@K, NDCG@K, Recall@K),
diversidad (intra-list diversity, cobertura, novedad) y
redistribución (Gini, CR5) para los tres escenarios.

Uso:
    cd /d D:\Master\TrabajoFinalUCM\TFM
    python scripts/evaluate_model.py
"""
import sys
import time
import logging
import numpy as np
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.repository import Repositorio
from src.recommender.affinity.cosine_model import CosineAffinityModel
from src.recommender.tdrs_calculator import TDRSCalculator
from src.recommender.reranking_engine import ReRankingEngine
from src.recommender.territorial_simulator import TerritorialImpactSimulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def calcular_relevancia_ground_truth(usuario, paquete) -> float:
    """
    Calcula relevancia "ground truth" de un paquete para un usuario.
    
    Simula interacciones basándose en match de preferencias:
    - Si la categoría del paquete coincide con la preferencia dominante del usuario → relevante
    - Si el presupuesto está en rango → bonus
    - Si la temporada coincide → bonus
    
    Retorna score de relevancia [0, 1].
    """
    # Mapeo categoría → preferencia
    cat_pref_map = {
        "playa": "pref_playa",
        "cultura": "pref_cultura",
        "aventura": "pref_aventura",
        "bienestar": "pref_bienestar",
        "gastronomia": "pref_gastronomia",
        "naturaleza": "pref_naturaleza",
    }
    
    relevancia = 0.0
    
    # Match de categoría con preferencias del usuario
    cat = paquete.categoria or "playa"
    pref_field = cat_pref_map.get(cat, "pref_playa")
    pref_valor = getattr(usuario, pref_field, 0.0)
    relevancia += pref_valor * 0.5  # Hasta 0.5 por match de categoría
    
    # Match de presupuesto
    precio = paquete.precio_base_eur or 1000
    if usuario.presupuesto_min_eur and usuario.presupuesto_max_eur:
        if usuario.presupuesto_min_eur <= precio <= usuario.presupuesto_max_eur:
            relevancia += 0.25
        elif precio < usuario.presupuesto_min_eur * 1.5 and precio > usuario.presupuesto_max_eur * 0.5:
            relevancia += 0.10
    
    # Match de temporada
    if usuario.temporada_preferida and paquete.temporada:
        if usuario.temporada_preferida == paquete.temporada:
            relevancia += 0.15
    
    # Match de duración
    dur = paquete.duracion_dias or 7
    if usuario.duracion_min_dias and usuario.duracion_max_dias:
        if usuario.duracion_min_dias <= dur <= usuario.duracion_max_dias:
            relevancia += 0.10
    
    return min(1.0, relevancia)


def precision_at_k(recommended_ids: list, relevant_ids: set, k: int) -> float:
    """Precision@K: proporción de ítems relevantes en top-K."""
    top_k = recommended_ids[:k]
    if not top_k:
        return 0.0
    relevant_in_top_k = sum(1 for id in top_k if id in relevant_ids)
    return relevant_in_top_k / k


def recall_at_k(recommended_ids: list, relevant_ids: set, k: int) -> float:
    """Recall@K: proporción de ítems relevantes recuperados en top-K."""
    if not relevant_ids:
        return 0.0
    top_k = recommended_ids[:k]
    relevant_in_top_k = sum(1 for id in top_k if id in relevant_ids)
    return relevant_in_top_k / len(relevant_ids)


def ndcg_at_k(recommended_ids: list, relevance_scores: dict, k: int) -> float:
    """NDCG@K: Normalized Discounted Cumulative Gain."""
    top_k = recommended_ids[:k]
    
    # DCG
    dcg = 0.0
    for i, id in enumerate(top_k):
        rel = relevance_scores.get(id, 0.0)
        dcg += rel / np.log2(i + 2)  # i+2 porque posiciones empiezan en 1
    
    # IDCG (ranking ideal)
    ideal_rels = sorted(relevance_scores.values(), reverse=True)[:k]
    idcg = 0.0
    for i, rel in enumerate(ideal_rels):
        idcg += rel / np.log2(i + 2)
    
    if idcg == 0:
        return 0.0
    return dcg / idcg


def intra_list_diversity(ranking: list) -> float:
    """Diversidad intra-lista: proporción de destinos únicos en el ranking."""
    if not ranking:
        return 0.0
    destinos = [r.get("destino_nombre", "") for r in ranking]
    return len(set(destinos)) / len(destinos)


def category_diversity(ranking: list) -> float:
    """Diversidad de categorías en el ranking."""
    if not ranking:
        return 0.0
    categorias = [r.get("categoria", "") for r in ranking]
    return len(set(categorias)) / len(categorias)


def main():
    start = time.time()
    
    # Cargar datos
    repo = Repositorio("sqlite:///data/sample_tui.db")
    usuarios = repo.list_usuarios(solo_sinteticos=True)[:1000]
    paquetes = repo.list_paquetes(page_size=10000)
    
    embeddings = np.load("data/embeddings/hybrid_vectors.npy")
    paquete_ids = np.load("data/embeddings/paquete_ids.npy", allow_pickle=True)
    
    logger.info("Evaluando con %d usuarios y %d paquetes", len(usuarios), len(paquetes))
    
    # Modelos
    affinity = CosineAffinityModel()
    tdrs_calc = TDRSCalculator()
    reranker = ReRankingEngine()
    simulator = TerritorialImpactSimulator()
    
    paquete_map = {p.id_paquete: p for p in paquetes}
    
    # Calcular diversificación por destino
    destino_count = Counter(p.destino_nombre for p in paquetes)
    max_count = max(destino_count.values()) if destino_count else 1
    diversificacion_por_destino = {d: 1.0 - (c / max_count) for d, c in destino_count.items()}
    
    # Métricas acumuladas por escenario
    metricas = {esc: {
        "precision_5": [], "precision_10": [],
        "recall_5": [], "recall_10": [],
        "ndcg_5": [], "ndcg_10": [],
        "diversity_destino": [], "diversity_categoria": [],
        "paquetes_recomendados": set(),
    } for esc in ["tradicional", "moderado", "intensivo"]}
    
    rankings_por_escenario = {"tradicional": [], "moderado": [], "intensivo": []}
    
    for i, usuario in enumerate(usuarios):
        # Vector de usuario
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
        
        # Ground truth: calcular relevancia real para cada paquete
        relevance_scores = {}
        for j, pkg_id in enumerate(paquete_ids):
            pkg = paquete_map.get(str(pkg_id))
            if pkg:
                rel = calcular_relevancia_ground_truth(usuario, pkg)
                relevance_scores[str(pkg_id)] = rel
        
        # Ítems relevantes (relevancia > 0.4)
        relevant_ids = {id for id, rel in relevance_scores.items() if rel > 0.4}
        
        # Candidatos con TDRS
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
                "categoria": pkg.categoria,
                "afinidad": float(score),
                "tdrs": tdrs,
                "ocupacion": ocupacion,
                "sostenibilidad": 1.0 if pkg.indicador_sostenibilidad_tui else 0.0,
                "capacidad": 0.5,
            })
        
        # Evaluar cada escenario
        for escenario in ["tradicional", "moderado", "intensivo"]:
            ranking = reranker.rank(candidates, escenario=escenario, k=10)
            rankings_por_escenario[escenario].append(ranking)
            
            rec_ids = [r["id_paquete"] for r in ranking]
            
            # Precision & Recall
            metricas[escenario]["precision_5"].append(precision_at_k(rec_ids, relevant_ids, 5))
            metricas[escenario]["precision_10"].append(precision_at_k(rec_ids, relevant_ids, 10))
            metricas[escenario]["recall_5"].append(recall_at_k(rec_ids, relevant_ids, 5))
            metricas[escenario]["recall_10"].append(recall_at_k(rec_ids, relevant_ids, 10))
            
            # NDCG
            metricas[escenario]["ndcg_5"].append(ndcg_at_k(rec_ids, relevance_scores, 5))
            metricas[escenario]["ndcg_10"].append(ndcg_at_k(rec_ids, relevance_scores, 10))
            
            # Diversidad
            metricas[escenario]["diversity_destino"].append(intra_list_diversity(ranking))
            metricas[escenario]["diversity_categoria"].append(category_diversity(ranking))
            
            # Cobertura
            metricas[escenario]["paquetes_recomendados"].update(rec_ids)
        
        if (i + 1) % 200 == 0:
            logger.info("  Evaluados %d/%d usuarios...", i + 1, len(usuarios))
    
    # Redistribución
    resultados_sim = simulator.simulate(rankings_por_escenario)
    
    # Cobertura del catálogo
    total_paquetes = len(paquetes)
    
    elapsed = time.time() - start
    
    # Resumen
    print(f"\n{'='*80}")
    print(f"  EVALUACIÓN COMPLETA DEL MODELO RECOMENDADOR")
    print(f"{'='*80}")
    print(f"  Usuarios evaluados: {len(usuarios)} | Paquetes: {len(paquetes)} | Tiempo: {elapsed:.1f}s")
    print(f"\n{'  ':<2}{'Métrica':<25} {'Tradicional':<14} {'Moderado':<14} {'Intensivo':<14}")
    print(f"  {'-'*65}")
    
    for esc_label, esc_key in [("Tradicional", "tradicional"), ("Moderado", "moderado"), ("Intensivo", "intensivo")]:
        pass  # Se imprime en formato tabla abajo
    
    # Tabla de resultados
    rows = [
        ("Precision@5", "precision_5"),
        ("Precision@10", "precision_10"),
        ("Recall@5", "recall_5"),
        ("Recall@10", "recall_10"),
        ("NDCG@5", "ndcg_5"),
        ("NDCG@10", "ndcg_10"),
        ("Diversidad destinos", "diversity_destino"),
        ("Diversidad categorías", "diversity_categoria"),
    ]
    
    for label, key in rows:
        vals = []
        for esc in ["tradicional", "moderado", "intensivo"]:
            val = np.mean(metricas[esc][key])
            vals.append(f"{val:.4f}")
        print(f"  {label:<25} {vals[0]:<14} {vals[1]:<14} {vals[2]:<14}")
    
    # Cobertura
    print(f"  {'Cobertura catálogo':<25}", end="")
    for esc in ["tradicional", "moderado", "intensivo"]:
        cov = len(metricas[esc]["paquetes_recomendados"]) / total_paquetes
        print(f" {cov:.4f}       ", end="")
    print()
    
    # Redistribución
    print(f"\n  {'--- Redistribución ---':<25}")
    print(f"  {'Gini turístico':<25}", end="")
    for esc in ["tradicional", "moderado", "intensivo"]:
        print(f" {resultados_sim[esc]['gini']:.4f}       ", end="")
    print()
    print(f"  {'CR5':<25}", end="")
    for esc in ["tradicional", "moderado", "intensivo"]:
        print(f" {resultados_sim[esc]['cr5']:.4f}       ", end="")
    print()
    print(f"  {'Destinos alcanzados':<25}", end="")
    for esc in ["tradicional", "moderado", "intensivo"]:
        print(f" {resultados_sim[esc]['num_destinos']:<14}", end="")
    print()
    
    # Resumen final
    print(f"\n  {'='*65}")
    trad_ndcg = np.mean(metricas["tradicional"]["ndcg_10"])
    mod_ndcg = np.mean(metricas["moderado"]["ndcg_10"])
    trad_gini = resultados_sim["tradicional"]["gini"]
    mod_gini = resultados_sim["moderado"]["gini"]
    
    print(f"  NDCG@10: Tradicional={trad_ndcg:.4f} vs Moderado={mod_ndcg:.4f} (caída={((trad_ndcg-mod_ndcg)/trad_ndcg*100):.1f}%)")
    print(f"  Gini:    Tradicional={trad_gini:.4f} vs Moderado={mod_gini:.4f} (reducción={((trad_gini-mod_gini)/trad_gini*100):.1f}%)")
    print(f"\n  → El moderado reduce el Gini un {((trad_gini-mod_gini)/trad_gini*100):.0f}% con una caída de NDCG del {((trad_ndcg-mod_ndcg)/trad_ndcg*100):.0f}%")
    print(f"{'='*80}\n")
    
    # Exportar resultados
    import csv
    output_path = "data/processed/evaluation_results.csv"
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["escenario", "precision_5", "precision_10", "recall_5", "recall_10", 
                        "ndcg_5", "ndcg_10", "diversity_destino", "diversity_categoria",
                        "cobertura", "gini", "cr5"])
        for esc in ["tradicional", "moderado", "intensivo"]:
            writer.writerow([
                esc,
                f"{np.mean(metricas[esc]['precision_5']):.4f}",
                f"{np.mean(metricas[esc]['precision_10']):.4f}",
                f"{np.mean(metricas[esc]['recall_5']):.4f}",
                f"{np.mean(metricas[esc]['recall_10']):.4f}",
                f"{np.mean(metricas[esc]['ndcg_5']):.4f}",
                f"{np.mean(metricas[esc]['ndcg_10']):.4f}",
                f"{np.mean(metricas[esc]['diversity_destino']):.4f}",
                f"{np.mean(metricas[esc]['diversity_categoria']):.4f}",
                f"{len(metricas[esc]['paquetes_recomendados']) / total_paquetes:.4f}",
                f"{resultados_sim[esc]['gini']:.4f}",
                f"{resultados_sim[esc]['cr5']:.4f}",
            ])
    print(f"  Resultados exportados a: {output_path}")


if __name__ == "__main__":
    main()
