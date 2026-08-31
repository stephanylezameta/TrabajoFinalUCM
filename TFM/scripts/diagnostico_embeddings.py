import sys
sys.path.insert(0, '.')
from scripts.recommendation.pipeline_consultas import QueryPipeline
from scripts.recommendation.recommendation_engine import TuiRecommender

pipeline = QueryPipeline()
recommender = TuiRecommender()

for consulta in ["Turismo cultural, museos e historia", "Aventura y deportes extremos para un grupo de amigos", "Playa relajante con buen clima"]:
    vector = pipeline.process_query(consulta)
    resultados = recommender.search(vector, top_k=10)
    print(f"\n--- {consulta} ---")
    for r in resultados[:10]:
        print(f"  {r['id_paquete']} score={r['score_similitud']:.4f}")