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


# Paleta cualitativa por zona (comunidad autónoma). Colores diferenciados y
# legibles sobre fondo oscuro. Se asignan de forma estable por nombre.
_ZONE_PALETTE = [
    (232, 89, 94),    # rojo TUI claro
    (79, 154, 214),   # azul
    (86, 191, 145),   # verde
    (240, 173, 78),   # ámbar
    (166, 122, 214),  # violeta
    (78, 201, 197),   # turquesa
    (230, 126, 179),  # rosa
    (150, 179, 90),   # oliva
    (219, 122, 96),   # terracota
    (120, 144, 214),  # índigo
    (215, 178, 74),   # oro
    (108, 194, 111),  # verde lima
]


def _zone_color(ccaa: str | None) -> tuple[int, int, int]:
    """Color RGB estable para una comunidad (zona). Mismo nombre → mismo color."""
    if not ccaa:
        return (148, 163, 184)  # gris para "sin comunidad"
    idx = sum(ord(c) for c in ccaa) % len(_ZONE_PALETTE)
    return _ZONE_PALETTE[idx]


def _interest_color(frac: float) -> list[int]:
    """Color RGBA (lista) de un punto según su intensidad de interés (0–1).

    Degradado de rosa claro a rojo TUI oscuro, coherente con la marca. La
    opacidad también sube con el interés para reforzar el foco.
    """
    stops = [
        (0.0, (251, 213, 214)),   # #FBD5D6
        (0.4, (232, 89, 94)),     # #E8595E
        (0.75, (212, 14, 20)),    # TUI red
        (1.0, (142, 10, 14)),     # #8E0A0E
    ]
    frac = max(0.0, min(1.0, frac))
    for (f0, c0), (f1, c1) in zip(stops, stops[1:]):
        if frac <= f1:
            t = 0 if f1 == f0 else (frac - f0) / (f1 - f0)
            rgb = [int(round(a + (b - a) * t)) for a, b in zip(c0, c1)]
            return rgb + [int(150 + 90 * frac)]
    return list(stops[-1][1]) + [240]


