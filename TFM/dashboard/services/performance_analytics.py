from __future__ import annotations

"""Métricas del panel «Monitor performance».

Todo se calcula sobre los eventos REALES de la app (tabla ``events``) y las
tablas de referencia (``sessions``, ``destinations``, ``destination_sentiment``).
Ninguna cifra se inventa: cuando no hay datos suficientes para una métrica, se
devuelve ``None`` o una lista vacía y la interfaz muestra «Sin datos
suficientes».

Eventos que usa (todos reales y observables en la app):
  - ``recommendation_request``  → recomendaciones generadas
  - ``recommendation_impression`` → destinos mostrados en un ranking (interés)
  - ``recommendation_click``    → clic en «Ver opciones» de una recomendación
  - ``page_view``               → navegación (engagement)

Los eventos guardan ``timestamp`` (texto ISO ``YYYY-MM-DD HH:MM:SS``),
``session_id``, ``destination`` y ``metadata`` (JSON). El filtrado por periodo se
hace con comparaciones de cadena sobre ``timestamp`` (orden lexicográfico válido
para ISO 8601). Los filtros de destino/CCAA/tipo se aplican tras unir con
``spain_reference``.
"""

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from database.repositories import AnalyticsRepository
from services import spain_reference
from utils.text import normalize_text

_repo = AnalyticsRepository()

# Eventos que instrumenta la app para el rendimiento de recomendaciones.
EV_REQUEST = "recommendation_request"
EV_IMPRESSION = "recommendation_impression"
EV_CLICK = "recommendation_click"
EV_PAGE_VIEW = "page_view"

# ``product_impression`` es el nombre histórico con el que la app registró en su
# día las mismas impresiones de recomendación por destino (con posición y score
# en metadata). Es dato real y equivalente, así que cuenta como impresión junto
# al nombre nuevo. No se mezcla ningún dato ficticio.
IMPRESSION_EVENTS = (EV_IMPRESSION, "product_impression")
CLICK_EVENTS = (EV_CLICK, "product_click", "destination_click")

# Presets de periodo del panel.
PERIOD_TODAY = "Hoy"
PERIOD_7D = "Últimos 7 días"
PERIOD_30D = "Últimos 30 días"
PERIOD_ALL = "Todo el histórico"
PERIOD_PRESETS = (PERIOD_TODAY, PERIOD_7D, PERIOD_30D, PERIOD_ALL)


def _safe_div(a, b):
    return (a / b) if b else None


# --------------------------------------------------------------------------
# Ventana temporal
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Period:
    """Ventana temporal cerrada por la izquierda y abierta por la derecha:
    ``start <= timestamp < end``. ``start``/``end`` son fechas (día completo).

    ``previous`` devuelve la ventana inmediatamente anterior de la misma
    duración, para calcular la variación vs. periodo anterior.
    """
    start: date | None
    end: date          # exclusivo (día siguiente al último incluido)
    label: str = ""

    @property
    def start_str(self) -> str | None:
        return f"{self.start.isoformat()} 00:00:00" if self.start else None

    @property
    def end_str(self) -> str:
        return f"{self.end.isoformat()} 00:00:00"

    def previous(self) -> "Period | None":
        if self.start is None:
            return None
        span = (self.end - self.start)
        if span.days <= 0:
            return None
        return Period(self.start - span, self.start, label="periodo anterior")


def resolve_period(preset: str, today: date | None = None,
                   custom_start: date | None = None,
                   custom_end: date | None = None) -> Period:
    """Traduce un preset (o un rango personalizado) a una ``Period``.

    ``today`` se puede fijar en pruebas. El rango personalizado tiene prioridad
    si se pasan ambas fechas.
    """
    today = today or date.today()
    if custom_start and custom_end:
        # end es exclusivo: se incluye el día final completo.
        return Period(custom_start, custom_end + timedelta(days=1), "Periodo personalizado")
    tomorrow = today + timedelta(days=1)
    if preset == PERIOD_TODAY:
        return Period(today, tomorrow, PERIOD_TODAY)
    if preset == PERIOD_7D:
        return Period(today - timedelta(days=6), tomorrow, PERIOD_7D)
    if preset == PERIOD_30D:
        return Period(today - timedelta(days=29), tomorrow, PERIOD_30D)
    return Period(None, tomorrow, PERIOD_ALL)


