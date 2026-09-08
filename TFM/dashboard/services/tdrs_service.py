from __future__ import annotations

import math
import os
from statistics import median
from typing import Any

import requests

from database.connection import db_session
from utils.text import normalize_text

# TDRS CSV v3.1
# Factores visibles: clima anual, popularidad, capacidad sanitaria y seguridad.
CSV_FACTORS = [
    ("sunny_days_pct", "% días soleados / año", "climate"),
    ("low_precipitation_pct", "% precipitación", "climate"),
    ("popularity", "Más visitado", "connectivity"),
    ("hospital_beds", "Capacidad sanitaria", "country"),
    ("safety", "Seguridad", "country"),
    # Sexto factor: satisfacción real, derivada del sentimiento de reseñas ya
    # clasificadas por el pipeline. Es la única señal del modelo que mide
    # experiencia vivida y no condiciones objetivas del destino.
    ("satisfaction", "Satisfacción de viajeros", "sentiment"),
]
FACTORS = CSV_FACTORS

# Los pesos de cada escenario están deliberadamente contrastados. Con un
# catálogo corto y unos pocos destinos fuertes en todas las señales, unos pesos
# tibios daban el mismo Top 3 en los tres escenarios y el selector no se notaba.
# Al extremar la señal dominante de cada escenario, el ranking sí cambia.
PRESETS = {
    "Popular": {
        "sunny_days_pct": 30,
        "low_precipitation_pct": 25,
        "popularity": 100,
        "hospital_beds": 20,
        "safety": 30,
        "satisfaction": 25,
        "impacto_local": 70,
        "diversificacion": 20,
        "temporada_baja": 15,
    },
    "Equilibrado": {
        "sunny_days_pct": 70,
        "low_precipitation_pct": 60,
        "popularity": 65,
        "hospital_beds": 65,
        "safety": 80,
        "satisfaction": 75,
        "impacto_local": 55,
        "diversificacion": 55,
        "temporada_baja": 55,
    },
    "Explorador": {
        "sunny_days_pct": 85,
        "low_precipitation_pct": 75,
        "popularity": 10,
        "hospital_beds": 70,
        "safety": 95,
        "satisfaction": 100,
        "impacto_local": 30,
        "diversificacion": 80,
        "temporada_baja": 85,
    },
    "Personalizado": {
        "sunny_days_pct": 60,
        "low_precipitation_pct": 60,
        "popularity": 60,
        "hospital_beds": 60,
        "safety": 60,
        "satisfaction": 60,
        "impacto_local": 60,
        "diversificacion": 60,
        "temporada_baja": 60,
    },
}

SCENARIO_META = {
    "Popular": {"icon_key": "mona_lisa", "description": "Prioriza volumen turístico y destinos con mayor popularidad."},
    "Equilibrado": {"icon_key": "roman", "description": "Combina clima, demanda, capacidad sanitaria y seguridad."},
    "Explorador": {"icon_key": "compass", "description": "Reduce el peso de popularidad y favorece señales de calidad del destino."},
    "Personalizado": {"icon_key": "custom", "description": "Permite ajustar manualmente todos los pesos del modelo."},
}

COUNTRY_ALIASES = {
    "espana": "spain",
    "grecia": "greece",
    "croacia": "croatia",
    "mexico": "mexico",
    "cabo verde": "cabo verde",
    "oceano indico": "maldives",
    "maldivas": "maldives",
}

RAW_FIELDS = [
    "sunny_days_pct",
    "precipitation_days_pct",
    "annual_passengers",
    "hospital_beds",
    "homicide_rate",
    "sentiment_score",
]


def _avg(rows: list[dict[str, Any]], field: str) -> float | None:
    vals = [float(r[field]) for r in rows if r.get(field) is not None]
    return sum(vals) / len(vals) if vals else None


def _sum(rows: list[dict[str, Any]], field: str) -> float | None:
    vals = [float(r[field]) for r in rows if r.get(field) is not None]
    return sum(vals) if vals else None


def _annual_climate(rows: list[dict[str, Any]]) -> dict[str, float | None] | None:
    if not rows:
        return None
    rain_days = _sum(rows, "rain_days")
    sunny_days_pct = None
    precipitation_days_pct = None
    if rain_days is not None:
        precipitation_days_pct = max(0.0, min(100.0, rain_days / 365.0 * 100.0))
        sunny_days_pct = max(0.0, min(100.0, 100.0 - precipitation_days_pct))
    return {
        "avg_air_temp_c": _avg(rows, "air_temp_c"),
        "annual_precipitation_mm": _sum(rows, "precipitation_mm"),
        "annual_rain_days": rain_days,
        "annual_sun_hours": _sum(rows, "sun_hours"),
        "sunny_days_pct": sunny_days_pct,
        "precipitation_days_pct": precipitation_days_pct,
        "avg_humidity_pct": _avg(rows, "humidity_pct"),
    }


