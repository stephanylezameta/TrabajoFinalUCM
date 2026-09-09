from __future__ import annotations


from html import escape

import streamlit as st

from components.assets import get_local_destination_image
from services import recommendation_api_service as reco

CHAT_HISTORY_KEY = "reco_chat_history"

# Sugerencias de arranque, para que el usuario no mire una caja vacía.
CHAT_SUGGESTIONS = (
    "Una escapada de playa tranquila en septiembre",
    "Naturaleza y senderismo, sin sitios masificados",
    "Cultura y buena gastronomía para un fin de semana",
)

# Catálogo de ejemplo para la maqueta cuando aún no hay resultados reales del
# modo filtros en sesión. Datos plausibles, solo para la vista previa.
_DEMO_DESTINOS = (
    {
        "name": "Cadaqués",
        "province": "Girona",
        "autonomous_community": "Cataluña",
        "typology": "Costa mediterránea",
        "headline": "Pueblo blanco de pescadores con calas de agua limpia y ritmo pausado.",
        "sunny_days": 24,
        "temperature_mean_c": 26,
        "poi_count": 38,
    },
    {
        "name": "Comillas",
        "province": "Cantabria",
        "autonomous_community": "Cantabria",
        "typology": "Costa cantábrica",
        "headline": "Modernismo junto al mar y playas amplias sin aglomeraciones.",
        "sunny_days": 17,
        "temperature_mean_c": 22,
        "poi_count": 29,
    },
    {
        "name": "Ronda",
        "province": "Málaga",
        "autonomous_community": "Andalucía",
        "typology": "Interior monumental",
        "headline": "El Tajo, casco histórico y gastronomía serrana a un paso de la costa.",
        "sunny_days": 27,
        "temperature_mean_c": 28,
        "poi_count": 46,
    },
)


# --------------------------------------------------------------------------
# Datos de tarjeta: preferimos resultados reales del modo filtros en sesión.
# --------------------------------------------------------------------------

def _tarjetas_desde_session_state() -> list[dict]:
    """Convierte el último ranking del modo filtros (si existe) en tarjetas
    compactas. Devuelve lista vacía si no hay resultados en sesión."""
    result = st.session_state.get("reco_result") or {}
    ranking = result.get("ranking") or []
    tarjetas: list[dict] = []
    for row in ranking[:3]:
        destination = row.get("destination") or {}
        name = destination.get("name")
        if not name:
            continue
        climate = row.get("climate_profile") or {}
        offers = row.get("what_it_offers") or {}
        tarjetas.append({
            "name": str(name),
            "province": str(destination.get("province") or ""),
            "autonomous_community": str(destination.get("autonomous_community") or ""),
            "typology": destination.get("primary_typology"),
            "headline": row.get("headline")
            or (row.get("strengths") or [""])[0],
            "sunny_days": climate.get("sunny_days"),
            "temperature_mean_c": climate.get("temperature_mean_c"),
            "poi_count": offers.get("poi_count"),
        })
    return tarjetas


def _tarjetas_demo(limit: int = 2) -> list[dict]:
    return [dict(d) for d in _DEMO_DESTINOS[:limit]]


def _photo_url(name: str, province: str, community: str) -> str | None:
    """Foto del destino desde el archivo local ``.jpg``, sin exponer crédito.

    No se consultan URLs externas ni Wikipedia: si no existe imagen local, la
    tarjeta se muestra sin foto (fondo/placeholder)."""
    local = get_local_destination_image(name)
    if local:
        return local.get("url")
    return None


def _place_line(name: str, province: str, community: str) -> str:
    """Ubicación legible sin repetir el nombre del municipio (mismo criterio
    que ``_place`` del modo filtros)."""
    seen = {name.strip().lower()}
    bits: list[str] = []
    for value in (province, community):
        key = value.strip().lower()
        if value.strip() and key not in seen:
            bits.append(value.strip())
            seen.add(key)
    return " · ".join(bits)


# --------------------------------------------------------------------------
# HTML de una tarjeta de destino compacta, para embeber en el chat.
# --------------------------------------------------------------------------

def _fmt(value, suffix: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, float) and value != value:  # NaN
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:,.0f}{suffix}"
    return escape(str(value))