def data_bounds() -> dict:
    """Primer y último día con eventos registrados (para el selector de rango)."""
    row = _repo.rows("SELECT MIN(timestamp) mn, MAX(timestamp) mx FROM events")
    if not row or not row[0].get("mn"):
        return {"min": None, "max": None}

    def _d(value):
        try:
            return datetime.fromisoformat(str(value)[:19]).date()
        except (TypeError, ValueError):
            return None

    return {"min": _d(row[0]["mn"]), "max": _d(row[0]["mx"])}


# --------------------------------------------------------------------------
# Filtros del panel
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Filters:
    """Filtros del panel. Todos opcionales; ``None``/"Todos" = sin filtrar."""
    destination: str | None = None
    community: str | None = None
    dest_type: str | None = None

    def allows(self, destination_name: str) -> bool:
        """¿Pasa un destino los filtros de destino/CCAA/tipo?"""
        ref = spain_reference.get_reference(destination_name)
        if self.community and self.community != "Todas":
            if not ref or ref.get("ccaa") != self.community:
                return False
        if self.dest_type and self.dest_type != "Todos":
            if not ref or ref.get("type") != self.dest_type:
                return False
        if self.destination and self.destination != "Todos":
            canonical = spain_reference.match_spain_destination(destination_name)
            target = spain_reference.match_spain_destination(self.destination) or self.destination
            if (canonical or destination_name) != target:
                return False
        return True

    @property
    def active(self) -> bool:
        return bool(
            (self.destination and self.destination != "Todos")
            or (self.community and self.community != "Todas")
            or (self.dest_type and self.dest_type != "Todos")
        )


def _period_clause(period: Period, alias: str = "") -> tuple[str, list]:
    prefix = f"{alias}." if alias else ""
    clauses, params = [], []
    if period.start_str is not None:
        clauses.append(f"{prefix}timestamp >= ?")
        params.append(period.start_str)
    clauses.append(f"{prefix}timestamp < ?")
    params.append(period.end_str)
    return (" AND ".join(clauses), params)


# --------------------------------------------------------------------------
# Conteos base de eventos en una ventana
# --------------------------------------------------------------------------

def _event_counts(period: Period) -> dict:
    where, params = _period_clause(period)
    rows = _repo.rows(
        f"SELECT event_type, COUNT(*) n, COUNT(DISTINCT session_id) ns "
        f"FROM events WHERE {where} GROUP BY event_type",
        tuple(params),
    )
    by_type = {r["event_type"]: r for r in rows}

    def n(ev):
        return int((by_type.get(ev) or {}).get("n", 0) or 0)

    def n_any(*evs):
        return sum(n(e) for e in evs)

    sessions = _repo.scalar(
        f"SELECT COUNT(DISTINCT session_id) FROM events WHERE {where}",
        tuple(params),
    ) or 0
    return {
        "requests": n(EV_REQUEST),
        "impressions": n_any(*IMPRESSION_EVENTS),
        "clicks": n_any(*CLICK_EVENTS),
        "page_views": n(EV_PAGE_VIEW),
        "active_sessions": int(sessions),
    }


def _sessions_started(period: Period) -> int:
    where, params = [], []
    if period.start_str is not None:
        where.append("started_at >= ?")
        params.append(period.start_str)
    where.append("started_at < ?")
    params.append(period.end_str)
    clause = " AND ".join(where)
    return int(_repo.scalar(f"SELECT COUNT(*) FROM sessions WHERE {clause}", tuple(params)) or 0)


# --------------------------------------------------------------------------
# KPIs principales (con variación vs periodo anterior)
# --------------------------------------------------------------------------

def _delta(current, previous):
    """Variación absoluta y porcentual. ``pct`` es ``None`` si no es calculable."""
    if current is None or previous is None:
        return {"abs": None, "pct": None}
    diff = current - previous
    pct = (diff / previous * 100) if previous else None
    return {"abs": diff, "pct": pct}


