"""
Optimiza los pesos (alpha, beta, gamma, delta, lambda) de los escenarios
"moderado" e "intensivo" del ReRankingEngine, buscando la combinacion
que minimice la concentracion territorial real (Gini, CR5) sin destruir
la relevancia (afinidad promedio), en vez de dejar los pesos fijos a
mano sin validar contra metricas reales.

IMPORTANTE: no se optimizan los pesos del TDRS en si (siguen siendo
reglas explicables, ver memoria tecnica) -- se optimiza el balance del
re-ranking (cuanto pesa la afinidad vs. la redistribucion en el score
final de cada escenario), que es una decision de politica de negocio
razonable de ajustar con datos, a diferencia de los pesos del TDRS
(que si se entrenaran con reservas historicas, aprenderian a *no*
redistribuir, porque el historico refleja el problema a corregir, no
la solucion -- ver justificacion completa en la conversacion).

Uso:
    cd TFM
    python scripts/optimizar_pesos_reranking.py
"""
import random
import sys
from pathlib import Path
from collections import Counter

import numpy as np

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from scripts.recommendation.pipeline_consultas import QueryPipeline
from scripts.recommendation.recommendation_engine import TuiRecommender
from src.recommender.tdrs_calculator import TDRSCalculator
from src.recommender.reranking_engine import ReRankingEngine
from scripts.recommendation.run_recommendation import (
    cargar_metadata_experiencias,
    cargar_ocupacion_por_destino,
    cargar_caracteristicas_destino,
    cargar_accesibilidad_por_destino,
    cargar_capacidad_por_destino,
    cargar_diversificacion_por_destino,
    cargar_temporada_baja_por_destino,
    cargar_impacto_local_por_destino,
    cargar_sentimiento_por_destino,
    cargar_modelo_lightgbm,
    calcular_candidato,
    normalizar_dict,
)

RANDOM_SEED = 42

CONSULTAS_MUESTRA = [
    "Busco unas vacaciones relajantes en la playa con buen clima",
    "Quiero un viaje cultural con museos e historia",
    "Aventura y deportes extremos para un grupo de amigos",
    "Vacaciones familiares con niños, todo incluido",
    "Escapada romantica para pareja, algo especial",
    "Viaje economico, mochilero, bajo presupuesto",
    "Lujo y exclusividad, hoteles de 5 estrellas",
    "Naturaleza y senderismo, contacto con el aire libre",
    "City break de fin de semana, poco tiempo",
    "Gastronomia local y experiencias culinarias",
    "Buceo y actividades acuaticas",
    "Destino tranquilo para desconectar del trabajo",
    "Fiesta y vida nocturna, ambiente joven",
    "Turismo de compras y ciudades cosmopolitas",
    "Playa paradisiaca, agua turquesa, snorkel",
    "Viaje de aniversario, algo memorable e intimo",
    "Turismo religioso y patrimonio historico",
    "Destino accesible en avion directo desde España",
    "Vacaciones de invierno, escapar del frio",
    "Isla tropical exotica, luna de miel",
]


def gini(valores: list[float]) -> float:
    """Coeficiente de Gini estandar sobre una lista de frecuencias."""
    if not valores or sum(valores) == 0:
        return 0.0
    v = sorted(valores)
    n = len(v)
    suma_acumulada = sum((i + 1) * x for i, x in enumerate(v))
    return (2 * suma_acumulada) / (n * sum(v)) - (n + 1) / n


def cr5(conteos_por_destino: Counter) -> float:
    """Concentration Ratio: fraccion del total que se lleva el top-5 destinos."""
    total = sum(conteos_por_destino.values())
    if total == 0:
        return 0.0
    top5 = sum(c for _, c in conteos_por_destino.most_common(5))
    return top5 / total


