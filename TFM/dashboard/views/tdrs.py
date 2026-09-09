from __future__ import annotations

"""Panel «Descubre destinos» (antes «Simulador TDRS»).

Tercera forma de consumir el MISMO modelo de recomendación. En lugar de un
formulario de viaje (Recomendador España) o un asistente conversacional, aquí un
VIAJERO ajusta una sola palanca sencilla —destinos populares ↔ joyas menos
concurridas— y ve destinos que encajan, con lo que necesita para decidir:
precio, sol, satisfacción y cuántas alternativas con menos gente hay.

Por debajo sigue siendo la tesis del TDRS (Tourism Demand Redistribution Score):
el dial mueve el objetivo de popularidad del modelo (0 = destinos menos
saturados · 1 = muy visitados), pero la vista lo presenta en lenguaje de viajero,
sin tecnicismos. El resultado NO se calcula aquí; sale del modelo real a través
de ``services.model_gateway`` (hoy, la Function de Azure). Si el modelo no
responde, la vista degrada con un mensaje claro.
"""

from html import escape

import streamlit as st

from components.assets import (
    SCENARIO_ICON_URLS,
    get_local_destination_image,
)
from components.ui import render_metric_rows
from services import model_gateway
from services import recommendation_api_service as reco
from services.destination_image_service import get_destination_image
from services.tdrs_service import (
    POLICY_ICON_BY_NAME,
    POLICY_META,
    POLICY_PRESETS,
    recommend_policy,
    traveler_metrics,
)
from services.tracking_service import register_event

VIEW_LABEL = "Panel de redistribución"

POLICIES = ("Tradicional", "Equilibrado", "Redistribuido")

# Intereses de política que el gestor puede ponderar. Se mapean 1:1 al contrato
# del modelo en model_gateway.POLICY_INTEREST_MAP.
POLICY_INTEREST_LABELS = {
    "coast_beach": "Costa y playa",
    "nature_mountains": "Naturaleza y montaña",
    "rural": "Rural e interior",
    "history_culture": "Historia y cultura",
    "gastronomy_wine": "Gastronomía y vino",
    "wellness": "Bienestar",
    "sports_outdoors": "Deporte y aire libre",
}

INTEREST_SLIDER_SUFFIX = {
    "coast_beach": "coast",
    "nature_mountains": "nature",
    "rural": "rural",
    "history_culture": "culture",
    "gastronomy_wine": "gastro",
    "wellness": "wellness",
    "sports_outdoors": "sports",
}


# --------------------------------------------------------------------------
# Estado y selección de escenario de política
# --------------------------------------------------------------------------

def _current_policy_name() -> str:
    name = st.session_state.get("tdrs_policy", "Equilibrado")
    if name not in POLICIES:
        name = "Equilibrado"
        st.session_state.tdrs_policy = name
    return name


# --------------------------------------------------------------------------
# Controles laterales: política de redistribución
# --------------------------------------------------------------------------

def render_tdrs_sidebar_controls() -> dict:
    """Controles de política del panel experto.

    Devuelve la política ya lista para el gateway: dial de popularidad, pesos de
    interés (0-100), preferencia de temperatura y restricciones.
    """
    policy_name = _current_policy_name()
    defaults = POLICY_PRESETS[policy_name]

    with st.sidebar.expander("¿Cómo quieres que sea el viaje?", expanded=True):
        st.caption(
            "¿Prefieres destinos populares o joyas menos concurridas? Muévelo "
            "hacia la izquierda para descubrir sitios con menos gente."
        )
        popularity_target = st.slider(
            "Populares ↔ menos concurridos",
            0.0, 1.0, float(defaults["popularity_target"]), 0.05,
            key=f"tdrs_{policy_name}_poptarget",
            help="Izquierda = joyas tranquilas con menos turistas · "
                 "derecha = destinos famosos y muy visitados.",
        )

    with st.sidebar.expander("¿Qué te apetece hacer?", expanded=True):
        st.caption(
            "Marca lo que más te gusta y ajustamos las propuestas a tu tipo de "
            "viaje."
        )
        interests: dict[str, int] = {}
        for code, label in POLICY_INTEREST_LABELS.items():
            suffix = INTEREST_SLIDER_SUFFIX[code]
            interests[code] = st.slider(
                label, 0, 100, int(defaults["interests"].get(code, 40)),
                key=f"tdrs_{policy_name}_{suffix}",
            )

    with st.sidebar.expander("Clima y fechas", expanded=False):
        temp_options = list(reco.TEMPERATURE_PREFERENCES)
        default_temp = defaults.get("temperature_preference", "mild")
        temperature = st.selectbox(
            "Preferencia de temperatura",
            temp_options,
            index=temp_options.index(default_temp) if default_temp in temp_options else 0,
            format_func=lambda code: reco.TEMPERATURE_LABELS[code],
            key=f"tdrs_{policy_name}_temp",
        )
        month = st.slider(
            "Mes de referencia", 1, 12, 7, 1,
            key=f"tdrs_{policy_name}_month",
            format="%d",
        )

    return {
        "policy_name": policy_name,
        "popularity_target": popularity_target,
        "interests": interests,
        "temperature_preference": temperature,
        "month": int(month),
    }


