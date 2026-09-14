from __future__ import annotations

"""Vista «Monitor performance»: panel de analítica turística.

Un único panel accionable que responde de un vistazo: cuántos usuarios hay, qué
recomendaciones funcionan, qué destinos generan más interés, dónde se concentra
ese interés en el mapa, qué destinos crecen, dónde hay saturación y qué
alternativas permiten redistribuir el flujo.

Todas las métricas salen de eventos REALES (``services/performance_analytics``).
Cuando un dato no está instrumentado, se declara «Sin datos suficientes» en vez
de inventarlo. No se toca la lógica de recomendación, los filtros de «Explora»
ni el resto de vistas.
"""

import json
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from services import performance_analytics as pa
from services import spain_reference
from services.analytics_service import get_dashboard_metrics, instrumentation_status

WORLD_GEOJSON = Path(__file__).resolve().parents[1] / "data" / "world_lowres.geojson"

# Acentos de marca reutilizados en el panel.
TUI_RED = "#D40E14"
TUI_DARK = "#111827"
MUTED = "#667085"

# Criterios de ordenación del ranking de destinos.
RANK_CRITERIA = {
    "Clics": "clicks",
    "CTR": "ctr",
}

# Meses abreviados en español para las etiquetas del eje temporal.
MESES_ABREV = (
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
)

# Colores de las series del gráfico de seguimiento (pocos, coherentes con TUI).
SERIE_COLORS = {
    "Recomendaciones": "#1B115C",
    "Impresiones": "#4B9CD3",
    "Clics": TUI_RED,
}


def _fecha_label(ts, monthly: bool) -> str:
    """Etiqueta de fecha en español: ``14-ene`` por día, ``ene-26`` por mes."""
    mes = MESES_ABREV[ts.month - 1]
    if monthly:
        return f"{mes}-{ts.strftime('%y')}"
    return f"{ts.day:02d}-{mes}"


# --------------------------------------------------------------------------
# Formato
# --------------------------------------------------------------------------

def _fmt_int(value) -> str:
    if value is None:
        return "—"
    return f"{int(value):,}".replace(",", ".")


def _fmt_pct(value, decimals: int = 1) -> str:
    """``value`` es una fracción 0–1; se muestra como porcentaje."""
    if value is None:
        return "—"
    return f"{value * 100:.{decimals}f}%".replace(".", ",")


def _fmt_ratio(value, decimals: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:.{decimals}f}".replace(".", ",")


def _delta_html(delta: dict, *, is_pct_metric: bool = False) -> str:
    """Chip de variación vs. periodo anterior. Vacío si no es calculable."""
    if not delta or delta.get("abs") is None:
        return '<div class="mp-kpi-foot">Sin periodo anterior para comparar</div>'
    diff = delta["abs"]
    pct = delta.get("pct")
    if abs(diff) < 1e-9:
        cls, arrow = "mp-delta-flat", "="
    elif diff > 0:
        cls, arrow = "mp-delta-up", "▲"
    else:
        cls, arrow = "mp-delta-down", "▼"
    if pct is None:
        txt = f"{arrow} {'+' if diff > 0 else ''}{_fmt_ratio(diff)} vs. periodo anterior"
    else:
        txt = f"{arrow} {'+' if pct > 0 else ''}{pct:.1f}% vs. periodo anterior".replace(".", ",")
    return f'<div class="mp-kpi-delta {cls}">{escape(txt)}</div>'


def _kpi_card(label: str, kpi: dict, *, kind: str = "int") -> str:
    """Tarjeta de KPI con valor, variación y estado.

    ``kind``: int | pct | ratio | text. Si el KPI no está disponible, muestra
    «Sin datos suficientes» y la nota de instrumentación.
    """
    available = kpi.get("available", True)
    value = kpi.get("value")
    if not available or value is None:
        note = kpi.get("note") or "Sin datos suficientes"
        return (
            f'<div class="mp-kpi"><div class="mp-kpi-label">{escape(label)}</div>'
            f'<div class="mp-kpi-value mp-muted">Sin datos</div>'
            f'<div class="mp-kpi-na">{escape(note)}</div></div>'
        )
    if kind == "pct":
        shown = _fmt_pct(value)
    elif kind == "ratio":
        shown = _fmt_ratio(value)
    elif kind == "text":
        shown = str(value)
    else:
        shown = _fmt_int(value)
    delta_html = _delta_html(kpi.get("delta") or {})
    return (
        f'<div class="mp-kpi"><div class="mp-kpi-label">{escape(label)}</div>'
        f'<div class="mp-kpi-value">{escape(shown)}</div>{delta_html}</div>'
    )


