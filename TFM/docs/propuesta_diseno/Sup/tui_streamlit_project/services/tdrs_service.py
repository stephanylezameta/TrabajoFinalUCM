from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from database.connection import db_session
from utils.text import normalize_text

FACTORS = [
    ("affinity", "Afinidad con el perfil", False),
    ("demand", "Demanda histórica", False),
    ("occupancy", "Capacidad disponible", True),
    ("local_impact", "Impacto en economía local", False),
    ("seasonality", "Temporada y clima", False),
    ("accessibility", "Accesibilidad", False),
    ("sustainability", "Sostenibilidad", False),
]

PRESETS = {
    "Popular": {"affinity": 40, "demand": 100, "occupancy": 0, "local_impact": 0, "seasonality": 20, "accessibility": 30, "sustainability": 0},
    "Equilibrado": {"affinity": 85, "demand": 75, "occupancy": 60, "local_impact": 50, "seasonality": 60, "accessibility": 50, "sustainability": 55},
    "Explorador": {"affinity": 75, "demand": 20, "occupancy": 95, "local_impact": 90, "seasonality": 55, "accessibility": 35, "sustainability": 85},
}


def get_destination_context(target_month: int = 11) -> list[dict[str, Any]]:
    with db_session() as conn:
        dests = [dict(r) for r in conn.execute("SELECT * FROM destinations ORDER BY name")]
        climate_rows = [dict(r) for r in conn.execute("SELECT * FROM climate_observations WHERE CAST(substr(year_month,6,2) AS INTEGER)=?", (target_month,))]
        conn_rows = [dict(r) for r in conn.execute("SELECT * FROM connectivity_stats")]
        countries = [dict(r) for r in conn.execute("SELECT * FROM country_indicators")]
    climate = {}
    for r in climate_rows:
        climate.setdefault(normalize_text(r["destination_name"]), []).append(r)
    connectivity = {normalize_text(r["destination_name"]): r for r in conn_rows}
    country_map = {normalize_text(r["country_name"]): r for r in countries}
    aliases = {"espana": "spain", "mexico": "mexico", "croacia": "croatia", "portugal": "portugal", "grecia": "greece", "cabo verde": "cabo verde"}

    out = []
    for d in dests:
        key = normalize_text(d["name"])
        cands = climate.get(key, [])
        if cands:
            def avg(k):
                vals = [float(x[k]) for x in cands if x.get(k) is not None]
                return sum(vals) / len(vals) if vals else None
            d["climate"] = {k: avg(k) for k in ["air_temp_c","water_temp_c","precipitation_mm","rain_days","sun_hours","humidity_pct"]}
        else:
            d["climate"] = None
        d["connectivity"] = connectivity.get(key)
        country_key = normalize_text(d.get("country_name"))
        d["country_indicators"] = country_map.get(country_key) or country_map.get(aliases.get(country_key, ""))
        out.append(d)
    return out


def compute_scores(weights: dict[str, float], max_price: float | None = None, max_occupancy_pct: float | None = None,
                   target_month: int = 11) -> dict[str, Any]:
    destinations = get_destination_context(target_month=target_month)
    total_weight = sum(max(0.0, float(weights.get(k, 0))) for k, _, _ in FACTORS)
    ranked, excluded = [], []
    for d in destinations:
        price = d.get("reference_price_eur")
        occupancy = d.get("occupancy")
        reasons = []
        if max_price is not None and price is not None and price > max_price:
            reasons.append("precio")
        if max_occupancy_pct is not None and occupancy is not None and occupancy * 100 > max_occupancy_pct:
            reasons.append("ocupación")
        if reasons:
            excluded.append({**d, "excluded_by": reasons})
            continue
        score = 0.0
        contributions = []
        for key, label, inverted in FACTORS:
            raw = d.get(key)
            if raw is None:
                value = 0.0
            else:
                value = 1.0 - float(raw) if inverted else float(raw)
            w = max(0.0, float(weights.get(key, 0)))
            contrib = (w / total_weight) * value if total_weight else 0.0
            score += contrib
            contributions.append({"factor": key, "label": label, "weight": w, "value": value, "contribution": contrib})
        contributions.sort(key=lambda x: x["contribution"], reverse=True)
        ranked.append({**d, "score": score, "contributions": contributions})
    ranked.sort(key=lambda x: (-x["score"], x["name"]))
    return {"ranked": ranked, "excluded": excluded, "total_weight": total_weight}


def gini(values: list[float]) -> float:
    vals = sorted(max(0.0, float(v)) for v in values)
    n = len(vals)
    total = sum(vals)
    if n == 0 or total == 0:
        return 0.0
    cum = sum((i + 1) * v for i, v in enumerate(vals))
    return (2 * cum) / (n * total) - (n + 1) / n


def scenario_metrics(ranked: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not ranked:
        return None
    exps = [math.exp(r["score"] * 9) for r in ranked]
    s = sum(exps)
    shares = [e / s for e in exps]
    pressure = sum(sh for r, sh in zip(ranked, shares) if (r.get("occupancy") or 0) > .75)
    emerging = sum(sh for r, sh in zip(ranked, shares) if (r.get("demand") or 0) < .35)
    top5 = ranked[:5]
    curve = [1, .55, .35, .22, .14]
    den = sum(curve[:len(top5)])
    weighted_demand = sum((r.get("demand") or 0) * curve[i] for i, r in enumerate(top5))
    ctr = 8.759 + 7.681 * (weighted_demand / den) if den else None
    zones = sorted({r.get("zone") for r in ranked if r.get("zone")})
    by_zone = [sum(sh for r, sh in zip(ranked, shares) if r.get("zone") == z) for z in zones]
    def mean(field):
        vals = [float(r[field]) for r in top5 if r.get(field) is not None]
        return sum(vals) / len(vals) if vals else None
    return {
        "pressure": pressure, "emerging_share": emerging, "estimated_ctr_pct": ctr,
        "saturated_top5": sum(1 for r in top5 if (r.get("occupancy") or 0) > .75),
        "territorial_balance": 1 - gini(by_zone), "avg_top5_price_eur": mean("reference_price_eur"),
        "avg_top5_co2_kg": mean("co2_kg"), "eligible": len(ranked),
    }
