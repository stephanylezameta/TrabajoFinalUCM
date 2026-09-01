"""
Repite el entrenamiento + evaluacion de LightGBM Ranker N veces, con
distintas semillas aleatorias (split train/val, muestreo de negativos),
para saber si el dominio de 'accesibilidad' sobre las demas variables es
consistente de verdad o una casualidad de una sola corrida -- y para
reportar Precision@10/NDCG@10 con un margen de error real, no un numero
suelto de una unica ejecucion.

Uso:
    cd TFM
    python scripts/evaluar_robustez_lightgbm.py
    python scripts/evaluar_robustez_lightgbm.py --intentos 30
"""
import argparse
import random
import sys
import time
from pathlib import Path

import numpy as np
import lightgbm as lgb

# Mismo patron que usa train_lightgbm_ranker.py: agrega la carpeta
# scripts/ (la propia, no la raiz del proyecto) al path, e importa el
# modulo vecino directo, sin prefijo "scripts.".
sys.path.insert(0, str(Path(__file__).resolve().parent))

import train_lightgbm_ranker as tlr


def correr_una_vez(db_path: str, seed: int) -> dict:
    """Reproduce exactamente el flujo de train_lightgbm_ranker.py pero
    con una semilla distinta, sin tocar los pesos guardados en disco
    (no sobreescribe el modelo de produccion)."""
    tlr.RANDOM_SEED = seed  # sobreescribe la constante del modulo importado

    X, y, groups, X_val, y_val, groups_val, X_test, test_customers, test_candidatos = (
        tlr.construir_dataset(db_path)
    )

    train_data = lgb.Dataset(X, label=y, group=groups)
    val_data = lgb.Dataset(X_val, label=y_val, group=groups_val, reference=train_data)
    params = {
        "objective": "lambdarank",
        "metric": "ndcg",
        "ndcg_eval_at": [10],
        "learning_rate": 0.05,
        "num_leaves": 31,
        "min_data_in_leaf": 5,
        "verbose": -1,
        "seed": seed,
    }
    model = lgb.train(
        params, train_data, num_boost_round=500,
        valid_sets=[val_data], valid_names=["validacion"],
        callbacks=[lgb.early_stopping(stopping_rounds=20, verbose=False)],
    )

    precision, ndcg = tlr.evaluar(model, X_test, test_candidatos, k=10)

    feature_names = [
        "precio", "duracion", "rating", "review_count", "ocupacion",
        "sensibilidad_ambiental", "accesibilidad", "capacidad",
        "diversificacion", "temporada_baja", "impacto_local",
    ]
    importancias = model.feature_importance(importance_type="gain")
    total_importancia = sum(importancias) or 1
    importancia_relativa = {
        nombre: float(imp) / total_importancia
        for nombre, imp in zip(feature_names, importancias)
    }

    return {
        "precision": precision,
        "ndcg": ndcg,
        "mejor_iteracion": model.best_iteration,
        "importancia_relativa": importancia_relativa,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/tui_recomendador.db")
    parser.add_argument("--intentos", type=int, default=30)
    args = parser.parse_args()

    print(f"Evaluando robustez de LightGBM Ranker con {args.intentos} corridas "
          f"(semillas distintas)...\n")

    resultados = []
    t0 = time.time()
    for i in range(args.intentos):
        seed = 1000 + i
        t_inicio = time.time()
        r = correr_una_vez(args.db, seed)
        resultados.append(r)
        print(f"  [{i+1}/{args.intentos}] seed={seed} | "
              f"Precision@10={r['precision']:.4f} | NDCG@10={r['ndcg']:.4f} | "
              f"mejor_iter={r['mejor_iteracion']} | "
              f"({time.time()-t_inicio:.1f}s)")

    precisiones = [r["precision"] for r in resultados]
    ndcgs = [r["ndcg"] for r in resultados]

    feature_names = list(resultados[0]["importancia_relativa"].keys())
    importancia_promedio = {
        f: float(np.mean([r["importancia_relativa"][f] for r in resultados]))
        for f in feature_names
    }
    importancia_ordenada = sorted(importancia_promedio.items(), key=lambda x: -x[1])

    print(f"\n{'='*60}")
    print(f"  ROBUSTEZ DE LightGBM RANKER ({args.intentos} corridas)")
    print(f"{'='*60}")
    print(f"  Precision@10: {np.mean(precisiones):.4f} +/- {np.std(precisiones):.4f} "
          f"(min={min(precisiones):.4f}, max={max(precisiones):.4f})")
    print(f"  NDCG@10:      {np.mean(ndcgs):.4f} +/- {np.std(ndcgs):.4f} "
          f"(min={min(ndcgs):.4f}, max={max(ndcgs):.4f})")
    print(f"\n  Importancia relativa PROMEDIO por feature (sobre {args.intentos} corridas):")
    for nombre, imp in importancia_ordenada:
        print(f"    {nombre:25s} {imp*100:5.1f}%")
    print(f"\n  Tiempo total: {(time.time()-t0)/60:.1f} minutos")
    print(f"{'='*60}\n")
    print("NOTA: este script NO sobreescribe el modelo de produccion")
    print("(data/lightgbm/lightgbm_ranker.pkl) -- solo genera evidencia")
    print("estadistica para la memoria. El modelo en produccion sigue")
    print("siendo el entrenado por train_lightgbm_ranker.py.")


if __name__ == "__main__":
    main()