def _section(title: str, subtitle: str = "") -> None:
    sub = f'<div class="mp-section-sub">{escape(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f'<div class="mp-section"><div class="mp-section-title">{escape(title)}</div>{sub}</div>',
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------
# Mapa de interés de España
# --------------------------------------------------------------------------

def _spain_polygons(ax) -> None:
    """Dibuja el contorno de los países (recortado luego a España) como fondo."""
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
            ax.fill(xs, ys, facecolor="#F4F7FA", edgecolor="#D8DEE6", linewidth=.5, zorder=1)


def render_spain_map(points: list[dict], metric_label: str = "Clics") -> None:
    """Mapa de España con intensidad de interés por destino.

    El tamaño y el color de cada punto escalan con el interés (clics, o
    impresiones si aún no hay clics). Más interés → punto mayor y más intenso.
    Responde a «¿dónde están haciendo clic los usuarios?»: solo dibuja destinos
    con interacción real; si no hay ninguno, lo declara.
    """
    active = [p for p in points if (p.get("clicks") or 0) > 0 or (p.get("impressions") or 0) > 0]
    if not active:
        st.info("Sin datos suficientes: todavía no hay interacción por destino en España para el periodo seleccionado.")
        return

    # Métrica de intensidad: clics si existen; si no, impresiones.
    use_clicks = any((p.get("clicks") or 0) > 0 for p in active)
    intensity_key = "clicks" if use_clicks else "impressions"
    intensity_name = "clics" if use_clicks else "impresiones"
    values = [p[intensity_key] for p in active]
    max_value = max(values) if values else 0

    cmap = LinearSegmentedColormap.from_list("tui_interest", ["#FBD5D6", "#E8595E", TUI_RED, "#8E0A0E"])

    fig, ax = plt.subplots(figsize=(9.6, 6.6))
    _spain_polygons(ax)

    for p in active:
        value = p[intensity_key]
        frac = (value / max_value) if max_value else 0
        size = 90 + 900 * (frac ** 0.6)
        color = cmap(0.25 + 0.75 * frac)
        ax.scatter(
            p["lon"], p["lat"], s=size, color=color,
            edgecolor="#FFFFFF", linewidth=1.1, alpha=.92, zorder=3,
        )
        ax.annotate(
            f"{p['destination']}\n{_fmt_int(value)}",
            (p["lon"], p["lat"]),
            xytext=(6, 6), textcoords="offset points",
            fontsize=7.5, color=TUI_DARK, fontweight="bold", zorder=4,
        )

    # Encuadre en la España peninsular + Canarias, con margen.
    ax.set_xlim(-19.0, 5.5)
    ax.set_ylim(26.5, 44.5)
    ax.set_facecolor("#FFFFFF")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Leyenda de intensidad discreta (barra de color) sin recargar.
    sm = plt.cm.ScalarMappable(cmap=cmap)
    sm.set_array([0, max_value])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.01)
    cbar.set_label(f"Intensidad de interés ({intensity_name})", fontsize=8, color=MUTED)
    cbar.ax.tick_params(labelsize=7, colors=MUTED)

    fig.tight_layout(pad=.4)
    st.pyplot(fig, width="stretch")
    plt.close(fig)


# --------------------------------------------------------------------------
# Filtros del panel
# --------------------------------------------------------------------------

