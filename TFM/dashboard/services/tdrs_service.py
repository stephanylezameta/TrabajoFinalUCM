from __future__ import annotations

"""Lógica de negocio del Panel experto de redistribución (antes Simulador TDRS).

El TDRS (Tourism Demand Redistribution Score) parte de una tesis: el modelo no
solo recomienda destinos, también puede REDISTRIBUIR la demanda. El mismo motor
entrenado, según el objetivo de popularidad que se le pida, favorece turismo
tradicional (destinos muy visitados) o destinos menos saturados.

Este módulo ya NO calcula el ranking por su cuenta. Antes hacía una media
ponderada local (o llamaba a un backend propio en ``localhost``); ahora la
política de redistribución se traduce a una llamada al modelo real a través de
``services.model_gateway`` (que hoy resuelve contra la Function de Azure).

Aquí quedan:
- ``POLICY_PRESETS`` / ``POLICY_META``: los escenarios de política de la vista.
- ``recommend_policy``: fachada de conveniencia sobre el gateway.
- ``traveler_metrics``: métricas orientadas al VIAJERO sobre el ranking devuelto
  por el modelo (precio desde, precio medio, días de sol, satisfacción y cuántas
  alternativas menos concurridas hay). Es lo que muestra la vista.
- ``redistribution_metrics``: métricas técnicas de reparto de la demanda (incluye
  el índice de Gini). Ya NO se muestra en la vista; se conserva para no romper
  contratos internos y los tests.
- ``CSV_FACTORS`` / ``PRESETS`` / ``SCENARIO_META``: se conservan para el
  asistente conversacional de pesos (``assistant_service``), que traduce lenguaje
  natural a pesos del modelo y sigue siendo una de las formas de consumo.
- ``gini``: utilidad de concentración, reutilizada por las métricas y los tests.
"""

from typing import Any

from services import model_gateway

# --------------------------------------------------------------------------
# Escenarios de POLÍTICA de redistribución (panel experto)
# --------------------------------------------------------------------------
# Cada escenario fija el dial de popularidad (0 = redistribuido / destinos poco
# saturados, 1 = tradicional / muy visitados) y unos intereses de referencia que
# el gateway traduce al contrato del modelo. El foco narrativo es el dial: mover
# la popularidad cambia qué destinos propone el modelo.
POLICY_PRESETS: dict[str, dict[str, Any]] = {
    "Tradicional": {
        "popularity_target": 0.85,
        "temperature_preference": "warm_sunny",
        "interests": {
            "coast_beach": 90,
            "history_culture": 60,
            "gastronomy_wine": 55,
            "nature_mountains": 20,
            "rural": 10,
            "wellness": 20,
            "sports_outdoors": 20,
        },
    },
    "Equilibrado": {
        "popularity_target": 0.5,
        "temperature_preference": "mild",
        "interests": {
            "coast_beach": 60,
            "history_culture": 60,
            "gastronomy_wine": 55,
            "nature_mountains": 55,
            "rural": 40,
            "wellness": 40,
            "sports_outdoors": 40,
        },
    },
    "Redistribuido": {
        "popularity_target": 0.15,
        "temperature_preference": "any",
        "interests": {
            "coast_beach": 25,
            "history_culture": 55,
            "gastronomy_wine": 60,
            "nature_mountains": 90,
            "rural": 85,
            "wellness": 60,
            "sports_outdoors": 60,
        },
    },
}

POLICY_META: dict[str, dict[str, str]] = {
    "Tradicional": {
        "icon_key": "mona_lisa",
        "tagline": "Turismo tradicional",
        "description": (
            "Popularidad alta: el modelo prioriza los destinos más visitados y "
            "consolidados. Es el reparto de demanda de partida."
        ),
    },
    "Equilibrado": {
        "icon_key": "roman",
        "tagline": "Reparto mixto",
        "description": (
            "Popularidad media: combina destinos conocidos con alternativas, "
            "suavizando la concentración de la demanda."
        ),
    },
    "Redistribuido": {
        "icon_key": "compass",
        "tagline": "Demanda redistribuida",
        "description": (
            "Popularidad baja: el modelo empuja hacia destinos menos saturados, "
            "el objetivo central del TDRS."
        ),
    },
}

