"""Sembrador de historia de uso para «Monitor performance».

Genera actividad realista (sesiones, recomendaciones, impresiones y clics)
repartida a lo largo de varios días, usando EXACTAMENTE las mismas funciones de
la app (``create_session`` y ``register_event``) y los mismos tipos de evento
que instrumenta el dashboard. No inventa esquemas ni escribe SQL a mano para los
eventos: solo ajusta los ``timestamp``/``started_at`` a fechas pasadas (las
funciones de la app siempre sellan «ahora»), para que la evolución temporal y la
comparación «vs. periodo anterior» tengan recorrido.

Pensado para poblar una base recién desplegada (p. ej. en Streamlit Cloud) y que
los paneles dejen de estar vacíos. Es idempotente por lote gracias a un prefijo
de sesión: relanzarlo añade un lote nuevo sin romper nada, y ``--reset`` borra
solo lo sembrado por este script.

Uso:
    python scripts/seed_history.py                # ~200 sesiones, 21 días
    python scripts/seed_history.py --sessions 120 --days 14
    python scripts/seed_history.py --reset        # borra lo sembrado y sale

Nota: escribe en la base que use la app (``config.DB_PATH`` / ``TUI_DB_PATH``).
En Cloud, ejecútalo en el mismo entorno donde corre la app.
"""

from __future__ import annotations

import argparse
import random
import uuid
from datetime import datetime, timedelta

from database.connection import db_session
from database.init_db import init_db
from services import spain_reference
from services.tracking_service import create_session, register_event

# Marca que identifica las sesiones sembradas por este script, para poder
# limpiarlas selectivamente sin tocar la actividad real.
SEED_SOURCE = "seed_history"
SEED_SESSION_PREFIX = "seed-"

VIEW_LABEL = "España"

# Catálogo de destinos que se recomiendan. Mezcla nacional (aparece en el mapa
# de España) e internacional (aparece en ranking/tablas, no en el mapa), igual
# que la app real. Se usan nombres canónicos de la referencia.
NATIONAL = [
    "Madrid", "Barcelona", "Sevilla", "Granada", "Málaga", "Costa del Sol",
    "Cádiz", "Alicante", "Valencia", "Bilbao", "San Sebastián", "Mallorca",
    "Menorca", "Ibiza", "Tenerife", "Gran Canaria", "Lanzarote", "Fuerteventura",
]
INTERNATIONAL = ["Algarve", "Santorini", "Creta", "Bali", "Cancún", "Marrakech", "Dubái"]

# Pesos de popularidad: unos destinos se recomiendan y clican más que otros,
# para que el ranking y el podio tengan forma (no todo plano).
POPULARITY = {
    "Costa del Sol": 5.0, "Mallorca": 4.5, "Tenerife": 4.2, "Barcelona": 4.0,
    "Málaga": 3.8, "Alicante": 3.4, "Gran Canaria": 3.2, "Madrid": 3.0,
    "Ibiza": 2.8, "Valencia": 2.4, "Sevilla": 2.2, "Granada": 1.8,
}
DEFAULT_WEIGHT = 1.2

ORIGINS = ("hero", "alternativa")
SOURCES = ("streamlit", "organic", "campaign", "direct")
DEVICES = ("desktop", "mobile", "tablet")


def _weight(dest: str) -> float:
    return POPULARITY.get(dest, DEFAULT_WEIGHT)


def _weighted_sample(pool: list[str], k: int) -> list[str]:
    """Muestra sin reemplazo ponderada por popularidad (ranking de una reco)."""
    pool = list(pool)
    chosen: list[str] = []
    for _ in range(min(k, len(pool))):
        weights = [_weight(d) for d in pool]
        pick = random.choices(pool, weights=weights, k=1)[0]
        chosen.append(pick)
        pool.remove(pick)
    return chosen


def _random_timestamp(day: datetime) -> datetime:
    """Hora verosímil dentro de un día: sesgada a tardes/noches."""
    hour = random.choices(
        population=list(range(8, 24)),
        weights=[1, 1, 2, 2, 3, 3, 4, 4, 3, 3, 4, 5, 5, 4, 3, 2],
        k=1,
    )[0]
    return day.replace(hour=hour, minute=random.randint(0, 59),
                       second=random.randint(0, 59), microsecond=0)


def _stamp(conn, *, session_id: str, event_ts: datetime | None = None,
           session_ts: datetime | None = None) -> None:
    """Fija timestamps históricos. La app sella «ahora»; aquí lo retrodatamos.

    Se hace sobre la MISMA base que usó ``register_event``/``create_session`` y
    solo sobre las filas recién creadas (por ``session_id``)."""
    if session_ts is not None:
        conn.execute(
            "UPDATE sessions SET started_at=? WHERE session_id=?",
            (session_ts.strftime("%Y-%m-%d %H:%M:%S"), session_id),
        )
    if event_ts is not None:
        # La sesión es nueva y solo contiene los eventos de este turno, así que
        # se pueden retrodatar todos sin afectar a otras sesiones.
        conn.execute(
            "UPDATE events SET timestamp=? WHERE session_id=?",
            (event_ts.strftime("%Y-%m-%d %H:%M:%S"), session_id),
        )


