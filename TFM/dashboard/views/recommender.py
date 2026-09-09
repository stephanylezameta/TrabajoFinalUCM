from __future__ import annotations

from html import escape

import streamlit as st

from components.assets import get_local_destination_image
from services import recommendation_api_service as reco
from services.destination_image_service import resolve_destination_image
from services.tracking_service import register_event
from views.recommender_chat import render_recommender_chat

# Etiqueta interna para el tracking. La vista se llama «España» en el menú, pero
# el evento mantiene un identificador descriptivo y estable.
VIEW_LABEL = "España"
STATE_KEY = "reco_result"
STATE_PAYLOAD = "reco_payload"
STATE_AUTORUN = "reco_autorun_done"
STATE_CUSTOM = "reco_is_custom"

# El asistente de viaje está INTEGRADO en la vista como un copiloto único, al
# estilo de los agentes de viaje conversacionales (Layla, Mindtrip): la
# conversación es la columna protagonista y las tarjetas de destino se muestran
# EMBEBIDAS dentro de la respuesta del asistente (ver ``recommender_chat.py``).
# El formulario de filtros (modo real contra Azure) queda como búsqueda avanzada
# secundaria, en un expander discreto.


# --------------------------------------------------------------------------
# Ayudas de formato
# --------------------------------------------------------------------------

def _fmt(value, suffix: str = "", decimals: int = 1) -> str:
    """Formatea un número; un dato ausente se muestra como `—`."""
    if value is None:
        return "—"
    if isinstance(value, float) and value != value:  # NaN
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:,.{decimals}f}{suffix}"
    return str(value)


def _chip(text: str, kind: str = "") -> str:
    css = f"reco-chip {kind}".strip()
    return f'<span class="{css}">{escape(text)}</span>'


def _bar(label: str, value: float | None) -> str:
    if value is None:
        return (
            f'<div class="reco-bar-row"><div class="reco-bar-label">{escape(label)}</div>'
            f'<div class="reco-bar-track"></div><div class="reco-bar-value">—</div></div>'
        )
    pct = max(0.0, min(1.0, float(value))) * 100
    return (
        f'<div class="reco-bar-row"><div class="reco-bar-label">{escape(label)}</div>'
        f'<div class="reco-bar-track"><div class="reco-bar-fill" style="width:{pct:.1f}%"></div></div>'
        f'<div class="reco-bar-value">{value:.2f}</div></div>'
    )


def _photo(row: dict) -> dict | None:
    """Fotografía del destino, ajustada a la tarjeta como banner.

    La resolución es en vivo y desambiguada: usa provincia y comunidad para no
    traer la imagen de un homónimo famoso (p. ej. "Palma" → Palma de Mallorca,
    no la Palma de Oro de Cannes). Se prueba primero una foto local si existe,
    porque es instantánea, pero la app no depende de tenerla: si no está, la
    busca en Wikipedia sin necesidad de redesplegar.
    """
    destination = row.get("destination") or {}
    name = destination.get("name")
    if not name:
        return None
    local = get_local_destination_image(name)
    if local:
        return local
    return resolve_destination_image(destination)


def _place(destination: dict) -> str:
    """Ubicación legible sin repetir el nombre del municipio.

    La API devuelve municipios donde a veces el nombre coincide con la provincia
    (p. ej. "Santa Cruz de Tenerife"). Se evita "Municipio · Municipio · CCAA":
    solo se añaden provincia y comunidad si aportan algo nuevo.
    """
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


def _unmatched_prefs(row: dict) -> list[str]:
    """Preferencias pedidas que el destino no cumple. `matched: null` no cuenta:
    el motor entrenado marca null cuando no tiene dato, no un incumplimiento."""
    match = row.get("preference_match") or {}
    labels = {
        "sunny_days": "días de sol",
        "precipitation_days": "días de lluvia",
        "popularity": "popularidad",
    }
    return [
        labels.get(key, key)
        for key, value in match.items()
        if isinstance(value, dict) and value.get("matched") is False
    ]


# --------------------------------------------------------------------------
# Formulario
# --------------------------------------------------------------------------

