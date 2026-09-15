from __future__ import annotations

"""Seguimiento de clics en las llamadas a la acción («Ver opciones») de las
recomendaciones.

Las tarjetas de recomendación enlazan a la web pública de TUI. Un enlace
externo abierto en una pestaña nueva no puede medirse desde Streamlit sin
JavaScript, así que se usa el patrón estándar de *click-through*: el enlace
apunta primero a la propia app con unos parámetros de consulta; la app registra
el clic y reenvía el navegador al destino real de TUI.

Esto NO altera la lógica de recomendación ni los filtros: solo observa que el
usuario pulsó «Ver opciones» sobre un destino concreto. Es la instrumentación
mínima necesaria para medir CTR y clics por destino en «Monitor performance».
"""

from html import escape
from urllib.parse import quote, urlencode

import streamlit as st

from services.tracking_service import register_event

# Destino externo real de las tarjetas (idéntico al que ya usaban los <a>).
def _url_destino(destination: str) -> str:
    """Link de busqueda de TUI para el destino especifico, no la portada
    generica -- cada tarjeta debe llevar a resultados de ESE destino."""
    from urllib.parse import quote as _quote
    return f"https://es.tui.com/es/resultados/{_quote(destination)}/"

# Nombres de los parámetros de consulta del click-through.
_PARAM_CLICK = "rc"          # destino sobre el que se hizo clic
_PARAM_RECO_ID = "rid"       # id de la recomendación (para unir con impresiones)
_PARAM_POSITION = "rpos"     # posición en el ranking (1 = destacada)
_PARAM_ORIGIN = "rorig"      # origen: explora / asistente


def build_click_href(destination: str, recommendation_id: str = "",
                     position: int | None = None, origin: str = "") -> str:
    """Construye el enlace de la CTA que pasa por el rastreador y luego redirige.

    Mantener ``target="_blank"`` en el ``<a>`` haría que el registro ocurriese en
    una pestaña nueva; por eso las CTAs instrumentadas abren en la misma pestaña
    (la app reaparece un instante y reenvía a TUI). El comportamiento observable
    para el usuario sigue siendo «pulsar y llegar a TUI».
    """
    params = {_PARAM_CLICK: destination or ""}
    if recommendation_id:
        params[_PARAM_RECO_ID] = recommendation_id
    if position is not None:
        params[_PARAM_POSITION] = str(position)
    if origin:
        params[_PARAM_ORIGIN] = origin
    return "?" + urlencode(params, quote_via=quote)


def handle_pending_click() -> None:
    """Si la URL trae un click-through pendiente, lo registra y redirige a TUI.

    Se llama una sola vez al arrancar la app, antes de pintar cualquier vista.
    Tras registrar el evento limpia los parámetros y hace un ``meta refresh`` al
    destino real, de modo que el usuario acaba en la web de TUI como esperaba.
    """
    params = st.query_params
    destination = params.get(_PARAM_CLICK)
    if not destination:
        return

    recommendation_id = params.get(_PARAM_RECO_ID, "") or ""
    origin = params.get(_PARAM_ORIGIN, "") or ""
    position_raw = params.get(_PARAM_POSITION, "") or ""
    try:
        position = int(position_raw) if position_raw else None
    except (TypeError, ValueError):
        position = None

    session_id = st.session_state.get("session_id")
    if session_id:
        register_event(
            session_id,
            "recommendation_click",
            origin or "recomendador",
            destination=str(destination),
            metadata={
                "recommendation_id": recommendation_id,
                "position": position,
                "origin": origin,
                "target_url": _url_destino(str(destination)),
            },
            # Un mismo click-through (misma reco + posición + destino) cuenta una
            # vez por sesión: recargar la URL de redirección no infla el CTR.
            dedupe_key=f"reco_click:{recommendation_id}:{position}:{destination}",
        )

    # Limpia los parámetros para que un rerun posterior no vuelva a disparar.
    st.query_params.clear()

    # Reenvía el navegador a la búsqueda de TUI para el destino específico
    # que el usuario clickeó (antes iba siempre a la portada genérica).
    url_final = _url_destino(str(destination))
    st.markdown(
        f"""
        <meta http-equiv="refresh" content="0; url={escape(url_final, quote=True)}">
        <p style="font-family:'Gotham',Arial,sans-serif;color:#667085;font-size:.9rem">
          Abriendo TUI...
          <a href="{escape(url_final, quote=True)}">Continuar</a>
        </p>
        """,
        unsafe_allow_html=True,
    )
    st.stop()
