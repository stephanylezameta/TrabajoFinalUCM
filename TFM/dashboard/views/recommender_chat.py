from __future__ import annotations


from html import escape

import streamlit as st

from components.assets import get_local_destination_image
from services import recommendation_api_service as reco

CHAT_HISTORY_KEY = "reco_chat_history"
# Historial y sesión que mantiene la propia API /chat (formato del backend,
# distinto del historial visual). Se guardan aparte para reenviarlos tal cual.
CHAT_API_HISTORY_KEY = "reco_chat_api_history"
CHAT_SESSION_KEY = "reco_chat_session_id"
# Mensaje del usuario a la espera de respuesta del asistente. Permite pintar el
# turno del usuario al instante y procesar la llamada (lenta) en el rerun
# siguiente, mostrando entretanto un indicador de «escribiendo…».
CHAT_PENDING_KEY = "reco_chat_pending"

# Claves de estado compartidas con views/recommender.py (STATE_KEY / STATE_CUSTOM):
# la tarjeta destacada y las alternativas leen de "reco_result". Al citar
# destinos en el chat, se sobrescriben para que la columna derecha refleje
# exactamente lo recomendado. Se replican como literales para no crear un import
# circular (recommender.py ya importa de este módulo).
RECO_STATE_KEY = "reco_result"
RECO_STATE_CUSTOM = "reco_is_custom"

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
    """Respuesta local de respaldo, cuando la API /chat no está configurada o
    falla. SOLO texto conversacional; no embebe tarjetas para no duplicar la
    sección de recomendación que aparece debajo."""
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
    return {"texto": texto, "tarjetas": []}


def _responder_asistente(mensaje_usuario: str) -> dict:
    """Obtiene la respuesta del asistente. Usa la API real POST /chat si está
    configurada; si no lo está o falla, cae a la respuesta local de respaldo.

    Devuelve {"texto": str, "tarjetas": list}. El chat conversacional del
    backend ya redacta las descripciones de destino en su propio texto, así que
    no se embeben tarjetas (se mantiene la recomendación destacada de abajo como
    apoyo visual)."""
    if not reco.is_configured():
        return _simular_respuesta_asistente(mensaje_usuario)

    api_history = st.session_state.get(CHAT_API_HISTORY_KEY, [])
    session_id = st.session_state.get(CHAT_SESSION_KEY)
    respuesta = reco.chat(mensaje_usuario, historial=api_history, session_id=session_id)

    if not respuesta.get("ok") or not respuesta.get("respuesta"):
        # Sin tumbar la conversación: se responde con el respaldo local.
        return _simular_respuesta_asistente(mensaje_usuario)

    st.session_state[CHAT_API_HISTORY_KEY] = respuesta.get("historial", [])
    st.session_state[CHAT_SESSION_KEY] = respuesta.get("session_id")

    # Sincroniza la recomendación destacada (columna derecha) y las alternativas
    # (2 y 3) con los destinos que el chat acaba de citar. Solo se actualiza si
    # este turno produjo una recomendación estructurada; en turnos meramente
    # conversacionales (preguntas de perfilado) se conserva la última tarjeta.
    reco_result = respuesta.get("reco_result")
    if reco_result and reco_result.get("ok") and (reco_result.get("ranking") or []):
        # El chat citó un ranking estructurado del catálogo: la tarjeta
        # destacada (derecha) y las alternativas (abajo) se sincronizan con ESOS
        # destinos, reordenados para que el #1 de la tarjeta sea el primero que
        # el asistente nombró en su texto (así no se contradicen).
        reco_result = _alinear_con_texto(reco_result, respuesta.get("respuesta") or "")
        st.session_state[RECO_STATE_KEY] = reco_result
        st.session_state[RECO_STATE_CUSTOM] = True
    else:
        # El turno NO trajo un ranking del catálogo (el agente solo hizo una
        # pregunta de perfilado o habló de destinos fuera del catálogo cerrado).
        # Se RETIRA la tarjeta destacada anterior en vez de dejar una que
        # contradiga la conversación: era el origen del "sigue saliendo Túnez"
        # cuando el chat hablaba de otro destino. La tarjeta solo reaparece
        # cuando el chat propone destinos reales del catálogo.
        st.session_state.pop(RECO_STATE_KEY, None)

    return {"texto": respuesta["respuesta"], "tarjetas": []}


def _alinear_con_texto(reco_result: dict, texto_chat: str) -> dict:
    """Reordena el ranking para que el destino que el asistente nombra PRIMERO en
    su texto sea la tarjeta destacada (#1). Evita que el chat hable de un destino
    y la tarjeta de la derecha muestre otro distinto del mismo ranking.

    Solo reordena entre los destinos que YA vienen en el ranking del catálogo; no
    inventa nada. Si no encuentra ninguna coincidencia, deja el orden original."""
    ranking = reco_result.get("ranking") or []
    if len(ranking) < 2 or not texto_chat:
        return reco_result
    texto = texto_chat.lower()

    def _pos(row: dict) -> int:
        nombre = str(((row.get("destination") or {}).get("name")) or "").strip().lower()
        if not nombre:
            return 10**9
        idx = texto.find(nombre)
        return idx if idx >= 0 else 10**9

    reordenado = sorted(ranking, key=_pos)
    if _pos(reordenado[0]) == 10**9:
        # Ningún destino del ranking aparece en el texto: no se toca.
        return reco_result
    nuevo = dict(reco_result)
    for i, row in enumerate(reordenado, start=1):
        row["rank"] = i
    nuevo["ranking"] = reordenado
    return nuevo


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