def get_destination_context() -> list[dict[str, Any]]:
    """Combina destinos con las fuentes CSV y duración real cuando existe.

    El clima se agrega al año completo (ver ``_annual_climate``), por lo que el
    contexto no depende de un mes concreto.
    """
    with db_session() as conn:
        dests = [dict(r) for r in conn.execute("SELECT * FROM destinations ORDER BY name")]
        climate_rows = [dict(r) for r in conn.execute("SELECT * FROM climate_observations")]
        conn_rows = [dict(r) for r in conn.execute("SELECT * FROM connectivity_stats")]
        countries = [dict(r) for r in conn.execute("SELECT * FROM country_indicators")]
        products = [dict(r) for r in conn.execute("SELECT title,destination,duration_days,nights,price FROM products")]
        sentiment_rows = [dict(r) for r in conn.execute("SELECT * FROM destination_sentiment")]

    climate: dict[str, list[dict[str, Any]]] = {}
    for r in climate_rows:
        climate.setdefault(normalize_text(r["destination_name"]), []).append(r)

    connectivity = {normalize_text(r["destination_name"]): r for r in conn_rows}
    country_map = {normalize_text(r["country_name"]): r for r in countries}
    sentiment = {normalize_text(r["destination_name"]): r for r in sentiment_rows}

    out: list[dict[str, Any]] = []
    for d in dests:
        key = normalize_text(d["name"])
        d["climate"] = _annual_climate(climate.get(key, []))
        d["connectivity"] = connectivity.get(key)
        d["sentiment"] = sentiment.get(key)

        country_key = normalize_text(d.get("country_name"))
        alias = COUNTRY_ALIASES.get(country_key, country_key)
        d["country_indicators"] = country_map.get(country_key) or country_map.get(alias)

        matched_product = None
        for p in products:
            title_key = normalize_text(p.get("title"))
            destination_key = normalize_text(p.get("destination"))
            if key and (key in title_key or key in destination_key):
                matched_product = p
                break
        d["catalog_stay_days"] = matched_product.get("duration_days") if matched_product else None
        d["catalog_nights"] = matched_product.get("nights") if matched_product else None
        d["catalog_price_eur"] = matched_product.get("price") if matched_product else None
        out.append(d)
    return out


def _raw_feature_row(d: dict[str, Any]) -> dict[str, float | None]:
    climate = d.get("climate") or {}
    conn = d.get("connectivity") or {}
    country = d.get("country_indicators") or {}
    sentiment = d.get("sentiment") or {}
    return {
        "sunny_days_pct": climate.get("sunny_days_pct"),
        "precipitation_days_pct": climate.get("precipitation_days_pct"),
        "annual_passengers": conn.get("annual_passengers"),
        "hospital_beds": country.get("hospital_beds_per_1000"),
        "homicide_rate": country.get("homicide_rate_per_100k"),
        "sentiment_score": sentiment.get("sentiment_score"),
    }


def _scale_value(field: str, value: float, observed: list[float]) -> float:
    if field in {"annual_passengers", "homicide_rate"}:
        value = math.log1p(max(float(value), 0.0))
        observed = [math.log1p(max(float(v), 0.0)) for v in observed]
    else:
        value = float(value)
        observed = [float(v) for v in observed]
    lo, hi = min(observed), max(observed)
    return 0.5 if hi <= lo else (value - lo) / (hi - lo)