def _render_form() -> dict | None:
    """Formulario de preferencias. Devuelve el payload si se ha enviado."""
    defaults = reco.default_request()

    with st.form("reco_form"):
        c1, c2, c3 = st.columns([1.1, 1, 1])
        month = c1.selectbox(
            "Mes del viaje",
            list(range(1, 13)),
            index=defaults["month"] - 1,
            format_func=reco.month_name,
        )
        trip_length = c2.number_input(
            "Duración (días)",
            min_value=reco.TRIP_LENGTH_RANGE[0],
            max_value=reco.TRIP_LENGTH_RANGE[1],
            value=defaults["trip_length_days"],
            step=1,
            help="La API admite viajes de 1 a 30 días.",
        )
        accommodation = c3.selectbox(
            "Alojamiento",
            reco.ACCOMMODATION_TYPES,
            index=reco.ACCOMMODATION_TYPES.index(defaults["accommodation_type"]),
            format_func=lambda code: reco.ACCOMMODATION_LABELS[code],
        )

        interests = st.multiselect(
            "Intereses",
            reco.INTERESTS,
            default=defaults["interests"],
            format_func=reco.interest_label,
            help="Selecciona al menos uno. Estos son los intereses que acepta el motor.",
        )

        c4, c5, c6 = st.columns(3)
        temperature = c4.selectbox(
            "Temperatura preferida",
            reco.TEMPERATURE_PREFERENCES,
            index=reco.TEMPERATURE_PREFERENCES.index(defaults["temperature_preference"]),
            format_func=lambda code: reco.TEMPERATURE_LABELS[code],
        )
        min_sunny = c5.slider(
            "Mínimo de días soleados / mes",
            reco.SUNNY_DAYS_RANGE[0], reco.SUNNY_DAYS_RANGE[1],
            defaults["minimum_sunny_days"],
        )
        max_precip = c6.slider(
            "Máximo de días de lluvia / mes",
            reco.PRECIPITATION_DAYS_RANGE[0], reco.PRECIPITATION_DAYS_RANGE[1],
            defaults["maximum_precipitation_days"],
        )

        popularity = st.slider(
            "Objetivo de popularidad",
            0.0, 1.0, defaults["popularity_target"], 0.05,
            help="0 = destinos poco conocidos · 1 = destinos muy conocidos. "
                 "El motor busca proximidad a este valor, no el máximo.",
        )

        with st.expander("Filtros de región", expanded=False):
            fc1, fc2 = st.columns(2)
            include_regions = fc1.multiselect(
                "Incluir solo estas comunidades", reco.AUTONOMOUS_COMMUNITIES
            )
            exclude_regions = fc2.multiselect(
                "Excluir comunidades", reco.AUTONOMOUS_COMMUNITIES
            )
            st.caption(
                "Si los filtros dejan menos de tres destinos disponibles, la API "
                "rechaza la petición con un aviso explícito."
            )

        submitted = st.form_submit_button(
            "Pedir recomendaciones", type="primary", width="stretch"
        )

    if not submitted:
        return None

    errors = reco.validate_request(
        month=month,
        trip_length_days=int(trip_length),
        interests=interests,
        temperature_preference=temperature,
        minimum_sunny_days=min_sunny,
        maximum_precipitation_days=max_precip,
        popularity_target=popularity,
        accommodation_type=accommodation,
    )
    if errors:
        for message in errors:
            st.error(message)
        return None

    return reco.build_payload(
        month=month,
        trip_length_days=int(trip_length),
        interests=interests,
        temperature_preference=temperature,
        minimum_sunny_days=min_sunny,
        maximum_precipitation_days=max_precip,
        popularity_target=popularity,
        accommodation_type=accommodation,
        include_regions=include_regions,
        exclude_regions=exclude_regions,
    )


# --------------------------------------------------------------------------
# Hero: la recomendación principal
# --------------------------------------------------------------------------

def _hero_facts(row: dict) -> list[tuple[str, str]]:
    climate = row.get("climate_profile") or {}
    offers = row.get("what_it_offers") or {}
    popularity = row.get("popularity_profile") or {}
    facts = [
        (_fmt(climate.get("sunny_days"), decimals=0), "Días de sol"),
        (_fmt(climate.get("temperature_mean_c"), "°", 0), "Temp. media"),
        (_fmt(offers.get("poi_count"), decimals=0), "Puntos de interés"),
    ]
    if popularity.get("index") is not None:
        facts.append((_fmt(popularity.get("index"), decimals=2), "Popularidad"))
    return facts