def _typing_indicator_html() -> str:
    """Burbuja del asistente con tres puntos animados («escribiendo…»),
    mostrada mientras se espera la respuesta del modelo."""
    return (
        '<div class="chatreco-row chatreco-row--bot">'
        '<div class="chatreco-avatar chatreco-avatar--bot">TUI</div>'
        '<div class="chatreco-bubble chatreco-bubble--bot chatreco-typing">'
        '<span class="chatreco-dot"></span>'
        '<span class="chatreco-dot"></span>'
        '<span class="chatreco-dot"></span>'
        '</div>'
        '</div>'
    )


# --------------------------------------------------------------------------
# Punto de entrada de la maqueta del chat.
# --------------------------------------------------------------------------

def render_recommender_chat() -> None:
    history = _ensure_history()
    pendiente = st.session_state.get(CHAT_PENDING_KEY)
    hay_turnos_usuario = any(m.get("role") == "user" for m in history)

    # TODA la ventana del chat (cabecera + sugerencias + historial completo) se
    # construye como UN ÚNICO bloque HTML y se pinta con un solo st.markdown.
    # Antes cada turno era un st.markdown suelto dentro de un bucle y las
    # sugerencias usaban st.columns condicional: al hacer st.rerun() tras cada
    # mensaje, React tenía que crear/destruir un nº variable de nodos y lanzaba
    # el error removeChild. Con un único nodo HTML, React lo monta de una pieza.
    parts = ['<div class="chatreco-window">']
    subtitulo = (
        "Conectado al modelo" if reco.is_configured()
        else "Vista previa · demostración visual"
    )
    parts.append(
        '<div class="chatreco-window-head">'
        '<span class="chatreco-window-dot"></span>'
        '<span class="chatreco-window-title">Asistente de viaje TUI</span>'
        f'<span class="chatreco-window-sub">{escape(subtitulo)}</span>'
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
    # Mientras hay un mensaje pendiente de respuesta, se muestra un indicador de
    # «escribiendo…» (tres puntos animados) en lugar de dejar la UI congelada.
    if pendiente:
        parts.append(_typing_indicator_html())
    # Ancla al final del historial: el script de auto-scroll la usa para dejar
    # visible el último mensaje dentro de la caja con scroll propio.
    parts.append('<div class="chatreco-scroll-anchor"></div>')
    parts.append('</div>')  # cierra chatreco-window
    st.markdown("".join(parts), unsafe_allow_html=True)

    # Auto-scroll: tras cada rerun deja la ventana de chat mostrando el último
    # mensaje (la caja tiene overflow propio, así la página no crece hacia
    # abajo). Se busca en el documento padre porque el markdown se pinta dentro
    # del iframe de Streamlit.
    st.markdown(
        """
        <script>
          (function () {
            const doc = window.parent && window.parent.document
              ? window.parent.document : document;
            const ventanas = doc.querySelectorAll('.chatreco-window');
            const ventana = ventanas[ventanas.length - 1];
            if (ventana) {
              requestAnimationFrame(function () {
                ventana.scrollTop = ventana.scrollHeight;
              });
            }
          })();
        </script>
        """,
        unsafe_allow_html=True,
    )

    # Procesa el mensaje pendiente: ya se ha pintado el turno del usuario y el
    # indicador «escribiendo…», así que ahora sí se llama al asistente (lento)
    # y, al terminar, se hace rerun para mostrar la respuesta.
    if pendiente:
        st.session_state.pop(CHAT_PENDING_KEY, None)
        respuesta = _responder_asistente(pendiente)
        history.append({
            "role": "assistant",
            "text": respuesta["texto"],
            "cards": respuesta["tarjetas"],
        })
        st.session_state[CHAT_HISTORY_KEY] = history
        st.rerun()

    # Pie: reinicio de la conversación.
    if hay_turnos_usuario:
        if st.button("Empezar de nuevo", key="chatreco_reset"):
            st.session_state.pop(CHAT_HISTORY_KEY, None)
            st.session_state.pop(CHAT_API_HISTORY_KEY, None)
            st.session_state.pop(CHAT_SESSION_KEY, None)
            st.session_state.pop(CHAT_PENDING_KEY, None)
            st.rerun()

    # Entrada del usuario: nativo de Streamlit.
    mensaje = st.chat_input("Escribe qué viaje buscas…")

    if mensaje:
        # UX: se pinta el turno del usuario INMEDIATAMENTE y se marca el mensaje
        # como pendiente de responder. El rerun siguiente lo procesa contra la
        # API (que puede tardar), así el usuario ve su mensaje al instante en
        # vez de esperar bloqueado a que el modelo conteste.
        history.append({"role": "user", "text": mensaje, "cards": []})
        st.session_state[CHAT_HISTORY_KEY] = history
        st.session_state[CHAT_PENDING_KEY] = mensaje
        st.rerun()