def get_kpis(period: Period, filters: Filters | None = None) -> dict:
    """KPIs principales del panel para la ventana dada.

    Los KPIs globales (sesiones, recomendaciones, page views) no dependen del
    destino, así que ignoran los filtros de destino/CCAA/tipo. Los KPIs que sí
    son por destino (impresiones, clics, CTR, destinos consultados) se calculan
    respetando los filtros, reutilizando ``get_destination_performance``.
    """
    counts = _event_counts(period)
    sessions_started = _sessions_started(period)

    # Métricas por destino, ya filtradas.
    dest_rows = get_destination_performance(period, filters)
    impressions = sum(r["impressions"] for r in dest_rows)
    clicks = sum(r["clicks"] for r in dest_rows)
    destinations_seen = len([r for r in dest_rows if r["impressions"] > 0])
    top_clicked = max(dest_rows, key=lambda r: r["clicks"], default=None)

    prev = period.previous()
    prev_counts = _event_counts(prev) if prev else None
    prev_sessions_started = _sessions_started(prev) if prev else None
    if prev:
        prev_dest = get_destination_performance(prev, filters)
        prev_impr = sum(r["impressions"] for r in prev_dest)
        prev_clicks = sum(r["clicks"] for r in prev_dest)
    else:
        prev_impr = prev_clicks = None

    ctr = _safe_div(clicks, impressions)
    prev_ctr = _safe_div(prev_clicks, prev_impr) if prev else None

    def kpi(value, prev_value, *, fmt="int", available=True):
        return {
            "value": value,
            "available": available,
            "delta": _delta(value, prev_value),
            "fmt": fmt,
        }

    return {
        "active_sessions": kpi(counts["active_sessions"],
                               prev_counts["active_sessions"] if prev_counts else None),
        "sessions_started": kpi(sessions_started, prev_sessions_started),
        "recommendations": kpi(counts["requests"],
                               prev_counts["requests"] if prev_counts else None),
        "impressions": kpi(impressions, prev_impr),
        "clicks": kpi(clicks, prev_clicks),
        "ctr": kpi(ctr, prev_ctr, fmt="pct1", available=impressions > 0),
        "destinations_seen": kpi(destinations_seen, None),
        "top_destination": {
            "value": top_clicked["destination"] if top_clicked and top_clicked["clicks"] > 0 else None,
            "clicks": top_clicked["clicks"] if top_clicked else 0,
            "available": bool(top_clicked and top_clicked["clicks"] > 0),
        },
        "page_views": kpi(counts["page_views"],
                          prev_counts["page_views"] if prev_counts else None),
        # No hay identidad de usuario (sessions.user_id siempre nulo) ni evento de
        # conversión/reserva emitido por la app: se declaran como no instrumentados.
        "users": {"value": None, "available": False,
                  "note": "Requiere identificar al usuario (sessions.user_id)"},
        "conversion": {"value": None, "available": False,
                       "note": "Requiere un evento de conversión/reserva"},
    }


# --------------------------------------------------------------------------
# Rendimiento por destino (impresiones, clics, CTR, sesiones)
# --------------------------------------------------------------------------

