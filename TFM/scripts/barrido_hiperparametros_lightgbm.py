"""
Barrido de hiperparametros de LightGBM Ranker, enfocado en si
'feature_fraction' (fraccion aleatoria de variables que ve cada arbol)
reduce el dominio de 'accesibilidad' (66.6% de importancia promedio,
confirmado con 100 corridas en evaluar_robustez_lightgbm.py) forzando
al modelo a apoyarse tambien en las otras 10 variables.

Prueba la combinacion de:
  - feature_fraction: 0.5, 0.6, 0.7, 0.8, 1.0 (1.0 = sin restriccion, el default de hoy)
  - num_leaves: 15, 31, 63
  - min_data_in_leaf: 5, 10, 20

Para cada combinacion, promedia sobre 5 semillas distintas (no una sola
corrida, para no confundir ruido aleatorio con una mejora real).

NO sobreescribe el modelo de produccion -- solo genera evidencia para
decidir si vale la pena reentrenar con nuevos hiperparametros.

Uso:
    cd TFM
    python scripts/barrido_hiperparametros_lightgbm.py
"""
import itertools
import sys
import time
from pathlib import Path

import numpy as np
import lightgbm as lgb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import train_lightgbm_ranker as tlr

FEATURE_FRACTIONS = [0.5, 0.6, 0.7, 0.8, 1.0]
NUM_LEAVES_OPCIONES = [15, 31, 63]
MIN_DATA_IN_LEAF_OPCIONES = [5, 10, 20]
SEMILLAS_POR_COMBO = 5

FEATURE_NAMES = [
    "precio", "duracion", "rating", "review_count", "ocupacion",
    "sensibilidad_ambiental", "accesibilidad", "capacidad",
    "diversificacion", "temporada_baja", "impacto_local",
]


def entrenar_y_evaluar(db_path: str, seed: int, feature_fraction: float, num_leaves: int, min_data_in_leaf: int) -> dict:
    tlr.RANDOM_SEED = seed
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
        "num_leaves": num_leaves,
        "min_data_in_leaf": min_data_in_leaf,
        "feature_fraction": feature_fraction,
        "verbose": -1,
        "seed": seed,
    }
    model = lgb.train(
        params, train_data, num_boost_round=500,
        valid_sets=[val_data], valid_names=["validacion"],
        callbacks=[lgb.early_stopping(stopping_rounds=20, verbose=False)],
    )

    precision, ndcg = tlr.evaluar(model, X_test, test_candidatos, k=10)
    importancias = model.feature_importance(importance_type="gain")
    total = sum(importancias) or 1
    importancia_accesibilidad = float(importancias[FEATURE_NAMES.index("accesibilidad")]) / total

    return {
        "precision": precision, "ndcg": ndcg,
        "importancia_accesibilidad": importancia_accesibilidad,
        "mejor_iteracion": model.best_iteration,
    }


def main():
    db_path = "data/tui_recomendador.db"
    combos = list(itertools.product(FEATURE_FRACTIONS, NUM_LEAVES_OPCIONES, MIN_DATA_IN_LEAF_OPCIONES))
    total_corridas = len(combos) * SEMILLAS_POR_COMBO

    print(f"Barrido de hiperparametros: {len(combos)} combinaciones x "
          f"{SEMILLAS_POR_COMBO} semillas = {total_corridas} corridas totales\n")

    t0 = time.time()
    resultados_por_combo = []

    for i, (ff, nl, mdl) in enumerate(combos, 1):
        precisiones, ndcgs, importancias_acc = [], [], []
        for s in range(SEMILLAS_POR_COMBO):
            seed = 2000 + i * 10 + s
            r = entrenar_y_evaluar(db_path, seed, ff, nl, mdl)
            precisiones.append(r["precision"])
            ndcgs.append(r["ndcg"])
            importancias_acc.append(r["importancia_accesibilidad"])

        resumen = {
            "feature_fraction": ff, "num_leaves": nl, "min_data_in_leaf": mdl,
            "precision_media": float(np.mean(precisiones)),
            "ndcg_medio": float(np.mean(ndcgs)),
            "importancia_accesibilidad_media": float(np.mean(importancias_acc)),
        }
        resultados_por_combo.append(resumen)
        print(f"  [{i}/{len(combos)}] ff={ff} num_leaves={nl} min_data={mdl} | "
              f"Precision@10={resumen['precision_media']:.4f} | "
              f"NDCG@10={resumen['ndcg_medio']:.4f} | "
              f"accesibilidad={resumen['importancia_accesibilidad_media']*100:.1f}% | "
              f"({time.time()-t0:.0f}s transcurridos)")

    print(f"\n{'='*70}")
    print(f"  RESULTADOS ORDENADOS POR NDCG@10 (mejores primero)")
    print(f"{'='*70}")
    top10 = sorted(resultados_por_combo, key=lambda r: -r["ndcg_medio"])[:10]
    for r in top10:
        print(f"  ff={r['feature_fraction']} num_leaves={r['num_leaves']} "
              f"min_data={r['min_data_in_leaf']} | "
              f"Precision@10={r['precision_media']:.4f} | NDCG@10={r['ndcg_medio']:.4f} | "
              f"accesibilidad={r['importancia_accesibilidad_media']*100:.1f}%")

    print(f"\n{'='*70}")
    print(f"  EFECTO DE feature_fraction SOBRE EL DOMINIO DE ACCESIBILIDAD")
    print(f"  (promediado sobre todas las combinaciones de num_leaves/min_data)")
    print(f"{'='*70}")
    for ff in FEATURE_FRACTIONS:
        subset = [r for r in resultados_por_combo if r["feature_fraction"] == ff]
        acc_media = np.mean([r["importancia_accesibilidad_media"] for r in subset])
        ndcg_media = np.mean([r["ndcg_medio"] for r in subset])
        print(f"  feature_fraction={ff}: accesibilidad={acc_media*100:.1f}% | NDCG@10 promedio={ndcg_media:.4f}")

    print(f"\nTiempo total: {(time.time()-t0)/60:.1f} minutos")
    print("\nNOTA: este script NO sobreescribe el modelo de produccion.")
    print("Si algun feature_fraction < 1.0 da mejor NDCG@10 con menor")
    print("dominio de accesibilidad, vale la pena actualizar los")
    print("hiperparametros por defecto en train_lightgbm_ranker.py y")
    print("reentrenar el modelo real con ese ajuste.")


if __name__ == "__main__":
    main()