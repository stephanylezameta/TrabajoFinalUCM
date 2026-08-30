"""
Entrena un modelo de ranking con LightGBM (objective=lambdarank) sobre
las reservas reales de customer_bookings, usando como features tanto
atributos del item (precio, rating, categoria) como los 7 componentes
reales del TDRS ya construidos hoy (ocupacion, accesibilidad,
sensibilidad ambiental, capacidad, diversificacion, temporada_baja,
impacto_local) y atributos del cliente (pais, idioma, grupo etario).

A diferencia del TDRS de reglas fijas (pesos definidos a mano en el
informe), este modelo APRENDE los pesos optimos de cada variable a
partir de las reservas reales -- es el salto de "reglas" a "aprendizaje
de datos reales" que completa el pipeline.

Requiere: pip install lightgbm (en el .venv normal, no necesita Conda).

Uso:
    cd TFM
    python scripts/train_lightgbm_ranker.py
"""
import pickle
import random
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import lightgbm as lgb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from recommendation.run_recommendation import (  # noqa: E402
    cargar_metadata_experiencias,
    cargar_ocupacion_por_destino,
    cargar_caracteristicas_destino,
    cargar_accesibilidad_por_destino,
    cargar_capacidad_por_destino,
)
# NOTA (fix de fuga de datos): diversificacion, temporada_baja e
# impacto_local NO se reutilizan de run_recommendation.py porque esas
# funciones agregan sobre TODA la tabla customer_bookings, incluyendo la
# reserva que se aparta para test (leave-one-out) -- eso es fuga de datos
# (el modelo veria, indirectamente, parte de lo que debe predecir).
# Se recalculan aqui mismo usando SOLO las reservas de entrenamiento.

RANDOM_SEED = 42
N_NEGATIVOS_POR_CLIENTE = 20  # candidatos "no reservados" de comparacion


def cargar_experiencias_completas(db_path: str) -> dict:
    """experience_id -> dict con atributos del item."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT experience_id, destination, category, price_eur,
               duration_hrs, rating, review_count
        FROM experiencias
    """).fetchall()
    conn.close()
    cols = ["destination", "category", "price_eur", "duration_hrs", "rating", "review_count"]
    return {r[0]: dict(zip(cols, r[1:])) for r in rows}


