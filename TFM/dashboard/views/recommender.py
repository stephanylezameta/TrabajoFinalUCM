from __future__ import annotations

"""Vista Recomendador España: consume el motor externo vía API.

Esta vista no calcula nada. Envía las preferencias a la API, pinta el ranking que
devuelve y expone su explicabilidad: por qué cada destino aparece, qué señales lo
sostienen, qué concesiones implica y con qué cobertura de datos se ha construido.

El motor es independiente del TDRS: ranquea municipios españoles a partir de
catálogo turístico, OpenStreetMap, señales de YouTube y clima histórico de AEMET.
"""

from html import escape

import pandas as pd
import streamlit as st

from services import recommendation_api_service as reco
from services.destination_image_service import get_destination_image
from services.tracking_service import register_event

VIEW_LABEL = "Recomendador España"
STATE_KEY = "reco_result"
STATE_PAYLOAD = "reco_payload"
STATE_AUTORUN = "reco_autorun_done"
STATE_CUSTOM = "reco_is_custom"


def _chip(text: str, kind: str = "") -> str:
    css = f"reco-chip {kind}".strip()
    return f'<span class="{css}">{escape(text)}</span>'


def _fmt(value, suffix: str = "", decimals: int = 1) -> str:
    """Formatea un número respetando la regla de que un dato ausente es `—`."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:,.{decimals}f}{suffix}"
    return str(value)


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
            help="Selecciona al menos uno. Estos son los siete intereses que acepta el motor.",
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


def _render_card(row: dict, idx: int) -> None:
    destination = row.get("destination") or {}
    climate = row.get("climate_profile") or {}
    offers = row.get("what_it_offers") or {}
    popularity = row.get("popularity_profile") or {}
    confidence = row.get("confidence") or {}
    match = row.get("preference_match") or {}

    name = str(destination.get("name") or "Destino sin nombre")
    place_bits = [destination.get("province"), destination.get("autonomous_community")]
    place = " · ".join(str(b) for b in place_bits if b)
    score = row.get("recommendation_score")
    score_text = "—" if score is None else f"{float(score):.2f}"
    typology = destination.get("primary_typology")

    strengths = [str(s) for s in (row.get("strengths") or [])]
    tradeoffs = [str(s) for s in (row.get("tradeoffs") or [])]
    reasons = [reco.reason_label(str(c)) for c in (row.get("reason_codes") or [])]
    available, total, missing = reco.coverage_summary(row.get("data_coverage"))

    parts: list[str] = [f'<div class="reco-card {"first" if idx == 0 else ""}">']

    photo = _photo(row)
    if photo:
        alt = photo.get("alt") or f"Imagen de {name}"
        parts.append(
            f'<img class="reco-photo" src="{escape(photo["url"], quote=True)}" '
            f'alt="{escape(alt, quote=True)}" loading="lazy">'
        )
    else:
        parts.append(f'<div class="reco-photo-fallback">{escape(name)}</div>')

    parts += [
        '<div class="reco-head"><div class="reco-head-main">',
        f'<div class="reco-rank">opción {row.get("rank", idx + 1)}</div>',
        f'<div class="reco-name">{escape(name)}</div>',
    ]
    if place:
        parts.append(f'<div class="reco-place">{escape(place)}</div>')
    parts.append("</div><div>")
    parts.append(f'<div class="reco-score">{escape(score_text)}</div>')
    parts.append('<div class="reco-score-label">score</div>')
    parts.append("</div></div>")

    if typology:
        parts.append(f'<span class="reco-typology">{escape(str(typology))}</span>')
    if row.get("headline"):
        parts.append(f'<div class="reco-headline">{escape(str(row["headline"]))}</div>')

    # Desglose de las cinco dimensiones del score.
    breakdown = reco.breakdown_rows(row.get("score_breakdown"))
    if breakdown:
        parts.append('<div class="reco-block"><div class="reco-block-title">Desglose del score</div>')
        for item in breakdown:
            parts.append(_bar(str(item["Dimensión"]), item["Valor"]))
        parts.append("</div>")

    # Datos objetivos del destino. Un valor ausente se muestra como `—`.
    parts.append('<div class="reco-block"><div class="reco-block-title">Perfil del destino</div>')
    parts.append('<div class="reco-meta-grid">')
    parts.append(
        f'<div class="reco-meta-item">Días de sol <strong>{_fmt(climate.get("sunny_days"), decimals=1)}</strong></div>'
    )
    parts.append(
        f'<div class="reco-meta-item">Días de lluvia <strong>{_fmt(climate.get("precipitation_days"), decimals=1)}</strong></div>'
    )
    parts.append(
        f'<div class="reco-meta-item">Temp. media <strong>{_fmt(climate.get("temperature_mean_c"), " °C", 1)}</strong></div>'
    )
    parts.append(
        f'<div class="reco-meta-item">Popularidad <strong>{_fmt(popularity.get("index"), decimals=2)}</strong></div>'
    )
    parts.append(
        f'<div class="reco-meta-item">Puntos de interés <strong>{_fmt(offers.get("poi_count"), decimals=0)}</strong></div>'
    )
    parts.append(
        f'<div class="reco-meta-item">Confianza <strong>{escape(reco.confidence_label(confidence.get("level")))}</strong></div>'
    )
    parts.append("</div></div>")

    if reasons:
        parts.append('<div class="reco-block"><div class="reco-block-title">Motivos</div>')
        parts.append('<div class="reco-chips">' + "".join(_chip(r, "ok") for r in reasons) + "</div>")
        parts.append("</div>")

    if strengths:
        parts.append('<div class="reco-block"><div class="reco-block-title">Fortalezas</div>')
        parts.append('<ul class="reco-list">' + "".join(f"<li>{escape(s)}</li>" for s in strengths) + "</ul>")
        parts.append("</div>")

    if tradeoffs:
        parts.append('<div class="reco-block"><div class="reco-block-title">Concesiones</div>')
        parts.append('<ul class="reco-list">' + "".join(f"<li>{escape(s)}</li>" for s in tradeoffs) + "</ul>")
        parts.append("</div>")

    # Trazabilidad: qué fuentes respaldan esta recomendación.
    if total:
        coverage_kind = "ok" if available == total else "warn"
        coverage_chips = [_chip(f"Cobertura {available}/{total}", coverage_kind)]
        coverage_chips += [_chip(f"Falta {name}", "warn") for name in missing]
        parts.append('<div class="reco-block"><div class="reco-block-title">Cobertura de datos</div>')
        parts.append('<div class="reco-chips">' + "".join(coverage_chips) + "</div>")
        parts.append("</div>")

    for warning in row.get("data_warnings") or []:
        parts.append(f'<div class="reco-block"><div class="reco-headline">{escape(str(warning))}</div></div>')

    # Comprobación explícita de si se cumple cada preferencia pedida.
    unmatched = [
        key for key, value in match.items()
        if isinstance(value, dict) and value.get("matched") is False
    ]
    if unmatched:
        labels = {
            "sunny_days": "días de sol",
            "precipitation_days": "días de lluvia",
            "popularity": "popularidad",
        }
        pending = ", ".join(labels.get(k, k) for k in unmatched)
        parts.append(
            f'<div class="reco-block"><div class="reco-chips">{_chip("No cumple: " + pending, "warn")}</div></div>'
        )

    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def _photo(row: dict) -> dict | None:
    """Fotografía del destino, buscada en Wikipedia. Decorativa y opcional.

    Los destinos que devuelve la API son municipios españoles, así que la
    búsqueda acierta casi siempre. Si falla, la tarjeta cae en su fondo sólido.
    """
    destination = (row.get("destination") or {}).get("name")
    if not destination:
        return None
    province = (row.get("destination") or {}).get("province")
    # Añadir la provincia desambigua topónimos repetidos, frecuentes en España.
    return get_destination_image(destination) or (
        get_destination_image(f"{destination} {province}") if province else None
    )


def _score_reading(score: float | None) -> str:
    """Lectura cualitativa del score. Un 0,86 a secas no dice nada al usuario."""
    if score is None:
        return ""
    value = float(score)
    if value >= 0.85:
        return "afinidad muy alta"
    if value >= 0.70:
        return "afinidad alta"
    if value >= 0.50:
        return "afinidad media"
    return "afinidad baja"


def _hero_facts(row: dict) -> list[tuple[str, str]]:
    """Cuatro datos objetivos del destino recomendado, con `—` si faltan."""
    climate = row.get("climate_profile") or {}
    offers = row.get("what_it_offers") or {}
    popularity = row.get("popularity_profile") or {}
    confidence = row.get("confidence") or {}
    return [
        (_fmt(climate.get("sunny_days"), decimals=0), "Días de sol"),
        (_fmt(climate.get("temperature_mean_c"), "°", 0), "Temp. media"),
        (_fmt(offers.get("poi_count"), decimals=0), "Puntos de interés"),
        (reco.confidence_label(confidence.get("level")), "Confianza"),
    ] + (
        [(_fmt(popularity.get("index"), decimals=2), "Popularidad")]
        if popularity.get("index") is not None else []
    )


def _render_hero(row: dict, payload: dict) -> None:
    """Tarjeta principal: la recomendación, legible de un vistazo."""
    destination = row.get("destination") or {}
    name = str(destination.get("name") or "Destino sin nombre")
    place = " · ".join(
        str(b) for b in (destination.get("province"), destination.get("autonomous_community")) if b
    )
    score = row.get("recommendation_score")
    score_text = "—" if score is None else f"{float(score):.2f}"

    # El "por qué" sale de la propia API: primero su titular, y si no, la
    # primera fortaleza. Nunca se redacta aquí una justificación inventada.
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

    # La fotografía va como fondo con degradado encima: da contexto visual sin
    # competir con el texto ni desplazar la información.
    photo = _photo(row)
    if photo:
        overlay = (
            "linear-gradient(180deg, rgba(17,24,39,.34) 0%, rgba(17,24,39,.74) 46%, "
            "rgba(17,24,39,.94) 100%)"
        )
        style = (
            f' style="background-image:{overlay}, '
            f'url(&quot;{escape(photo["url"], quote=True)}&quot;)"'
        )
        parts = [f'<div class="hero-reco has-photo"{style}>']
    else:
        parts = ['<div class="hero-reco">']

    parts.append('<div class="hero-reco-kicker">Destino recomendado</div>')
    parts.append('<div class="hero-reco-top"><div>')
    parts.append(f'<h2 class="hero-reco-name">{escape(name)}</h2>')
    if place:
        parts.append(f'<div class="hero-reco-place">{escape(place)}</div>')
    parts.append('</div><div class="hero-reco-score">')
    parts.append(f'<div class="hero-reco-score-value">{escape(score_text)}</div>')
    parts.append('<div class="hero-reco-score-label">afinidad</div>')
    reading = _score_reading(score)
    if reading:
        parts.append(f'<div class="hero-reco-read">{escape(reading)}</div>')
    parts.append("</div></div>")

    if why:
        parts.append(f'<p class="hero-reco-why">{escape(why)}</p>')

    parts.append('<div class="hero-reco-chips">')
    parts.append("".join(f'<span class="hero-reco-chip">{escape(c)}</span>' for c in chips))
    for tradeoff in tradeoffs[:1]:
        parts.append(f'<span class="hero-reco-chip warn">{escape(tradeoff)}</span>')
    parts.append("</div>")

    parts.append('<div class="hero-reco-facts">')
    for value, label in _hero_facts(row):
        parts.append(
            f'<div class="hero-reco-fact"><div class="hero-reco-fact-value">{escape(str(value))}</div>'
            f'<div class="hero-reco-fact-label">{escape(label)}</div></div>'
        )
    parts.append("</div>")

    # Atribución de la fotografía, como en las tarjetas del simulador.
    if photo and photo.get("credit"):
        parts.append(f'<div class="hero-reco-credit">{escape(str(photo["credit"]))}</div>')
    parts.append("</div>")

    st.markdown("".join(parts), unsafe_allow_html=True)


def _render_result(result: dict, skip_first: bool = False) -> None:
    engine = result.get("engine") or {}
    engine_type = engine.get("type") or "—"
    engine_version = engine.get("version") or "—"
    trained = engine.get("trained_model_used")
    trained_text = "modelo entrenado" if trained else "heurística determinista"
    cached = " · respuesta servida desde caché local" if result.get("from_cache") else ""

    st.markdown(
        f'<div class="reco-engine">Motor <strong>{escape(str(engine_type))}</strong> · '
        f'versión <strong>{escape(str(engine_version))}</strong> · {escape(trained_text)}'
        f'{escape(cached)}</div>',
        unsafe_allow_html=True,
    )

    ranking = result.get("ranking") or []
    if not ranking:
        st.info("La API no ha devuelto destinos para estos criterios.")
        return

    # El primer destino ya se muestra destacado arriba, así que aquí solo van
    # las alternativas. Sin bloque destacado se pintan las tres.
    cards = ranking[1:] if skip_first else ranking
    if cards:
        cols = st.columns(len(cards), gap="medium")
        for position, row in enumerate(cards):
            with cols[position]:
                _render_card(row, position + (1 if skip_first else 0))

    with st.expander("Comparativa en tabla", expanded=False):
        table = pd.DataFrame(reco.ranking_table(ranking))
        st.dataframe(table, width="stretch", hide_index=True)

    warnings = result.get("warnings") or []
    if warnings:
        with st.expander("Advertencias del motor", expanded=False):
            for warning in warnings:
                st.caption(f"· {warning}")

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
            'TUI_RECO_API_BASE = "https://<function-app>.azurewebsites.net/api/recommendations"\n'
            'TUI_RECO_API_KEY = "<function-key>"',
            language="toml",
        )


def _run(payload: dict, is_custom: bool) -> dict:
    """Llama a la API, guarda el resultado en sesión y registra el evento."""
    with st.spinner("Consultando el motor de recomendaciones…"):
        result = reco.fetch_recommendations(payload)
    st.session_state[STATE_KEY] = result
    st.session_state[STATE_PAYLOAD] = payload
    st.session_state[STATE_CUSTOM] = is_custom

    # Trazabilidad de uso: la app registra sus propias interacciones.
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
    """Pide una recomendación por defecto la primera vez que se abre la vista.

    Así el dashboard muestra una recomendación real sin exigir que el usuario
    rellene nada. Solo se hace una vez por sesión, y el cliente cachea la
    respuesta, de modo que no se consume cuota de la API en cada rerun.
    """
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


def render_recommender() -> None:
    st.markdown("### Recomendador de destinos de España")
    st.caption(
        "Motor externo consumido por API. Es independiente del Simulador TDRS: "
        "ranquea municipios españoles combinando catálogo turístico, "
        "OpenStreetMap, señales de YouTube y clima histórico de AEMET. "
        "Devuelve siempre tres destinos con su explicabilidad."
    )

    configured = reco.is_configured()
    if not configured:
        st.caption("Endpoint sin configurar · la vista queda en modo informativo")
        _render_error({
            "error_kind": "not_configured",
            "error": "La API de recomendaciones no está configurada.",
        })
        with st.expander("Ver el contrato que se enviaría", expanded=False):
            _render_form()
        return

    host = reco.endpoint_host()
    if host:
        st.caption(f"Endpoint activo · {host}")

    # La recomendación se muestra sin pedirla: es la respuesta principal de la
    # vista, no el resultado de rellenar un formulario.
    _autorun_if_needed()

    result = st.session_state.get(STATE_KEY) or {}
    payload = st.session_state.get(STATE_PAYLOAD) or {}
    ranking = result.get("ranking") or []

    if result.get("ok") and ranking:
        _render_hero(ranking[0], payload)
        if not st.session_state.get(STATE_CUSTOM):
            st.caption(
                "Recomendación con preferencias por defecto. Ajústalas abajo para "
                "adaptarla a tu viaje."
            )
    elif result and not result.get("ok"):
        _render_error(result)

    # El formulario queda plegado: sirve para refinar, no para empezar.
    with st.expander("Ajustar preferencias", expanded=not ranking):
        new_payload = _render_form()
    if new_payload is not None:
        _run(new_payload, is_custom=True)
        st.rerun()

    if result.get("ok") and ranking:
        st.divider()
        if len(ranking) > 1:
            st.markdown('<div class="alt-title">Otras opciones</div>', unsafe_allow_html=True)
        _render_result(result, skip_first=True)