def generar_candidatos_por_consulta(db_path: str) -> list[list[dict]]:
    """Corre la etapa cara (embeddings + LightGBM + TDRS con pesos
    DEFAULT) UNA sola vez por consulta, reutilizable para probar muchas
    combinaciones de pesos de re-ranking sin recalcular todo cada vez."""
    print("Inicializando pipeline (una sola vez)...")
    query_pipeline = QueryPipeline()
    recommender = TuiRecommender()
    metadata = cargar_metadata_experiencias(db_path)
    ocupacion_por_destino = cargar_ocupacion_por_destino(db_path)
    sensibilidad_por_destino = cargar_caracteristicas_destino(db_path)
    accesibilidad_por_destino = cargar_accesibilidad_por_destino(db_path)
    capacidad_por_destino = cargar_capacidad_por_destino(db_path)
    diversificacion_por_destino = cargar_diversificacion_por_destino(db_path)
    temporada_baja_por_destino = cargar_temporada_baja_por_destino(db_path)
    impacto_local_por_destino = cargar_impacto_local_por_destino(db_path)
    sentimiento_por_destino = cargar_sentimiento_por_destino(db_path)
    tdrs_calc = TDRSCalculator()  # pesos DEFAULT, no se tocan

    modelo_lgbm, _ = cargar_modelo_lightgbm()
    precios = normalizar_dict({eid: m["price_eur"] for eid, m in metadata.items()})
    duraciones = normalizar_dict({eid: m["duration_hrs"] for eid, m in metadata.items()})
    ratings = normalizar_dict({eid: m["rating"] for eid, m in metadata.items()})
    reviews = normalizar_dict({eid: m["review_count"] for eid, m in metadata.items()})

    todos_los_candidatos = []
    for i, consulta in enumerate(CONSULTAS_MUESTRA, 1):
        print(f"  [{i}/{len(CONSULTAS_MUESTRA)}] '{consulta[:50]}...'")
        query_vector = query_pipeline.process_query(consulta)
        candidatos_afinidad = recommender.search(query_vector, top_k=30)

        candidatos = []
        for c in candidatos_afinidad:
            id_paq = c["id_paquete"]
            meta = metadata.get(id_paq, {"destino_nombre": "desconocido"})
            destino = meta["destino_nombre"]

            # Reutiliza EXACTAMENTE la misma logica de scoring que usa
            # recomendar() en produccion (mezcla de 3 señales de afinidad
            # + TDRS) -- antes este script tenia su propia copia,
            # desactualizada respecto a produccion (usaba solo LightGBM
            # o solo coseno, nunca la mezcla de 3 señales real), lo que
            # invalidaba cualquier optimizacion de pesos hecha con esa
            # version vieja. Unificado el 31/08.
            candidato, _ = calcular_candidato(
                id_paq, destino, c["score_similitud"],
                ocupacion_por_destino, sensibilidad_por_destino,
                accesibilidad_por_destino, capacidad_por_destino,
                diversificacion_por_destino, temporada_baja_por_destino,
                impacto_local_por_destino, sentimiento_por_destino,
                modelo_lgbm, precios, duraciones, ratings, reviews, tdrs_calc,
            )
            candidatos.append(candidato)
        todos_los_candidatos.append(candidatos)

    return todos_los_candidatos


def evaluar_pesos(candidatos_por_consulta: list[list[dict]], pesos: dict, k: int = 10) -> dict:
    """Aplica el re-ranking con 'pesos' dados a cada consulta, agrega la
    distribucion de destinos elegidos en TODAS las consultas, y calcula
    Gini/CR5/afinidad promedio sobre ese agregado."""
    reranker = ReRankingEngine()
    reranker.SCENARIOS = {**ReRankingEngine.SCENARIOS, "custom": pesos}

    conteo_destinos = Counter()
    afinidades = []
    for candidatos in candidatos_por_consulta:
        ranking = reranker.rank(candidatos, escenario="custom", k=k)
        for r in ranking:
            conteo_destinos[r["destino_nombre"]] += 1
            afinidades.append(r["afinidad"])

    return {
        "gini": gini(list(conteo_destinos.values())),
        "cr5": cr5(conteo_destinos),
        "afinidad_promedio": float(np.mean(afinidades)) if afinidades else 0.0,
        "destinos_distintos": len(conteo_destinos),
    }


def buscar_pesos_optimos(
    candidatos_por_consulta: list[list[dict]],
    afinidad_minima_relativa: float,
    n_intentos: int = 60,
    alpha_maximo: float | None = None,
    beta_minimo: float | None = None,
) -> tuple[dict, dict]:
    """Busqueda aleatoria (Dirichlet para alpha/beta/gamma/delta, uniforme
    para lambda) de la combinacion de pesos con menor Gini, sujeta a un
    piso minimo de afinidad promedio relativa al escenario tradicional.

    alpha_maximo / beta_minimo: opcionales, fuerzan que un escenario sea
    estructuralmente MAS agresivo en redistribucion que otro (ver uso en
    intensivo). Sin esto, dos busquedas independientes pueden converger
    al mismo punto por casualidad, sin relacion de orden garantizada."""
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    ref = evaluar_pesos(candidatos_por_consulta, ReRankingEngine.SCENARIOS["tradicional"])
    piso_afinidad = ref["afinidad_promedio"] * afinidad_minima_relativa

    mejor_pesos, mejor_gini, mejor_metrics = None, float("inf"), None
    for _ in range(n_intentos):
        a, b, g, d = np.random.dirichlet([1, 1, 1, 1])
        lam = np.random.uniform(0.0, 0.30)

        if alpha_maximo is not None and a > alpha_maximo:
            continue
        if beta_minimo is not None and b < beta_minimo:
            continue

        pesos = {"alpha": float(a), "beta": float(b), "gamma": float(g),
                 "delta": float(d), "lambda_": float(lam)}
        metrics = evaluar_pesos(candidatos_por_consulta, pesos)
        if metrics["afinidad_promedio"] < piso_afinidad:
            continue
        if metrics["gini"] < mejor_gini:
            mejor_gini = metrics["gini"]
            mejor_pesos = pesos
            mejor_metrics = metrics

    return mejor_pesos, mejor_metrics


