"""
Orquestador del flujo completo de recomendación:
consulta de texto -> vector -> afinidad -> TDRS -> re-ranking (3 escenarios).

Este archivo estaba vacio; conecta las piezas ya existentes (QueryPipeline,
TuiRecommender, TDRSCalculator, ReRankingEngine) que hasta ahora funcionaban
de forma aislada.

Uso:
    cd TFM
    python scripts/recommendation/run_recommendation.py
    python scripts/recommendation/run_recommendation.py --db data/tui_recomendador.db --top-k 10
"""
import argparse
import sqlite3
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.recommendation.pipeline_consultas import QueryPipeline
from scripts.recommendation.recommendation_engine import TuiRecommender
from src.recommender.tdrs_calculator import TDRSCalculator
from src.recommender.reranking_engine import ReRankingEngine


def cargar_metadata_experiencias(db_path: str) -> dict:
    """id_paquete (experience_id) -> {destino_nombre, category}."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT experience_id, destination, category FROM experiencias"
    ).fetchall()
    conn.close()
    return {r[0]: {"destino_nombre": r[1], "category": r[2]} for r in rows}


def cargar_ocupacion_por_destino(db_path: str) -> dict:
    """Ocupación real normalizada [0,1] por destino (Eurostat/INE)."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("""
            SELECT destino_nombre, AVG(valor)
            FROM indicadores_destino
            WHERE tipo_indicador = 'ocupacion_hotelera_mensual'
            GROUP BY destino_nombre
        """).fetchall()
    finally:
        conn.close()
    valores = {d: v for d, v in rows}
    if valores:
        vmin, vmax = min(valores.values()), max(valores.values())
        if vmax > vmin:
            valores = {d: (v - vmin) / (vmax - vmin) for d, v in valores.items()}
    return valores


def recomendar(
    texto_consulta: str,
    db_path: str = "data/tui_recomendador.db",
    top_k_candidatos: int = 30,
    k_final: int = 10,
) -> dict[str, list[dict]]:
    """Ejecuta el flujo completo y devuelve los 3 rankings (tradicional/moderado/intensivo)."""

    print(f"\n1) Vectorizando consulta: '{texto_consulta}'")
    query_pipeline = QueryPipeline()
    query_vector = query_pipeline.process_query(texto_consulta)

    print("2) Buscando candidatos por afinidad (similitud coseno)...")
    recommender = TuiRecommender()
    candidatos_afinidad = recommender.search(query_vector, top_k=top_k_candidatos)

    print("3) Calculando TDRS por candidato (redistribución/sostenibilidad)...")
    metadata = cargar_metadata_experiencias(db_path)
    ocupacion_por_destino = cargar_ocupacion_por_destino(db_path)
    tdrs_calc = TDRSCalculator()

    candidatos = []
    for c in candidatos_afinidad:
        id_paq = c["id_paquete"]
        meta = metadata.get(id_paq, {"destino_nombre": "desconocido", "category": ""})
        destino = meta["destino_nombre"]
        # Afinidad viene como similitud coseno (puede ser negativa); se
        # recorta a [0,1] porque TDRSCalculator exige ese rango.
        afinidad_norm = max(0.0, min(1.0, (c["score_similitud"] + 1) / 2))
        ocupacion_real = ocupacion_por_destino.get(destino, 0.5)

        tdrs = tdrs_calc.calculate(
            afinidad=afinidad_norm,
            ocupacion=ocupacion_real,
            # Resto de componentes (capacidad, accesibilidad, impacto_local,
            # temporada_baja, diversificacion, sensibilidad_ambiental):
            # sin fuente real conectada aun, quedan en el valor neutro por
            # defecto de TDRSCalculator.calculate(). Ver seccion "Pendientes"
            # de la memoria tecnica -- prioridad para la proxima etapa.
        )

        candidatos.append({
            "id_paquete": id_paq,
            "destino_nombre": destino,
            "afinidad": afinidad_norm,
            "tdrs": tdrs,
            "sostenibilidad": max(0.0, tdrs),
            "capacidad": 0.5,
            "ocupacion": ocupacion_real,
        })

    print("4) Aplicando re-ranking (3 escenarios)...")
    reranker = ReRankingEngine()
    rankings = reranker.rank_all_scenarios(candidatos, k=k_final)

    return rankings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/tui_recomendador.db")
    parser.add_argument(
        "--consulta", default="Busco unas vacaciones relajantes en la playa con buen clima",
    )
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    rankings = recomendar(args.consulta, db_path=args.db, k_final=args.top_k)

    for escenario, resultados in rankings.items():
        print(f"\n{'='*60}")
        print(f"  ESCENARIO: {escenario.upper()}")
        print(f"{'='*60}")
        for i, r in enumerate(resultados, 1):
            print(f"  {i:2d}. {r['id_paquete']} | {r['destino_nombre']:20s} | "
                  f"score_final={r['score_final']:.4f} | tdrs={r['tdrs']:.3f}")


if __name__ == "__main__":
    main()