def get_destination_performance(period: Period, filters: Filters | None = None) -> list[dict]:
    """Interés por destino a partir de impresiones y clics reales.

    Une los eventos ``recommendation_impression`` y ``recommendation_click`` por
    nombre de destino (normalizado). Añade la ficha geográfica de España cuando
    el destino es reconocible. Devuelve una fila por destino con impresiones,
    clics, CTR, sesiones que lo vieron y sesiones que hicieron clic.
    """
    filters = filters or Filters()
    where, params = _period_clause(period)
    interaction_events = tuple(dict.fromkeys(IMPRESSION_EVENTS + CLICK_EVENTS))
    placeholders = ",".join("?" for _ in interaction_events)
    rows = _repo.rows(
        f"""
        SELECT destination,
               event_type,
               COUNT(*) n,
               COUNT(DISTINCT session_id) ns
          FROM events
         WHERE {where}
           AND event_type IN ({placeholders})
           AND destination IS NOT NULL AND destination <> ''
         GROUP BY destination, event_type
        """,
        tuple(params) + interaction_events,
    )

    agg: dict[str, dict] = {}
    for r in rows:
        raw = r["destination"]
        canonical = spain_reference.match_spain_destination(raw) or raw
        entry = agg.setdefault(canonical, {
            "destination": canonical,
            "impressions": 0, "clicks": 0,
            "impression_sessions": 0, "click_sessions": 0,
        })
        if r["event_type"] in IMPRESSION_EVENTS:
            entry["impressions"] += int(r["n"])
            entry["impression_sessions"] += int(r["ns"])
        elif r["event_type"] in CLICK_EVENTS:
            entry["clicks"] += int(r["n"])
            entry["click_sessions"] += int(r["ns"])

    out = []
    for entry in agg.values():
        if not filters.allows(entry["destination"]):
            continue
        ref = spain_reference.get_reference(entry["destination"])
        entry["ctr"] = _safe_div(entry["clicks"], entry["impressions"])
        entry["users"] = entry["impression_sessions"]  # proxy: sesiones únicas
        entry["ccaa"] = ref.get("ccaa") if ref else None
        entry["province"] = ref.get("province") if ref else None
        entry["type"] = ref.get("type") if ref else None
        entry["country"] = (ref.get("country") or "España") if ref else None
        # España = destino con ficha y sin país extranjero declarado. Los
        # internacionales tienen ficha (para ranking/tablas) pero country != España.
        entry["in_spain"] = ref is not None and entry["country"] == "España"
        out.append(entry)

    out.sort(key=lambda r: (-r["clicks"], -r["impressions"], r["destination"]))
    for i, entry in enumerate(out, start=1):
        entry["rank"] = i
    return out


def rank_destinations(period: Period, filters: Filters | None = None,
                      order_by: str = "clicks", limit: int | None = None) -> list[dict]:
    """Ranking de destinos por el criterio pedido: clicks, ctr, users, impressions."""
    rows = get_destination_performance(period, filters)
    key_map = {
        "clicks": lambda r: (r["clicks"], r["impressions"]),
        "impressions": lambda r: (r["impressions"], r["clicks"]),
        "users": lambda r: (r["users"], r["clicks"]),
        "ctr": lambda r: ((r["ctr"] if r["ctr"] is not None else -1), r["clicks"]),
    }
    key = key_map.get(order_by, key_map["clicks"])
    ordered = sorted(rows, key=lambda r: (key(r), r["destination"]), reverse=True)
    return ordered[:limit] if limit else ordered


def get_destination_trends(period: Period, filters: Filters | None = None) -> list[dict]:
    """Variación de clics por destino vs. el periodo anterior de igual duración.

    Permite ver qué destinos crecen y cuáles caen. Si no hay periodo anterior
    (histórico completo), ``delta`` queda a ``None``.
    """
    current = {r["destination"]: r for r in get_destination_performance(period, filters)}
    prev = period.previous()
    prev_map = {}
    if prev:
        prev_map = {r["destination"]: r for r in get_destination_performance(prev, filters)}

    out = []
    for name, row in current.items():
        prev_clicks = prev_map.get(name, {}).get("clicks") if prev else None
        out.append({
            **row,
            "prev_clicks": prev_clicks,
            "delta_clicks": (row["clicks"] - prev_clicks) if prev_clicks is not None else None,
        })
    out.sort(key=lambda r: (-r["clicks"], r["destination"]))
    return out


# --------------------------------------------------------------------------
# Evolución temporal (serie diaria)
# --------------------------------------------------------------------------