def render_spain_map(points: list[dict], metric_label: str = "Clics") -> None:
    """Mapa INTERACTIVO de España con la intensidad de interés por destino.

    Usa pydeck (zoom, arrastre y tooltip al pasar el cursor). El radio y el color
    de cada círculo escalan con el interés (clics, o impresiones si aún no hay
    clics). Responde a «¿dónde están interactuando los usuarios?»: solo dibuja
    destinos con interacción real; si no hay ninguno, lo declara. Si pydeck no
    estuviera disponible, cae a un mapa estático de respaldo.
    """
    active = [p for p in points if (p.get("clicks") or 0) > 0 or (p.get("impressions") or 0) > 0]
    if not active:
        st.info("Sin datos suficientes: todavía no hay interacción por destino en España para el periodo seleccionado.")
        return

    # Métrica de intensidad: clics si existen; si no, impresiones.
    use_clicks = any((p.get("clicks") or 0) > 0 for p in active)
    intensity_key = "clicks" if use_clicks else "impressions"
    intensity_name = "clics" if use_clicks else "impresiones"
    max_value = max(p[intensity_key] for p in active) or 1

    try:
        import pydeck as pdk
    except ImportError:
        _render_spain_map_static(active, intensity_key, intensity_name, max_value)
        return

    # Etiquetamos solo los destinos con más interés: el resto satura el mapa y
    # se consulta con el tooltip. Umbral: top 8 por intensidad.
    ordered = sorted(active, key=lambda p: p[intensity_key], reverse=True)
    labelled = {id(p) for p in ordered[:8]}

    rows = []
    for p in active:
        value = p[intensity_key]
        frac = value / max_value
        # Color propio por comunidad (zona); la opacidad sube con el interés
        # para que se distinga la zona y a la vez destaque la intensidad.
        r, g, b = _zone_color(p["ccaa"])
        alpha = int(150 + 90 * frac)
        rows.append({
            "lat": p["lat"],
            "lon": p["lon"],
            "destino": p["destination"],
            "etiqueta": p["destination"] if id(p) in labelled else "",
            "comunidad": p["ccaa"] or "—",
            "clics": _fmt_int(p["clicks"]),
            "impresiones": _fmt_int(p["impressions"]),
            "usuarios": _fmt_int(p["users"]),
            "ctr": _fmt_pct(p["ctr"]),
            "ranking": f"#{p['rank']}",
            "intensidad": value,
            "radio": 14000 + 46000 * (frac ** 0.6),
            "color": [r, g, b, alpha],
        })

    # Conjunto de caracteres para el TextLayer: sin esto, deck.gl no dibuja las
    # tildes ni la ñ (usa solo ASCII por defecto y muestra huecos). Lo derivamos
    # de las propias etiquetas; así incluye acentos/ñ y evitamos caracteres
    # conflictivos (comillas, backslash) que rompen el parseo JSON de deck.gl.
    used_chars = set()
    for row in rows:
        used_chars.update(row["etiqueta"])
    used_chars.discard('"')
    used_chars.discard("'")
    used_chars.discard("\\")
    char_set = sorted(used_chars) or [" "]

    view = pdk.ViewState(latitude=39.6, longitude=-3.6, zoom=4.7, min_zoom=3, max_zoom=9, pitch=0)
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=rows,
        get_position="[lon, lat]",
        get_radius="radio",
        get_fill_color="color",
        get_line_color=[255, 255, 255],
        line_width_min_pixels=1.5,
        radius_min_pixels=4,
        radius_max_pixels=60,
        stroked=True,
        pickable=True,
        opacity=0.9,
    )
    # Etiquetas legibles sobre mapa oscuro: texto blanco, negrita, con un
    # recuadro oscuro translúcido detrás y desplazadas hacia arriba del punto.
    text_layer = pdk.Layer(
        "TextLayer",
        data=rows,
        get_position="[lon, lat]",
        get_text="etiqueta",
        get_size=13,
        get_color=[255, 255, 255],
        get_pixel_offset=[0, -14],
        get_alignment_baseline="'bottom'",
        get_text_anchor="'middle'",
        character_set=char_set,
        font_family="'Arial, sans-serif'",
        font_weight="'bold'",
        background=True,
        get_background_color=[17, 24, 39, 190],
        background_padding=[5, 3, 5, 3],
        outline_width=1,
        outline_color=[17, 24, 39],
        pickable=False,
    )
    tooltip = {
        "html": (
            "<div style='font-weight:700;font-size:13px;margin-bottom:2px'>{destino}"
            "<span style='color:#FBB;font-weight:600'> &middot; {ranking}</span></div>"
            "<div style='color:#C7CDD9;font-size:11px;margin-bottom:4px'>{comunidad}</div>"
            "<div>Clics: <b>{clics}</b> &middot; Impresiones: <b>{impresiones}</b></div>"
            "<div>Usuarios: <b>{usuarios}</b> &middot; CTR: <b>{ctr}</b></div>"
        ),
        "style": {
            "backgroundColor": "rgba(17,24,39,0.95)",
            "color": "#FFFFFF",
            "fontSize": "12px",
            "fontFamily": "system-ui, -apple-system, sans-serif",
            "borderRadius": "8px",
            "padding": "9px 12px",
            "boxShadow": "0 6px 20px rgba(0,0,0,0.28)",
            "maxWidth": "240px",
        },
    }
    deck = pdk.Deck(
        layers=[layer, text_layer],
        initial_view_state=view,
        map_style="dark",
        tooltip=tooltip,
    )
    st.pydeck_chart(deck, use_container_width=True)
    _render_map_legend(intensity_name, active)


