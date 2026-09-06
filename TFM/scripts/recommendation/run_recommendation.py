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
    """Ocupación real normalizada [0,1] por destino (Eurostat/INE), con
    19/39 destinos cubiertos. Para los 20 restantes, en vez de un
    fallback neutro fijo (0.5) sin ninguna base, se usa el volumen real
    de reservas (customer_bookings) como proxy de demanda -- no es
    ocupacion hotelera real, pero es mejor que un numero inventado sin
    ninguna relacion con el destino. Normalizado por separado dentro de
    ese subgrupo (no mezclado en la misma escala que el dato Eurostat),
    para no inventar una falsa comparabilidad directa entre ambos.
    Documentar esta distincion en la memoria (31/08)."""
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

    # Fallback por volumen de reservas para destinos sin dato Eurostat
    try:
        conn = sqlite3.connect(db_path)
        destinos_catalogo = {
            r[0] for r in conn.execute("SELECT DISTINCT destination FROM experiencias").fetchall()
        }
        conteo_reservas = conn.execute("""
            SELECT e.destination, COUNT(*)
            FROM customer_bookings b
            JOIN experiencias e ON b.experience_id = e.experience_id
            GROUP BY e.destination
        """).fetchall()
        conn.close()

        faltantes = destinos_catalogo - set(valores.keys())
        conteo_faltantes = {d: c for d, c in conteo_reservas if d in faltantes}
        conteo_norm = normalizar_dict(conteo_faltantes)
        valores.update(conteo_norm)
    except Exception:
        pass  # si falla el fallback, los destinos faltantes quedan sin dato (0.5 en el uso final)

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