def get_timeseries(period: Period, filters: Filters | None = None) -> list[dict]:
    """Serie diaria de recomendaciones, impresiones, clics, sesiones y CTR.

    Devuelve una fila por día del periodo (incluyendo días sin actividad, a 0)
    para que las tendencias no tengan huecos engañosos.
    """
    where, params = _period_clause(period)
    rows = _repo.rows(
        f"""
        SELECT substr(timestamp,1,10) day, event_type,
               COUNT(*) n, COUNT(DISTINCT session_id) ns
          FROM events
         WHERE {where}
         GROUP BY substr(timestamp,1,10), event_type
        """,
        tuple(params),
    )

    per_day: dict[str, dict] = {}
    for r in rows:
        day = r["day"]
        d = per_day.setdefault(day, {"requests": 0, "impressions": 0, "clicks": 0})
        if r["event_type"] == EV_REQUEST:
            d["requests"] += int(r["n"])
        elif r["event_type"] in IMPRESSION_EVENTS:
            d["impressions"] += int(r["n"])
        elif r["event_type"] in CLICK_EVENTS:
            d["clicks"] += int(r["n"])

    # Sesiones activas por día (cualquier evento).
    sess_rows = _repo.rows(
        f"SELECT substr(timestamp,1,10) day, COUNT(DISTINCT session_id) ns "
        f"FROM events WHERE {where} GROUP BY substr(timestamp,1,10)",
        tuple(params),
    )
    sessions_by_day = {r["day"]: int(r["ns"]) for r in sess_rows}

    bounds = data_bounds()
    start = period.start or bounds["min"]
    end_day = period.end - timedelta(days=1)
    if start is None:
        return []

    out = []
    cursor = start
    while cursor <= end_day:
        key = cursor.isoformat()
        d = per_day.get(key, {"requests": 0, "impressions": 0, "clicks": 0})
        ctr = _safe_div(d["clicks"], d["impressions"])
        out.append({
            "day": key,
            "requests": d["requests"],
            "impressions": d["impressions"],
            "clicks": d["clicks"],
            "sessions": sessions_by_day.get(key, 0),
            "ctr": (ctr * 100) if ctr is not None else None,
        })
        cursor += timedelta(days=1)
    return out


# --------------------------------------------------------------------------
# Engagement
# --------------------------------------------------------------------------

def get_engagement(period: Period) -> dict:
    """Comportamiento agregado: sesiones activas, recomendaciones y clics por
    sesión, y páginas vistas por sesión. No incluye usuarios nuevos/recurrentes
    ni tiempo de sesión porque la app no identifica usuarios ni cierra sesiones
    (``sessions.user_id`` y ``sessions.ended_at`` no se instrumentan)."""
    counts = _event_counts(period)
    active = counts["active_sessions"]
    return {
        "active_sessions": active,
        "recommendations": counts["requests"],
        "clicks": counts["clicks"],
        "page_views": counts["page_views"],
        "recos_per_session": _safe_div(counts["requests"], active),
        "clicks_per_session": _safe_div(counts["clicks"], active),
        "views_per_session": _safe_div(counts["page_views"], active),
        "new_vs_returning_available": False,
        "session_duration_available": False,
    }


# --------------------------------------------------------------------------
# Funnel de interacción
# --------------------------------------------------------------------------

def get_funnel(period: Period, filters: Filters | None = None) -> list[dict]:
    """Funnel a nivel de destino/impresión.

    Recomendaciones mostradas (impresiones) → Recomendaciones clicadas (clics).
    Ambos pasos comparten unidad (destinos-impresión), así que los clics son un
    subconjunto de las impresiones y el embudo decrece de forma monotónica: la
    conversión del paso es exactamente el CTR y nunca supera el 100%.

    «Recomendaciones generadas» (``recommendation_request``) NO se incluye como
    escalón porque está en otra unidad (peticiones, no impresiones): una sola
    solicitud genera varias impresiones —una por destino del ranking—, por lo que
    aparecería por debajo de «mostradas» y rompería el embudo. Se expone como KPI
    de volumen aparte. Tampoco se incluye «destino consultado» ni «conversión»
    porque no existe un evento propio para ellos; se declaran como pendientes de
    instrumentar.
    """
    dest_rows = get_destination_performance(period, filters)
    impressions = sum(r["impressions"] for r in dest_rows)
    clicks = sum(r["clicks"] for r in dest_rows)

    steps = [
        {"step": "Recomendaciones mostradas", "value": impressions, "available": True},
        {"step": "Recomendaciones clicadas", "value": clicks, "available": True},
    ]
    base = steps[0]["value"] or 0
    prev_value = None
    for s in steps:
        s["pct_of_top"] = _safe_div(s["value"], base)
        s["pct_of_prev"] = _safe_div(s["value"], prev_value) if prev_value else None
        prev_value = s["value"]
    return steps


def funnel_pending_steps() -> list[str]:
    """Pasos del funnel del brief que hoy NO tienen evento propio."""
    return ["Destino consultado", "Acción final / conversión"]


# --------------------------------------------------------------------------
# Saturación vs. interés (matriz de redistribución)
# --------------------------------------------------------------------------