def _chat_card_html(dest: dict) -> str:
    name = str(dest.get("name") or "Destino")
    province = str(dest.get("province") or "")
    community = str(dest.get("autonomous_community") or "")
    typology = dest.get("typology")
    headline = str(dest.get("headline") or "")
    place = _place_line(name, province, community)
    photo = _photo_url(name, province, community)

    parts = ['<div class="chatreco-card">']

    # Banner: imagen a todo el ancho, pegada a los bordes, esquinas superiores.
    parts.append('<div class="chatreco-media-wrap">')
    if photo:
        parts.append(
            f'<img class="chatreco-media" src="{escape(photo, quote=True)}" '
            f'alt="{escape(f"Imagen de {name}", quote=True)}" loading="lazy">'
        )
    else:
        parts.append(f'<div class="chatreco-media-fallback">{escape(name)}</div>')
    parts.append('<div class="chatreco-media-veil"></div>')
    parts.append('<div class="chatreco-media-caption">')
    parts.append(f'<div class="chatreco-name">{escape(name)}</div>')
    if place:
        parts.append(f'<div class="chatreco-place">📍 {escape(place)}</div>')
    parts.append('</div>')  # caption
    parts.append('</div>')  # media-wrap

    # Cuerpo compacto: tipología, motivo y tres datos.
    parts.append('<div class="chatreco-body">')
    if typology:
        parts.append(f'<span class="chatreco-typology">{escape(str(typology))}</span>')
    if headline:
        parts.append(f'<p class="chatreco-headline">{escape(headline)}</p>')

    parts.append('<div class="chatreco-facts">')
    for value, label in (
        (_fmt(dest.get("sunny_days")), "Días de sol"),
        (_fmt(dest.get("temperature_mean_c"), "°"), "Temp. media"),
        (_fmt(dest.get("poi_count")), "Puntos interés"),
    ):
        parts.append(
            f'<div class="chatreco-fact"><div class="chatreco-fact-value">{value}</div>'
            f'<div class="chatreco-fact-label">{escape(label)}</div></div>'
        )
    parts.append('</div>')  # facts

    parts.append('<button class="chatreco-cta" disabled>Ver esta propuesta</button>')
    parts.append('</div>')  # body
    parts.append('</div>')  # card
    return "".join(parts)


# --------------------------------------------------------------------------
# Simulación del asistente (SOLO MAQUETA). Aquí se enchufaría el /chat real.
# --------------------------------------------------------------------------

def _simular_respuesta_asistente(mensaje_usuario: str) -> dict:
    """Respuesta simulada del asistente: SOLO texto conversacional.

    No embebe tarjetas de destino en el chat para no duplicar visualmente la
    sección "Recomendación del modelo" que aparece debajo (donde la opción 1 es
    la protagonista). El asistente conversa y remite a esa recomendación.
    No hay red ni modelo: es una demostración visual.
    """
    tarjetas = _tarjetas_desde_session_state()
    nombres = ", ".join(t["name"] for t in tarjetas[:3])
    if nombres:
        texto = (
            "He tomado nota de lo que buscas. Con tu perfil encajan destinos "
            f"como {nombres}. Justo abajo tienes la recomendación destacada del "
            "modelo, con su porqué y un par de alternativas. ¿Prefieres priorizar "
            "el buen tiempo, la tranquilidad o la variedad de planes?"
        )
    else:
        texto = (
            "Suena a un viaje estupendo. Ajusta el mes, los intereses y el clima "
            "en «Ajustar filtros» de abajo y el modelo te propondrá los destinos "
            "que mejor encajan, con el motivo de cada elección."
        )

    # Sin tarjetas en el chat: la recomendación visual vive abajo, no duplicada.
    return {"texto": texto, "tarjetas": []}


# --------------------------------------------------------------------------
# Render del historial y de una respuesta del asistente con tarjetas.
# --------------------------------------------------------------------------

def _ensure_history() -> list[dict]:
    """Inicializa el historial con el saludo del asistente la primera vez."""
    history = st.session_state.get(CHAT_HISTORY_KEY)
    if history is None:
        history = [{
            "role": "assistant",
            "text": (
                "¡Hola! Soy tu asistente de viaje de TUI. Cuéntame en tus "
                "palabras qué viaje te apetece —el ambiente, las fechas, con "
                "quién vas— y te propongo destinos por España que encajen."
            ),
            "cards": [],
        }]
        st.session_state[CHAT_HISTORY_KEY] = history
    return history


