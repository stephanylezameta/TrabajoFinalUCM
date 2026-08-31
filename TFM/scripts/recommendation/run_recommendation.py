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
import pickle
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.recommendation.pipeline_consultas import QueryPipeline
from scripts.recommendation.recommendation_engine import TuiRecommender
from src.recommender.tdrs_calculator import TDRSCalculator
from src.recommender.reranking_engine import ReRankingEngine


def cargar_metadata_experiencias(db_path: str) -> dict:
    """id_paquete (experience_id) -> atributos completos, incluyendo los
    numericos que necesita el modelo LightGBM (precio, duracion, rating,
    review_count) ademas del destino/categoria."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT experience_id, destination, category, price_eur,
               duration_hrs, rating, review_count
        FROM experiencias
    """).fetchall()
    conn.close()
    return {
        r[0]: {
            "destino_nombre": r[1], "category": r[2], "price_eur": r[3],
            "duration_hrs": r[4], "rating": r[5], "review_count": r[6],
        }
        for r in rows
    }


def normalizar_dict(d: dict) -> dict:
    """Normaliza un dict numerico a [0,1] (mismo criterio usado al
    entrenar LightGBM, ver train_lightgbm_ranker.py)."""
    valores = [v for v in d.values() if v is not None]
    if not valores:
        return {k: 0.5 for k in d}
    vmin, vmax = min(valores), max(valores)
    if vmax == vmin:
        return {k: 0.5 for k in d}
    return {k: (v - vmin) / (vmax - vmin) if v is not None else 0.5 for k, v in d.items()}


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
        else:
            valores = {d: 0.5 for d in valores}
    return valores


def cargar_caracteristicas_destino(db_path: str) -> dict:
    """Sensibilidad ambiental por destino (destinos_caracteristicas).

    NOTA: estos valores fueron asignados manualmente por el equipo en
    scripts/extract_destination_features.py, no provienen de un índice
    ambiental oficial. Documentar como limitación en la memoria.
    """
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT destino_nombre, sensibilidad_ambiental FROM destinos_caracteristicas"
        ).fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()
    return {d: v for d, v in rows if v is not None}


def cargar_accesibilidad_por_destino(db_path: str) -> dict:
    """Accesibilidad real normalizada [0,1] por destino, a partir de
    pasajeros anuales estimados (conectividad_destinos, fuente AENA/CSV
    de conectividad). A más pasajeros, mayor accesibilidad."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT destino_nombre, pasajeros_anuales FROM conectividad_destinos"
        ).fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()
    valores = {d: v for d, v in rows if v}
    if valores:
        vmin, vmax = min(valores.values()), max(valores.values())
        if vmax > vmin:
            valores = {d: (v - vmin) / (vmax - vmin) for d, v in valores.items()}
        else:
            valores = {d: 0.5 for d in valores}
    return valores


def cargar_capacidad_por_destino(db_path: str) -> dict:
    """Capacidad: poblacion_estimada del destino (destinos_caracteristicas),
    normalizado [0,1]. Reemplaza el conteo de experiencias del catalogo
    (constante en 150 para todos los destinos por diseno del dataset
    sintetico -- sin variacion, no discriminaba). Poblacion si tiene
    variacion real entre destinos (150K a 3.28M) y es un proxy razonable
    de infraestructura/capacidad de absorcion turistica.

    NOTA: dato semi-curado (extraido por el equipo, no de censo oficial
    verificado por destino), igual que sensibilidad_ambiental. Documentar
    como limitacion en la memoria."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT destino_nombre, poblacion_estimada FROM destinos_caracteristicas"
        ).fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()
    valores = {d: v for d, v in rows if v}
    if valores:
        vmin, vmax = min(valores.values()), max(valores.values())
        if vmax > vmin:
            valores = {d: (v - vmin) / (vmax - vmin) for d, v in valores.items()}
        else:
            valores = {d: 0.5 for d in valores}
    return valores