def _saturation_lookup() -> dict[str, dict]:
    """Indicador de saturación por destino, en escala 0–1, a partir de datos
    reales del proyecto.

    Prioridad de fuentes (todas reales, ninguna inventada):
      1. ``destinations.occupancy`` / ``demand`` (0–1 del pipeline TDRS) si están.
      2. ``connectivity_stats.annual_passengers``: volumen anual de pasajeros
         aéreos, normalizado por el máximo entre destinos. Es el mejor proxy de
         presión/flujo turístico disponible.
      3. ``destinations.local_impact`` (0–1): impacto sobre el destino.

    Devuelve ``{norm_name: {"saturation": float|None, "source": str}}`` solo para
    los destinos con algún indicador real.
    """
    dest_rows = _repo.rows(
        "SELECT name, demand, occupancy, local_impact FROM destinations"
    )
    conn_rows = _repo.rows(
        "SELECT destination_name, annual_passengers FROM connectivity_stats "
        "WHERE annual_passengers IS NOT NULL"
    )
    max_pax = max((float(r["annual_passengers"]) for r in conn_rows), default=0.0)
    pax_by_dest = {
        normalize_text(r["destination_name"]): float(r["annual_passengers"])
        for r in conn_rows
    }

    out: dict[str, dict] = {}
    for r in dest_rows:
        key = normalize_text(r["name"])
        tdrs = r["occupancy"] if r["occupancy"] is not None else r["demand"]
        if tdrs is not None:
            out[key] = {"saturation": float(tdrs), "source": "tdrs"}
        elif key in pax_by_dest and max_pax > 0:
            out[key] = {"saturation": pax_by_dest[key] / max_pax, "source": "pasajeros"}
        elif r["local_impact"] is not None:
            out[key] = {"saturation": float(r["local_impact"]), "source": "impacto local"}
    # Destinos que solo aparecen en conectividad (por si algún nombre no está en
    # la tabla de destinos) también obtienen su proxy de pasajeros.
    for key, pax in pax_by_dest.items():
        if key not in out and max_pax > 0:
            out[key] = {"saturation": pax / max_pax, "source": "pasajeros"}
    return out


def _sentiment_lookup() -> dict[str, dict]:
    rows = _repo.rows(
        "SELECT destination_name, reviews_analyzed, sentiment_score, negative_pct "
        "FROM destination_sentiment"
    )
    return {
        normalize_text(r["destination_name"]): {
            "reviews": r["reviews_analyzed"],
            "sentiment": r["sentiment_score"],
            "negative_pct": r["negative_pct"],
        }
        for r in rows
    }


def get_interest_vs_saturation(period: Period, filters: Filters | None = None) -> dict:
    """Cruza el interés del usuario (clics/impresiones) con la saturación real
    del destino, para identificar oportunidades de redistribución.

    Cada destino con interés se clasifica en un cuadrante:
      - Alta demanda + alta saturación → masificado
      - Alta demanda + baja saturación → oportunidad
      - Baja demanda + alta saturación → menor prioridad
      - Baja demanda + baja saturación → oportunidad secundaria

    «Demanda» = clics (o impresiones si aún no hay clics). Los umbrales son la
    mediana de cada eje entre los destinos con dato, no valores arbitrarios.
    Devuelve ``{"points": [...], "thresholds": {...}, "available": bool}``.
    """
    sat_map = _saturation_lookup()
    dest_rows = get_destination_performance(period, filters)

    points = []
    for r in dest_rows:
        sat = sat_map.get(normalize_text(r["destination"]), {})
        saturation = sat.get("saturation")
        if saturation is None:
            continue
        interest = r["clicks"] if r["clicks"] > 0 else r["impressions"]
        if interest <= 0:
            continue
        points.append({
            "destination": r["destination"],
            "interest": interest,
            "clicks": r["clicks"],
            "impressions": r["impressions"],
            "saturation": float(saturation),
        })

    if not points:
        return {"points": [], "thresholds": {}, "available": False}

    def _median(values):
        s = sorted(values)
        n = len(s)
        mid = n // 2
        return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2

    interest_thr = _median([p["interest"] for p in points])
    sat_thr = _median([p["saturation"] for p in points])

    for p in points:
        high_interest = p["interest"] >= interest_thr
        high_sat = p["saturation"] >= sat_thr
        if high_interest and high_sat:
            p["quadrant"] = "Masificado"
        elif high_interest and not high_sat:
            p["quadrant"] = "Oportunidad"
        elif not high_interest and high_sat:
            p["quadrant"] = "Menor prioridad"
        else:
            p["quadrant"] = "Oportunidad secundaria"

    return {
        "points": points,
        "thresholds": {"interest": interest_thr, "saturation": sat_thr},
        "available": True,
    }


