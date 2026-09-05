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

from components.ui import render_metric_rows
from services import recommendation_api_service as reco
from services.tracking_service import register_event

VIEW_LABEL = "Recomendador España"
STATE_KEY = "reco_result"
STATE_PAYLOAD = "reco_payload"


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

    parts: list[str] = [
        f'<div class="reco-card {"first" if idx == 0 else ""}">',
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


def _render_result(result: dict) -> None:
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

    scores = [
        float(r["recommendation_score"]) for r in ranking
        if isinstance(r.get("recommendation_score"), (int, float))
    ]
    coverages = [reco.coverage_summary(r.get("data_coverage")) for r in ranking]
    full_coverage = sum(1 for available, total, _ in coverages if total and available == total)
    render_metric_rows([
        ("Destinos propuestos", len(ranking)),
        ("Score máximo", f"{max(scores):.2f}" if scores else "—"),
        ("Con cobertura completa", f"{full_coverage}/{len(ranking)}"),
    ], columns=3)

    cols = st.columns(len(ranking), gap="medium")
    for idx, row in enumerate(ranking):
        with cols[idx]:
            _render_card(row, idx)

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


def render_recommender() -> None:
    st.markdown("### Recomendador de destinos de España")
    st.caption(
        "Motor externo consumido por API. Es independiente del Simulador TDRS: "
        "ranquea municipios españoles combinando catálogo turístico, "
        "OpenStreetMap, señales de YouTube y clima histórico de AEMET. "
        "Devuelve siempre tres destinos con su explicabilidad."
    )

    configured = reco.is_configured()
    host = reco.endpoint_host()
    if configured and host:
        st.caption(f"Endpoint activo · {host}")
    elif not configured:
        st.caption("Endpoint sin configurar · la vista queda en modo informativo")

    payload = _render_form()

    if payload is not None:
        with st.spinner("Consultando el motor de recomendaciones…"):
            result = reco.fetch_recommendations(payload)
        st.session_state[STATE_KEY] = result
        st.session_state[STATE_PAYLOAD] = payload

        # Trazabilidad de uso: la app registra sus propias interacciones.
        register_event(
            st.session_state.session_id,
            "recommendation_request",
            VIEW_LABEL,
            metadata={
                "ok": bool(result.get("ok")),
                "error_kind": result.get("error_kind"),
                "month": payload["travel"]["month"],
                "trip_length_days": payload["travel"]["trip_length_days"],
                "interests": payload["preferences"]["interests"],
                "recommendation_id": result.get("recommendation_id"),
                "engine_version": (result.get("engine") or {}).get("version"),
            },
        )

    result = st.session_state.get(STATE_KEY)
    if not result:
        if configured:
            st.info("Ajusta tus preferencias y pulsa **Pedir recomendaciones**.")
        else:
            _render_error({
                "error_kind": "not_configured",
                "error": "La API de recomendaciones no está configurada.",
            })
        return

    st.divider()
    if result.get("ok"):
        _render_result(result)
    else:
        _render_error(result)