def cargar_diversificacion_por_destino(db_path: str) -> dict:
    """Diversificacion: entropia de Shannon de los paises de origen de los
    clientes que reservaron cada destino (customer_bookings.country),
    normalizada [0,1]. Reemplaza el conteo de categorias del catalogo
    (constante en 10 para todos los destinos, sin variacion). Esta version
    mide diversidad real de la DEMANDA (cuantos paises distintos visitan
    el destino), con variacion genuina segun el dataset (149.941 reservas
    reales, no sinteticas-uniformes)."""
    import math
    from collections import Counter

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("""
            SELECT e.destination, b.country
            FROM customer_bookings b
            JOIN experiencias e ON b.experience_id = e.experience_id
            WHERE b.country IS NOT NULL
        """).fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()

    por_destino_paises = defaultdict(list)
    for destino, pais in rows:
        por_destino_paises[destino].append(pais)

    valores = {}
    for destino, paises in por_destino_paises.items():
        total = len(paises)
        if total < 2:
            continue
        conteos = Counter(paises)
        entropia = -sum(
            (c / total) * math.log2(c / total) for c in conteos.values()
        )
        valores[destino] = entropia

    if valores:
        vmin, vmax = min(valores.values()), max(valores.values())
        if vmax > vmin:
            valores = {d: (v - vmin) / (vmax - vmin) for d, v in valores.items()}
        else:
            valores = {d: 0.5 for d in valores}
    return valores


def cargar_impacto_local_por_destino(db_path: str) -> dict:
    """Impacto local: ingresos totales generados por destino
    (SUM(price_paid_eur) en customer_bookings), normalizado [0,1]. Proxy
    economico real -- antes este componente del TDRS quedaba en valor
    neutro fijo (0.5) por falta de fuente conectada."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("""
            SELECT e.destination, SUM(b.price_paid_eur)
            FROM customer_bookings b
            JOIN experiencias e ON b.experience_id = e.experience_id
            GROUP BY e.destination
        """).fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()
    valores = {d: v for d, v in rows if v}
    if valores:
        vmin, vmax = min(valores.values()), max(valores.values())
        if vmax > vmin:
            valores = {d: (v - vmin) / (vmax - vmin) for d, v in valores.items()}
        else:
            valores = {d: 0.5 for d in valores}
    return valores


def cargar_temporada_baja_por_destino(db_path: str) -> dict:
    """Temporada baja (ingenieria de variable): mide que tan repartidas
    estan las reservas de un destino a lo largo del año (coeficiente de
    variacion mensual, invertido). Un destino con reservas muy concentradas
    en pocos meses puntua bajo (alta estacionalidad); uno con demanda
    repartida todo el año puntua alto. Calculado desde customer_bookings
    (travel_date) cruzado con experiencias.destination."""
    import numpy as np
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("""
            SELECT e.destination, strftime('%m', b.travel_date) as mes
            FROM customer_bookings b
            JOIN experiencias e ON b.experience_id = e.experience_id
            WHERE b.travel_date IS NOT NULL
        """).fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()

    por_destino_mes = defaultdict(lambda: defaultdict(int))
    for destino, mes in rows:
        if mes:
            por_destino_mes[destino][mes] += 1

    valores = {}
    for destino, meses in por_destino_mes.items():
        conteos = list(meses.values())
        if len(conteos) < 2 or np.mean(conteos) == 0:
            continue
        cv = np.std(conteos) / np.mean(conteos)  # coeficiente de variacion
        valores[destino] = cv

    if valores:
        vmin, vmax = min(valores.values()), max(valores.values())
        if vmax > vmin:
            valores = {d: 1 - (v - vmin) / (vmax - vmin) for d, v in valores.items()}
        else:
            valores = {d: 0.5 for d in valores}
    return valores


def cargar_sentimiento_por_destino(db_path: str) -> dict:
    """Sentimiento real agregado por destino (media del score de
    resenas_sentimiento sobre las 37.956 reseñas reales analizadas con
    XLM-RoBERTa). Hasta ahora solo se usaba mezclado dentro de un
    atributo del vector hibrido (estrellas_hotel_norm, 50/50 con rating
    sintetico); se expone aqui como señal propia e independiente para el
    calculo de afinidad en tiempo real, en vez de quedar diluida entre
    otras 6 variables del vector."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("""
            SELECT r.destino_nombre, AVG(s.sentiment_score)
            FROM resenas r
            JOIN resenas_sentimiento s ON r.id_resena = s.id_resena
            GROUP BY r.destino_nombre
        """).fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()
    return {d: v for d, v in rows if v is not None}


def crear_tabla_log(db_path: str) -> None:
    """Crea la tabla donde se registra cada recomendacion servida, para
    poder reentrenar en el futuro un modelo de mezcla (coseno/LightGBM/
    sentimiento) aprendido en vez de con pesos fijos -- hoy no existen
    datos de la forma (consulta, item, ¿fue relevante?) porque
    customer_bookings no tiene ninguna consulta de texto asociada. Cada
    fila de este log es un candidato futuro para ese entrenamiento, una
    vez que se pueda cruzar con reservas/feedback reales de los
    usuarios que usaron el buscador."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recomendaciones_log (
            log_id TEXT PRIMARY KEY,
            fecha TEXT NOT NULL,
            texto_consulta TEXT NOT NULL,
            escenario TEXT NOT NULL,
            posicion INTEGER NOT NULL,
            id_paquete TEXT NOT NULL,
            destino_nombre TEXT NOT NULL,
            afinidad_coseno REAL,
            afinidad_lgbm REAL,
            afinidad_sentimiento REAL,
            afinidad_final REAL,
            tdrs REAL,
            score_final REAL
        )
    """)
    conn.commit()
    conn.close()


def guardar_log_recomendaciones(db_path: str, texto_consulta: str, rankings: dict, detalle_afinidad: dict) -> None:
    """Guarda cada resultado servido en recomendaciones_log."""
    import uuid
    import time as time_module

    conn = sqlite3.connect(db_path)
    fecha = time_module.strftime("%Y-%m-%d %H:%M:%S")
    for escenario, resultados in rankings.items():
        for posicion, r in enumerate(resultados, 1):
            detalle = detalle_afinidad.get(r["id_paquete"], {})
            conn.execute(
                """INSERT INTO recomendaciones_log
                   (log_id, fecha, texto_consulta, escenario, posicion, id_paquete,
                    destino_nombre, afinidad_coseno, afinidad_lgbm, afinidad_sentimiento,
                    afinidad_final, tdrs, score_final)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()), fecha, texto_consulta, escenario, posicion,
                    r["id_paquete"], r["destino_nombre"],
                    detalle.get("coseno"), detalle.get("lgbm"), detalle.get("sentimiento"),
                    r["afinidad"], r["tdrs"], r["score_final"],
                ),
            )
    conn.commit()
    conn.close()