# --------------------------------------------------------------------------
# Selector de escenario de política (área principal)
# --------------------------------------------------------------------------

def render_policy_selector() -> None:
    current = _current_policy_name()
    with st.container(border=True):
        cols = st.columns(3, gap="medium")
        for idx, name in enumerate(POLICIES):
            icon_url = SCENARIO_ICON_URLS[POLICY_ICON_BY_NAME[name]]
            cols[idx].markdown(
                f'<div class="scenario-icon-wrap">'
                f'<img class="scenario-icon" src="{escape(icon_url, quote=True)}" '
                f'alt="{escape(name, quote=True)}"></div>',
                unsafe_allow_html=True,
            )
            clicked = cols[idx].button(
                name,
                key=f"tdrs_policy_btn_{name}",
                width="stretch",
                type="primary" if current == name else "secondary",
            )
            if clicked and current != name:
                st.session_state.tdrs_policy = name
                st.rerun()
        meta = POLICY_META[current]
        icon = SCENARIO_ICON_URLS[POLICY_ICON_BY_NAME[current]]
        st.markdown(
            f'<div class="selector-active">'
            f'<strong><img class="scenario-active-icon" src="{escape(icon, quote=True)}" alt="">'
            f'{escape(current)} · {escape(meta["tagline"])}</strong> · '
            f'{escape(meta["description"])}</div>',
            unsafe_allow_html=True,
        )


# --------------------------------------------------------------------------
# Ángulo de redistribución: cómo el dial mueve la demanda
# --------------------------------------------------------------------------

def _fmt(value, suffix: str = "", decimals: int = 0) -> str:
    if value is None:
        return "—"
    if isinstance(value, float) and value != value:  # NaN
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:,.{decimals}f}{suffix}"
    return escape(str(value))