def seed(num_sessions: int, days: int, seed_value: int | None) -> dict:
    if seed_value is not None:
        random.seed(seed_value)

    init_db()  # asegura el esquema (no borra nada existente)

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_day = today - timedelta(days=days - 1)

    totals = {"sessions": 0, "requests": 0, "impressions": 0, "clicks": 0}

    for _ in range(num_sessions):
        # Reparte la sesión en un día del rango (con ligera tendencia creciente
        # hacia días recientes, para que la serie no sea plana).
        day_offset = min(days - 1, int(random.triangular(0, days - 1, days - 1)))
        day = start_day + timedelta(days=day_offset)
        base_ts = _random_timestamp(day)

        session_id = SEED_SESSION_PREFIX + uuid.uuid4().hex[:16]
        create_session(
            source=random.choice(SOURCES),
            device=random.choice(DEVICES),
            country="ES",
            session_id=session_id,
        )
        totals["sessions"] += 1

        # page_view de entrada (engagement).
        register_event(session_id, "page_view", VIEW_LABEL,
                       dedupe_key=f"pv:{session_id}:reco")

        # 1–3 peticiones de recomendación por sesión.
        n_requests = random.choices((1, 2, 3), weights=(6, 3, 1), k=1)[0]
        cursor_ts = base_ts
        for _r in range(n_requests):
            cursor_ts = cursor_ts + timedelta(minutes=random.randint(1, 6))
            recommendation_id = uuid.uuid4().hex[:12]
            origin = random.choice(ORIGINS)

            # Mezcla de destinos del ranking: mayoría nacional + alguno internac.
            k = random.choice((3, 4, 5))
            pool = NATIONAL + (INTERNATIONAL if random.random() < 0.6 else [])
            ranking = _weighted_sample(pool, k)

            register_event(
                session_id, "recommendation_request", VIEW_LABEL,
                metadata={"origin": origin, "recommendation_id": recommendation_id,
                          "engine_version": "seed-1.0"},
                dedupe_key=f"req:{session_id}:{recommendation_id}",
            )
            totals["requests"] += 1

            # Una impresión por destino del ranking (con posición y score).
            for position, dest in enumerate(ranking, start=1):
                score = round(max(0.0, min(1.0, random.gauss(0.75 - 0.05 * position, 0.08))), 4)
                register_event(
                    session_id, "recommendation_impression", VIEW_LABEL,
                    destination=dest,
                    metadata={"position": position, "score": score,
                              "origin": origin, "recommendation_id": recommendation_id},
                    dedupe_key=f"reco_impression:{recommendation_id}:{position}:{dest}",
                )
                totals["impressions"] += 1

            # Clics: probabilidad por posición (CTR realista, decae con la
            # posición) modulada por la popularidad del destino.
            for position, dest in enumerate(ranking, start=1):
                base_ctr = {1: 0.22, 2: 0.12, 3: 0.07}.get(position, 0.04)
                p_click = min(0.6, base_ctr * (_weight(dest) / 2.5))
                if random.random() < p_click:
                    register_event(
                        session_id, "recommendation_click", "recomendacion",
                        destination=dest,
                        metadata={"position": position, "origin": origin,
                                  "recommendation_id": recommendation_id},
                        dedupe_key=f"reco_click:{recommendation_id}:{position}:{dest}",
                    )
                    totals["clicks"] += 1

        # Retrodata todos los eventos y la sesión a la fecha elegida.
        with db_session() as conn:
            _stamp(conn, session_id=session_id, event_ts=base_ts, session_ts=base_ts)

    return totals


def reset() -> int:
    """Borra únicamente lo sembrado por este script (sesiones con prefijo seed)."""
    with db_session() as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM events WHERE session_id LIKE ?",
            (SEED_SESSION_PREFIX + "%",),
        ).fetchone()[0]
        conn.execute("DELETE FROM events WHERE session_id LIKE ?", (SEED_SESSION_PREFIX + "%",))
        conn.execute("DELETE FROM sessions WHERE session_id LIKE ?", (SEED_SESSION_PREFIX + "%",))
    return int(n)


def main() -> None:
    parser = argparse.ArgumentParser(description="Siembra historia de uso para el panel.")
    parser.add_argument("--sessions", type=int, default=200, help="Número de sesiones a crear.")
    parser.add_argument("--days", type=int, default=21, help="Días hacia atrás a repartir.")
    parser.add_argument("--seed", type=int, default=42, help="Semilla aleatoria (reproducible).")
    parser.add_argument("--reset", action="store_true", help="Borra lo sembrado y sale.")
    args = parser.parse_args()

    if args.reset:
        removed = reset()
        print(f"Eliminados {removed} eventos sembrados (y sus sesiones).")
        return

    totals = seed(args.sessions, args.days, args.seed)
    print("Siembra completada:")
    print(f"  sesiones:       {totals['sessions']}")
    print(f"  recomendaciones:{totals['requests']}")
    print(f"  impresiones:    {totals['impressions']}")
    print(f"  clics:          {totals['clicks']}")
    ctr = (totals["clicks"] / totals["impressions"] * 100) if totals["impressions"] else 0
    print(f"  CTR global:     {ctr:.1f}%")


if __name__ == "__main__":
    main()