def cargar_clima_por_destino(db_path: str) -> tuple[dict, dict, dict]:
    """3 señales climaticas reales SEPARADAS por destino (Open-Meteo,
    extract_climate_data.py, cobertura completa 39/39 destinos), en vez
    de un promedio compuesto en un solo numero.

    Version 3 (01/09): la version anterior promediaba temperatura +
    sequedad + horas de sol en un solo score, con peso igual para las
    3 decidido a mano -- eso le quita a LightGBM (un modelo de arboles,
    diseñado justo para aprender el peso relativo y las interacciones
    entre variables por si solo) la posibilidad de descubrir, por
    ejemplo, que las horas de sol importan mas que la sequedad. Agrupar
    con pesos fijos tiene sentido en el TDRS (por explicabilidad, a
    proposito), pero no en LightGBM, que no tiene esa restriccion.

    Devuelve (temp_confort, dias_secos, horas_sol_norm), 3 dicts
    independientes, cada uno normalizado [0,1] por separado."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("""
            SELECT destino_nombre, temp_media, precipitacion_mm, horas_sol
            FROM clima_destinos
        """).fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()

    por_destino = defaultdict(list)
    for destino, temp, precip, sol in rows:
        por_destino[destino].append((temp, precip, sol))

    temp_confort = {}
    dias_secos = {}
    horas_sol_promedio = {}
    for destino, registros in por_destino.items():
        temps = [t for t, p, s in registros if t is not None]
        precs = [p for t, p, s in registros if p is not None]
        soles = [s for t, p, s in registros if s is not None]
        if temps:
            temp_confort[destino] = sum(1 for t in temps if 18 <= t <= 28) / len(temps)
        if precs:
            dias_secos[destino] = sum(1 for p in precs if p <= 50.0) / len(precs)
        if soles:
            horas_sol_promedio[destino] = sum(soles) / len(soles)

    horas_sol_norm = normalizar_dict(horas_sol_promedio)
    return temp_confort, dias_secos, horas_sol_norm


def cargar_datos_humanos_por_destino(db_path: str) -> dict:
    """Valores REALES interpretables por destino (no scores 0-1 para el
    modelo, sino los numeros que un humano puede leer directo: % dias
    soleados, % dias con lluvia, pasajeros/año, camas de hospital,
    tasa de homicidios, sentimiento real, cobertura de reseñas).

    Agregada (01/09) para el dashboard: los sliders y la tabla de
    'Recomendador España' muestran valores humanos (ej. '84% dias
    soleados', '920k pasajeros/año'), no los scores internos 0-1 que
    usa LightGBM -- son cosas distintas por diseño, no un error de
    escala. Reutiliza precipitacion_mm y horas_sol de clima_destinos,
    que ya estaban en la tabla real (Open-Meteo) pero nunca se habian
    usado (solo se usaba temp_media hasta ahora)."""
    conn = sqlite3.connect(db_path)
    resultado = defaultdict(dict)

    try:
        rows = conn.execute("""
            SELECT destino_nombre, temp_media, precipitacion_mm, horas_sol
            FROM clima_destinos
        """).fetchall()
        por_destino_clima = defaultdict(list)
        for destino, temp, precip, sol in rows:
            por_destino_clima[destino].append((temp, precip, sol))
        for destino, registros in por_destino_clima.items():
            temps = [t for t, p, s in registros if t is not None]
            precs = [p for t, p, s in registros if p is not None]
            soles = [s for t, p, s in registros if s is not None]
            total = len(registros)
            if total:
                dias_soleados_pct = round(
                    100 * sum(1 for t in temps if t is not None and 18 <= t <= 28) / len(temps), 1
                ) if temps else None
                precipitacion_pct = round(
                    100 * sum(1 for p in precs if p is not None and p > 50.0) / len(precs), 1
                ) if precs else None
                resultado[destino]["dias_soleados_pct"] = dias_soleados_pct
                resultado[destino]["precipitacion_pct"] = precipitacion_pct
                resultado[destino]["horas_sol_promedio_dia"] = (
                    round(sum(soles) / len(soles) / 30, 1) if soles else None
                )
    except Exception:
        pass

    try:
        rows = conn.execute(
            "SELECT destino_nombre, pasajeros_anuales FROM conectividad_destinos"
        ).fetchall()
        for destino, pax in rows:
            resultado[destino]["pasajeros_anuales"] = pax
    except Exception:
        pass

    try:
        rows = conn.execute(
            "SELECT destino_nombre, camas_hospital_1000hab, tasa_homicidios_100mil "
            "FROM seguridad_destinos"
        ).fetchall()
        for destino, camas, homicidios in rows:
            resultado[destino]["camas_hospital_1000hab"] = round(camas, 2) if camas is not None else None
            resultado[destino]["tasa_homicidios_100mil"] = round(homicidios, 2) if homicidios is not None else None
    except Exception:
        pass

    try:
        rows = conn.execute("""
            SELECT r.destino_nombre, AVG(s.sentiment_score), COUNT(*)
            FROM resenas r
            JOIN resenas_sentimiento s ON r.id_resena = s.id_resena
            GROUP BY r.destino_nombre
        """).fetchall()
        for destino, sentimiento, n_resenas in rows:
            resultado[destino]["sentimiento_real"] = round(sentimiento, 2) if sentimiento else None
            resultado[destino]["n_resenas_reales"] = n_resenas
    except Exception:
        pass

    conn.close()
    return dict(resultado)


def cargar_capacidad_sanitaria_por_destino(db_path: str) -> dict:
    """Camas de hospital por 1000 habitantes, normalizado [0,1]. Dato
    real (integrar_csvs_nuevos.py, fuente tipo Banco Mundial).

    Version 2 (01/09): separada de 'tasa_homicidios' -- antes se
    promediaban en un solo 'seguridad' con peso fijo 50/50 decidido a
    mano, quitandole a LightGBM la posibilidad de aprender el peso
    relativo real de cada una (mismo problema detectado en 'clima',
    corregido con el mismo criterio: separar, no promediar, cuando el
    modelo es flexible y puede aprender la combinacion por si solo)."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT destino_nombre, camas_hospital_1000hab FROM seguridad_destinos"
        ).fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()
    return normalizar_dict({d: c for d, c in rows if c is not None})


