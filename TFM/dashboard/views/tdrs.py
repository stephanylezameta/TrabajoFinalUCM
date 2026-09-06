from __future__ import annotations

"""Vista Simulador TDRS: escenarios, pesos, restricciones y asistente lateral."""

from html import escape

import pandas as pd
import streamlit as st

from components.assets import (
    SCENARIO_ICON_URLS,
    get_local_destination_image,
)
from components.ui import render_metric_rows
from services.assistant_service import (
    ai_connection_status,
    build_weights as build_assistant_weights,
    converse as assistant_converse,
    initial_message as assistant_initial_message,
    normalize_preferences as normalize_assistant_preferences,
)
from services.destination_image_service import get_destination_image
from services.tdrs_service import PRESETS, SCENARIO_META, compute_scores, scenario_metrics
from services.tracking_service import register_event

SCENARIOS = ("Popular", "Equilibrado", "Explorador")

MODEL_SLIDER_SUFFIX = {
    "sunny_days_pct": "sunny",
    "low_precipitation_pct": "precip",
    "popularity": "popular",
    "hospital_beds": "beds",
    "safety": "safety",
    "satisfaction": "satisf",
}


def _ensure_tdrs_assistant_state(scenario: str) -> None:
    if "tdrs_assistant_messages" not in st.session_state:
        st.session_state.tdrs_assistant_messages = [
            {"role": "assistant", "content": assistant_initial_message()}
        ]
    if "tdrs_assistant_preferences" not in st.session_state:
        st.session_state.tdrs_assistant_preferences = normalize_assistant_preferences({})
    if "tdrs_assistant_focus" not in st.session_state:
        st.session_state.tdrs_assistant_focus = None
    if "tdrs_assistant_source" not in st.session_state:
        st.session_state.tdrs_assistant_source = "local"

    # Los criterios que aún no se han hablado conservan el preset del escenario
    # activo. Así la conversación puede continuar aunque el usuario cambie de
    # Popular a Equilibrado o Explorador.
    st.session_state.tdrs_assistant_proposal = build_assistant_weights(
        st.session_state.tdrs_assistant_preferences,
        PRESETS[scenario],
    )


def _reset_tdrs_assistant() -> None:
    st.session_state.tdrs_assistant_messages = [
        {"role": "assistant", "content": assistant_initial_message()}
    ]
    st.session_state.tdrs_assistant_preferences = normalize_assistant_preferences({})
    st.session_state.tdrs_assistant_focus = None
    st.session_state.tdrs_assistant_proposal = None
    st.session_state.tdrs_assistant_applied = None
    st.session_state.tdrs_assistant_source = "local"


def _apply_assistant_weights(scenario: str) -> None:
    recommended = st.session_state.get("tdrs_assistant_proposal") or {}
    if not recommended:
        return
    for field, value in recommended.items():
        suffix = MODEL_SLIDER_SUFFIX[field]
        st.session_state[f"sb_{scenario}_{suffix}"] = int(value)
    st.session_state.tdrs_assistant_applied = {
        "scenario": scenario,
        "weights": dict(recommended),
    }
    register_event(
        st.session_state.session_id,
        "assistant_weights_applied",
        "Simulador TDRS · Asistente IA",
        metadata={
            "scenario": scenario,
            "preferences": st.session_state.get("tdrs_assistant_preferences", {}),
            "weights": recommended,
            "assistant_source": st.session_state.get("tdrs_assistant_source", "local"),
        },
    )


def _process_assistant_message(prompt: str, scenario: str) -> None:
    prompt = prompt.strip()
    if not prompt:
        return

    messages = list(st.session_state.get("tdrs_assistant_messages", []))
    messages.append({"role": "user", "content": prompt})
    result = assistant_converse(
        prompt=prompt,
        messages=messages,
        preferences=st.session_state.get("tdrs_assistant_preferences", {}),
        scenario=scenario,
        scenario_defaults=PRESETS[scenario],
        focus_field=st.session_state.get("tdrs_assistant_focus"),
    )
    messages.append({"role": "assistant", "content": result["reply"]})

    st.session_state.tdrs_assistant_messages = messages[-14:]
    st.session_state.tdrs_assistant_preferences = result["preferences"]
    st.session_state.tdrs_assistant_proposal = result["weights"]
    st.session_state.tdrs_assistant_focus = result.get("focus_field")
    st.session_state.tdrs_assistant_source = result.get("source", "local")
    st.session_state.tdrs_assistant_applied = None

    register_event(
        st.session_state.session_id,
        "assistant_message",
        "Simulador TDRS · Asistente IA",
        metadata={
            "scenario": scenario,
            "assistant_source": result.get("source", "local"),
            "missing_preferences": result.get("missing", []),
        },
    )