# Iconos reutilizados del selector antiguo por escenario de política.
POLICY_ICON_BY_NAME = {
    "Tradicional": "Popular",
    "Equilibrado": "Equilibrado",
    "Redistribuido": "Explorador",
}


# --------------------------------------------------------------------------
# Compatibilidad con el asistente conversacional de pesos
# --------------------------------------------------------------------------
# El asistente (``assistant_service``) traduce lenguaje natural a pesos del
# modelo y necesita el vocabulario de factores y unos presets de referencia.
# Se conservan aquí para no romper esa forma de consumo ni sus tests.
CSV_FACTORS = [
    ("sunny_days_pct", "% días soleados / año", "climate"),
    ("low_precipitation_pct", "% precipitación", "climate"),
    ("popularity", "Más visitado", "connectivity"),
    ("hospital_beds", "Capacidad sanitaria", "country"),
    ("safety", "Seguridad", "country"),
    ("satisfaction", "Satisfacción de viajeros", "sentiment"),
]
FACTORS = CSV_FACTORS

PRESETS = {
    "Popular": {
        "sunny_days_pct": 30,
        "low_precipitation_pct": 25,
        "popularity": 100,
        "hospital_beds": 20,
        "safety": 30,
        "satisfaction": 25,
    },
    "Equilibrado": {
        "sunny_days_pct": 70,
        "low_precipitation_pct": 60,
        "popularity": 65,
        "hospital_beds": 65,
        "safety": 80,
        "satisfaction": 75,
    },
    "Explorador": {
        "sunny_days_pct": 85,
        "low_precipitation_pct": 75,
        "popularity": 10,
        "hospital_beds": 70,
        "safety": 95,
        "satisfaction": 100,
    },
    "Personalizado": {
        "sunny_days_pct": 60,
        "low_precipitation_pct": 60,
        "popularity": 60,
        "hospital_beds": 60,
        "safety": 60,
        "satisfaction": 60,
    },
}

SCENARIO_META = {
    "Popular": {"icon_key": "mona_lisa", "description": "Prioriza volumen turístico y destinos con mayor popularidad."},
    "Equilibrado": {"icon_key": "roman", "description": "Combina clima, demanda, capacidad sanitaria y seguridad."},
    "Explorador": {"icon_key": "compass", "description": "Reduce el peso de popularidad y favorece señales de calidad del destino."},
    "Personalizado": {"icon_key": "custom", "description": "Permite ajustar manualmente todos los pesos del modelo."},
}


# --------------------------------------------------------------------------
# Consumo del modelo por política
# --------------------------------------------------------------------------

def recommend_policy(policy: dict[str, Any], max_price: float | None = None) -> dict[str, Any]:
    """Ranquea el catálogo aplicando una política de redistribución.

    Fachada fina sobre ``model_gateway.recommend_by_policy``: el ranking sale del
    modelo real, no de un cálculo local.
    """
    return model_gateway.recommend_by_policy(policy, max_price=max_price)


# --------------------------------------------------------------------------
# Métricas de reparto de la demanda
# --------------------------------------------------------------------------

def _popularity_index(row: dict[str, Any]) -> float | None:
    """Índice de popularidad del destino (0-1) tal y como lo devuelve el modelo."""
    profile = row.get("popularity_profile") or {}
    value = profile.get("index")
    if value is None:
        return None
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def gini(values: list[float]) -> float:
    """Índice de Gini (0 = reparto uniforme, →1 = máxima concentración)."""
    vals = sorted(max(0.0, float(v)) for v in values)
    n = len(vals)
    total = sum(vals)
    if n == 0 or total == 0:
        return 0.0
    cum = sum((i + 1) * v for i, v in enumerate(vals))
    return (2 * cum) / (n * total) - (n + 1) / n