def _assistant_message_html(msg: dict) -> str:
    """HTML de un turno del asistente: fila con avatar cuadrado + burbuja, y las
    tarjetas de destino embebidas justo debajo. Devuelve string (no renderiza)."""
    text = str(msg.get("text") or "")
    html = (
        '<div class="chatreco-row chatreco-row--bot">'
        '<div class="chatreco-avatar chatreco-avatar--bot">TUI</div>'
        f'<div class="chatreco-bubble chatreco-bubble--bot">{escape(text)}</div>'
        '</div>'
    )
    cards = msg.get("cards") or []
    if cards:
        html += '<div class="chatreco-cards-grid">' + "".join(
            _chat_card_html(dest) for dest in cards
        ) + "</div>"
    return html


def _user_message_html(msg: dict) -> str:
    """HTML de un turno del usuario: burbuja a la derecha + avatar cuadrado."""
    text = str(msg.get("text") or "")
    return (
        '<div class="chatreco-row chatreco-row--user">'
        f'<div class="chatreco-bubble chatreco-bubble--user">{escape(text)}</div>'
        '<div class="chatreco-avatar chatreco-avatar--user">Tú</div>'
        '</div>'
    )


# --------------------------------------------------------------------------
# Punto de entrada de la maqueta del chat.
# --------------------------------------------------------------------------

def render_recommender_chat() -> None:
    history = _ensure_history()
    hay_turnos_usuario = any(m.get("role") == "user" for m in history)

    # TODA la ventana del chat (cabecera + sugerencias + historial completo) se
    # construye como UN ÚNICO bloque HTML y se pinta con un solo st.markdown.
    # Antes cada turno era un st.markdown suelto dentro de un bucle y las
    # sugerencias usaban st.columns condicional: al hacer st.rerun() tras cada
    # mensaje, React tenía que crear/destruir un nº variable de nodos y lanzaba
    # el error removeChild. Con un único nodo HTML, React lo monta de una pieza.
    parts = ['<div class="chatreco-window">']
    parts.append(
        '<div class="chatreco-window-head">'
        '<span class="chatreco-window-dot"></span>'
        '<span class="chatreco-window-title">Asistente de viaje TUI</span>'
        '<span class="chatreco-window-sub">Vista previa · demostración visual</span>'
        '</div>'
    )
    if not hay_turnos_usuario:
        parts.append('<div class="chatreco-suggest-title">Prueba a pedir algo así:</div>')
        parts.append('<div class="chatreco-suggest-chips">')
        parts.append("".join(
            f'<span class="chatreco-suggest-chip">{escape(s)}</span>'
            for s in CHAT_SUGGESTIONS
        ))
        parts.append('</div>')
    for msg in history:
        if msg.get("role") == "assistant":
            parts.append(_assistant_message_html(msg))
        else:
            parts.append(_user_message_html(msg))
    parts.append('</div>')  # cierra chatreco-window
    st.markdown("".join(parts), unsafe_allow_html=True)

    # Entrada del usuario: nativo de Streamlit.
    mensaje = st.chat_input("Escribe qué viaje buscas…")

    if mensaje:
        history.append({"role": "user", "text": mensaje, "cards": []})

        # -----------------------------------------------------------------
        # GANCHO /chat REAL: aquí, en producción, se llamaría al backend en
        # vez de simular. Ver docstring del módulo para el contrato exacto.
        #   respuesta = _llamar_chat_backend(mensaje, history, session_id)
        # De momento, maqueta 100% en cliente:
        # -----------------------------------------------------------------
        respuesta = _simular_respuesta_asistente(mensaje)

        history.append({
            "role": "assistant",
            "text": respuesta["texto"],
            "cards": respuesta["tarjetas"],
        })
        st.session_state[CHAT_HISTORY_KEY] = history
        st.rerun()

    # Pie: reinicio de la conversación de la maqueta.
    if hay_turnos_usuario:
        if st.button("Empezar de nuevo", key="chatreco_reset"):
            st.session_state.pop(CHAT_HISTORY_KEY, None)
            st.rerun()
