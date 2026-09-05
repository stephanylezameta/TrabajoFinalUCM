from __future__ import annotations

import math
from statistics import median
from typing import Any

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

PRESETS = {
    "Popular": {
        "sunny_days_pct": 45,
        "low_precipitation_pct": 35,
        "popularity": 100,
        "hospital_beds": 35,
        "safety": 45,
        # Popular prioriza volumen: la satisfacción pesa poco a propósito, y es
        # justo el escenario donde se ve la tensión con destinos saturados.
        "satisfaction": 40,
    },
    "Equilibrado": {
        "sunny_days_pct": 70,
        "low_precipitation_pct": 60,
        "popularity": 75,
        "hospital_beds": 65,
        "safety": 80,
        "satisfaction": 70,
    },
    "Explorador": {
        "sunny_days_pct": 80,
        "low_precipitation_pct": 70,
        "popularity": 30,
        "hospital_beds": 75,
        "safety": 90,
        # Explorador busca calidad del destino frente a masificación: la
        # satisfacción real es su señal más pertinente.
        "satisfaction": 95,
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


def compute_scores(
    weights: dict[str, float],
    max_price: float | None = None,
    max_stay_days: int | None = None,
) -> dict[str, Any]:
    """Ranquea los destinos aplicando pesos y restricciones.

    Las restricciones solo excluyen cuando el dato existe: un precio o una
    duración desconocidos no descartan el destino.
    """
    destinations = _knn_impute(get_destination_context(), k=3)
    ranges = _model_ranges(destinations)
    ranked: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for d in destinations:
        reasons: list[str] = []
        price = d.get("reference_price_eur")
        stay_days = d.get("catalog_stay_days")
        if max_price is not None and price is not None and float(price) > float(max_price):
            reasons.append("precio")
        if max_stay_days is not None and stay_days is not None and int(stay_days) > int(max_stay_days):
            reasons.append("días hospedados")
        if reasons:
            excluded.append({**d, "excluded_by": reasons})
            continue

        factor_values = csv_factor_values(d, ranges)
        total_weight = sum(max(0.0, float(weights.get(key, 0))) for key, _, _ in CSV_FACTORS)
        score = 0.0
        contributions: list[dict[str, Any]] = []
        for key, label, source in CSV_FACTORS:
            value = factor_values.get(key)
            weight = max(0.0, float(weights.get(key, 0)))
            contribution = (weight / total_weight) * float(value) if value is not None and total_weight > 0 else 0.0
            score += contribution
            contributions.append({
                "factor": key,
                "label": label,
                "source": source,
                "weight": weight,
                "value": value,
                "contribution": contribution,
            })
        contributions.sort(key=lambda x: x["contribution"], reverse=True)
        ranked.append({
            **d,
            "score": score,
            "csv_factor_values": factor_values,
            "contributions": contributions,
        })

    ranked.sort(key=lambda x: (-x["score"], -x["data_coverage"], x["name"]))
    return {
        "ranked": ranked,
        "excluded": excluded,
        "factor_model": "TDRS CSV v3.2 · 6 señales · KNN",
        "max_price": max_price,
        "max_stay_days": max_stay_days,
        "imputation_method": "KNN k=3 sobre señales CSV; los campos imputados se marcan en la salida",
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