def render_tdrs_assistant(scenario: str) -> None:
    _ensure_tdrs_assistant_state(scenario)

    with st.sidebar.expander("Asistente IA", expanded=False):
        st.caption(
            "Cuéntame con tus propias palabras qué buscas. El asistente irá "
            "recogiendo tus preferencias y propondrá pesos para el TDRS."
        )
        connection = ai_connection_status()
        messages = st.session_state.get("tdrs_assistant_messages", [])
        has_user_turn = any(m.get("role") == "user" for m in messages)
        last_source = st.session_state.get("tdrs_assistant_source", "local")
        if connection == "connected" and (not has_user_turn or last_source == "ai"):
            st.markdown("🟢 **IA conectada**")
        elif connection == "connected":
            st.markdown("🟠 **IA configurada · último turno resuelto con fallback local**")
        else:
            st.markdown("⚪ **Conector IA preparado · modo local de demostración**")

        # Mostramos los últimos turnos para mantener el lateral compacto.
        for item in messages[-8:]:
            with st.chat_message(item.get("role", "assistant")):
                st.markdown(item.get("content", ""))

        with st.form(f"assistant_chat_form_{scenario}", clear_on_submit=True):
            prompt = st.text_input(
                "Mensaje",
                placeholder="Ej.: quiero sol, seguridad y lugares tranquilos…",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("Enviar", width="stretch")

        if submitted and prompt.strip():
            _process_assistant_message(prompt, scenario)
            st.rerun()

        # No enseñamos una propuesta antes de que el usuario haya conversado.
        proposal = st.session_state.get("tdrs_assistant_proposal") or {}
        if proposal and has_user_turn:
            st.markdown(
                '<div class="assistant-summary"><strong>Propuesta actual</strong><br>'
                f'Sol <strong>{proposal["sunny_days_pct"]}</strong> · '
                f'precipitación <strong>{proposal["low_precipitation_pct"]}</strong> · '
                f'popularidad <strong>{proposal["popularity"]}</strong> · '
                f'sanidad <strong>{proposal["hospital_beds"]}</strong> · '
                f'seguridad <strong>{proposal["safety"]}</strong> · '
                f'satisfacción <strong>{proposal["satisfaction"]}</strong>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.button(
                "Aplicar propuesta al modelo",
                key=f"assistant_apply_{scenario}",
                width="stretch",
                type="primary",
                on_click=_apply_assistant_weights,
                args=(scenario,),
            )

        st.button(
            "Nueva conversación",
            key=f"assistant_reset_{scenario}",
            width="stretch",
            on_click=_reset_tdrs_assistant,
        )

        applied = st.session_state.get("tdrs_assistant_applied")
        if applied and applied.get("scenario") == scenario:
            st.success("La propuesta del asistente ya está aplicada a los pesos del modelo.")


def render_tdrs_sidebar_controls() -> dict:
    """Controles laterales del TDRS, incluido el asistente de personalización."""
    scenario = st.session_state.get("tdrs_scenario", "Equilibrado")
    if scenario not in SCENARIOS:
        scenario = "Equilibrado"
        st.session_state.tdrs_scenario = scenario
    defaults = PRESETS[scenario]

    # El asistente aparece primero y solo existe dentro de la vista Simulador TDRS.
    render_tdrs_assistant(scenario)

    with st.sidebar.expander("Pesos del modelo", expanded=True):
        weights = {
            "sunny_days_pct": st.slider("% días soleados / año", 0, 100, int(defaults["sunny_days_pct"]), key=f"sb_{scenario}_sunny"),
            "low_precipitation_pct": st.slider("% precipitación · menos es mejor", 0, 100, int(defaults["low_precipitation_pct"]), key=f"sb_{scenario}_precip"),
            "popularity": st.slider("Más visitado", 0, 100, int(defaults["popularity"]), key=f"sb_{scenario}_popular"),
            "hospital_beds": st.slider("Capacidad sanitaria", 0, 100, int(defaults["hospital_beds"]), key=f"sb_{scenario}_beds"),
            "safety": st.slider("Seguridad", 0, 100, int(defaults["safety"]), key=f"sb_{scenario}_safety"),
            "satisfaction": st.slider(
                "Satisfacción de viajeros", 0, 100, int(defaults["satisfaction"]),
                key=f"sb_{scenario}_satisf",
                help="Sentimiento medio de reseñas reales analizadas por el pipeline.",
            ),
        }

    with st.sidebar.expander("Restricciones", expanded=True):
        max_price = st.slider("Precio máximo (€)", 400, 2500, 2500, 50, key=f"sb_{scenario}_price")
        max_stay_days = st.slider("Máx. días hospedados", 1, 365, 365, 1, key=f"sb_{scenario}_stay")

    return {
        "scenario": scenario,
        "weights": weights,
        "max_price": max_price,
        "max_stay_days": max_stay_days,
    }


def render_tdrs_scenario_selector() -> None:
    current = st.session_state.get("tdrs_scenario", "Equilibrado")
    if current not in SCENARIOS:
        current = "Equilibrado"
        st.session_state.tdrs_scenario = current

    with st.container(border=True):
        cols = st.columns(3, gap="medium")
        for idx, name in enumerate(SCENARIOS):
            icon_url = SCENARIO_ICON_URLS[name]
            cols[idx].markdown(
                f'<div class="scenario-icon-wrap"><img class="scenario-icon" src="{escape(icon_url, quote=True)}" alt="{escape(name, quote=True)}"></div>',
                unsafe_allow_html=True,
            )
            clicked = cols[idx].button(
                name,
                key=f"tdrs_top_scenario_{name}",
                width="stretch",
                type="primary" if current == name else "secondary",
            )
            if clicked and current != name:
                st.session_state.tdrs_scenario = name
                st.rerun()
        meta = SCENARIO_META[current]
        active_icon = SCENARIO_ICON_URLS[current]
        st.markdown(
            f'<div class="selector-active"><strong><img class="scenario-active-icon" src="{escape(active_icon, quote=True)}" alt="">{escape(current)}</strong> · {escape(meta["description"])}</div>',
            unsafe_allow_html=True,
        )


def render_tdrs(controls: dict) -> None:
    weights = controls["weights"]

    render_tdrs_scenario_selector()

    scenario = controls["scenario"]
    res = compute_scores(
        weights,
        max_price=controls["max_price"],
        max_stay_days=controls["max_stay_days"],
    )

    # Instrumentación: se registra la impresión de los tres destinos del podio.
    # Es interacción real y trazable (el usuario los está viendo recomendados) y
    # alimenta el mapa y los KPIs de Control Web, que sin esto quedaban a cero.
    # El dedupe por escenario evita duplicar en cada rerun.
    for pos, r in enumerate(res["ranked"][:3], 1):
        register_event(
            st.session_state.session_id,
            "product_impression",
            "Simulador TDRS",
            destination=r["name"],
            metadata={"scenario": scenario, "position": pos, "score": round(r["score"], 3)},
            dedupe_key=f"tdrs_impression:{scenario}:{r['name']}",
        )

    # Primero se prepara el ranking para mostrar las tres opciones principales
    # inmediatamente después del selector, sin alterar cálculos, datos ni controles.
    rank_rows = []
    for pos, r in enumerate(res["ranked"], 1):
        model = r.get("model_values") or {}
        raw = r.get("model_raw_values") or {}
        rank_rows.append({
            "Opción": pos,
            "Destino": r["name"],
            "Días soleados %": model.get("sunny_days_pct"),
            "Precipitación %": model.get("precipitation_days_pct"),
            "Pasajeros/año": model.get("annual_passengers"),
            # Se muestra el valor REAL, no el imputado: un destino sin reseñas
            # aparece como `—` aunque el KNN le haya estimado un valor para
            # calcular el score. Es la regla de dato ausente ≠ dato estimado.
            "Satisfacción": raw.get("sentiment_score"),
            "Precio €": r.get("reference_price_eur"),
        })

    # Las tres opciones principales se muestran directamente tras el selector, sin título adicional.
    # El precio queda destacado en la esquina superior derecha del área informativa.
    podium = []
    for idx, row in enumerate(rank_rows[:3]):
        visitors = row.get("Pasajeros/año")
        visitors_text = "—" if visitors is None else f"{int(round(visitors)):,} pasajeros/año"
        price_text = "—" if row.get("Precio €") is None else f"{float(row['Precio €']):,.0f} €"
        destination = str(row["Destino"])
        # Prioridad: fotografía descargada a local (rápida y sin red). Si el
        # destino no la tiene, se busca en Wikipedia y se cachea por proceso.
        image = get_local_destination_image(destination) or get_destination_image(destination)
        if image:
            image_html = (
                f'<img class="podium-image" src="{escape(image["url"], quote=True)}" '
                f'alt="{escape(image.get("alt", f"Imagen de {destination}"), quote=True)}" loading="lazy">'
            )
        else:
            image_html = f'<div class="podium-image-fallback">{escape(destination)}</div>'
        podium.append(
            f'<div class="podium-card {"first" if idx == 0 else ""}">'
            f'{image_html}'
            f'<div class="podium-head">'
            f'<div class="podium-head-main">'
            f'<div class="podium-rank">opción {idx+1}</div>'
            f'<div class="podium-name">{escape(destination)}</div>'
            f'</div>'
            f'<div class="podium-price">{escape(price_text)}</div>'
            f'</div>'
            f'<div class="podium-meta">{escape(visitors_text)}</div>'
            '</div>'
        )
    if podium:
        st.markdown('<div class="podium-grid">' + ''.join(podium) + '</div>', unsafe_allow_html=True)

    # Los KPIs se mantienen exactamente iguales y aparecen debajo de las tres opciones.
    metrics = scenario_metrics(res["ranked"])
    if metrics:
        def fmt(v, suffix="", decimals=1):
            return "—" if v is None else f"{v:.{decimals}f}{suffix}"

        visitors = metrics.get("avg_top5_annual_passengers")
        visitors_text = "—" if visitors is None else (
            f"{visitors/1_000_000:.1f} M/año" if visitors >= 1_000_000 else f"{visitors/1_000:.0f} k/año"
        )
        # La satisfacción se acompaña de cuántos del Top 5 tienen reseñas reales,
        # para que la media no se lea como si toda ella fuese dato observado.
        real = metrics.get("top5_sentiment_real")
        satisfaction = metrics.get("avg_top5_sentiment")
        satisfaction_text = "—" if satisfaction is None else f"{satisfaction:.2f}"
        render_metric_rows([
            ("Elegibles", metrics["eligible"]),
            ("Días soleados Top 5", fmt(metrics.get("avg_top5_sunny_days_pct"), "%", 0)),
            ("Visitantes Top 5", visitors_text),
            ("Satisfacción Top 5", satisfaction_text),
            ("Con reseñas reales", f"{real}/5" if real is not None else "—"),
        ], columns=5)

    remaining_rows = rank_rows[3:] if len(rank_rows) > 3 else rank_rows
    if remaining_rows:
        display = pd.DataFrame(remaining_rows)[[
            "Opción",
            "Destino",
            "Días soleados %",
            "Precipitación %",
            "Pasajeros/año",
            "Satisfacción",
            "Precio €",
        ]]
        # La tabla visible se limita a variables comerciales y de clima.
        # Score, cobertura, sanidad, seguridad y trazabilidad KNN siguen
        # disponibles internamente para el cálculo, pero no se muestran aquí.
        for col in ["Días soleados %", "Precipitación %", "Pasajeros/año", "Satisfacción", "Precio €"]:
            display[col] = display[col].map(
                lambda v, col=col: "—" if pd.isna(v) else (
                    f"{v:,.0f}" if col in {"Pasajeros/año", "Precio €"} else f"{v:.2f}"
                )
            )
        st.dataframe(display, width="stretch", hide_index=True, height=500)
    if res["excluded"]:
        st.warning(
            f"{len(res['excluded'])} destinos quedan fuera por precio o duración conocida del catálogo."
        )