def _knn_impute(destinations: list[dict[str, Any]], k: int = 3) -> list[dict[str, Any]]:
    """Imputa faltantes del modelo con KNN y conserva trazabilidad.

    Los valores originales no se sobrescriben en SQLite. La estimación solo vive
    en el contexto del scoring y cada campo imputado queda listado en
    `knn_imputed_fields`.
    """
    raw_rows = [_raw_feature_row(d) for d in destinations]
    observed_by_field = {
        field: [float(r[field]) for r in raw_rows if r.get(field) is not None]
        for field in RAW_FIELDS
    }

    result: list[dict[str, Any]] = []
    for idx, d in enumerate(destinations):
        raw = dict(raw_rows[idx])
        estimated = dict(raw)
        imputed: list[str] = []

        for target in RAW_FIELDS:
            if estimated.get(target) is not None:
                continue
            candidates: list[tuple[float, float]] = []
            for j, candidate in enumerate(raw_rows):
                target_value = candidate.get(target)
                if target_value is None or j == idx:
                    continue

                distances: list[float] = []
                for feature in RAW_FIELDS:
                    if feature == target:
                        continue
                    a = raw.get(feature)
                    b = candidate.get(feature)
                    observed = observed_by_field.get(feature) or []
                    if a is None or b is None or len(observed) < 2:
                        continue
                    sa = _scale_value(feature, float(a), observed)
                    sb = _scale_value(feature, float(b), observed)
                    distances.append((sa - sb) ** 2)

                # Similaridad categórica como apoyo cuando hay poca cobertura.
                category_penalty = 0.0
                if d.get("country_name") and d.get("country_name") == destinations[j].get("country_name"):
                    category_penalty -= 0.20
                if d.get("zone") and d.get("zone") == destinations[j].get("zone"):
                    category_penalty -= 0.10

                base = math.sqrt(sum(distances) / len(distances)) if distances else 1.0
                distance = max(0.02, base + category_penalty)
                candidates.append((distance, float(target_value)))

            if candidates:
                nearest = sorted(candidates, key=lambda x: x[0])[: max(1, int(k))]
                weights = [1.0 / (dist + 0.05) for dist, _ in nearest]
                estimate = sum(w * val for w, (_, val) in zip(weights, nearest)) / sum(weights)
            else:
                observed = observed_by_field.get(target) or []
                estimate = float(median(observed)) if observed else None

            if estimate is not None:
                estimated[target] = estimate
                imputed.append(target)

        enriched = dict(d)
        enriched["model_raw_values"] = raw
        enriched["model_values"] = estimated
        enriched["knn_imputed_fields"] = imputed
        enriched["data_coverage"] = sum(1 for v in raw.values() if v is not None) / len(RAW_FIELDS)
        enriched["model_coverage"] = sum(1 for v in estimated.values() if v is not None) / len(RAW_FIELDS)
        result.append(enriched)
    return result


def _minmax(value: float | None, values: list[float], invert: bool = False, log_scale: bool = False) -> float | None:
    if value is None or not values:
        return None
    vals = [float(v) for v in values]
    val = float(value)
    if log_scale:
        vals = [math.log1p(max(v, 0.0)) for v in vals]
        val = math.log1p(max(val, 0.0))
    lo, hi = min(vals), max(vals)
    score = 1.0 if hi <= lo else (val - lo) / (hi - lo)
    score = max(0.0, min(1.0, score))
    return 1.0 - score if invert else score


def _model_ranges(destinations: list[dict[str, Any]]) -> dict[str, list[float]]:
    return {
        field: [float(d["model_values"][field]) for d in destinations if d["model_values"].get(field) is not None]
        for field in RAW_FIELDS
    }


def csv_factor_values(d: dict[str, Any], ranges: dict[str, list[float]]) -> dict[str, float | None]:
    model = d.get("model_values") or _raw_feature_row(d)
    return {
        "sunny_days_pct": _minmax(model.get("sunny_days_pct"), ranges["sunny_days_pct"]),
        "low_precipitation_pct": _minmax(model.get("precipitation_days_pct"), ranges["precipitation_days_pct"], invert=True),
        "popularity": _minmax(model.get("annual_passengers"), ranges["annual_passengers"], log_scale=True),
        "hospital_beds": _minmax(model.get("hospital_beds"), ranges["hospital_beds"]),
        "safety": _minmax(model.get("homicide_rate"), ranges["homicide_rate"], invert=True, log_scale=True),
        "satisfaction": _minmax(model.get("sentiment_score"), ranges["sentiment_score"]),
    }


TUI_MODELO_API_BASE = os.getenv("TUI_MODELO_API_BASE", "http://localhost:8000")

_MAPEO_PESOS = {
    "sunny_days_pct": "sunny_days_pct",
    "low_precipitation_pct": "dry_months_pct",
    "popularity": "popularity",
    "hospital_beds": "hospital_beds",
    "safety": "safety",
    "satisfaction": "satisfaction",
    "impacto_local": "impacto_local",
    "diversificacion": "diversificacion",
    "temporada_baja": "temporada_baja",
}