def _render_filters() -> tuple[pa.Period, pa.Filters]:
    """Barra de filtros: periodo, destino, comunidad autónoma y tipo.

    Devuelve la ventana temporal resuelta y los filtros de destino. Afectan de
    forma coherente a todas las métricas y gráficos del panel.
    """
    bounds = pa.data_bounds()
    with st.container():
        c1, c2, c3, c4 = st.columns([1.1, 1, 1, 1], gap="small")
        preset = c1.selectbox("Periodo", pa.PERIOD_PRESETS, index=1, key="mp_period")

        dest_options = ["Todos"] + list(spain_reference.SPAIN_DESTINATIONS.keys())
        destination = c2.selectbox("Destino", dest_options, index=0, key="mp_destination")

        comm_options = ["Todas"] + spain_reference.community_options()
        community = c3.selectbox("Comunidad autónoma", comm_options, index=0, key="mp_community")

        type_options = ["Todos"] + spain_reference.type_options()
        dest_type = c4.selectbox("Tipo de destino", type_options, index=0, key="mp_type")

        custom_start = custom_end = None
        if preset == pa.PERIOD_ALL and bounds.get("min"):
            st.caption(
                f"Histórico disponible: {bounds['min'].isoformat()} → {bounds['max'].isoformat()}."
            )

    period = pa.resolve_period(preset, custom_start=custom_start, custom_end=custom_end)
    filters = pa.Filters(
        destination=destination if destination != "Todos" else None,
        community=community if community != "Todas" else None,
        dest_type=dest_type if dest_type != "Todos" else None,
    )
    return period, filters


# --------------------------------------------------------------------------
# Bloques del panel
# --------------------------------------------------------------------------