def cargar_modelo_lightgbm():
    """Carga el modelo LightGBM entrenado (train_lightgbm_ranker.py).
    Devuelve (model, feature_names) o (None, None) si no existe todavia."""
    model_path = Path("data/lightgbm/lightgbm_ranker.pkl")
    names_path = Path("data/lightgbm/feature_names.pkl")
    if not model_path.exists() or not names_path.exists():
        return None, None
    with open(model_path, "rb") as f:
        model = pickle.load(f)
    with open(names_path, "rb") as f:
        feature_names = pickle.load(f)
    return model, feature_names


def recomendar(
    texto_consulta: str,
    db_path: str = "data/tui_recomendador.db",
    top_k_candidatos: int = 30,
    k_final: int = 10,
) -> dict[str, list[dict]]:
    """Ejecuta el flujo completo y devuelve los 3 rankings (tradicional/moderado/intensivo).

    Afinidad: se calcula mezclando 3 señales (ver comentarios en el bucle
    principal): coseno (sensible a la consulta), LightGBM (comportamiento
    real, sin contexto de consulta) y sentimiento real (XLM-RoBERTa).
    """

    print(f"\n1) Vectorizando consulta: '{texto_consulta}'")
    query_pipeline = QueryPipeline()
    query_vector = query_pipeline.process_query(texto_consulta)

    print("2) Buscando candidatos por afinidad semantica (similitud coseno)...")
    recommender = TuiRecommender()
    candidatos_afinidad = recommender.search(query_vector, top_k=top_k_candidatos)

    print("3) Calculando TDRS por candidato (redistribución/sostenibilidad)...")
    metadata = cargar_metadata_experiencias(db_path)
    ocupacion_por_destino = cargar_ocupacion_por_destino(db_path)
    sensibilidad_por_destino = cargar_caracteristicas_destino(db_path)
    accesibilidad_por_destino = cargar_accesibilidad_por_destino(db_path)
    capacidad_por_destino = cargar_capacidad_por_destino(db_path)
    diversificacion_por_destino = cargar_diversificacion_por_destino(db_path)
    temporada_baja_por_destino = cargar_temporada_baja_por_destino(db_path)
    impacto_local_por_destino = cargar_impacto_local_por_destino(db_path)
    sentimiento_por_destino = cargar_sentimiento_por_destino(db_path)
    tdrs_calc = TDRSCalculator()

    modelo_lgbm, feature_names_lgbm = cargar_modelo_lightgbm()
    if modelo_lgbm is not None:
        print("   -> Modelo LightGBM Ranker encontrado, re-puntuando afinidad "
              "con datos de comportamiento real...")
        precios = normalizar_dict({eid: m["price_eur"] for eid, m in metadata.items()})
        duraciones = normalizar_dict({eid: m["duration_hrs"] for eid, m in metadata.items()})
        ratings = normalizar_dict({eid: m["rating"] for eid, m in metadata.items()})
        reviews = normalizar_dict({eid: m["review_count"] for eid, m in metadata.items()})
    else:
        print("   -> Modelo LightGBM no encontrado (correr train_lightgbm_ranker.py "
              "primero); usando afinidad por coseno solamente.")

    candidatos = []
    detalle_afinidad = {}
    for c in candidatos_afinidad:
        id_paq = c["id_paquete"]
        meta = metadata.get(id_paq, {"destino_nombre": "desconocido", "category": ""})
        destino = meta["destino_nombre"]

        ocupacion_real = ocupacion_por_destino.get(destino, 0.5)
        sensibilidad_real = sensibilidad_por_destino.get(destino, 0.3)
        accesibilidad_real = accesibilidad_por_destino.get(destino, 0.5)
        capacidad_real = capacidad_por_destino.get(destino, 0.5)
        diversificacion_real = diversificacion_por_destino.get(destino, 0.5)
        temporada_baja_real = temporada_baja_por_destino.get(destino, 0.5)
        impacto_local_real = impacto_local_por_destino.get(destino, 0.5)
        sentimiento_real = sentimiento_por_destino.get(destino, 0.5)

        afinidad_coseno = max(0.0, min(1.0, (c["score_similitud"] + 1) / 2))

        if modelo_lgbm is not None:
            # 11 features, mismo orden que train_lightgbm_ranker.py: precio,
            # duracion, rating, review_count, ocupacion, sensibilidad,
            # accesibilidad, capacidad, diversificacion, temporada_baja,
            # impacto_local.
            features = [[
                precios.get(id_paq, 0.5),
                duraciones.get(id_paq, 0.5),
                ratings.get(id_paq, 0.5),
                reviews.get(id_paq, 0.5),
                ocupacion_real,
                sensibilidad_real,
                accesibilidad_real,
                capacidad_real,
                diversificacion_real,
                temporada_baja_real,
                impacto_local_real,
            ]]
            score_lgbm = float(modelo_lgbm.predict(features)[0])
            afinidad_lgbm = 1 / (1 + np.exp(-score_lgbm))
            # Mezcla de 3 señales, no reemplazo (fix 28/08 + ampliado):
            #  - coseno: unica sensible al texto de la consulta real del
            #    usuario (fix critico del vector hibrido, ver commit).
            #  - LightGBM: aprendido de 149.941 reservas reales, sin
            #    contexto de consulta -- calidad/comportamiento general.
            #  - sentimiento: promedio real de XLM-RoBERTa sobre 37.956
            #    reseñas reales por destino. Antes solo se usaba diluido
            #    dentro de un atributo del vector hibrido (50/50 con
            #    rating sintetico); se expone aqui como señal propia,
            #    independiente, en vez de perdida entre otras 6 variables.
            W_COSENO, W_LGBM, W_SENTIMIENTO = 0.5, 0.3, 0.2
            afinidad_norm = (
                W_COSENO * afinidad_coseno
                + W_LGBM * afinidad_lgbm
                + W_SENTIMIENTO * sentimiento_real
            )
        else:
            afinidad_lgbm = None
            afinidad_norm = afinidad_coseno

        detalle_afinidad[id_paq] = {
            "coseno": afinidad_coseno, "lgbm": afinidad_lgbm, "sentimiento": sentimiento_real,
        }

        tdrs = tdrs_calc.calculate(
            afinidad=afinidad_norm,
            ocupacion=ocupacion_real,
            sensibilidad_ambiental=sensibilidad_real,
            accesibilidad=accesibilidad_real,
            capacidad=capacidad_real,
            diversificacion=diversificacion_real,
            temporada_baja=temporada_baja_real,
            impacto_local=impacto_local_real,
        )

        candidatos.append({
            "id_paquete": id_paq,
            "destino_nombre": destino,
            "afinidad": afinidad_norm,
            "tdrs": tdrs,
            "sostenibilidad": max(0.0, tdrs),
            "capacidad": capacidad_real,
            "ocupacion": ocupacion_real,
        })

    print("4) Aplicando re-ranking (3 escenarios)...")
    reranker = ReRankingEngine()
    rankings = reranker.rank_all_scenarios(candidatos, k=k_final)

    print("5) Registrando resultados para futuro reentrenamiento...")
    try:
        crear_tabla_log(db_path)
        guardar_log_recomendaciones(db_path, texto_consulta, rankings, detalle_afinidad)
    except Exception as e:
        print(f"   -> No se pudo guardar el log (no bloqueante): {e}")

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