def _render_map_legend(intensity_name: str, active: list[dict]) -> None:
    """Leyenda del mapa: color por comunidad (zona) y tamaño del punto.

    El color de cada punto identifica su comunidad; el tamaño crece con el
    interés. Solo listamos las comunidades presentes en el periodo.
    """
    zonas = []
    vistos = set()
    for p in active:
        nombre = p["ccaa"] or "Sin comunidad"
        if nombre in vistos:
            continue
        vistos.add(nombre)
        r, g, b = _zone_color(p["ccaa"])
        zonas.append((nombre, f"rgb({r},{g},{b})"))
    zonas.sort(key=lambda z: z[0])

    chips = "".join(
        f'<span class="mp-legend-item">'
        f'<span class="mp-legend-dot" style="background:{color};width:12px;height:12px"></span>'
        f'<span class="mp-legend-label">{escape(nombre)}</span></span>'
        for nombre, color in zonas
    )
    st.markdown(
        f"""
        <div class="mp-map-legend">
          <div class="mp-legend-item">
            <span class="mp-legend-dot mp-dot-sm"></span>
            <span class="mp-legend-dot mp-dot-md"></span>
            <span class="mp-legend-dot mp-dot-lg"></span>
            <span class="mp-legend-label">El tamaño crece con los {intensity_name}</span>
          </div>
        </div>
        <div class="mp-map-legend mp-legend-zones">{chips}</div>
        """,
        unsafe_allow_html=True,
    )


def _render_spain_map_static(active: list[dict], intensity_key: str,
                             intensity_name: str, max_value: float) -> None:
    """Mapa estático de respaldo (matplotlib) por si pydeck no está disponible."""
    cmap = LinearSegmentedColormap.from_list("tui_interest", ["#FBD5D6", "#E8595E", TUI_RED, "#8E0A0E"])
    fig, ax = plt.subplots(figsize=(9.6, 6.6))
    _spain_polygons(ax)
    for p in active:
        value = p[intensity_key]
        frac = (value / max_value) if max_value else 0
        ax.scatter(p["lon"], p["lat"], s=90 + 900 * (frac ** 0.6),
                   color=cmap(0.25 + 0.75 * frac), edgecolor="#FFFFFF",
                   linewidth=1.1, alpha=.92, zorder=3)
        ax.annotate(f"{p['destination']}\n{_fmt_int(value)}", (p["lon"], p["lat"]),
                    xytext=(6, 6), textcoords="offset points", fontsize=7.5,
                    color=TUI_DARK, fontweight="bold", zorder=4)
    ax.set_xlim(-19.0, 5.5)
    ax.set_ylim(26.5, 44.5)
    ax.set_facecolor("#FFFFFF")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.tight_layout(pad=.4)
    st.pyplot(fig, width="stretch")
    plt.close(fig)


# --------------------------------------------------------------------------
# Filtros del panel
# --------------------------------------------------------------------------

def _render_filters() -> tuple[pa.Period, pa.Filters]:
    """Barra de filtros: periodo, destino y tipo.

    Devuelve la ventana temporal resuelta y los filtros de destino. Afectan de
    forma coherente a todas las métricas y gráficos del panel.
    """
    bounds = pa.data_bounds()
    with st.container():
        c1, c2, c3 = st.columns([1.1, 1, 1], gap="small")
        preset = c1.selectbox("Periodo", pa.PERIOD_PRESETS, index=1, key="mp_period")

        dest_options = ["Todos"] + list(spain_reference.SPAIN_DESTINATIONS.keys())
        destination = c2.selectbox("Destino", dest_options, index=0, key="mp_destination")

        type_options = ["Todos"] + spain_reference.type_options()
        dest_type = c3.selectbox("Tipo de destino", type_options, index=0, key="mp_type")

        custom_start = custom_end = None
        if preset == pa.PERIOD_ALL and bounds.get("min"):
            st.caption(
                f"Histórico disponible: {bounds['min'].isoformat()} → {bounds['max'].isoformat()}."
            )

    period = pa.resolve_period(preset, custom_start=custom_start, custom_end=custom_end)
    filters = pa.Filters(
        destination=destination if destination != "Todos" else None,
        dest_type=dest_type if dest_type != "Todos" else None,
    )
    return period, filters


# --------------------------------------------------------------------------
# Bloques del panel
# --------------------------------------------------------------------------