def _render_kpis(period: pa.Period, filters: pa.Filters) -> dict:
    kpis = pa.get_kpis(period, filters)
    cards = [
        _kpi_card("Sesiones activas", kpis["active_sessions"]),
        _kpi_card("Sesiones iniciadas", kpis["sessions_started"]),
        _kpi_card("Recomendaciones", kpis["recommendations"]),
        _kpi_card("Impresiones", kpis["impressions"]),
        _kpi_card("Clics", kpis["clicks"]),
        _kpi_card("CTR", kpis["ctr"], kind="pct"),
        _kpi_card("Destinos consultados", kpis["destinations_seen"]),
    ]
    st.markdown('<div class="mp-kpi-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)

    top = kpis.get("top_destination") or {}
    if top.get("available"):
        st.markdown(
            f'<div class="mp-note">Destino más clicado: '
            f'<strong>{escape(str(top["value"]))}</strong> · {_fmt_int(top["clicks"])} clics.</div>',
            unsafe_allow_html=True,
        )
    return kpis


def _render_evolution(period: pa.Period, filters: pa.Filters) -> None:
    series = pa.get_timeseries(period, filters)
    if not series:
        st.info("Sin datos suficientes para la evolución temporal.")
        return
    df = pd.DataFrame(series)
    df["fecha"] = pd.to_datetime(df["day"])

    # Con rangos amplios el eje diario se satura: a partir de ~45 días se
    # agrupa por mes y las etiquetas pasan a «ene-26». Así el usuario puede
    # «alejar» el periodo sin que las fechas se amontonen.
    monthly = len(df) > 45
    if monthly:
        grp = df.set_index("fecha").resample("MS").agg({
            "requests": "sum", "impressions": "sum", "clicks": "sum", "sessions": "sum",
        }).reset_index()
        grp["ctr"] = grp.apply(
            lambda r: (r["clicks"] / r["impressions"] * 100) if r["impressions"] else None,
            axis=1,
        )
        plot_df = grp
    else:
        plot_df = df

    labels = [_fecha_label(ts, monthly) for ts in plot_df["fecha"]]
    unidad = "mes" if monthly else "día"

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.caption(f"Recomendaciones, impresiones y clics por {unidad}")
        _line_chart(
            labels,
            {
                "Recomendaciones": list(plot_df["requests"]),
                "Impresiones": list(plot_df["impressions"]),
                "Clics": list(plot_df["clicks"]),
            },
        )
    with c2:
        st.caption(f"Sesiones activas por {unidad}")
        _bar_chart(labels, list(plot_df["sessions"]))


def _style_time_axis(ax, labels: list[str]) -> None:
    """Estilo común de los gráficos de seguimiento: sin cuadrícula interna,
    fondo limpio, solo el eje inferior visible y etiquetas de fecha rotadas
    lo justo para que encajen dentro del cuadro."""
    ax.set_facecolor("#FFFFFF")
    ax.grid(False)
    ax.tick_params(labelsize=7.5, colors=MUTED, length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#E7EBF0")
    # Limita el número de etiquetas para que no se solapen (máx ~12 visibles).
    n = len(labels)
    step = max(1, n // 12)
    ticks = list(range(0, n, step))
    if (n - 1) not in ticks:
        ticks.append(n - 1)
    ax.set_xticks(ticks)
    ax.set_xticklabels([labels[i] for i in ticks], rotation=0, ha="center")


def _line_chart(labels: list[str], series: dict[str, list], height: float = 2.6) -> None:
    x = list(range(len(labels)))
    fig, ax = plt.subplots(figsize=(6.4, height))
    for name, values in series.items():
        ax.plot(x, values, marker="o", markersize=3.2, linewidth=2,
                color=SERIE_COLORS.get(name, TUI_RED), label=name)
    _style_time_axis(ax, labels)
    if len(series) > 1:
        ax.legend(frameon=False, fontsize=7.5, loc="upper right", ncol=len(series),
                  labelcolor=TUI_DARK)
    fig.tight_layout(pad=.4)
    st.pyplot(fig, width="stretch")
    plt.close(fig)


def _bar_chart(labels: list[str], values: list) -> None:
    x = list(range(len(labels)))
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    ax.bar(x, values, color=TUI_RED, width=0.62)
    _style_time_axis(ax, labels)
    fig.tight_layout(pad=.4)
    st.pyplot(fig, width="stretch")
    plt.close(fig)


def _render_ranking(period: pa.Period, filters: pa.Filters) -> list[dict]:
    if st.session_state.get("mp_rank_order") not in RANK_CRITERIA:
        st.session_state.mp_rank_order = "Clics"

    st.markdown('<div class="mp-scope">', unsafe_allow_html=True)
    cols = st.columns(len(RANK_CRITERIA), gap="small")
    for idx, label in enumerate(RANK_CRITERIA):
        selected = st.session_state.mp_rank_order == label
        if cols[idx].button(label, key=f"mp_rank_btn_{label}", width="stretch",
                            type="primary" if selected else "secondary"):
            if not selected:
                st.session_state.mp_rank_order = label
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    order_key = RANK_CRITERIA[st.session_state.mp_rank_order]
    rows = pa.rank_destinations(period, filters, order_by=order_key)
    active = [r for r in rows if r["impressions"] > 0 or r["clicks"] > 0]
    if not active:
        st.info("Sin datos suficientes para el ranking de destinos.")
        return rows

    def metric_of(r):
        if order_key == "ctr":
            return _fmt_pct(r["ctr"])
        if order_key == "users":
            return _fmt_int(r["users"])
        if order_key == "impressions":
            return _fmt_int(r["impressions"])
        return _fmt_int(r["clicks"])

    def metric_num(r):
        if order_key == "ctr":
            return r["ctr"] or 0
        return r.get(order_key, 0) or 0

    max_val = max((metric_num(r) for r in active), default=0) or 1
    bars = ['<div class="mp-rank">']
    for i, r in enumerate(active[:12], start=1):
        frac = metric_num(r) / max_val
        pos_cls = "mp-rank-pos mp-top" if i <= 3 else "mp-rank-pos"
        tag = r["ccaa"] or ("Fuera de España" if not r["in_spain"] else "")
        bars.append(
            f'<div class="mp-rank-row"><div class="{pos_cls}">{i}</div>'
            '<div class="mp-rank-main">'
            f'<div class="mp-rank-name"><span>{escape(r["destination"])}</span>'
            f'<span class="mp-rank-metric">{metric_of(r)}</span></div>'
            f'<div class="mp-rank-track"><div class="mp-rank-fill" style="width:{frac * 100:.1f}%"></div></div>'
            f'<div class="mp-rank-sub">{_fmt_int(r["clicks"])} clics · {_fmt_int(r["impressions"])} impresiones · '
            f'CTR {_fmt_pct(r["ctr"])} · {_fmt_int(r["users"])} usuarios</div>'
            '</div>'
            f'<div class="mp-rank-tag">{escape(str(tag))}</div></div>'
        )
    bars.append("</div>")
    st.markdown("".join(bars), unsafe_allow_html=True)
    return rows


def _render_map(period: pa.Period, filters: pa.Filters) -> None:
    points = pa.get_spain_interest_map(period, filters)
    left, right = st.columns([1.5, 1], gap="large")
    with left:
        render_spain_map(points)
    with right:
        st.caption("Detalle por destino")
        active = [p for p in points if p["impressions"] > 0 or p["clicks"] > 0]
        if active:
            df = pd.DataFrame([{
                "Ranking": p["rank"],
                "Destino": p["destination"],
                "Clics": p["clicks"],
                "Usuarios": p["users"],
                "Impresiones": p["impressions"],
                "CTR": _fmt_pct(p["ctr"]),
                "Comunidad": p["ccaa"],
            } for p in active])
            st.dataframe(df, width="stretch", hide_index=True, height=320)
        else:
            st.info("Sin datos suficientes para el detalle del mapa.")

    unmapped = pa.unmapped_interest(period, filters)
    if unmapped:
        names = ", ".join(f"{u['destination']} ({_fmt_int(u['impressions'])})" for u in unmapped[:6])
        st.markdown(
            f'<div class="mp-note">{len(unmapped)} destino(s) con interés no se dibujan en el mapa '
            f'de España (internacionales o sin coordenada): {escape(names)}.</div>',
            unsafe_allow_html=True,
        )


def _render_top_destinations(rows: list[dict], period: pa.Period, filters: pa.Filters) -> None:
    trends = {t["destination"]: t for t in pa.get_destination_trends(period, filters)}
    active = [r for r in rows if r["impressions"] > 0 or r["clicks"] > 0][:3]
    if not active:
        st.info("Sin datos suficientes para el podio de destinos.")
        return
    cards = ['<div class="mp-quad-legend">']
    labels = ["1.º", "2.º", "3.º"]
    for i, r in enumerate(active):
        t = trends.get(r["destination"], {})
        delta = t.get("delta_clicks")
        if delta is None:
            delta_txt = "Sin comparación de periodo"
        elif delta > 0:
            delta_txt = f"▲ +{_fmt_int(delta)} clics vs. periodo anterior"
        elif delta < 0:
            delta_txt = f"▼ {_fmt_int(delta)} clics vs. periodo anterior"
        else:
            delta_txt = "= sin cambio vs. periodo anterior"
        cards.append(
            f'<div class="mp-quad-item"><div class="mp-quad-name">{labels[i]} · {escape(r["destination"])}</div>'
            f'<div class="mp-quad-desc">{_fmt_int(r["clicks"])} clics · {_fmt_int(r["users"])} usuarios · '
            f'CTR {_fmt_pct(r["ctr"])}</div>'
            f'<div class="mp-quad-dests">{escape(delta_txt)}</div></div>'
        )
    cards.append("</div>")
    st.markdown("".join(cards), unsafe_allow_html=True)


def _render_engagement(period: pa.Period, filters: pa.Filters) -> None:
    eng = pa.get_engagement(period)
    cards = [
        _kpi_card("Sesiones activas", {"value": eng["active_sessions"], "available": True, "delta": {}}),
        _kpi_card("Recomendaciones/sesión", {"value": eng["recos_per_session"], "available": eng["recos_per_session"] is not None, "delta": {}}, kind="ratio"),
        _kpi_card("Clics/sesión", {"value": eng["clicks_per_session"], "available": eng["clicks_per_session"] is not None, "delta": {}}, kind="ratio"),
        _kpi_card("Páginas/sesión", {"value": eng["views_per_session"], "available": eng["views_per_session"] is not None, "delta": {}}, kind="ratio"),
        _kpi_card("Usuarios nuevos vs. recurrentes", {"value": None, "available": False, "note": "Requiere identificar al usuario (sessions.user_id)"}),
        _kpi_card("Tiempo medio de sesión", {"value": None, "available": False, "note": "Requiere cierre de sesión (sessions.ended_at)"}),
    ]
    st.markdown('<div class="mp-kpi-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)


def _render_funnel(period: pa.Period, filters: pa.Filters) -> None:
    steps = pa.get_funnel(period, filters)
    top = steps[0]["value"] or 0
    if top <= 0:
        st.info("Sin datos suficientes para el funnel.")
        return
    blocks = ['<div class="mp-funnel">']
    for i, s in enumerate(steps):
        frac = (s["value"] / top) if top else 0
        drop = ""
        if i > 0 and s.get("pct_of_prev") is not None:
            lost = 1 - s["pct_of_prev"]
            drop = f'<div class="mp-funnel-drop">Conversión desde el paso anterior: {_fmt_pct(s["pct_of_prev"])} · pérdida {_fmt_pct(lost)}</div>'
        blocks.append(
            f'<div class="mp-funnel-step"><div class="mp-funnel-head">'
            f'<span class="mp-funnel-label">{escape(s["step"])}</span>'
            f'<span class="mp-funnel-value">{_fmt_int(s["value"])} '
            f'<span class="mp-funnel-pct">· {_fmt_pct(frac)} del total</span></span></div>'
            f'<div class="mp-funnel-track"><div class="mp-funnel-fill" style="width:{max(frac, 0.02) * 100:.1f}%"></div></div>'
            f'{drop}</div>'
        )
    blocks.append("</div>")
    st.markdown("".join(blocks), unsafe_allow_html=True)


def _render_saturation(period: pa.Period, filters: pa.Filters) -> None:
    data = pa.get_interest_vs_saturation(period, filters)
    if not data.get("available"):
        st.info(
            "Sin datos suficientes: se necesita interés por destino y un indicador "
            "de saturación (pasajeros / ocupación) para el mismo destino."
        )
        return
    points = data["points"]
    thr = data["thresholds"]

    left, right = st.columns([1.3, 1], gap="large")
    with left:
        fig, ax = plt.subplots(figsize=(7.4, 5.4))
        colors = {
            "Masificado": "#B80B10",
            "Oportunidad": "#19865E",
            "Menor prioridad": "#8D5D00",
            "Oportunidad secundaria": "#4B5563",
        }
        for p in points:
            ax.scatter(p["saturation"], p["interest"], s=140,
                       color=colors.get(p["quadrant"], MUTED), alpha=.85,
                       edgecolor="#fff", linewidth=1.1, zorder=3)
            ax.annotate(p["destination"], (p["saturation"], p["interest"]),
                        xytext=(5, 4), textcoords="offset points", fontsize=7.5,
                        color=TUI_DARK, zorder=4)
        ax.axvline(thr["saturation"], color="#C5CBD3", linewidth=1, linestyle="--", zorder=1)
        ax.axhline(thr["interest"], color="#C5CBD3", linewidth=1, linestyle="--", zorder=1)
        ax.set_xlabel("Saturación del destino →", fontsize=8, color=MUTED)
        ax.set_ylabel("Interés del usuario →", fontsize=8, color=MUTED)
        ax.tick_params(labelsize=7, colors=MUTED)
        ax.set_facecolor("#FFFFFF")
        for spine in ax.spines.values():
            spine.set_color("#E7EBF0")
        fig.tight_layout(pad=.5)
        st.pyplot(fig, width="stretch")
        plt.close(fig)

    with right:
        quad_desc = {
            "Masificado": "Alto interés + alta saturación → destino masificado.",
            "Oportunidad": "Alto interés + baja saturación → oportunidad.",
            "Menor prioridad": "Bajo interés + alta saturación → menor prioridad.",
            "Oportunidad secundaria": "Bajo interés + baja saturación → oportunidad secundaria.",
        }
        grouped: dict[str, list[str]] = {}
        for p in points:
            grouped.setdefault(p["quadrant"], []).append(p["destination"])
        items = ['<div class="mp-quad-legend">']
        for quad, desc in quad_desc.items():
            dests = grouped.get(quad, [])
            dest_txt = ", ".join(dests) if dests else "—"
            items.append(
                f'<div class="mp-quad-item"><div class="mp-quad-name">{escape(quad)}</div>'
                f'<div class="mp-quad-desc">{escape(desc)}</div>'
                f'<div class="mp-quad-dests">{escape(dest_txt)}</div></div>'
            )
        items.append("</div>")
        st.markdown("".join(items), unsafe_allow_html=True)
        st.markdown(
            '<div class="mp-note">Saturación estimada con datos reales de flujo '
            '(pasajeros aéreos anuales) e impacto local del proyecto.</div>',
            unsafe_allow_html=True,
        )


def _render_potential(period: pa.Period, filters: pa.Filters) -> None:
    rows = pa.get_potential_destinations(period, filters, limit=6)
    if not rows:
        st.info("Sin datos suficientes para detectar destinos con potencial.")
        return
    df = pd.DataFrame([{
        "Destino": r["destination"],
        "Comunidad": r["ccaa"],
        "Tipo": r["type"],
        "Clics": r["clicks"],
        "Saturación": _fmt_pct(r["saturation"]),
        "Sentimiento": _fmt_pct(r["sentiment"]),
        "Reseñas": r["reviews"],
        "Potencial": _fmt_pct(r["potential_score"]),
    } for r in rows])
    st.dataframe(df, width="stretch", hide_index=True)
    st.markdown(
        '<div class="mp-note">Combina interés bajo, saturación baja y buen sentimiento real de reseñas. '
        'Alternativas para redistribuir el flujo desde los destinos masificados.</div>',
        unsafe_allow_html=True,
    )


def _render_instrumentation() -> None:
    """Nota discreta (leyenda) sobre el estado de instrumentación, en vez de una
    sección con tabla propia."""
    m = get_dashboard_metrics()
    disponibles, pendientes = [], []
    for row in instrumentation_status(m):
        if str(row.get("estado", "")).startswith("disponible"):
            disponibles.append(row["KPI"])
        else:
            pendientes.append(f'{row["KPI"]} (necesita {row["necesita"]})')
    partes = []
    if disponibles:
        partes.append("Disponibles: " + ", ".join(disponibles) + ".")
    if pendientes:
        partes.append("Pendientes de instrumentar: " + "; ".join(pendientes) + ".")
    st.markdown(
        '<div class="mp-note"><strong>Estado de instrumentación.</strong> '
        + escape(" ".join(partes)) + "</div>",
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------
# Entrada
# --------------------------------------------------------------------------

def render_control_web() -> None:
    period, filters = _render_filters()

    _section("KPIs principales", "Visión rápida del uso de la plataforma y del rendimiento de las recomendaciones.")
    _render_kpis(period, filters)

    _section("Seguimiento", "Detecta picos, caídas y cambios de comportamiento por día en el periodo seleccionado.")
    _render_evolution(period, filters)

    _section("Rendimiento de recomendaciones", "Ranking de destinos por interés. Cambia el criterio de ordenación.")
    ranked = _render_ranking(period, filters)

    _section("Mapa de interés turístico", "¿Dónde están interactuando los usuarios? Intensidad por destino en España.")
    _render_map(period, filters)

    _section("Destinos más recomendados", "Podio de destinos y su variación respecto al periodo anterior.")
    _render_top_destinations(ranked, period, filters)

    _section("Funnel de interacción", "Dónde se pierde el usuario a lo largo del recorrido.")
    _render_funnel(period, filters)

    _section("Saturación vs. interés", "Oportunidades de redistribución del flujo turístico.")
    _render_saturation(period, filters)