def cargar_seguridad_criminalidad_por_destino(db_path: str) -> dict:
    """Inverso de la tasa de homicidios por 100mil habitantes,
    normalizado [0,1] (mas alto = mas seguro). Dato real
    (integrar_csvs_nuevos.py, fuente tipo Banco Mundial), separada de
    'capacidad_sanitaria' por el mismo motivo (ver docstring de
    cargar_capacidad_sanitaria_por_destino)."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT destino_nombre, tasa_homicidios_100mil FROM seguridad_destinos"
        ).fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()
    homicidios_norm = normalizar_dict({d: h for d, h in rows if h is not None})
    return {d: 1.0 - v for d, v in homicidios_norm.items()}


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


def registrar_oportunidad(db_path: str, texto_consulta: str, destino: str, categoria_coincidente: str | None = None) -> None:
    """Registra un destino con reseñas reales (fuera del catalogo de 39
    experiencias vendibles) que coincide con una consulta real de usuario
    -- panel interno de oportunidades de expansion para TUI, nunca
    mostrado al usuario final."""
    import uuid
    import time as time_module

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS destinos_oportunidad (
            oportunidad_id TEXT PRIMARY KEY,
            fecha TEXT NOT NULL,
            texto_consulta TEXT NOT NULL,
            destino_nombre TEXT NOT NULL,
            categoria_coincidente TEXT
        )
    """)
    conn.execute(
        """INSERT INTO destinos_oportunidad
           (oportunidad_id, fecha, texto_consulta, destino_nombre, categoria_coincidente)
           VALUES (?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), time_module.strftime("%Y-%m-%d %H:%M:%S"),
         texto_consulta, destino, categoria_coincidente),
    )
    conn.commit()
    conn.close()


def cargar_indice_oportunidades():
    """Carga el indice semantico de destinos oportunidad (generado por
    generar_indice_oportunidades.py). Devuelve (embeddings, nombres) o
    (None, None) si el indice todavia no existe."""
    ruta_emb = Path("data/oportunidades/oportunidades_embeddings.npy")
    ruta_nombres = Path("data/oportunidades/oportunidades_nombres.npy")
    if not ruta_emb.exists() or not ruta_nombres.exists():
        return None, None
    return np.load(ruta_emb), np.load(ruta_nombres, allow_pickle=True)


def detectar_oportunidades(db_path: str, texto_consulta: str, query_vector: np.ndarray | None = None, top_n: int = 3) -> None:
    """Busca, entre los destinos con reseñas reales pero SIN experiencias
    en el catalogo, los que semanticamente mejor calzan con la consulta
    -- panel interno de oportunidades de expansion para TUI, nunca
    mostrado al usuario final. No bloqueante: si falla, no interrumpe la
    recomendacion principal al usuario.

    Usa el indice semantico (data/oportunidades/, generado por
    generar_indice_oportunidades.py sobre 435 destinos con reseñas
    reales fuera del catalogo) si esta disponible. Si no existe todavia,
    cae de vuelta a la version v1 (coincidencia literal del nombre del
    destino en la consulta)."""
    try:
        embeddings_indice, nombres_indice = cargar_indice_oportunidades()

        if embeddings_indice is not None and query_vector is not None:
            dim_indice = embeddings_indice.shape[1]
            query_vector_semantico = np.asarray(query_vector).reshape(-1)[:dim_indice]
            query_norm = query_vector_semantico / (np.linalg.norm(query_vector_semantico) + 1e-8)
            emb_norm = embeddings_indice / (
                np.linalg.norm(embeddings_indice, axis=1, keepdims=True) + 1e-8
            )
            similitudes = emb_norm @ query_norm
            top_idx = np.argsort(-similitudes)[:top_n]
            UMBRAL_MINIMO = 0.75
            for idx in top_idx:
                if similitudes[idx] >= UMBRAL_MINIMO:
                    registrar_oportunidad(
                        db_path, texto_consulta, str(nombres_indice[idx]),
                        categoria_coincidente=f"similitud={similitudes[idx]:.3f}",
                    )
            return

        conn = sqlite3.connect(db_path)
        destinos_catalogo = {
            r[0] for r in conn.execute("SELECT DISTINCT destination FROM experiencias").fetchall()
        }
        destinos_con_resenas = conn.execute(
            "SELECT DISTINCT destino_nombre FROM resenas"
        ).fetchall()
        conn.close()

        for (destino,) in destinos_con_resenas:
            if not destino or destino in destinos_catalogo:
                continue
            if destino.lower() in texto_consulta.lower():
                registrar_oportunidad(db_path, texto_consulta, destino)
    except Exception:
        pass  # nunca debe romper el flujo principal de recomendacion


def crear_tabla_log(db_path: str) -> None:
    """Crea las tablas de log de recomendaciones y de feedback del
    usuario, para poder reentrenar en el futuro un modelo de mezcla
    (coseno/LightGBM/sentimiento) aprendido en vez de con pesos fijos --
    hoy no existen datos de la forma (consulta, item, ¿fue relevante?)
    porque customer_bookings no tiene ninguna consulta de texto asociada.
    Cada fila de recomendaciones_log + su feedback asociado es un
    ejemplo de entrenamiento futuro."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recomendaciones_log (
            log_id TEXT PRIMARY KEY,
            session_id TEXT,
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback_usuario (
            feedback_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            log_id TEXT,
            id_paquete TEXT NOT NULL,
            senal TEXT NOT NULL,
            fecha TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def guardar_log_recomendaciones(
    db_path: str, texto_consulta: str, rankings: dict, detalle_afinidad: dict,
    session_id: str | None = None,
) -> dict[str, str]:
    """Guarda cada resultado servido en recomendaciones_log. Devuelve un
    dict {id_paquete: log_id} del escenario 'moderado' (el que se le
    muestra al usuario por defecto), para que registrar_feedback() pueda
    referenciar exactamente que fila del log genero cada reaccion."""
    import uuid
    import time as time_module

    conn = sqlite3.connect(db_path)
    fecha = time_module.strftime("%Y-%m-%d %H:%M:%S")
    log_ids_moderado = {}
    for escenario, resultados in rankings.items():
        for posicion, r in enumerate(resultados, 1):
            detalle = detalle_afinidad.get(r["id_paquete"], {})
            log_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO recomendaciones_log
                   (log_id, session_id, fecha, texto_consulta, escenario, posicion,
                    id_paquete, destino_nombre, afinidad_coseno, afinidad_lgbm,
                    afinidad_sentimiento, afinidad_final, tdrs, score_final)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    log_id, session_id, fecha, texto_consulta, escenario, posicion,
                    r["id_paquete"], r["destino_nombre"],
                    detalle.get("coseno"), detalle.get("lgbm"), detalle.get("sentimiento"),
                    r["afinidad"], r["tdrs"], r["score_final"],
                ),
            )
            if escenario == "moderado":
                log_ids_moderado[r["id_paquete"]] = log_id
    conn.commit()
    conn.close()
    return log_ids_moderado


