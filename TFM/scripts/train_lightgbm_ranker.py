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
from collections import defaultdict, Counter
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
    cargar_clima_por_destino,
    cargar_capacidad_sanitaria_por_destino,
    cargar_seguridad_criminalidad_por_destino,
)
# NOTA (fix de fuga de datos): diversificacion, temporada_baja e
# impacto_local NO se reutilizan de run_recommendation.py porque esas
# funciones agregan sobre TODA la tabla customer_bookings, incluyendo la
# reserva que se aparta para test (leave-one-out) -- eso es fuga de datos
# (el modelo veria, indirectamente, parte de lo que debe predecir).
# Se recalculan aqui mismo usando SOLO las reservas de entrenamiento.
# clima_por_destino y seguridad_por_destino SI se reutilizan directo:
# vienen de clima_destinos/seguridad_destinos, tablas independientes de
# customer_bookings, sin riesgo de fuga.

RANDOM_SEED = 42
N_NEGATIVOS_POR_CLIENTE = 20  # candidatos "no reservados" de comparacion

# Hiperparametros de produccion (31/08), ajustados tras barrido de 45
# combinaciones x 5 semillas: num_leaves=15 (arboles mas simples),
# min_data_in_leaf=20 (hojas mas conservadoras) y feature_fraction=0.8
# (cada arbol ve solo 80% de las variables) dieron, EN PROMEDIO sobre
# varias semillas, mejor NDCG@10 y menor dominio de 'accesibilidad' que
# los valores anteriores (num_leaves=31, min_data_in_leaf=5, sin
# feature_fraction). Definido UNA sola vez aca y reutilizado por
# evaluar_robustez_lightgbm.py y barrido_hiperparametros_lightgbm.py,
# para que ningun script quede con una copia desactualizada (como paso
# antes con 'sostenibilidad', duplicada y corregida en un solo lugar
# mientras el otro archivo seguia con la version vieja)."""
PARAMS_LIGHTGBM_BASE = {
    "objective": "lambdarank",
    "metric": "ndcg",
    "ndcg_eval_at": [10],
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_data_in_leaf": 20,
    "feature_fraction": 0.8,
    "verbose": -1,
}