def _render_hero(row: dict, payload: dict) -> None:
    destination = row.get("destination") or {}
    name = str(destination.get("name") or "Destino sin nombre")
    place = _place(destination)
    typology = destination.get("primary_typology")

    why = str(row.get("headline") or "")
    strengths = [str(s) for s in (row.get("strengths") or [])]
    if not why and strengths:
        why = strengths[0]

    travel = payload.get("travel") or {}
    month = reco.month_name(travel.get("month", 1))
    days = travel.get("trip_length_days")
    interests = [
        reco.interest_label(code)
        for code in (payload.get("preferences", {}).get("interests") or [])
    ]
    chips = [f"{month} · {days} días"] + interests
    tradeoffs = [str(s) for s in (row.get("tradeoffs") or [])]

    photo = _photo(row)
    parts = ['<div class="offer">']

    # --- Banner de la oferta: imagen a todo el ancho con el titular montado ---
    if photo:
        parts.append(
            f'<div class="offer-media" style="background-image:'
            f'url(&quot;{escape(photo["url"], quote=True)}&quot;)">'
        )
    else:
        parts.append('<div class="offer-media offer-media--empty">')
    parts.append('<div class="offer-media-veil"></div>')
    parts.append('<div class="offer-flag">Recomendado para ti</div>')
    parts.append('<div class="offer-media-caption">')
    parts.append(f'<h2 class="offer-name">{escape(name)}</h2>')
    if place:
        parts.append(f'<div class="offer-place">📍 {escape(place)}</div>')
    parts.append('</div>')  # caption
    parts.append('</div>')  # media

    # --- Panel de la oferta: motivo, contexto y datos, estilo comercial ---
    parts.append('<div class="offer-body">')
    if typology:
        parts.append(f'<span class="offer-typology">{escape(str(typology))}</span>')
    if why:
        parts.append(f'<p class="offer-why">{escape(why)}</p>')

    parts.append('<div class="offer-chips">')
    parts.append("".join(f'<span class="offer-chip">{escape(c)}</span>' for c in chips))
    for tradeoff in tradeoffs[:1]:
        parts.append(f'<span class="offer-chip warn">⚠ {escape(tradeoff)}</span>')
    parts.append('</div>')

    parts.append('<div class="offer-facts">')
    for value, label in _hero_facts(row):
        parts.append(
            f'<div class="offer-fact"><div class="offer-fact-value">{escape(str(value))}</div>'
            f'<div class="offer-fact-label">{escape(label)}</div></div>'
        )
    parts.append('</div>')
    parts.append('</div>')  # body
    parts.append('</div>')  # offer

    st.markdown("".join(parts), unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Tarjeta galería: cada una de las otras opciones
# --------------------------------------------------------------------------

def _card_html(row: dict, idx: int) -> str:
    """Devuelve el HTML de una tarjeta de alternativa (no la renderiza).

    Se construye como string para poder concatenar todas las tarjetas en un
    único ``st.markdown`` (rejilla CSS), en vez de usar ``st.columns`` con un
    número variable de columnas: ese patrón disparaba el error removeChild de
    React al repintar tras un rerun.
    """
    destination = row.get("destination") or {}
    climate = row.get("climate_profile") or {}
    offers = row.get("what_it_offers") or {}

    name = str(destination.get("name") or "Destino")
    place = _place(destination)
    typology = destination.get("primary_typology")

    parts = ['<div class="reco-card">']

    # Banner: la imagen ocupa todo el ancho, pegada al borde, con chip de ranking.
    parts.append('<div class="reco-photo-wrap">')
    photo = _photo(row)
    if photo:
        alt = photo.get("alt") or f"Imagen de {name}"
        parts.append(
            f'<img class="reco-photo" src="{escape(photo["url"], quote=True)}" '
            f'alt="{escape(alt, quote=True)}" loading="lazy">'
        )
    else:
        parts.append(f'<div class="reco-photo-fallback">{escape(name)}</div>')
    parts.append('<div class="reco-photo-veil"></div>')
    parts.append(f'<div class="reco-rank-badge">Opción {row.get("rank", idx + 1)}</div>')
    # Nombre y lugar montados sobre la imagen, estilo tarjeta de viaje.
    parts.append('<div class="reco-photo-caption">')
    parts.append(f'<div class="reco-name">{escape(name)}</div>')
    if place:
        parts.append(f'<div class="reco-place">📍 {escape(place)}</div>')
    parts.append('</div>')  # cierra caption
    parts.append('</div>')  # cierra photo-wrap

    # Cuerpo: todo visible, sin desplegables, para comparar de un vistazo.
    parts.append('<div class="reco-body">')

    if typology:
        parts.append(f'<span class="reco-typology">{escape(str(typology))}</span>')
    if row.get("headline"):
        parts.append(f'<p class="reco-headline">{escape(str(row["headline"]))}</p>')

    # Tres datos objetivos, en rejilla compacta.
    parts.append('<div class="reco-facts">')
    for value, label in (
        (_fmt(climate.get("sunny_days"), decimals=0), "Días de sol"),
        (_fmt(climate.get("temperature_mean_c"), "°", 0), "Temp. media"),
        (_fmt(offers.get("poi_count"), decimals=0), "Puntos interés"),
    ):
        parts.append(
            f'<div class="reco-fact"><div class="reco-fact-value">{escape(str(value))}</div>'
            f'<div class="reco-fact-label">{escape(label)}</div></div>'
        )
    parts.append('</div>')

    # Motivos como chips.
    reasons = [reco.reason_label(str(c)) for c in (row.get("reason_codes") or [])]
    if reasons:
        parts.append('<div class="reco-block-title">Por qué encaja</div>')
        parts.append('<div class="reco-chips">' + "".join(_chip(r, "ok") for r in reasons[:4]) + '</div>')

    # Fortalezas, en lista corta.
    strengths = [str(s) for s in (row.get("strengths") or [])]
    if strengths:
        parts.append('<div class="reco-block-title">Fortalezas</div>')
        parts.append(
            '<ul class="reco-list">'
            + "".join(f'<li>{escape(s)}</li>' for s in strengths[:3])
            + '</ul>'
        )

    # (El desglose del score no se muestra en las opciones 2 y 3: recarga la
    # tarjeta y no aporta a la decisión rápida. Queda solo en la destacada.)

    # Concesiones: lo que el destino no cumple del todo.
    tradeoffs = [str(s) for s in (row.get("tradeoffs") or [])]
    unmatched = _unmatched_prefs(row)
    concessions = tradeoffs[:2]
    if unmatched:
        concessions.append("No cumple: " + ", ".join(unmatched))
    if concessions:
        parts.append('<div class="reco-block-title">A tener en cuenta</div>')
        parts.append(
            '<div class="reco-chips">'
            + "".join(_chip(c, "warn") for c in concessions)
            + '</div>'
        )

    parts.append('</div>')  # cierra body
    parts.append('</div>')  # cierra card
    return "".join(parts)


# --------------------------------------------------------------------------
# Orquestación
# --------------------------------------------------------------------------

def _render_alternatives(result: dict) -> None:
    ranking = result.get("ranking") or []
    cards = ranking[1:]
    if not cards:
        return
    # Todas las tarjetas en UN SOLO bloque HTML (rejilla CSS), no en st.columns
    # de número variable: ese patrón rompía el DOM de React (removeChild).
    grid = '<div class="alt-grid">' + "".join(
        _card_html(row, position + 1) for position, row in enumerate(cards)
    ) + "</div>"
    st.markdown(
        '<div class="alt-title">Otras opciones que encajan</div>' + grid,
        unsafe_allow_html=True,
    )

    footer_bits = []
    if result.get("recommendation_id"):
        footer_bits.append(f"ID de recomendación: {result['recommendation_id']}")
    if result.get("generated_at"):
        footer_bits.append(f"generada el {str(result['generated_at']).replace('T', ' ')[:19]}")
    if footer_bits:
        st.caption(" · ".join(footer_bits))


def _render_error(result: dict) -> None:
    kind = result.get("error_kind")
    message = str(result.get("error") or "Error desconocido.")
    if kind == "validation":
        st.warning(message)
    elif kind == "not_configured":
        st.info(message)
    else:
        st.error(message)

    if kind == "not_configured":
        st.markdown(
            "Configura el endpoint en `.streamlit/secrets.toml` (hay una plantilla "
            "en `.streamlit/secrets.toml.example`) o como variables de entorno:"
        )
        st.code(
            'TUI_RECO_API_URL = "https://<function-app>.azurewebsites.net/api/recommendations?code=<clave>"',
            language="toml",
        )


def _run(payload: dict, is_custom: bool) -> dict:
    """Llama a la API, guarda el resultado en sesión y registra el evento."""
    # El modelo corre en la nube con arranque en frío: la primera consulta del
    # día puede tardar. Se avisa para que la espera no parezca un cuelgue.
    with st.spinner(
        "Consultando el modelo de recomendaciones… "
        "La primera consulta puede tardar unos segundos mientras el servicio "
        "despierta."
    ):
        result = reco.fetch_recommendations(payload)
    st.session_state[STATE_KEY] = result
    st.session_state[STATE_PAYLOAD] = payload
    st.session_state[STATE_CUSTOM] = is_custom

    register_event(
        st.session_state.session_id,
        "recommendation_request",
        VIEW_LABEL,
        metadata={
            "ok": bool(result.get("ok")),
            "error_kind": result.get("error_kind"),
            "origin": "formulario" if is_custom else "automatica",
            "month": payload["travel"]["month"],
            "trip_length_days": payload["travel"]["trip_length_days"],
            "interests": payload["preferences"]["interests"],
            "recommendation_id": result.get("recommendation_id"),
            "engine_version": (result.get("engine") or {}).get("version"),
        },
    )
    return result


def _autorun_if_needed() -> None:
    """Pide una recomendación por defecto la primera vez que se abre la vista."""
    if st.session_state.get(STATE_AUTORUN):
        return
    st.session_state[STATE_AUTORUN] = True
    defaults = reco.default_request()
    _run(
        reco.build_payload(
            month=defaults["month"],
            trip_length_days=defaults["trip_length_days"],
            interests=defaults["interests"],
            temperature_preference=defaults["temperature_preference"],
            minimum_sunny_days=defaults["minimum_sunny_days"],
            maximum_precipitation_days=defaults["maximum_precipitation_days"],
            popularity_target=defaults["popularity_target"],
            accommodation_type=defaults["accommodation_type"],
        ),
        is_custom=False,
    )


def _render_advanced_form() -> None:
    """Expander compacto con el formulario de filtros (modelo real Azure).

    Vive ENCIMA de los resultados, en la columna derecha. Al enviar, corre la
    petición real contra el motor y refresca el ranking mostrado debajo.
    """
    if not reco.is_configured():
        with st.expander("🔍 Ajustar filtros a mano", expanded=False):
            _render_error({
                "error_kind": "not_configured",
                "error": "El recomendador no está conectado.",
            })
            st.caption("Este es el contrato que se enviaría al motor:")
            _render_form()
        return

    with st.expander("🔍 Ajustar filtros y recalcular el ranking", expanded=False):
        st.caption(
            "¿Prefieres afinar a mano? Ajusta mes, intereses y clima y el motor "
            "vuelve a proponerte destinos."
        )
        new_payload = _render_form()
        if new_payload is not None:
            _run(new_payload, is_custom=True)
            st.rerun()


def _render_featured(result: dict) -> None:
    """Recomendación destacada (hero) para la columna junto al chat."""
    ranking = result.get("ranking") or []
    if not (result.get("ok") and ranking):
        if result and not result.get("ok"):
            _render_error(result)
        elif not reco.is_configured():
            st.info(
                "Conecta el modelo para ver aquí, junto al chat, la recomendación "
                "destacada y sus alternativas."
            )
        return
    if not st.session_state.get(STATE_CUSTOM):
        st.caption(
            "Propuesta con preferencias por defecto. Ajusta los filtros de "
            "arriba para adaptarla a tu viaje."
        )
    _render_hero(ranking[0], payload=st.session_state.get(STATE_PAYLOAD) or {})


def render_recommender() -> None:
    st.markdown(
        '<div class="reco-header">'
        '<div class="reco-kicker">España</div>'
        '<h2 class="reco-hero-title"><em>Recomendador</em> de viajes '
        'por España</h2>'
        '<p class="reco-hero-lead">Cuéntale al asistente cómo te gusta viajar '
        '—el ambiente, las fechas, con quién vas— y te irá enseñando destinos '
        'que encajan contigo, con el motivo de cada elección.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Precalcula una recomendación por defecto (autorun) para que la vista tenga
    # contenido en cuanto se abre, sin pantallas vacías. Sin API no se lanza el
    # modelo real (se informa).
    if reco.is_configured():
        _autorun_if_needed()

    result = st.session_state.get(STATE_KEY) or {}
    ranking = result.get("ranking") or []

    # Fila superior: dos columnas a la vista, sin scroll largo.
    #   · Izquierda: el copiloto de viaje (chat maqueta).
    #   · Derecha: la recomendación destacada del modelo + filtros.
    # No se envuelven los widgets en <div> propios: hacerlo rompe el árbol DOM
    # de React que gestiona Streamlit (error removeChild). El estilo compacto se
    # aplica por clase directamente en el HTML de cada bloque.
    # Disposición VERTICAL: primero el copiloto de viaje (chat), y DEBAJO toda
    # la sección "Recomendación del modelo" (filtros + destacada + alternativas)
    # a todo el ancho.
    render_recommender_chat()

    # Separador visual entre la conversación (arriba) y la recomendación del
    # modelo (abajo), para que el paso de una zona a otra sea claro.
    st.markdown('<div class="reco-section-sep"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="reco-results-title">Recomendación del modelo</div>'
        '<div class="reco-results-sub">La propuesta destacada del motor para tu '
        'perfil, con dos alternativas que también encajan.</div>',
        unsafe_allow_html=True,
    )
    _render_advanced_form()
    _render_featured(result)
    if result.get("ok") and len(ranking) > 1:
        _render_alternatives(result)