def _render_kpis(period: pa.Period, filters: pa.Filters) -> dict:
    kpis = pa.get_kpis(period, filters)
    cards = [
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
        _chart_title(f"Recomendaciones, impresiones y clics por {unidad}")
        _line_chart(
            labels,
            {
                "Recomendaciones": list(plot_df["requests"]),
                "Impresiones": list(plot_df["impressions"]),
                "Clics": list(plot_df["clicks"]),
            },
        )
    with c2:
        _chart_title(f"Sesiones activas por {unidad}")
        _bar_chart(labels, list(plot_df["sessions"]))


def _chart_title(text: str) -> None:
    """Título de gráfico en tono oscuro TUI, para que resalte más que un caption."""
    st.markdown(
        f'<div style="font-size:.8rem;font-weight:800;color:{TUI_DARK};margin:.1rem 0 .35rem">'
        f'{escape(text)}</div>',
        unsafe_allow_html=True,
    )


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
        # Leyenda debajo del gráfico para no taparse con las líneas.
        ax.legend(frameon=False, fontsize=7.5, loc="upper center",
                  bbox_to_anchor=(0.5, -0.18), ncol=len(series),
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

    order_key = RANK_CRITERIA[st.session_state.mp_rank_order]
    rows = pa.rank_destinations(period, filters, order_by=order_key)
    return rows


def _render_map(period: pa.Period, filters: pa.Filters) -> None:
    points = pa.get_spain_interest_map(period, filters)
    # El mapa interactivo va a todo el ancho (es el protagonista); el detalle
    # por destino se muestra debajo, en una tabla ordenable.
    render_spain_map(points)

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
    cards = ['<div class="mp-podium">']
    rank_cls = ["gold", "silver", "bronze"]
    for i, r in enumerate(active):
        t = trends.get(r["destination"], {})
        delta = t.get("delta_clicks")
        if delta is None:
            delta_html = '<span class="mp-podium-delta mp-podium-delta--none">sin histórico</span>'
        elif delta > 0:
            delta_html = f'<span class="mp-podium-delta mp-podium-delta--up">+{_fmt_int(delta)}</span>'
        elif delta < 0:
            delta_html = f'<span class="mp-podium-delta mp-podium-delta--down">{_fmt_int(delta)}</span>'
        else:
            delta_html = '<span class="mp-podium-delta mp-podium-delta--flat">igual</span>'
        cards.append(
            f'<div class="mp-podium-item mp-podium-item--{rank_cls[i]}">'
            f'<span class="mp-podium-rank">{i + 1}</span>'
            f'<span class="mp-podium-body">'
            f'<span class="mp-podium-name">{escape(r["destination"])}</span>'
            f'<span class="mp-podium-stats">{_fmt_int(r["clicks"])} clics · {_fmt_int(r["users"])} usuarios · '
            f'CTR {_fmt_pct(r["ctr"])}</span></span>'
            f'{delta_html}</div>'
        )
    cards.append("</div>")
    st.markdown("".join(cards), unsafe_allow_html=True)


def _render_engagement(period: pa.Period, filters: pa.Filters) -> None:
    eng = pa.get_engagement(period)
    cards = [
        _kpi_card("Sesiones activas", {"value": eng["active_sessions"], "available": True, "delta": {}}),
        _kpi_card("Recomendaciones generadas", {"value": eng["recommendations"], "available": True, "delta": {}}),
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
    # El primer paso (impresiones) es siempre el mayor: el embudo decrece de
    # forma monotónica, así que sirve de referencia para el ancho de las barras.
    blocks = ['<div class="mp-funnel">']
    for i, s in enumerate(steps):
        frac = (s["value"] / top) if top else 0
        width = max(frac, 0.08) * 100
        drop = ""
        if i > 0 and s.get("pct_of_prev") is not None:
            lost = 1 - s["pct_of_prev"]
            drop = (
                f'<div class="mp-funnel-drop">Conversión: {_fmt_pct(s["pct_of_prev"])} · '
                f'pérdida {_fmt_pct(lost)}</div>'
            )
        blocks.append(
            f'<div class="mp-funnel-step">'
            f'<div class="mp-funnel-bar" style="width:{width:.1f}%">'
            f'<span class="mp-funnel-label">{escape(s["step"])}</span>'
            f'<span class="mp-funnel-value">{_fmt_int(s["value"])}'
            f'<span class="mp-funnel-pct"> · {_fmt_pct(frac)}</span></span>'
            f'</div>{drop}</div>'
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
        tx, ty = thr["saturation"], thr["interest"]
        xs = [p["saturation"] for p in points]
        ys = [p["interest"] for p in points]
        x0, x1 = min(xs + [tx]), max(xs + [tx])
        y0, y1 = min(ys + [ty]), max(ys + [ty])
        xpad = (x1 - x0) * 0.12 or 1
        ypad = (y1 - y0) * 0.12 or 1
        ax.set_xlim(x0 - xpad, x1 + xpad)
        ax.set_ylim(y0 - ypad, y1 + ypad)

        # Fondo tenue por cuadrante para leer de un vistazo dónde cae cada zona.
        ax.axvspan(tx, x1 + xpad, ymin=0.5, ymax=1, facecolor="#B80B10", alpha=.05, zorder=0)
        ax.axvspan(x0 - xpad, tx, ymin=0.5, ymax=1, facecolor="#19865E", alpha=.05, zorder=0)
        ax.axvspan(tx, x1 + xpad, ymin=0, ymax=0.5, facecolor="#8D5D00", alpha=.05, zorder=0)
        ax.axvspan(x0 - xpad, tx, ymin=0, ymax=0.5, facecolor="#4B5563", alpha=.05, zorder=0)

        for p in points:
            ax.scatter(p["saturation"], p["interest"], s=150,
                       color=colors.get(p["quadrant"], MUTED), alpha=.9,
                       edgecolor="#fff", linewidth=1.2, zorder=3)
            ax.annotate(p["destination"], (p["saturation"], p["interest"]),
                        xytext=(6, 5), textcoords="offset points", fontsize=7.5,
                        color=TUI_DARK, fontweight="medium", zorder=4)
        ax.axvline(tx, color="#B4BCC7", linewidth=1, linestyle="--", zorder=1)
        ax.axhline(ty, color="#B4BCC7", linewidth=1, linestyle="--", zorder=1)
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
        # Cada cuadrante: clave CSS, título, acción sugerida y descripción de la
        # regla (interés × saturación). El orden refleja prioridad de negocio.
        quad_meta = {
            "Masificado": (
                "masificado", "Descongestionar",
                "Alto interés y alta saturación. Redirige demanda hacia alternativas.",
            ),
            "Oportunidad": (
                "oportunidad", "Impulsar",
                "Alto interés y baja saturación. Margen para captar más flujo.",
            ),
            "Menor prioridad": (
                "menor", "Vigilar",
                "Bajo interés y alta saturación. No requiere acción inmediata.",
            ),
            "Oportunidad secundaria": (
                "secundaria", "Explorar",
                "Bajo interés y baja saturación. Potencial a futuro.",
            ),
        }
        grouped: dict[str, list[str]] = {}
        for p in points:
            grouped.setdefault(p["quadrant"], []).append(p["destination"])

        items = ['<div class="mp-quad-grid">']
        for quad, (cls, action, desc) in quad_meta.items():
            dests = grouped.get(quad, [])
            chips = "".join(
                f'<span class="mp-quad-chip">{escape(d)}</span>' for d in dests
            ) or '<span class="mp-quad-empty">Sin destinos</span>'
            items.append(
                f'<div class="mp-quad-card mp-quad--{cls}">'
                f'<div class="mp-quad-top">'
                f'<span class="mp-quad-name">{escape(quad)}</span></div>'
                f'<div class="mp-quad-action">{escape(action)}</div>'
                f'<div class="mp-quad-desc">{escape(desc)}</div>'
                f'<div class="mp-quad-chips">{chips}</div>'
                f'</div>'
            )
        items.append("</div>")
        st.markdown("".join(items), unsafe_allow_html=True)


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

    ranked = _render_ranking(period, filters)

    _section("Mapa de interés turístico", "Contrasta dónde se recomiendan los destinos frente a dónde los usuarios realmente hacen clic en España.")
    _render_map(period, filters)

    left, right = st.columns([1, 1], gap="large")
    with left:
        _section("Destinos más recomendados", "Podio de destinos y su variación respecto al periodo anterior.")
        _render_top_destinations(ranked, period, filters)
    with right:
        _section("Funnel de interacción")
        _render_funnel(period, filters)

    _section("Saturación vs. interés", "Oportunidades de redistribución del flujo turístico.")
    _render_saturation(period, filters)