def _price_txt(value) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):,.0f} €".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def render_redistribution_band(popularity_target: float, metrics: dict) -> None:
    """Banda-resumen orientada al viajero.

    Traduce el dial en una frase útil (qué tipo de viaje va a proponer) y muestra
    lo que ayuda a decidir: desde cuánto cuesta, cuánto sol hay y cuántas
    alternativas con menos gente se han encontrado. Sin tecnicismos.
    """
    pct = max(0.0, min(1.0, float(popularity_target))) * 100
    less_crowded = metrics.get("less_crowded_count") or 0
    eligible = metrics.get("eligible") or 0

    if popularity_target <= 0.35:
        stance = "Joyas con menos gente"
        note = (
            "Priorizamos destinos poco masificados: buen ambiente sin las "
            "aglomeraciones de los clásicos."
        )
    elif popularity_target >= 0.65:
        stance = "Los grandes clásicos"
        note = (
            "Priorizamos los destinos más famosos y visitados de España, con "
            "toda su oferta consolidada."
        )
    else:
        stance = "Lo mejor de los dos mundos"
        note = (
            "Mezclamos destinos conocidos con alternativas más tranquilas para "
            "que elijas con calma."
        )

    from_txt = _price_txt(metrics.get("from_price"))
    sun = metrics.get("avg_sunny_days")
    sun_txt = "—" if sun is None else f"{sun:.0f} días"
    if eligible:
        crowd_txt = f"{less_crowded} de {eligible}"
    else:
        crowd_txt = "—"

    st.markdown(
        f'<div class="redist-band">'
        f'<div class="redist-head">'
        f'<div class="redist-stance">{escape(stance)}</div>'
        f'<div class="redist-note">{escape(note)}</div>'
        f'</div>'
        f'<div class="redist-stats">'
        f'<div class="redist-stat"><div class="redist-stat-value">{escape(from_txt)}</div>'
        f'<div class="redist-stat-label">Precio desde</div></div>'
        f'<div class="redist-stat"><div class="redist-stat-value">{escape(sun_txt)}</div>'
        f'<div class="redist-stat-label">Sol al mes</div></div>'
        f'<div class="redist-stat"><div class="redist-stat-value">{escape(crowd_txt)}</div>'
        f'<div class="redist-stat-label">Con menos gente</div></div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------
# Podio de destinos redistribuidos
# --------------------------------------------------------------------------

def _place(destination: dict) -> str:
    """Ubicación sin repetir el nombre del municipio (mismo criterio que la
    vista Recomendador España)."""
    name = str(destination.get("name") or "").strip()
    province = str(destination.get("province") or "").strip()
    community = str(destination.get("autonomous_community") or "").strip()
    seen = {name.lower()}
    bits: list[str] = []
    for value in (province, community):
        key = value.lower()
        if value and key not in seen:
            bits.append(value)
            seen.add(key)
    return " · ".join(bits)


def _destination_photo(name: str, destination: dict) -> dict | None:
    image = get_local_destination_image(name)
    if image:
        return image
    return get_destination_image(name) or None


def _crowd_tag(row: dict) -> str:
    """Etiqueta de nivel de gente en lenguaje de viajero (no un número técnico)."""
    popularity = (row.get("popularity_profile") or {}).get("index")
    if popularity is None:
        return ""
    try:
        idx = float(popularity)
    except (TypeError, ValueError):
        return ""
    if idx <= 0.4:
        return "Menos concurrido"
    if idx >= 0.7:
        return "Muy popular"
    return "Ambiente equilibrado"


def render_podium(ranking: list[dict]) -> None:
    podium = []
    for idx, row in enumerate(ranking[:3]):
        destination = row.get("destination") or {}
        name = str(destination.get("name") or "Destino")
        place = _place(destination)
        crowd_txt = _crowd_tag(row)
        typology = destination.get("primary_typology")

        image = _destination_photo(name, destination)
        if image:
            image_html = (
                f'<img class="podium-image" src="{escape(image["url"], quote=True)}" '
                f'alt="{escape(image.get("alt", f"Imagen de {name}"), quote=True)}" loading="lazy">'
            )
        else:
            image_html = f'<div class="podium-image-fallback">{escape(name)}</div>'

        tag = escape(str(typology)) if typology else escape(crowd_txt)
        podium.append(
            f'<div class="podium-card {"first" if idx == 0 else ""}">'
            f'{image_html}'
            f'<div class="podium-head">'
            f'<div class="podium-head-main">'
            f'<div class="podium-rank">opción {idx + 1}</div>'
            f'<div class="podium-name">{escape(name)}</div>'
            f'</div>'
            f'<div class="podium-price redist-poptag">{tag}</div>'
            f'</div>'
            f'<div class="podium-meta">{escape(place or crowd_txt)}</div>'
            '</div>'
        )
    if podium:
        st.markdown('<div class="podium-grid">' + ''.join(podium) + '</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Degradación elegante cuando el modelo no responde
# --------------------------------------------------------------------------

def _render_unavailable(result: dict | None) -> None:
    kind = (result or {}).get("error_kind")
    message = (result or {}).get("error") or "El modelo no está disponible ahora mismo."
    if kind == "not_configured" or not model_gateway.is_configured():
        st.info(
            "Las propuestas se calculan con nuestro motor de recomendación en la "
            "nube, que ahora mismo no está conectado. En cuanto esté disponible "
            "verás aquí los destinos que encajan con lo que buscas."
        )
    elif kind in {"network", "cooldown"}:
        st.warning(
            "No hemos podido traer las propuestas ahora mismo (el servicio puede "
            "estar despertando). Ajusta lo que buscas y vuelve a intentarlo en "
            "unos segundos."
        )
    else:
        st.error(escape(str(message)))


# --------------------------------------------------------------------------
# Orquestación
# --------------------------------------------------------------------------

def _run_policy(controls: dict) -> dict:
    policy = {
        "popularity_target": controls["popularity_target"],
        "interests": controls["interests"],
        "temperature_preference": controls["temperature_preference"],
        "month": controls["month"],
    }
    with st.spinner(
        "Consultando el modelo… La primera consulta puede tardar mientras el "
        "servicio despierta."
    ):
        result = recommend_policy(policy)

    register_event(
        st.session_state.session_id,
        "policy_recommendation",
        VIEW_LABEL,
        metadata={
            "policy": controls["policy_name"],
            "popularity_target": controls["popularity_target"],
            "ok": bool(result.get("ok")),
            "error_kind": result.get("error_kind"),
            "backend": result.get("backend"),
        },
    )
    return result


def render_tdrs(controls: dict) -> None:
    st.markdown(
        '<div class="reco-header">'
        '<div class="reco-kicker">Descubre destinos</div>'
        '<h2 class="reco-hero-title">Encuentra tu viaje, '
        '<em>con más o menos gente</em></h2>'
        '<p class="reco-hero-lead">Dinos si buscas los grandes clásicos o joyas '
        'menos concurridas y te proponemos destinos que encajan, con lo que '
        'necesitas para decidir: precio, sol y ambiente.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    render_policy_selector()

    if controls is None:
        controls = render_tdrs_sidebar_controls()

    result = _run_policy(controls)
    ranking = result.get("ranking") or [] if result.get("ok") else []

    if not (result.get("ok") and ranking):
        _render_unavailable(result)
        return

    metrics = traveler_metrics(ranking) or {}

    # Impresión de los destinos del podio (interacción trazable para Control Web).
    for pos, row in enumerate(ranking[:3], 1):
        name = (row.get("destination") or {}).get("name") or ""
        register_event(
            st.session_state.session_id,
            "product_impression",
            VIEW_LABEL,
            destination=name,
            metadata={
                "policy": controls["policy_name"],
                "position": pos,
                "score": round(float(row.get("recommendation_score") or 0), 3),
            },
            dedupe_key=f"tdrs_impression:{controls['policy_name']}:{name}",
        )

    render_redistribution_band(controls["popularity_target"], metrics)
    render_podium(ranking)

    # Métricas pensadas para que un VIAJERO decida. Las de precio solo aparecen
    # si el modelo envía precio; si no, se omiten con elegancia.
    eligible = metrics.get("eligible", 0)
    less_crowded = metrics.get("less_crowded_count", 0)
    metric_cards: list[tuple[str, object]] = []
    if metrics.get("from_price") is not None:
        metric_cards.append(("Precio desde", _price_txt(metrics.get("from_price"))))
    if metrics.get("avg_price") is not None:
        metric_cards.append(("Precio medio", _price_txt(metrics.get("avg_price"))))
    metric_cards.append(("Días de sol", _fmt(metrics.get("avg_sunny_days"), decimals=0)))
    metric_cards.append(("Satisfacción", _fmt(metrics.get("avg_satisfaction"), decimals=0)))
    metric_cards.append((
        "Alternativas con menos gente",
        f"{less_crowded} destino{'s' if less_crowded != 1 else ''}",
    ))
    # Número FIJO de columnas (5) aunque el nº de métricas varíe entre 3 y 5
    # según haya precio: un st.columns de tamaño cambiante entre reruns rompe
    # el DOM de React (removeChild).
    render_metric_rows(metric_cards, columns=5)

    # Trazabilidad de la llamada al modelo.
    footer = []
    if result.get("recommendation_id"):
        footer.append(f"ID de recomendación: {result['recommendation_id']}")
    footer.append(f"modelo consumido vía backend «{result.get('backend', 'azure')}»")
    st.caption(" · ".join(footer))