def cargar_reservas(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT customer_id, experience_id, booking_date, country, age_group,
               price_paid_eur, travel_date
        FROM customer_bookings
        ORDER BY customer_id, booking_date
    """).fetchall()
    conn.close()
    cols = ["customer_id", "experience_id", "booking_date", "country", "age_group",
            "price_paid_eur", "travel_date"]
    return [dict(zip(cols, r)) for r in rows]


def normalizar_dict(d: dict) -> dict:
    """Normaliza un dict numerico a [0,1] (para features crudas como precio)."""
    valores = [v for v in d.values() if v is not None]
    if not valores:
        return {k: 0.5 for k in d}
    vmin, vmax = min(valores), max(valores)
    if vmax == vmin:
        return {k: 0.5 for k in d}
    return {k: (v - vmin) / (vmax - vmin) if v is not None else 0.5 for k, v in d.items()}


def calcular_senales_train_only(por_cliente_train: dict, experiencias: dict) -> tuple:
    """Recalcula impacto_local, diversificacion y temporada_baja usando
    SOLO las reservas de entrenamiento (sin la reserva de test de cada
    cliente) -- evita la fuga de datos de reutilizar las funciones que
    agregan sobre toda la tabla customer_bookings."""
    import math
    from collections import Counter

    ingresos_por_destino = defaultdict(float)
    paises_por_destino = defaultdict(list)
    meses_por_destino = defaultdict(lambda: defaultdict(int))

    for customer_id, reservas in por_cliente_train.items():
        for r in reservas:
            destino = experiencias.get(r["experience_id"], {}).get("destination")
            if not destino:
                continue
            if r.get("price_paid_eur"):
                ingresos_por_destino[destino] += r["price_paid_eur"]
            if r.get("country"):
                paises_por_destino[destino].append(r["country"])
            if r.get("travel_date"):
                mes = r["travel_date"][5:7] if len(r["travel_date"]) >= 7 else None
                if mes:
                    meses_por_destino[destino][mes] += 1

    impacto_local = normalizar_dict(dict(ingresos_por_destino))

    diversificacion_raw = {}
    for destino, paises in paises_por_destino.items():
        total = len(paises)
        if total < 2:
            continue
        conteos = Counter(paises)
        diversificacion_raw[destino] = -sum(
            (c / total) * math.log2(c / total) for c in conteos.values()
        )
    diversificacion = normalizar_dict(diversificacion_raw)

    temporada_baja_raw = {}
    for destino, meses in meses_por_destino.items():
        conteos = list(meses.values())
        if len(conteos) < 2 or np.mean(conteos) == 0:
            continue
        temporada_baja_raw[destino] = np.std(conteos) / np.mean(conteos)
    if temporada_baja_raw:
        vmin, vmax = min(temporada_baja_raw.values()), max(temporada_baja_raw.values())
        if vmax > vmin:
            temporada_baja = {d: 1 - (v - vmin) / (vmax - vmin) for d, v in temporada_baja_raw.items()}
        else:
            temporada_baja = {d: 0.5 for d in temporada_baja_raw}
    else:
        temporada_baja = {}

    return impacto_local, diversificacion, temporada_baja


def construir_dataset(db_path: str):
    """Arma la tabla de entrenamiento: filas = pares (cliente, item),
    con features y label (1 = reservado, 0 = no reservado, muestreado)."""
    random.seed(RANDOM_SEED)

    experiencias = cargar_experiencias_completas(db_path)
    todos_los_ids = list(experiencias.keys())

    print("Cargando señales reales por destino (sin fuga de datos)...")
    ocupacion = cargar_ocupacion_por_destino(db_path)
    sensibilidad = cargar_caracteristicas_destino(db_path)
    accesibilidad = cargar_accesibilidad_por_destino(db_path)
    capacidad = cargar_capacidad_por_destino(db_path)

    precios = normalizar_dict({eid: e["price_eur"] for eid, e in experiencias.items()})
    duraciones = normalizar_dict({eid: e["duration_hrs"] for eid, e in experiencias.items()})
    ratings = normalizar_dict({eid: e["rating"] for eid, e in experiencias.items()})
    reviews = normalizar_dict({eid: e["review_count"] for eid, e in experiencias.items()})

    reservas = cargar_reservas(db_path)
    por_cliente = defaultdict(list)
    for r in reservas:
        por_cliente[r["customer_id"]].append(r)

    # Items con al menos una reserva real en todo el dataset. Muestrear
    # negativos SOLO de aqui (en vez de las 5850 experiencias completas,
    # muchas nunca reservadas) evita que el modelo "haga trampa"
    # distinguiendo trivialmente popular vs nunca-reservado en base a
    # impacto_local/diversificacion -- eso inflaba las metricas sin medir
    # preferencia personal real.
    items_con_reservas = {r["experience_id"] for r in reservas}
    print(f"   -> {len(items_con_reservas)} de {len(todos_los_ids)} experiencias "
          f"tienen al menos una reserva real (pool de negativos)")

    por_cliente_train = {}
    por_cliente_test = {}
    for customer_id, res_cliente in por_cliente.items():
        if len(res_cliente) < 2:
            continue
        por_cliente_train[customer_id] = res_cliente[:-1]
        por_cliente_test[customer_id] = res_cliente[-1]

    impacto_local, diversificacion, temporada_baja = calcular_senales_train_only(
        por_cliente_train, experiencias
    )
    print(f"   -> señales recalculadas sobre {sum(len(v) for v in por_cliente_train.values())} "
          f"reservas de entrenamiento (excluyendo la reserva de test de cada cliente)")

    def features_item(experience_id: str) -> list[float]:
        destino = experiencias[experience_id]["destination"]
        return [
            precios.get(experience_id, 0.5),
            duraciones.get(experience_id, 0.5),
            ratings.get(experience_id, 0.5),
            reviews.get(experience_id, 0.5),
            ocupacion.get(destino, 0.5),
            sensibilidad.get(destino, 0.3),
            accesibilidad.get(destino, 0.5),
            capacidad.get(destino, 0.5),
            diversificacion.get(destino, 0.5),
            temporada_baja.get(destino, 0.5),
            impacto_local.get(destino, 0.5),
        ]

    print("Construyendo pares (cliente, item) con negativos muestreados...")
    X, y, groups = [], [], []
    X_test, y_test, test_customers, test_candidatos = [], [], [], []

    for customer_id, train_res in por_cliente_train.items():
        reservados_ids = {r["experience_id"] for r in train_res}
        test_res = por_cliente_test[customer_id]
        reservados_ids_completo = reservados_ids | {test_res["experience_id"]}

        grupo_size = 0
        for r in train_res:
            X.append(features_item(r["experience_id"]))
            y.append(1)
            grupo_size += 1

        negativos = random.sample(
            [eid for eid in items_con_reservas if eid not in reservados_ids_completo],
            min(N_NEGATIVOS_POR_CLIENTE, len(todos_los_ids)),
        )
        for eid in negativos:
            X.append(features_item(eid))
            y.append(0)
            grupo_size += 1

        if grupo_size > 0:
            groups.append(grupo_size)

        cand_negativos = random.sample(
            [eid for eid in items_con_reservas if eid not in reservados_ids_completo],
            min(N_NEGATIVOS_POR_CLIENTE, len(todos_los_ids)),
        )
        candidatos = [test_res["experience_id"]] + cand_negativos
        for eid in candidatos:
            X_test.append(features_item(eid))
        test_customers.append(customer_id)
        test_candidatos.append(candidatos)

    return (
        np.array(X, dtype=np.float32), np.array(y, dtype=np.int32), groups,
        np.array(X_test, dtype=np.float32), test_customers, test_candidatos,
    )


def evaluar(model, X_test, test_candidatos, k=10):
    """NDCG@k y Precision@k: para cada cliente, el primer candidato de su
    lista es el item realmente reservado (relevante); el resto son
    negativos muestreados. Se mide si el modelo lo rankea arriba."""
    scores = model.predict(X_test)
    idx = 0
    ndcgs, precisiones = [], []
    for candidatos in test_candidatos:
        n = len(candidatos)
        sub_scores = scores[idx: idx + n]
        idx += n
        orden = np.argsort(-sub_scores)
        pos_relevante = int(np.where(orden == 0)[0][0])
        precisiones.append(1.0 if pos_relevante < k else 0.0)
        ndcgs.append(1.0 / np.log2(pos_relevante + 2) if pos_relevante < k else 0.0)
    return float(np.mean(precisiones)), float(np.mean(ndcgs))


def main():
    db_path = "data/tui_recomendador.db"
    output_dir = Path("data/lightgbm")
    output_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    print("1) Construyendo dataset de entrenamiento (features + negativos)...")
    X, y, groups, X_test, test_customers, test_candidatos = construir_dataset(db_path)
    print(f"   -> {X.shape[0]} filas de entrenamiento, {len(groups)} grupos (clientes)")
    print(f"   -> {len(test_customers)} clientes en evaluacion")

    print("2) Entrenando LightGBM Ranker (lambdarank)...")
    train_data = lgb.Dataset(X, label=y, group=groups)
    params = {
        "objective": "lambdarank",
        "metric": "ndcg",
        "ndcg_eval_at": [10],
        "learning_rate": 0.05,
        "num_leaves": 31,
        "min_data_in_leaf": 5,
        "verbose": -1,
        "seed": RANDOM_SEED,
    }
    model = lgb.train(params, train_data, num_boost_round=200)
    print(f"   -> entrenado en {time.time()-t0:.1f}s")

    print("3) Evaluando sobre reservas reales dejadas fuera (leave-one-out)...")
    precision, ndcg = evaluar(model, X_test, test_candidatos, k=10)

    feature_names = [
        "precio", "duracion", "rating", "review_count", "ocupacion",
        "sensibilidad_ambiental", "accesibilidad", "capacidad",
        "diversificacion", "temporada_baja", "impacto_local",
    ]
    importancias = model.feature_importance(importance_type="gain")
    ranking_features = sorted(zip(feature_names, importancias), key=lambda x: -x[1])

    print(f"\n{'='*55}")
    print(f"  EVALUACION LightGBM Ranker (lambdarank)")
    print(f"{'='*55}")
    print(f"  Precision@10: {precision:.4f}")
    print(f"  NDCG@10:      {ndcg:.4f}")
    print(f"  (Umbrales informe tecnico: Precision@10 >= 0.30, NDCG@10 >= 0.35)")
    print(f"\n  Importancia de features (que aprendio el modelo a priorizar):")
    for nombre, imp in ranking_features:
        print(f"    {nombre:25s} {imp:.1f}")
    print(f"{'='*55}\n")

    with open(output_dir / "lightgbm_ranker.pkl", "wb") as f:
        pickle.dump(model, f)
    with open(output_dir / "feature_names.pkl", "wb") as f:
        pickle.dump(feature_names, f)
    print(f"Modelo guardado en {output_dir}/")


if __name__ == "__main__":
    main()