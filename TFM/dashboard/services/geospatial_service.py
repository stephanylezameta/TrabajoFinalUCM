from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from config import DATA_DIR
from services.analytics_service import get_destination_metrics
from utils.text import normalize_text

COORDINATES_PATH = DATA_DIR / "destination_coordinates.csv"

ALIASES = {
    "espana islas baleares": "mallorca",
    "islas baleares": "mallorca",
    "croacia dalmacia": "split",
    "dalmacia": "split",
    "portugal algarve": "algarve",
    "oceano indico male": "maldivas",
    "grecia creta": "creta",
}


def _load_coordinates() -> pd.DataFrame:
    if not COORDINATES_PATH.exists():
        return pd.DataFrame(columns=["destination", "latitude", "longitude", "display_name", "coordinate_source"])
    return pd.read_csv(COORDINATES_PATH)


def _match_coordinate_key(name: str, available: dict[str, dict[str, Any]]) -> str | None:
    key = normalize_text(name)
    key = ALIASES.get(key, key)
    if key in available:
        return key
    for alias, target in ALIASES.items():
        if alias in key and target in available:
            return target
    # Fallback conservador por inclusión de nombre, sin inventar coordenadas.
    for candidate in available:
        if candidate and (candidate in key or key in candidate):
            return candidate
    return None


def get_geospatial_metrics() -> list[dict[str, Any]]:
    """Une métricas reales de tracking con coordenadas de referencia del prototipo.

    Las métricas proceden de events/bookings. Las coordenadas se leen de un CSV
    explícito y trazable; no se derivan ni se inventan a partir del nombre.
    """
    coords_df = _load_coordinates()
    coord_map = {
        normalize_text(row["destination"]): row.to_dict()
        for _, row in coords_df.iterrows()
    }

    metrics = get_destination_metrics()
    aggregated: dict[str, dict[str, Any]] = {}
    for row in metrics:
        destination = row.get("destination") or ""
        key = _match_coordinate_key(destination, coord_map)
        if not key:
            continue
        target = aggregated.setdefault(
            key,
            {
                "destination": coord_map[key]["display_name"],
                "latitude": float(coord_map[key]["latitude"]),
                "longitude": float(coord_map[key]["longitude"]),
                "coordinate_source": coord_map[key]["coordinate_source"],
                "impressions": 0,
                "clicks": 0,
                "detail_views": 0,
                "bookings": 0,
                "revenue_eur": 0.0,
            },
        )
        for field in ("impressions", "clicks", "detail_views", "bookings"):
            target[field] += int(row.get(field) or 0)
        target["revenue_eur"] += float(row.get("revenue_eur") or 0.0)

    # Para que el mapa siga siendo un mapa cuando todavía no hay tracking con
    # destino, añadimos los destinos de referencia con intensidad 0. Esto no
    # inventa interacción: los valores comerciales siguen siendo cero.
    if not aggregated:
        for key, coord in coord_map.items():
            aggregated[key] = {
                "destination": coord["display_name"],
                "latitude": float(coord["latitude"]),
                "longitude": float(coord["longitude"]),
                "coordinate_source": coord["coordinate_source"],
                "impressions": 0,
                "clicks": 0,
                "detail_views": 0,
                "bookings": 0,
                "revenue_eur": 0.0,
            }

    return sorted(aggregated.values(), key=lambda r: (-r["clicks"], -r["bookings"], r["destination"]))


def get_unmapped_destinations() -> list[dict[str, Any]]:
    """Destinos con interacción registrada que no tienen coordenada asignada.

    ``get_geospatial_metrics`` los descarta para no inventar una posición, pero
    descartarlos en silencio deja el mapa incompleto sin que nadie se entere.
    Esta función expone la omisión para que la interfaz pueda declararla, en
    coherencia con la regla de trazabilidad del proyecto.
    """
    coord_map = {
        normalize_text(row["destination"]): row.to_dict()
        for _, row in _load_coordinates().iterrows()
    }
    unmapped: dict[str, dict[str, Any]] = {}
    for row in get_destination_metrics():
        destination = row.get("destination") or ""
        if not destination or destination == "Sin destino":
            continue
        if _match_coordinate_key(destination, coord_map):
            continue
        entry = unmapped.setdefault(destination, {
            "destination": destination,
            "clicks": 0,
            "bookings": 0,
            "revenue_eur": 0.0,
        })
        entry["clicks"] += int(row.get("clicks") or 0)
        entry["bookings"] += int(row.get("bookings") or 0)
        entry["revenue_eur"] += float(row.get("revenue_eur") or 0.0)
    return sorted(unmapped.values(), key=lambda r: (-r["clicks"], r["destination"]))


def coordinate_coverage() -> dict[str, Any]:
    """Resumen de cobertura del fichero de coordenadas."""
    coords = _load_coordinates()
    unmapped = get_unmapped_destinations()
    return {
        "coordinates_available": int(len(coords)),
        "unmapped_destinations": len(unmapped),
        "unmapped_names": [row["destination"] for row in unmapped],
        "source_path": str(COORDINATES_PATH),
    }


def metric_value(row: dict[str, Any], metric: str) -> float:
    if metric == "Reservas":
        return float(row.get("bookings") or 0)
    if metric == "Ingresos":
        return float(row.get("revenue_eur") or 0)
    return float(row.get("clicks") or 0)