def registrar_feedback(
    db_path: str, session_id: str, id_paquete: str, senal: str, log_id: str | None = None,
) -> None:
    """Registra la reaccion del usuario a una recomendacion concreta
    dentro de una sesion conversacional.

    senal: uno de 'rechazado', 'interesado', 'reservado'. El agente lo
    llama cada vez que detecta una reaccion clara en la conversacion
    (ej. "no me gusta eso" -> 'rechazado'; "eso suena bien" -> 'interesado').
    Esta tabla, cruzada con recomendaciones_log, es la fuente de datos
    real (consulta + resultado + reaccion) que hoy no existe y que hace
    falta para poder entrenar en el futuro los pesos de la mezcla de
    señales en vez de dejarlos fijos."""
    import uuid
    import time as time_module

    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO feedback_usuario (feedback_id, session_id, log_id, id_paquete, senal, fecha)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), session_id, log_id, id_paquete, senal,
         time_module.strftime("%Y-%m-%d %H:%M:%S")),
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


def calcular_candidato(
    id_paq: str,
    destino: str,
    score_similitud: float,
    ocupacion_por_destino: dict, sensibilidad_por_destino: dict,
    accesibilidad_por_destino: dict, capacidad_por_destino: dict,
    diversificacion_por_destino: dict, temporada_baja_por_destino: dict,
    impacto_local_por_destino: dict, sentimiento_por_destino: dict,
    temp_confort_por_destino: dict, dias_secos_por_destino: dict, horas_sol_por_destino: dict,
    capacidad_sanitaria_por_destino: dict, seguridad_criminalidad_por_destino: dict,
    modelo_lgbm, precios: dict, duraciones: dict, ratings: dict, reviews: dict,
    tdrs_calc: TDRSCalculator,
) -> tuple[dict, dict]:
    """Logica de scoring de UN candidato: mezcla de las 3 señales de
    afinidad + calculo del TDRS + construccion del dict final.

    Extraida (31/08) para que recomendar() y optimizar_pesos_reranking.py
    usen la MISMA logica en vez de reimplementarla cada uno por su lado
    -- asi se evita que un fix (como el de 'sostenibilidad' duplicando
    'tdrs', encontrado y corregido hoy) tenga que aplicarse a mano en
    mas de un lugar, y arriesgarse a que uno de los dos quede desactualizado.

    Devuelve (candidato_dict, detalle_afinidad_dict)."""
    ocupacion_real = ocupacion_por_destino.get(destino, 0.5)
    sensibilidad_real = sensibilidad_por_destino.get(destino, 0.3)
    accesibilidad_real = accesibilidad_por_destino.get(destino, 0.5)
    # Bandera (01/09): distingue si 'accesibilidad' es dato real (AENA,
    # solo cubre aeropuertos españoles) o un relleno neutro 0.5 para
    # destinos internacionales que nunca van a tener ese dato. Sin esto,
    # el modelo (y el dashboard) tratarian el 0.5 como si fuera un valor
    # medido "intermedio", cuando en realidad significa "no sabemos" --
    # una diferencia real, no un matiz cosmetico.
    tiene_accesibilidad_real = 1.0 if destino in accesibilidad_por_destino else 0.0
    capacidad_real = capacidad_por_destino.get(destino, 0.5)
    diversificacion_real = diversificacion_por_destino.get(destino, 0.5)
    temporada_baja_real = temporada_baja_por_destino.get(destino, 0.5)
    impacto_local_real = impacto_local_por_destino.get(destino, 0.5)
    sentimiento_real = sentimiento_por_destino.get(destino, 0.5)
    temp_confort_real = temp_confort_por_destino.get(destino, 0.5)
    dias_secos_real = dias_secos_por_destino.get(destino, 0.5)
    horas_sol_real = horas_sol_por_destino.get(destino, 0.5)
    capacidad_sanitaria_real = capacidad_sanitaria_por_destino.get(destino, 0.5)
    seguridad_criminalidad_real = seguridad_criminalidad_por_destino.get(destino, 0.5)

    afinidad_coseno = max(0.0, min(1.0, (score_similitud + 1) / 2))

    if modelo_lgbm is not None:
        # 19 features, mismo orden que train_lightgbm_ranker.py: precio,
        # duracion, rating, review_count, ocupacion, sensibilidad,
        # accesibilidad, capacidad, diversificacion, temporada_baja,
        # impacto_local, temp_confort, dias_secos, horas_sol,
        # capacidad_sanitaria, seguridad_criminalidad,
        # tiene_accesibilidad_real, match_categoria_cliente,
        # diferencia_precio_habitual_cliente.
        # Las ultimas 2 requieren un cliente identificado con historial;
        # en una consulta de texto libre anonima como esta no hay
        # cliente conocido, se usan valores neutros (0.0 = sin
        # coincidencia de categoria, 0.5 = sin diferencia de precio
        # respecto a un habito desconocido).
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
            temp_confort_real,
            dias_secos_real,
            horas_sol_real,
            capacidad_sanitaria_real,
            seguridad_criminalidad_real,
            tiene_accesibilidad_real,
            0.0,
            0.5,
        ]]
        score_lgbm = float(modelo_lgbm.predict(features)[0])
        afinidad_lgbm = 1 / (1 + np.exp(-score_lgbm))
        # Mezcla de 3 señales, no reemplazo: coseno (unica sensible al
        # texto de la consulta real del usuario), LightGBM (aprendido de
        # 149.941 reservas reales, sin contexto de consulta) y
        # sentimiento real (XLM-RoBERTa sobre 37.956 reseñas reales).
        W_COSENO, W_LGBM, W_SENTIMIENTO = 0.5, 0.3, 0.2
        afinidad_norm = (
            W_COSENO * afinidad_coseno
            + W_LGBM * afinidad_lgbm
            + W_SENTIMIENTO * sentimiento_real
        )
    else:
        afinidad_lgbm = None
        afinidad_norm = afinidad_coseno

    detalle = {
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

    candidato = {
        "id_paquete": id_paq,
        "destino_nombre": destino,
        "afinidad": afinidad_norm,
        "tdrs": tdrs,
        # 'sostenibilidad' mide sensibilidad ambiental invertida (menos
        # sensible = mas sostenible visitarlo), un concepto DISTINTO de
        # 'tdrs' (redistribucion) -- fix del 31/08, antes ambos eran el
        # mismo valor (max(0.0, tdrs)), duplicando la influencia real del
        # TDRS en el score final sin que los pesos del re-ranking lo
        # reflejaran.
        "sostenibilidad": 1.0 - sensibilidad_real,
        "capacidad": capacidad_real,
        "ocupacion": ocupacion_real,
    }
    return candidato, detalle


def recomendar(
    texto_consulta: str,
    db_path: str = "data/tui_recomendador.db",
    top_k_candidatos: int = 30,
    k_final: int = 10,
    session_id: str | None = None,
    excluir_ids: list[str] | None = None,
    excluir_destinos: list[str] | None = None,
    filtros: dict | None = None,
    objetivo_popularidad: float | None = None,
) -> tuple[dict[str, list[dict]], str]:
    """Ejecuta el flujo completo y devuelve (rankings, session_id).

    Afinidad: mezcla de 3 señales -- coseno (sensible al texto de la
    consulta), LightGBM (comportamiento real de 149.941 reservas) y
    sentimiento real (XLM-RoBERTa sobre 37.956 reseñas). Ver detalle en
    los comentarios del bucle principal.

    Pensado para uso conversacional, no solo consulta unica:
      session_id: identifica la conversacion en curso. Si se pasa, cada
        resultado mostrado y cada llamada a registrar_feedback() quedan
        asociados a la misma sesion, permitiendo reconstruir despues
        toda la conversacion y su desenlace.
      excluir_ids / excluir_destinos: lo que el usuario ya rechazo en
        esta sesion (el agente los va acumulando turno a turno).
      filtros: filtros explicitos, opcionales, combinables con el texto
        libre -- para la variante "manual" del buscador (sin pasar por
        el agente) o para cuando el agente ya extrajo preferencias
        concretas de la conversacion. Claves soportadas hoy:
          - presupuesto_max: float, precio_eur <= este valor
          - categoria: str, coincidencia exacta con experiencias.category
          - destino: str, coincidencia exacta con experiencias.destination
      objetivo_popularidad: opcional, 0.0-1.0. Si se pasa, agrega un
        4to ranking ("personalizado") interpolando entre el extremo de
        redistribucion (0.0, mismos pesos que 'intensivo') y el extremo
        de pura afinidad/popularidad (1.0, mismos pesos que
        'tradicional') -- para el slider continuo del dashboard, sin
        reemplazar los 3 escenarios fijos ya existentes.
    """
    excluir_ids = set(excluir_ids or [])
    excluir_destinos = set(excluir_destinos or [])
    filtros = filtros or {}

    print(f"\n1) Vectorizando consulta: '{texto_consulta}'")
    query_pipeline = QueryPipeline()
    query_vector = query_pipeline.process_query(texto_consulta)

    print("2) Buscando candidatos por afinidad semantica (similitud coseno)...")
    recommender = TuiRecommender()
    # Se pide un pool mas grande de lo habitual porque parte se va a
    # descartar por exclusiones/filtros antes de llegar al TDRS.
    candidatos_afinidad = recommender.search(query_vector, top_k=top_k_candidatos * 3)

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
    temp_confort_por_destino, dias_secos_por_destino, horas_sol_por_destino = cargar_clima_por_destino(db_path)
    capacidad_sanitaria_por_destino = cargar_capacidad_sanitaria_por_destino(db_path)
    seguridad_criminalidad_por_destino = cargar_seguridad_criminalidad_por_destino(db_path)
    datos_humanos_por_destino = cargar_datos_humanos_por_destino(db_path)
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
        meta = metadata.get(id_paq, {"destino_nombre": "desconocido", "category": "", "price_eur": None})
        destino = meta["destino_nombre"]

        # --- Exclusiones y filtros (arquitectura conversacional/manual) ---
        if id_paq in excluir_ids:
            continue
        if destino in excluir_destinos:
            continue
        if "presupuesto_max" in filtros and meta.get("price_eur") is not None:
            if meta["price_eur"] > filtros["presupuesto_max"]:
                continue
        if "categoria" in filtros and meta.get("category") != filtros["categoria"]:
            continue
        if "destino" in filtros and destino != filtros["destino"]:
            continue

        candidato, detalle = calcular_candidato(
            id_paq, destino, c["score_similitud"],
            ocupacion_por_destino, sensibilidad_por_destino,
            accesibilidad_por_destino, capacidad_por_destino,
            diversificacion_por_destino, temporada_baja_por_destino,
            impacto_local_por_destino, sentimiento_por_destino,
            temp_confort_por_destino, dias_secos_por_destino, horas_sol_por_destino,
            capacidad_sanitaria_por_destino, seguridad_criminalidad_por_destino,
            modelo_lgbm, precios, duraciones, ratings, reviews, tdrs_calc,
        )
        # Datos humanos: valores reales para mostrar en el dashboard
        # (% dias soleados, pasajeros/año, etc.), separados de los
        # scores 0-1 que usa el modelo internamente -- no afecta el
        # scoring, es solo para presentacion.
        candidato["datos_humanos"] = datos_humanos_por_destino.get(destino, {})
        candidato["precio_eur"] = meta.get("price_eur")
        candidatos.append(candidato)
        detalle_afinidad[id_paq] = detalle

    print("4) Aplicando re-ranking (3 escenarios)...")
    reranker = ReRankingEngine()
    rankings = reranker.rank_all_scenarios(candidatos, k=k_final)
    if objetivo_popularidad is not None:
        # Ranking adicional con el slider continuo del dashboard
        # ('Recomendador España'), sin reemplazar los 3 escenarios fijos
        # (que sigue usando 'Simulador TDRS' con sus 3 botones).
        rankings["personalizado"] = reranker.rank_por_objetivo_popularidad(
            candidatos, objetivo_popularidad, k=k_final,
        )

    print("5) Registrando resultados para futuro reentrenamiento...")
    log_ids = {}
    if session_id is None:
        import uuid as uuid_module
        session_id = str(uuid_module.uuid4())
    try:
        crear_tabla_log(db_path)
        log_ids = guardar_log_recomendaciones(
            db_path, texto_consulta, rankings, detalle_afinidad, session_id=session_id,
        )
    except Exception as e:
        print(f"   -> No se pudo guardar el log (no bloqueante): {e}")

    detectar_oportunidades(db_path, texto_consulta, query_vector=query_vector)

    for r in rankings.get("moderado", []):
        r["log_id"] = log_ids.get(r["id_paquete"])

    return rankings, session_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/tui_recomendador.db")
    parser.add_argument(
        "--consulta", default="Busco unas vacaciones relajantes en la playa con buen clima",
    )
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    rankings, session_id = recomendar(args.consulta, db_path=args.db, k_final=args.top_k)

    for escenario, resultados in rankings.items():
        print(f"\n{'='*60}")
        print(f"  ESCENARIO: {escenario.upper()}")
        print(f"{'='*60}")
        for i, r in enumerate(resultados, 1):
            print(f"  {i:2d}. {r['id_paquete']} | {r['destino_nombre']:20s} | "
                  f"score_final={r['score_final']:.4f} | tdrs={r['tdrs']:.3f}")


if __name__ == "__main__":
    main()