def get_potential_destinations(period: Period, filters: Filters | None = None,
                               limit: int = 6) -> list[dict]:
    """Destinos con potencial de redistribución: poco interés relativo, baja
    saturación y buena valoración (sentimiento real de reseñas).

    Combina las tres señales reales disponibles. Un destino puntúa alto si:
    recibe pocos clics, tiene baja saturación y buen sentimiento. Solo se
    consideran destinos con dato de saturación Y de sentimiento; el resto se
    omite en vez de rellenarse con supuestos.
    """
    sat_map = _saturation_lookup()
    sent_map = _sentiment_lookup()
    dest_rows = {r["destination"]: r for r in get_destination_performance(period, filters)}

    max_clicks = max((r["clicks"] for r in dest_rows.values()), default=0)

    candidates = []
    for name, ref in spain_reference.SPAIN_DESTINATIONS.items():
        if filters and not filters.allows(name):
            continue
        key = normalize_text(name)
        sat = sat_map.get(key, {}).get("saturation")
        sent = sent_map.get(key, {})
        sentiment = sent.get("sentiment")
        if sat is None or sentiment is None:
            continue
        clicks = dest_rows.get(name, {}).get("clicks", 0)
        impressions = dest_rows.get(name, {}).get("impressions", 0)
        interest_norm = (clicks / max_clicks) if max_clicks else 0.0
        # Puntuación de potencial: premia bajo interés, baja saturación y buen
        # sentimiento. Pesos iguales y explícitos.
        score = (1 - interest_norm) * 0.34 + (1 - float(sat)) * 0.33 + float(sentiment) * 0.33
        candidates.append({
            "destination": name,
            "clicks": clicks,
            "impressions": impressions,
            "saturation": float(sat),
            "sentiment": float(sentiment),
            "reviews": sent.get("reviews"),
            "ccaa": ref["ccaa"],
            "type": ref["type"],
            "potential_score": round(score, 4),
        })

    candidates.sort(key=lambda r: -r["potential_score"])
    return candidates[:limit]


# --------------------------------------------------------------------------
# Mapa de interés (destinos españoles con coordenada + métricas)
# --------------------------------------------------------------------------

def get_spain_interest_map(period: Period, filters: Filters | None = None) -> list[dict]:
    """Puntos del mapa de España: un punto por destino español con interés.

    Une el rendimiento por destino con las coordenadas de ``spain_reference``.
    Solo incluye destinos reconocidos en España (los internacionales o sin
    coordenada no se dibujan en un mapa de España). El campo ``rank`` refleja la
    posición por clics.
    """
    rows = get_destination_performance(period, filters)
    points = []
    for r in rows:
        ref = spain_reference.get_reference(r["destination"])
        # Solo destinos españoles: los internacionales tienen ficha (para
        # ranking y tablas) pero no se dibujan en el mapa de España.
        if not ref or not r.get("in_spain"):
            continue
        points.append({
            "destination": r["destination"],
            "lat": ref["lat"],
            "lon": ref["lon"],
            "province": ref["province"],
            "ccaa": ref["ccaa"],
            "type": ref["type"],
            "impressions": r["impressions"],
            "clicks": r["clicks"],
            "users": r["users"],
            "ctr": r["ctr"],
            "rank": r["rank"],
        })
    return points


def unmapped_interest(period: Period, filters: Filters | None = None) -> list[dict]:
    """Destinos con interés real que no están en la referencia de España (no se
    pintan en el mapa). Se declaran para no ocultar interacción."""
    rows = get_destination_performance(period, filters)
    return [
        {"destination": r["destination"], "clicks": r["clicks"], "impressions": r["impressions"]}
        for r in rows
        if not r["in_spain"] and (r["clicks"] > 0 or r["impressions"] > 0)
    ]