_CAMPOS_COBERTURA = [
    "sunny_days_pct", "precipitation_days_pct", "annual_passengers",
    "hospital_beds", "homicide_rate", "sentiment_score",
]


def compute_scores(
    weights: dict[str, float],
    max_price: float | None = None,
    max_stay_days: int | None = None,
) -> dict[str, Any]:
    """Ranquea los 39 destinos reales llamando al modelo real (embeddings +
    LightGBM + TDRS con datos reales de Eurostat/INE, AENA, Open-Meteo,
    sentimiento XLM-RoBERTa), en vez de la reimplementacion local anterior
    con datos propios del dashboard.

    NOTA (fix de integracion): 'max_stay_days' ya no filtra nada -- el dato
    de "dias hospedados" (estancia media real) resulto tener valores
    fisicamente imposibles en la fuente INE (menos de 1 noche promedio) y
    quedo desactivado en el modelo hasta investigar la extraccion original.
    """
    pesos_api = {
        _MAPEO_PESOS[clave]: valor
        for clave, valor in weights.items()
        if clave in _MAPEO_PESOS
    }

    if sum(max(0.0, v) for v in pesos_api.values()) <= 0:
        return {
            "ranked": [], "excluded": [],
            "factor_model": "Ajusta al menos un criterio para generar un ranking",
            "max_price": max_price, "max_stay_days": max_stay_days,
            "imputation_method": "Sin pesos activos",
        }

    try:
        resp = requests.post(
            f"{TUI_MODELO_API_BASE}/tdrs_ranking",
            json={"weights": pesos_api, "max_price": max_price},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {
            "ranked": [], "excluded": [],
            "factor_model": "Error de conexion con el modelo real",
            "max_price": max_price, "max_stay_days": max_stay_days,
            "imputation_method": f"API no disponible: {exc}",
        }

    ranked: list[dict[str, Any]] = []
    for item in data.get("ranked", []):
        dh = item.get("datos_humanos") or {}
        model_values = {
            "sunny_days_pct": dh.get("dias_soleados_pct"),
            "precipitation_days_pct": dh.get("precipitacion_pct"),
            "annual_passengers": dh.get("pasajeros_anuales"),
            "hospital_beds": dh.get("camas_hospital_1000hab"),
            "homicide_rate": dh.get("tasa_homicidios_100mil"),
            "sentiment_score": dh.get("sentimiento_real"),
        }
        cobertura = sum(1 for c in _CAMPOS_COBERTURA if model_values.get(c) is not None)
        ranked.append({
            "name": item["destino_nombre"],
            "score": item["score"],
            "reference_price_eur": item.get("precio_referencia_eur"),
            "model_values": model_values,
            "model_raw_values": {"sentiment_score": dh.get("sentimiento_real")},
            "data_coverage": cobertura / len(_CAMPOS_COBERTURA),
            "contributions": item.get("contribuciones", []),
        })

    excluded = [
        {"name": e["destino_nombre"], "excluded_by": e.get("excluded_by", [])}
        for e in data.get("excluded", [])
    ]

    return {
        "ranked": ranked,
        "excluded": excluded,
        "factor_model": "Modelo real TUI (embeddings + LightGBM + TDRS, datos reales)",
        "max_price": max_price,
        "max_stay_days": max_stay_days,
        "imputation_method": "Sin imputacion: valores ausentes se muestran como tal, no se estiman",
    }


def gini(values: list[float]) -> float:
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


def scenario_metrics(ranked: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not ranked:
        return None
    top5 = ranked[:5]

    def model(field: str) -> list[float | None]:
        return [(r.get("model_values") or {}).get(field) for r in top5]

    return {
        "eligible": len(ranked),
        "avg_data_coverage": _mean([r.get("data_coverage") for r in ranked]),
        "avg_top5_sunny_days_pct": _mean(model("sunny_days_pct")),
        "avg_top5_precipitation_days_pct": _mean(model("precipitation_days_pct")),
        "avg_top5_annual_passengers": _mean(model("annual_passengers")),
        "avg_top5_hospital_beds": _mean(model("hospital_beds")),
        "avg_top5_homicide_rate": _mean(model("homicide_rate")),
        "avg_top5_sentiment": _mean(model("sentiment_score")),
        # Cuántos del Top 5 tienen sentimiento real y no estimado por KNN.
        "top5_sentiment_real": sum(
            1 for r in top5
            if (r.get("model_raw_values") or {}).get("sentiment_score") is not None
        ),
    }