# Nombres de features, en el MISMO orden que se arma el vector en
# features_item() mas abajo y en calcular_candidato() de
# run_recommendation.py (deben coincidir exactamente entre
# entrenamiento e inferencia). Centralizado aca (31/08) para que
# evaluar_robustez_lightgbm.py y barrido_hiperparametros_lightgbm.py no
# queden con una copia propia desactualizada. Clima se separo en 3
# señales y seguridad en 2 (01/09) -- todas datos reales (Open-Meteo,
# indicadores tipo Banco Mundial) que antes se promediaban a mano con
# peso fijo, quitandole a LightGBM la posibilidad de aprender el peso
# relativo real de cada una por si solo.
FEATURE_NAMES = [
    "precio", "duracion", "rating", "review_count", "ocupacion",
    "sensibilidad_ambiental", "accesibilidad", "capacidad",
    "diversificacion", "temporada_baja", "impacto_local",
    "temp_confort", "dias_secos", "horas_sol",
    "capacidad_sanitaria", "seguridad_criminalidad",
    "tiene_accesibilidad_real",
    "match_categoria_cliente", "diferencia_precio_habitual_cliente",
]


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
    temp_confort, dias_secos, horas_sol = cargar_clima_por_destino(db_path)
    capacidad_sanitaria = cargar_capacidad_sanitaria_por_destino(db_path)
    seguridad_criminalidad = cargar_seguridad_criminalidad_por_destino(db_path)

    precios = normalizar_dict({eid: e["price_eur"] for eid, e in experiencias.items()})
    duraciones = normalizar_dict({eid: e["duration_hrs"] for eid, e in experiencias.items()})
    ratings = normalizar_dict({eid: e["rating"] for eid, e in experiencias.items()})
    reviews = normalizar_dict({eid: e["review_count"] for eid, e in experiencias.items()})

    reservas = cargar_reservas(db_path)
    por_cliente = defaultdict(list)
    for r in reservas:
        por_cliente[r["customer_id"]].append(r)

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

    ids_train_completo = list(por_cliente_train.keys())
    random.shuffle(ids_train_completo)
    corte = int(len(ids_train_completo) * 0.85)
    ids_train = set(ids_train_completo[:corte])
    ids_val = set(ids_train_completo[corte:])
    print(f"   -> split interno: {len(ids_train)} clientes para entrenar, "
          f"{len(ids_val)} para validacion (early stopping)")

    impacto_local, diversificacion, temporada_baja = calcular_senales_train_only(
        por_cliente_train, experiencias
    )
    print(f"   -> señales recalculadas sobre {sum(len(v) for v in por_cliente_train.values())} "
          f"reservas de entrenamiento (excluyendo la reserva de test de cada cliente)")

    # Negativos "dificiles" por VECINDAD MULTI-EJE (31/08 v2), en vez de
    # un solo eje (accesibilidad). Diagnostico: al controlar solo
    # accesibilidad, el modelo migro a explotar 'impacto_local' (81.7%
    # de precision con UN SOLO split del arbol, confirmado de forma
    # aislada) -- cualquier variable agregada por destino que correlacione
    # con "popularidad general" sirve de atajo si no esta controlada en
    # el muestreo de negativos. La solucion real: controlar VARIAS
    # variables de popularidad a la vez (accesibilidad + impacto_local),
    # no solo una. Si tras esto una tercera variable vuelve a dominar,
    # confirma que el problema es estructural (popularidad real
    # correlaciona con reservas reales, es dificil de evitar del todo
    # sin datos de preferencia personal), no un ajuste pendiente.
    destinos_unicos = {experiencias[eid]["destination"] for eid in items_con_reservas}
    rango_accesibilidad = {
        d: i for i, d in enumerate(sorted(destinos_unicos, key=lambda d: accesibilidad.get(d, 0.5)))
    }
    rango_impacto = {
        d: i for i, d in enumerate(sorted(destinos_unicos, key=lambda d: impacto_local.get(d, 0.5)))
    }
    VENTANA_VECINDAD = 8  # un poco mas ancha, al controlar 2 ejes a la vez

    items_por_destino = defaultdict(list)
    for eid in items_con_reservas:
        items_por_destino[experiencias[eid]["destination"]].append(eid)

    def vecinos_de(destino: str) -> list[str]:
        """Items de destinos con accesibilidad E impacto_local parecidos
        (interseccion de ambas vecindades, no solo una)."""
        ra = rango_accesibilidad.get(destino)
        ri = rango_impacto.get(destino)
        if ra is None or ri is None:
            return list(items_con_reservas)
        vecinos_acc = set(sorted(destinos_unicos, key=lambda d: accesibilidad.get(d, 0.5))[
            max(0, ra - VENTANA_VECINDAD): ra + VENTANA_VECINDAD + 1
        ])
        vecinos_imp = set(sorted(destinos_unicos, key=lambda d: impacto_local.get(d, 0.5))[
            max(0, ri - VENTANA_VECINDAD): ri + VENTANA_VECINDAD + 1
        ])
        destinos_vecinos = vecinos_acc & vecinos_imp
        if not destinos_vecinos:  # interseccion vacia, ampliar a la union
            destinos_vecinos = vecinos_acc | vecinos_imp
        return [eid for d in destinos_vecinos for eid in items_por_destino[d]]

    print(f"   -> negativos difíciles: muestreados por interseccion de "
          f"vecindad de accesibilidad E impacto_local (ventana +/-{VENTANA_VECINDAD})")

    def features_item_personalizado(
        experience_id: str, categoria_preferida: str | None, precio_habitual: float,
    ) -> list[float]:
        """16 features de siempre (destino/item) + 2 de personalizacion por cliente
        (fix 31/08 v2, con codificacion leave-one-out CORRECTA esta vez):
        coincidencia con la categoria mas reservada por ESTE cliente, y
        distancia al precio que ESTE cliente suele pagar. El perfil del
        cliente (categoria_preferida, precio_habitual) se calcula por
        fuera de esta funcion, EXCLUYENDO la propia fila que se esta
        featurizando cuando es un ejemplo positivo (evita la circularidad
        detectada y revertida el 28/08: antes el perfil se calculaba con
        TODAS las reservas del cliente, incluida la misma que se
        intentaba predecir)."""
        destino = experiencias[experience_id]["destination"]
        categoria_item = experiencias[experience_id]["category"]
        precio_item = precios.get(experience_id, 0.5)
        match_categoria = 1.0 if (categoria_preferida is not None and categoria_preferida == categoria_item) else 0.0
        diff_precio = abs(precio_item - precio_habitual)
        # Bandera (01/09): distingue accesibilidad real (AENA, solo
        # aeropuertos españoles) de relleno neutro para destinos
        # internacionales -- sin esto el modelo trataria el 0.5 como un
        # valor medido real, no como "dato ausente".
        tiene_accesibilidad_real = 1.0 if destino in accesibilidad else 0.0
        return [
            precio_item,
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
            temp_confort.get(destino, 0.5),
            dias_secos.get(destino, 0.5),
            horas_sol.get(destino, 0.5),
            capacidad_sanitaria.get(destino, 0.5),
            seguridad_criminalidad.get(destino, 0.5),
            tiene_accesibilidad_real,
            match_categoria,
            diff_precio,
        ]

    def perfil_cliente(bookings: list[dict]) -> tuple[str | None, float]:
        """Categoria preferida y precio habitual a partir de una lista de
        reservas (ya sea el historial completo o con leave-one-out ya
        aplicado por el llamador)."""
        categorias = [
            experiencias[r["experience_id"]]["category"]
            for r in bookings if r["experience_id"] in experiencias
        ]
        precios_cliente = [precios.get(r["experience_id"], 0.5) for r in bookings]
        categoria_pref = Counter(categorias).most_common(1)[0][0] if categorias else None
        precio_prom = float(np.mean(precios_cliente)) if precios_cliente else 0.5
        return categoria_pref, precio_prom

    print("Construyendo pares (cliente, item) con negativos muestreados...")
    X, y, groups = [], [], []
    X_val, y_val, groups_val = [], [], []
    X_test, y_test, test_customers, test_candidatos = [], [], [], []

    for customer_id, train_res in por_cliente_train.items():
        reservados_ids = {r["experience_id"] for r in train_res}
        test_res = por_cliente_test[customer_id]
        reservados_ids_completo = reservados_ids | {test_res["experience_id"]}

        es_validacion = customer_id in ids_val
        X_dest, y_dest, groups_dest = (X_val, y_val, groups_val) if es_validacion else (X, y, groups)

        # Perfil completo del cliente (para los negativos, no hay
        # circularidad en usar todo su historial -- ver nota mas abajo).
        categoria_pref_completo, precio_prom_completo = perfil_cliente(train_res)

        # Negativos por reserva individual (fix 31/08 v3), no por
        # cliente. Diagnostico: al muestrear negativos de la UNION de
        # vecindades de todos los destinos de un cliente con varias
        # reservas, la variacion de impacto_local/accesibilidad ENTRE
        # esos destinos seguia disponible dentro del grupo aunque cada
        # negativo individual estuviera bien emparejado -- LightGBM
        # compara el grupo completo entre si, no pares aislados. Ahora
        # cada reserva positiva trae SUS PROPIOS negativos, muestreados
        # solo de la vecindad de SU destino especifico.
        negativos_por_positivo = max(1, N_NEGATIVOS_POR_CLIENTE // max(1, len(train_res)))

        grupo_size = 0
        for idx, r in enumerate(train_res):
            # Leave-one-out A NIVEL DE FILA: el perfil de este cliente se
            # calcula con sus OTRAS reservas, excluyendo esta misma --
            # asi "categoria preferida" no incluye la respuesta que se
            # esta prediciendo.
            resto = train_res[:idx] + train_res[idx + 1:]
            categoria_pref_loo, precio_prom_loo = perfil_cliente(resto)
            X_dest.append(features_item_personalizado(
                r["experience_id"], categoria_pref_loo, precio_prom_loo,
            ))
            y_dest.append(1)
            grupo_size += 1

            # Negativos de ESTE positivo especifico, no de la union.
            destino_r = experiencias[r["experience_id"]]["destination"]
            pool_negativos_fila = [
                eid for eid in vecinos_de(destino_r) if eid not in reservados_ids_completo
            ]
            if not pool_negativos_fila:
                pool_negativos_fila = [eid for eid in items_con_reservas if eid not in reservados_ids_completo]
            negativos_fila = random.sample(
                pool_negativos_fila, min(negativos_por_positivo, len(pool_negativos_fila)),
            )
            # Los negativos SI usan el perfil completo (todas las
            # reservas de train): un negativo no "es" ninguna reserva
            # real del cliente, no hay circularidad en incluir todo su
            # historial para juzgar si el negativo encaja con su perfil.
            for eid in negativos_fila:
                X_dest.append(features_item_personalizado(
                    eid, categoria_pref_completo, precio_prom_completo,
                ))
                y_dest.append(0)
                grupo_size += 1

        if grupo_size > 0:
            groups_dest.append(grupo_size)

        destino_test = experiencias[test_res["experience_id"]]["destination"]
        pool_test_neg = [
            eid for eid in vecinos_de(destino_test)
            if eid not in reservados_ids_completo
        ]
        if not pool_test_neg:
            pool_test_neg = [eid for eid in items_con_reservas if eid not in reservados_ids_completo]
        cand_negativos = random.sample(
            pool_test_neg, min(N_NEGATIVOS_POR_CLIENTE, len(pool_test_neg)),
        )
        # El candidato de test (incluido el positivo real) se featuriza
        # con el perfil COMPLETO de train -- no hay fuga: el perfil se
        # construye solo con reservas de train, la reserva de test nunca
        # entra en el calculo (ver por_cliente_train/por_cliente_test).
        candidatos = [test_res["experience_id"]] + cand_negativos
        for eid in candidatos:
            X_test.append(features_item_personalizado(
                eid, categoria_pref_completo, precio_prom_completo,
            ))
        test_customers.append(customer_id)
        test_candidatos.append(candidatos)

    return (
        np.array(X, dtype=np.float32), np.array(y, dtype=np.int32), groups,
        np.array(X_val, dtype=np.float32), np.array(y_val, dtype=np.int32), groups_val,
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
    X, y, groups, X_val, y_val, groups_val, X_test, test_customers, test_candidatos = construir_dataset(db_path)
    print(f"   -> {X.shape[0]} filas de entrenamiento, {len(groups)} grupos (clientes)")
    print(f"   -> {X_val.shape[0]} filas de validacion, {len(groups_val)} grupos")
    print(f"   -> {len(test_customers)} clientes en evaluacion final (test)")

    print("2) Entrenando LightGBM Ranker (lambdarank) con early stopping...")
    train_data = lgb.Dataset(X, label=y, group=groups)
    val_data = lgb.Dataset(X_val, label=y_val, group=groups_val, reference=train_data)
    # Hiperparametros de produccion, ver PARAMS_LIGHTGBM_BASE arriba.
    params = {**PARAMS_LIGHTGBM_BASE, "seed": RANDOM_SEED}
    model = lgb.train(
        params, train_data,
        num_boost_round=500,
        valid_sets=[val_data],
        valid_names=["validacion"],
        callbacks=[
            lgb.early_stopping(stopping_rounds=20, verbose=True),
            lgb.log_evaluation(period=50),
        ],
    )
    print(f"   -> entrenado en {time.time()-t0:.1f}s "
          f"(mejor iteracion: {model.best_iteration})")

    print("3) Evaluando sobre reservas reales dejadas fuera (leave-one-out)...")
    precision, ndcg = evaluar(model, X_test, test_candidatos, k=10)

    feature_names = FEATURE_NAMES
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