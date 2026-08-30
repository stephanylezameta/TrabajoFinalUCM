"""
Entrena un modelo colaborativo con LightFM (WARP loss) sobre las reservas
reales de customer_bookings (149.941 registros, 10.045 clientes, 5.850
experiencias). Complementa la afinidad por contenido (embeddings + coseno)
con una señal de "qué reserva la gente de verdad" (colaborativo).

Requiere el entorno lightfm_env (Conda), no el .venv del resto del
proyecto -- LightFM no compila en Windows sin herramientas de C++, se
instalo via conda-forge (binario precompilado).

Uso:
    conda activate lightfm_env
    cd TFM
    python scripts/train_lightfm.py
"""
import pickle
import sqlite3
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from lightfm import LightFM
from lightfm.evaluation import precision_at_k, recall_at_k
from scipy.sparse import coo_matrix


def cargar_interacciones(db_path: str) -> list[tuple[str, str, str]]:
    """Devuelve (customer_id, experience_id, booking_date) de todas las reservas."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT customer_id, experience_id, booking_date FROM customer_bookings "
        "ORDER BY customer_id, booking_date"
    ).fetchall()
    conn.close()
    return rows


def construir_matrices(interacciones: list[tuple[str, str, str]]):
    """Construye matrices train/test dispersas, dejando la ULTIMA reserva
    de cada cliente en test (evaluacion tipo leave-one-out)."""
    por_cliente = defaultdict(list)
    for customer_id, experience_id, booking_date in interacciones:
        por_cliente[customer_id].append(experience_id)

    usuarios = sorted(por_cliente.keys())
    experiencias = sorted({e for lst in por_cliente.values() for e in lst})
    user_idx = {u: i for i, u in enumerate(usuarios)}
    item_idx = {e: i for i, e in enumerate(experiencias)}

    train_rows, train_cols = [], []
    test_rows, test_cols = [], []

    for customer_id, exps in por_cliente.items():
        u = user_idx[customer_id]
        if len(exps) < 2:
            # Sin suficiente historial para separar train/test; todo a train.
            for e in exps:
                train_rows.append(u)
                train_cols.append(item_idx[e])
            continue
        # Ultima reserva (ya viene ordenada por booking_date) -> test.
        # Si esa reserva es una REPETICION de un item ya presente en train
        # del mismo cliente (booking duplicado), no se puede usar como test
        # limpio (apareceria en ambas matrices) -- se descarta del test en
        # ese caso, todo el historial de ese cliente queda en train.
        items_train_cliente = set(exps[:-1])
        for e in exps[:-1]:
            train_rows.append(u)
            train_cols.append(item_idx[e])
        if exps[-1] not in items_train_cliente:
            test_rows.append(u)
            test_cols.append(item_idx[exps[-1]])
        else:
            train_rows.append(u)
            train_cols.append(item_idx[exps[-1]])

    n_users, n_items = len(usuarios), len(experiencias)
    train = coo_matrix(
        (np.ones(len(train_rows)), (train_rows, train_cols)),
        shape=(n_users, n_items),
    ).tocsr()
    test = coo_matrix(
        (np.ones(len(test_rows)), (test_rows, test_cols)),
        shape=(n_users, n_items),
    ).tocsr()

    return train, test, usuarios, experiencias, user_idx, item_idx


def main():
    db_path = "data/tui_recomendador.db"
    output_dir = Path("data/lightfm")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("1) Cargando interacciones reales (customer_bookings)...")
    interacciones = cargar_interacciones(db_path)
    print(f"   -> {len(interacciones)} reservas cargadas")

    print("2) Construyendo matrices train/test (leave-one-out por cliente)...")
    train, test, usuarios, experiencias, user_idx, item_idx = construir_matrices(interacciones)
    print(f"   -> {train.shape[0]} usuarios, {train.shape[1]} experiencias")
    print(f"   -> train: {train.nnz} interacciones | test: {test.nnz} interacciones")

    print("3) Entrenando LightFM (loss=logistic)...")
    # NOTA: el informe tecnico original proponia WARP (DECISION del informe),
    # pero el sampler de WARP/BPR tiene un bug conocido en builds de LightFM
    # sin soporte OpenMP en Windows (crash silencioso a nivel C, confirmado
    # mediante prueba aislada: WARP y BPR fallan, logistic funciona con el
    # mismo entorno/datos). Se usa 'logistic' como alternativa funcional,
    # documentado como limitacion tecnica del entorno, no del diseño.
    t0 = time.time()
    model = LightFM(loss="logistic", no_components=32, random_state=42)
    model.fit(train, epochs=20, num_threads=1)  # 1 thread: sin OpenMP en esta instalacion
    print(f"   -> entrenado en {time.time()-t0:.1f}s")

    print("4) Evaluando sobre el conjunto de test...")
    prec = precision_at_k(model, test, train_interactions=train, k=10).mean()
    rec = recall_at_k(model, test, train_interactions=train, k=10).mean()

    print(f"\n{'='*50}")
    print(f"  EVALUACION LightFM (logistic)")
    print(f"{'='*50}")
    print(f"  Precision@10: {prec:.4f}")
    print(f"  Recall@10:    {rec:.4f}")
    print(f"  (Umbral informe tecnico: Precision@10 >= 0.30)")
    print(f"{'='*50}\n")

    print("5) Guardando modelo y mapeos de IDs...")
    with open(output_dir / "lightfm_model.pkl", "wb") as f:
        pickle.dump(model, f)
    with open(output_dir / "lightfm_mappings.pkl", "wb") as f:
        pickle.dump({
            "usuarios": usuarios,
            "experiencias": experiencias,
            "user_idx": user_idx,
            "item_idx": item_idx,
        }, f)
    print(f"   -> guardado en {output_dir}/")


if __name__ == "__main__":
    main()