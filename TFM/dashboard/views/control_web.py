from __future__ import annotations

"""Vista Control Web: KPIs comerciales, mapa geoespacial e instrumentación."""

import json
from pathlib import Path

import pandas as pd
import streamlit as st
from matplotlib import pyplot as plt

from components.ui import render_metric_rows, render_system_alerts
from services.analytics_service import (
    get_dashboard_metrics,
    get_destination_metrics,
    instrumentation_status,
)
from services.geospatial_service import get_geospatial_metrics, metric_value

WORLD_GEOJSON = Path(__file__).resolve().parents[1] / "data" / "world_lowres.geojson"

GEO_METRICS = ("Clics", "Reservas", "Ingresos")


def _draw_world_polygons(ax) -> None:
    if not WORLD_GEOJSON.exists():
        return
    try:
        world = json.loads(WORLD_GEOJSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    for feature in world.get("features", []):
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") or []
        polygons = coords if geometry.get("type") == "MultiPolygon" else [coords]
        for polygon in polygons:
            if not polygon:
                continue
            ring = polygon[0]
            if len(ring) < 3:
                continue
            xs = [pt[0] for pt in ring]
            ys = [pt[1] for pt in ring]
            ax.fill(xs, ys, facecolor="#F4FBFE", edgecolor="#C5E6F4", linewidth=.45, zorder=1)


def render_geospatial_map(rows: list[dict], metric: str) -> None:
    if not rows:
        st.info("No hay destinos geolocalizados disponibles para el mapa.")
        return
    values = [metric_value(r, metric) for r in rows]
    max_value = max(values) if values else 0
    active = [r for r in rows if metric_value(r, metric) > 0]
    focus = active if active else rows

    fig, ax = plt.subplots(figsize=(10.5, 5.4))
    _draw_world_polygons(ax)
    for row in rows:
        value = metric_value(row, metric)
        size = 34 if max_value <= 0 else 38 + 300 * ((value / max_value) ** 0.55)
        point_color = "#D40E14" if value > 0 else "#AEE8FF"
        ax.scatter(
            row["longitude"], row["latitude"], s=size, color=point_color,
            edgecolor="#FFFFFF", linewidth=1.0, alpha=.88, zorder=3,
        )
        if value > 0 or len(rows) <= 18:
            label_value = f"{value:,.0f}" if metric != "Ingresos" else f"{value:,.0f} €"
            ax.annotate(
                f"{row['destination']}\n{label_value}",
                (row["longitude"], row["latitude"]),
                xytext=(4, 5), textcoords="offset points",
                fontsize=7, color="#0E2642", zorder=4,
            )

    lons = [r["longitude"] for r in focus]
    lats = [r["latitude"] for r in focus]
    if lons and lats:
        lon_margin = max(6.0, (max(lons) - min(lons)) * .18)
        lat_margin = max(5.0, (max(lats) - min(lats)) * .22)
        ax.set_xlim(max(-180, min(lons) - lon_margin), min(180, max(lons) + lon_margin))
        ax.set_ylim(max(-60, min(lats) - lat_margin), min(85, max(lats) + lat_margin))
    ax.set_facecolor("#FFFFFF")
    ax.grid(True, color="#E7F4F9", linewidth=.5, alpha=.65)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.tight_layout(pad=.3)
    st.pyplot(fig, width="stretch")
    plt.close(fig)


def render_control_web() -> None:
    render_system_alerts("Alertas de sistema")
    m = get_dashboard_metrics()
    render_metric_rows([
        ("Sesiones", m["sessions"]),
        ("Clics", m["clicks"]),
        ("Reservas", m["bookings"]),
        ("Ingresos", f"{m['revenue_eur']:,.0f} €"),
        ("Cancelaciones", m["cancellations"]),
        ("ROI", f"{m['roi']:.1%}" if m.get("roi") is not None else "Pendiente"),
    ], columns=3)

    left, right = st.columns([1.45, 1], gap="large")
    with left:
        st.markdown("### Mapa geoespacial")
        if "geo_metric_selected" not in st.session_state:
            st.session_state.geo_metric_selected = "Clics"
        metric = st.session_state.geo_metric_selected
        metric_cols = st.columns(3, gap="small")
        for idx, label in enumerate(GEO_METRICS):
            clicked = metric_cols[idx].button(
                label,
                key=f"geo_metric_button_{label}",
                width="stretch",
                type="primary" if metric == label else "secondary",
            )
            if clicked and metric != label:
                st.session_state.geo_metric_selected = label
                st.rerun()
        geo_rows = get_geospatial_metrics()
        render_geospatial_map(geo_rows, metric)
    with right:
        st.markdown("### Estado de instrumentación")
        st.dataframe(
            pd.DataFrame(instrumentation_status()),
            width="stretch", hide_index=True, height=300,
        )

    st.markdown("### Rendimiento por destino")
    destinations = pd.DataFrame(get_destination_metrics())
    if destinations.empty:
        st.info("Todavía no hay interacción por destino suficiente para construir esta tabla.")
    else:
        st.dataframe(destinations, width="stretch", hide_index=True)