def main():
    db_path = "data/tui_recomendador.db"

    print("=" * 60)
    print("  OPTIMIZACION DE PESOS DE RE-RANKING (Gini/CR5 reales)")
    print("=" * 60)

    candidatos_por_consulta = generar_candidatos_por_consulta(db_path)

    print("\n--- Rendimiento ACTUAL (pesos fijos del informe) ---")
    for escenario in ["tradicional", "moderado", "intensivo"]:
        m = evaluar_pesos(candidatos_por_consulta, ReRankingEngine.SCENARIOS[escenario])
        print(f"  {escenario:12s} | Gini={m['gini']:.4f} | CR5={m['cr5']:.4f} | "
              f"afinidad_prom={m['afinidad_promedio']:.4f} | destinos_distintos={m['destinos_distintos']}")

    print("\n--- Buscando pesos optimizados: MODERADO (piso afinidad 90%) ---")
    pesos_moderado, m_moderado = buscar_pesos_optimos(candidatos_por_consulta, afinidad_minima_relativa=0.90)
    if pesos_moderado:
        print(f"  Pesos: {pesos_moderado}")
        print(f"  Gini={m_moderado['gini']:.4f} | CR5={m_moderado['cr5']:.4f} | "
              f"afinidad_prom={m_moderado['afinidad_promedio']:.4f}")
    else:
        print("  No se encontro combinacion que cumpla el piso de afinidad.")

    print("\n--- Buscando pesos optimizados: INTENSIVO (piso afinidad 70%, "
          "forzado a redistribuir mas que moderado) ---")
    alpha_mod = pesos_moderado["alpha"] if pesos_moderado else 1.0
    beta_mod = pesos_moderado["beta"] if pesos_moderado else 0.0
    pesos_intensivo, m_intensivo = buscar_pesos_optimos(
        candidatos_por_consulta, afinidad_minima_relativa=0.70,
        alpha_maximo=alpha_mod * 0.80, beta_minimo=beta_mod * 1.15,
        n_intentos=300,
    )

    if pesos_intensivo:
        print(f"  Pesos: {pesos_intensivo}")
        print(f"  Gini={m_intensivo['gini']:.4f} | CR5={m_intensivo['cr5']:.4f} | "
              f"afinidad_prom={m_intensivo['afinidad_promedio']:.4f}")
    else:
        print("  No se encontro combinacion que cumpla el piso de afinidad.")

    print("\n" + "=" * 60)
    print("  Comparacion final: pesos fijos (informe) vs optimizados")
    print("=" * 60)
    m_moderado_actual = evaluar_pesos(candidatos_por_consulta, ReRankingEngine.SCENARIOS["moderado"])
    m_intensivo_actual = evaluar_pesos(candidatos_por_consulta, ReRankingEngine.SCENARIOS["intensivo"])
    print(f"  MODERADO  actual:      Gini={m_moderado_actual['gini']:.4f}")
    if pesos_moderado:
        print(f"  MODERADO  optimizado:  Gini={m_moderado['gini']:.4f}  "
              f"({'MEJOR' if m_moderado['gini'] < m_moderado_actual['gini'] else 'sin mejora'})")
    print(f"  INTENSIVO actual:      Gini={m_intensivo_actual['gini']:.4f}")
    if pesos_intensivo:
        print(f"  INTENSIVO optimizado:  Gini={m_intensivo['gini']:.4f}  "
              f"({'MEJOR' if m_intensivo['gini'] < m_intensivo_actual['gini'] else 'sin mejora'})")
    print("=" * 60)


if __name__ == "__main__":
    main()