def _mean(values: list[float | None]) -> float | None:
    vals = [float(v) for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def redistribution_metrics(ranking: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Resume cómo reparte la demanda el ranking devuelto por el modelo.

    ``ranking`` es la lista normalizada del gateway (filas del contrato de
    Azure). Devuelve popularidad media, concentración (Gini) y cuántos destinos
    del ranking son de baja popularidad, que es la señal de redistribución.
    """
    if not ranking:
        return None

    indices = [idx for idx in (_popularity_index(r) for r in ranking) if idx is not None]
    sunny = _mean([(r.get("climate_profile") or {}).get("sunny_days") for r in ranking])
    poi = _mean([(r.get("what_it_offers") or {}).get("poi_count") for r in ranking])

    low_popularity = sum(1 for idx in indices if idx <= 0.4)

    return {
        "eligible": len(ranking),
        "avg_popularity": _mean(indices),
        "popularity_gini": gini(indices) if indices else None,
        "with_popularity": len(indices),
        "low_popularity_count": low_popularity,
        "avg_sunny_days": sunny,
        "avg_poi_count": poi,
    }


# --------------------------------------------------------------------------
# Métricas orientadas al VIAJERO (lo que muestra la vista)
# --------------------------------------------------------------------------
# El panel lo usa un viajero, no un gestor. En vez de tecnicismos (Gini,
# concentración), se resumen las señales que ayudan a decidir un viaje: desde
# cuánto cuesta, cuánto sol hay, cómo lo valoran otros y cuántas alternativas
# menos concurridas propone el modelo.

# Umbral (0-1) por debajo del cual un destino se considera "menos concurrido".
LOW_CROWD_THRESHOLD = 0.4


def _price(row: dict[str, Any]) -> float | None:
    """Precio de referencia del destino, buscando las claves habituales del
    contrato. Si el modelo no envía precio, devuelve ``None`` (la vista lo omite
    con elegancia)."""
    candidates = (
        row.get("reference_price_eur"),
        row.get("price"),
        (row.get("pricing") or {}).get("from_eur"),
        (row.get("pricing") or {}).get("reference_eur"),
        (row.get("what_it_offers") or {}).get("reference_price_eur"),
    )
    for value in candidates:
        if value is None:
            continue
        try:
            price = float(value)
        except (TypeError, ValueError):
            continue
        if price > 0:
            return price
    return None


def _satisfaction(row: dict[str, Any]) -> float | None:
    """Satisfacción / valoración media del destino.

    Busca las claves habituales; si no hay dato, devuelve ``None`` para que la
    vista muestre «—» sin inventar un valor."""
    candidates = (
        (row.get("sentiment_profile") or {}).get("satisfaction"),
        (row.get("sentiment_profile") or {}).get("score"),
        (row.get("sentiment") or {}).get("satisfaction"),
        row.get("satisfaction"),
        (row.get("reputation") or {}).get("rating"),
    )
    for value in candidates:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def traveler_metrics(ranking: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Resume el ranking del modelo en señales útiles para el viajero.

    Devuelve, sobre el ranking (Top) devuelto por el modelo:
      - ``from_price`` / ``avg_price``: precio más barato y precio medio (o
        ``None`` si el modelo no manda precio; la vista omite esas tarjetas).
      - ``avg_sunny_days``: media de días de sol.
      - ``avg_satisfaction``: satisfacción media (o ``None`` si no hay dato).
      - ``less_crowded_count``: cuántos destinos son de baja popularidad, es
        decir, alternativas con menos gente.
      - ``eligible``: nº de destinos del ranking.
    """
    if not ranking:
        return None

    prices = [p for p in (_price(r) for r in ranking) if p is not None]
    satisfactions = [s for s in (_satisfaction(r) for r in ranking) if s is not None]
    indices = [idx for idx in (_popularity_index(r) for r in ranking) if idx is not None]
    sunny = _mean([(r.get("climate_profile") or {}).get("sunny_days") for r in ranking])

    return {
        "eligible": len(ranking),
        "from_price": min(prices) if prices else None,
        "avg_price": _mean(prices) if prices else None,
        "avg_sunny_days": sunny,
        "avg_satisfaction": _mean(satisfactions) if satisfactions else None,
        "less_crowded_count": sum(1 for idx in indices if idx <= LOW_CROWD_THRESHOLD),
    }
