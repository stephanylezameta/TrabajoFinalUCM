from __future__ import annotations

import json
import random
from html import escape

import streamlit as st

import unicodedata

from components.assets import SCENARIO_ICON_URLS, get_local_destination_image
from services import price_lookup
from services import recommendation_api_service as reco
from services.tracking_service import register_event
from views.recommender_chat import render_recommender_chat

# Etiqueta interna para el tracking. La vista se llama «España» en el menú, pero
# el evento mantiene un identificador descriptivo y estable.
VIEW_LABEL = "España"

# --------------------------------------------------------------------------
# Normalización para búsqueda de lugares (case + accent insensitive)
# --------------------------------------------------------------------------

def _normalize_place(text: str) -> str:
    """Convierte a minúsculas y elimina diacríticos para comparación."""
    nfkd = unicodedata.normalize("NFKD", str(text).lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# Lista de destinos conocidos: clave normalizada → nombre original para mostrar.
# Se usa en el multiselect de «Excluir lugares»: Streamlit filtra por la clave
# (normalizada, sin tildes ni mayúsculas) y muestra el nombre original.
_DESTINOS_CONOCIDOS_MAP: dict[str, str] = {
    _normalize_place(n): n for n in [
        "Algarve", "Alicante", "Antalya", "Bali", "Barcelona", "Bilbao",
        "Cabo Verde", "Cádiz", "Cancún", "Cerdeña", "Córdoba",
        "Costa Amalfitana", "Creta", "Dubai", "Dubrovnik", "Fuerteventura",
        "Gran Canaria", "Granada", "Hurghada", "Ibiza", "Lanzarote",
        "Madrid", "Málaga", "Maldivas", "Mallorca", "Menorca", "Naxos",
        "Punta Cana", "Rodas", "San Sebastián", "Santorini", "Sevilla",
        "Split", "Tenerife", "Túnez", "Zadar",
    ]
}
STATE_KEY = "reco_result"
STATE_PAYLOAD = "reco_payload"
STATE_AUTORUN = "reco_autorun_done"
STATE_CUSTOM = "reco_is_custom"
STATE_POLICY = "reco_policy"

# --------------------------------------------------------------------------
# Escenarios de redistribución (TDRS) integrados en el recomendador.
# --------------------------------------------------------------------------
# Cada escenario es una forma de pedir al MISMO modelo (la Function de Azure vía
# ``reco.fetch_recommendations``) un reparto distinto de la demanda. La palanca
# central es ``popularity_target`` (0 = destinos menos saturados · 1 = turismo
# tradicional muy visitado); los intereses de referencia se traducen al contrato
# del modelo. Es la tesis del TDRS aplicada sobre el recomendador real.
POLICIES = ("Tradicional", "Equilibrado", "Redistribuido")
DEFAULT_POLICY = "Equilibrado"

POLICY_PRESETS: dict[str, dict] = {
    "Tradicional": {
        # Destinos muy visitados / turismo masivo → objetivo de popularidad bajo
        # (el filtro objetivo_popularidad del API: valores bajos = muy populares/masificados)
        "popularity_target": 0.20,
        "temperature_preference": "warm_sunny",
        "interests": {
            "coast_beach": 90, "history_culture": 60, "gastronomy_wine": 55,
            "nature_mountains": 20, "rural": 10, "wellness": 20, "sports_outdoors": 20,
        },
    },
    "Equilibrado": {
        "popularity_target": 0.50,
        "temperature_preference": "mild",
        "interests": {
            "coast_beach": 60, "history_culture": 60, "gastronomy_wine": 55,
            "nature_mountains": 55, "rural": 40, "wellness": 40, "sports_outdoors": 40,
        },
    },
    "Redistribuido": {
        # Destinos poco saturados, máxima redistribución → objetivo de popularidad
        # mucho más bajo que Tradicional
        "popularity_target": 0.05,
        "temperature_preference": "any",
        "interests": {
            "coast_beach": 25, "history_culture": 55, "gastronomy_wine": 60,
            "nature_mountains": 90, "rural": 85, "wellness": 60, "sports_outdoors": 60,
        },
    },
}

# Cada escenario mapea a uno de los iconos empaquetados en assets.
POLICY_ICON_BY_NAME = {
    "Tradicional": "Popular",
    "Equilibrado": "Equilibrado",
    "Redistribuido": "Explorador",
}

# Umbral (0-100) por encima del cual un interés se envía al modelo, y máximo de
# intereses que admite el contrato del recomendador.
_INTEREST_ACTIVE_THRESHOLD = 50
_MAX_INTERESTS = 3


def _current_policy_name() -> str:
    name = st.session_state.get(STATE_POLICY, DEFAULT_POLICY)
    if name not in POLICIES:
        name = DEFAULT_POLICY
        st.session_state[STATE_POLICY] = name
    return name


def _policy_to_payload(policy_name: str) -> dict:
    """Traduce un escenario de redistribución al payload del recomendador.

    Mueve ``popularity_target`` según el escenario y envía los intereses de
    referencia que superan el umbral (máximo tres, como exige el contrato).
    """
    preset = POLICY_PRESETS.get(policy_name, POLICY_PRESETS[DEFAULT_POLICY])
    defaults = reco.default_request()

    weights: dict[str, int] = preset.get("interests") or {}
    interests = [
        code
        for code, weight in sorted(weights.items(), key=lambda kv: -float(kv[1]))
        if code in reco.INTERESTS and float(weight) >= _INTEREST_ACTIVE_THRESHOLD
    ][:_MAX_INTERESTS]
    if not interests:
        interests = list(defaults["interests"])[:_MAX_INTERESTS]

    temperature = preset.get("temperature_preference", defaults["temperature_preference"])
    if temperature not in reco.TEMPERATURE_LABELS:
        temperature = defaults["temperature_preference"]

    # Los escenarios solo mueven la popularidad y los intereses de referencia:
    # el objetivo es explorar el reparto de demanda, no filtrar por precio ni
    # categoría (esos filtros quedan para la búsqueda avanzada del usuario).
    return reco.build_payload(
        interests=interests,
        temperature_preference=temperature,
        popularity_target=max(0.0, min(1.0, float(preset["popularity_target"]))),
    )

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


def _price_txt(value: float | None) -> str | None:
    """Formatea el precio orientativo (p. ej. «1.615 €»), o None si no hay."""
    if value is None:
        return None
    try:
        return f"{float(value):,.0f} €".replace(",", ".")
    except (TypeError, ValueError):
        return None


def _trip_line(price: float | None) -> str:
    """Reservado. Ya no se muestra ni duración ni precio en las tarjetas: los
    montos en euros no eran fiables (precio orientativo derivado) y confundían.
    Devuelve cadena vacía para no pintar nada."""
    return ""


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
    """Fotografía del destino para el banner de la tarjeta.

    Solo imágenes locales (``assets/destinations/*.jpg``). Se prueba por nombre,
    provincia y comunidad, porque el nombre del municipio no siempre coincide con
    el archivo pero la provincia (p. ej. «Málaga») suele existir. No se consultan
    URLs externas ni Wikipedia: si no hay archivo local, la tarjeta cae al
    placeholder sólido.
    """
    destination = row.get("destination") or {}
    for candidate in (
        destination.get("name"),
        destination.get("province"),
        destination.get("autonomous_community"),
    ):
        candidate = str(candidate or "").strip()
        if not candidate:
            continue
        local = get_local_destination_image(candidate)
        if local:
            return local
    return None


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
    """Formulario de preferencias alineado con el contrato del API (/recomendar).

    Campos obligatorios (marcados con *):
      - texto_consulta  → se deriva de «Intereses» (obligatorio)
      - objetivo_popularidad → slider (obligatorio, con valor del escenario activo)

    Campos opcionales:
      - temperature_preference → clima
      - presupuesto_max        → presupuesto
      - categoria              → categoría de experiencia
      - excluir_destinos       → destinos a excluir (text input, coma-separados)
    """
    # Pre-rellena los valores del escenario activo para que el formulario
    # refleje siempre el preset del botón seleccionado.
    preset = POLICY_PRESETS.get(_current_policy_name(), POLICY_PRESETS["Equilibrado"])
    default_popularity = float(preset.get("popularity_target", 0.5))
    default_temp = preset.get("temperature_preference", "any")
    if default_temp not in reco.TEMPERATURE_PREFERENCES:
        default_temp = "any"
    temp_index = list(reco.TEMPERATURE_PREFERENCES).index(default_temp)

    # Intereses por defecto: los que superen el umbral en el preset activo.
    preset_weights: dict[str, int] = preset.get("interests") or {}
    default_interests = [
        code for code, w in sorted(preset_weights.items(), key=lambda kv: -float(kv[1]))
        if code in reco.INTERESTS and float(w) >= _INTEREST_ACTIVE_THRESHOLD
    ][:_MAX_INTERESTS]
    if not default_interests:
        default_interests = [reco.INTERESTS[0]]

    with st.form("reco_form"):
        # --- CAMPO OBLIGATORIO: Intereses → texto_consulta ---
        interests = st.multiselect(
            "Intereses *",
            list(reco.INTERESTS),
            default=default_interests,
            format_func=reco.interest_label,
            placeholder="Selecciona al menos uno",
            help=(
                "Obligatorio. Se traduce a texto_consulta para la búsqueda semántica del motor. "
                "Opciones: " + ", ".join(reco.interest_label(c) for c in reco.INTERESTS)
            ),
        )

        # --- CAMPO OBLIGATORIO: Objetivo de popularidad → objetivo_popularidad ---
        popularity = st.slider(
            "Objetivo de popularidad *",
            0.0, 1.0, default_popularity, 0.05,
            help=(
                "Obligatorio. 0.0 = destinos muy masificados/populares · "
                "1.0 = destinos alternativos poco saturados. "
                "El motor busca proximidad a este valor."
            ),
        )

        c1, c2 = st.columns(2)

        # --- Temperatura preferida (opcional) ---
        temperature = c1.selectbox(
            "Temperatura preferida",
            list(reco.TEMPERATURE_PREFERENCES),
            index=temp_index,
            format_func=lambda code: reco.TEMPERATURE_LABELS[code],
            help=(
                "Opcional. Opciones: "
                + ", ".join(f"{reco.TEMPERATURE_LABELS[c]} ({c})" for c in reco.TEMPERATURE_PREFERENCES)
            ),
        )

        # --- Categoría de experiencia (opcional, múltiple) → categoria ---
        categorias_sel = c2.multiselect(
            "Categoría de experiencia",
            list(reco.CATEGORIES),
            default=[],
            format_func=lambda code: reco.CATEGORY_LABELS[code],
            placeholder="Cualquiera",
            help=(
                "Opcional. Selecciona una o más categorías. "
                "Opciones: " + ", ".join(reco.CATEGORY_LABELS.values())
            ),
        )
        # Para la llamada al modelo se usa la primera seleccionada (contrato admite una)
        categoria = categorias_sel[0] if categorias_sel else None

        c3, c4 = st.columns(2)

        # --- Presupuesto máximo (opcional) → presupuesto_max ---
        presupuesto = c3.number_input(
            "Presupuesto máximo (€)",
            min_value=0,
            value=None,
            step=50,
            placeholder="Sin límite",
            help="Opcional. Precio orientativo por persona en euros (precio_eur ≤ presupuesto_max).",
        )

        # c4 reservada: el multiselect de excluir lugares va FUERA del st.form
        # (necesita session_state para búsqueda case+accent-insensitive propia).
        c4.empty()

        submitted = st.form_submit_button(
            "Buscar destinos", type="primary", use_container_width=True,
        )

    # --- Excluir lugares: multiselect insensible a tildes ---
    # Cada destino aparece como dos opciones: "Túnez" y "tunez" (normalizada).
    # format_func siempre muestra el nombre original con tilde.
    # Así el usuario puede escribir con o sin tilde y encontrar el mismo lugar.
    # Al enviar al modelo se usa siempre el nombre original.
    _SK_EXCLUIR = "reco_excluir_sel"
    _excluir_prev = [n for n in (st.session_state.get(_SK_EXCLUIR) or [])
                     if n in _DESTINOS_CONOCIDOS_MAP.values()]

    # Opciones: nombre original + alias sin tilde (si difiere del original)
    _opciones_excluir = []
    for _nombre_orig in _DESTINOS_CONOCIDOS_MAP.values():
        _opciones_excluir.append(_nombre_orig)
        _alias = _normalize_place(_nombre_orig)
        if _alias != _nombre_orig.lower():
            _opciones_excluir.append(_alias)

    excluir_sel_raw = st.multiselect(
        "Excluir lugares",
        options=_opciones_excluir,
        default=_excluir_prev,
        format_func=lambda v: _DESTINOS_CONOCIDOS_MAP.get(_normalize_place(v), v),
        placeholder="Escribe o selecciona lugares a excluir…",
        help="Escribe con o sin tildes: tunez y Túnez encuentran lo mismo.",
        key="reco_excluir_multisel",
    )
    # Normalizar selección: convertir alias sin tilde al nombre original
    excluir_sel = list({
        _DESTINOS_CONOCIDOS_MAP.get(_normalize_place(v), v)
        for v in excluir_sel_raw
    })
    st.session_state[_SK_EXCLUIR] = excluir_sel

    if not submitted:
        return None

    if not interests:
        st.error("Selecciona al menos un interés (campo obligatorio).")
        return None

    temperature = temperature or "any"
    presupuesto_max = float(presupuesto) if presupuesto else None
    excluir = list(st.session_state.get(_SK_EXCLUIR) or [])

    errors = reco.validate_request(
        interests=interests,
        temperature_preference=temperature,
        popularity_target=popularity,
        presupuesto_max=presupuesto_max,
        categoria=categoria,
    )
    if errors:
        for message in errors:
            st.error(message)
        return None

    return reco.build_payload(
        interests=interests,
        temperature_preference=temperature,
        popularity_target=popularity,
        presupuesto_max=presupuesto_max,
        categoria=categoria,
        exclude_destinations=excluir,
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
    index = popularity.get("index")
    if index is not None:
        try:
            facts.append((f"{float(index) * 100:.0f}%", "Popularidad"))
        except (TypeError, ValueError):
            pass
    return facts


def _render_hero(row: dict, payload: dict, compact: bool = False) -> None:
    """Tarjeta de oferta destacada (opción 1), al estilo de las ofertas TUI:
    imagen grande con el badge «Oferta TUI», título en azul, línea de duración y
    precio orientativo (si hay), y los datos reales del modelo."""
    destination = row.get("destination") or {}
    name = str(destination.get("name") or "Destino sin nombre")
    place = _place(destination)
    typology = destination.get("primary_typology")

    why = str(row.get("headline") or "")
    strengths = [str(s) for s in (row.get("strengths") or [])]
    if not why and strengths:
        why = strengths[0]

    tradeoffs = [str(s) for s in (row.get("tradeoffs") or [])]

    photo = _photo(row)
    offer_cls = "offer offer--compact" if compact else "offer"
    parts = [f'<div class="{offer_cls}">']

    # --- Banner: imagen a todo el ancho con el badge «Oferta TUI». Se usa un
    # <img> real (no background-image inline): con data URIs largas el
    # background-image con comillas escapadas no cargaba. ---
    if photo:
        alt = photo.get("alt") or f"Imagen de {name}"
        parts.append(
            '<div class="offer-media">'
            f'<img class="offer-media-img" src="{escape(photo["url"], quote=True)}" '
            f'alt="{escape(alt, quote=True)}">'
        )
    else:
        parts.append('<div class="offer-media offer-media--empty">')
    parts.append('<div class="offer-flag">Oferta TUI</div>')
    parts.append('</div>')  # media

    # --- Cuerpo: título, motivo, lugares y datos ---
    parts.append('<div class="offer-body">')
    parts.append(f'<h2 class="offer-name">{escape(name)}</h2>')
    if place:
        parts.append(f'<div class="offer-place">📍 {escape(place)}</div>')

    if typology:
        parts.append(f'<span class="offer-typology">{escape(str(typology))}</span>')
    if why:
        parts.append(f'<p class="offer-why">{escape(why)}</p>')

    # Lo más parecido a una «lista de lugares» que ofrece el modelo: sus
    # fortalezas reales. Si no hay, no se muestra nada.
    if strengths:
        parts.append(
            '<div class="offer-places">'
            + "".join(f'<span class="offer-place-item">{escape(s)}</span>' for s in strengths[:3])
            + '</div>'
        )
    for tradeoff in tradeoffs[:1]:
        parts.append(f'<div class="offer-tradeoff">⚠ {escape(tradeoff)}</div>')

    parts.append('<div class="offer-facts">')
    for value, label in _hero_facts(row):
        parts.append(
            f'<div class="offer-fact"><div class="offer-fact-value">{escape(str(value))}</div>'
            f'<div class="offer-fact-label">{escape(label)}</div></div>'
        )
    parts.append('</div>')

    parts.append('<a class="offer-cta" href="https://es.tui.com/es/" target="_blank" rel="noopener noreferrer">Ver opciones</a>')
    parts.append('</div>')  # body
    parts.append('</div>')  # offer

    st.markdown("".join(parts), unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Tarjeta galería: cada una de las otras opciones
# --------------------------------------------------------------------------

def _card_html(row: dict, idx: int, compact: bool = False, payload: dict | None = None) -> str:
    """HTML de una tarjeta de alternativa (opciones 2, 3…), estilo oferta TUI.

    Se construye como string para concatenar todas las tarjetas en un único
    ``st.markdown`` (rejilla CSS), en vez de usar ``st.columns`` de número
    variable: ese patrón disparaba el error removeChild de React tras un rerun.

    Sigue el mismo patrón que la destacada —imagen con badge «Oferta TUI»,
    título azul, duración y precio orientativo si hay— pero más contenido:
    en modo ``compact`` muestra solo lo esencial (sin motivos ni concesiones).
    """
    payload = payload or {}
    destination = row.get("destination") or {}
    climate = row.get("climate_profile") or {}
    offers = row.get("what_it_offers") or {}

    name = str(destination.get("name") or "Destino")
    place = _place(destination)
    typology = destination.get("primary_typology")

    parts = ['<div class="reco-card">']

    # Banner: imagen a todo el ancho con el badge «Oferta TUI».
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
    # Sin badge "Oferta TUI" en tarjetas alternativas (solo va en la primera opción)
    parts.append('</div>')  # cierra photo-wrap

    # Cuerpo: título azul debajo de la imagen (estilo oferta TUI).
    parts.append('<div class="reco-body">')
    parts.append(f'<div class="reco-name">{escape(name)}</div>')
    if place:
        parts.append(f'<div class="reco-place">📍 {escape(place)}</div>')

    if not compact:
        if typology:
            parts.append(f'<span class="reco-typology">{escape(str(typology))}</span>')
        if row.get("headline"):
            parts.append(f'<p class="reco-headline">{escape(str(row["headline"]))}</p>')

        # Tres datos objetivos del modelo, en rejilla compacta.
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

        # Fortalezas del modelo, como lista corta de "lugares"/motivos.
        strengths = [str(s) for s in (row.get("strengths") or [])]
        if strengths:
            parts.append(
                '<div class="reco-places">'
                + "".join(f'<span class="reco-place-item">{escape(s)}</span>' for s in strengths[:2])
                + '</div>'
            )
        parts.append('<a class="reco-cta" href="https://es.tui.com/es/" target="_blank" rel="noopener noreferrer">Ver opciones</a>')

    parts.append('</div>')  # cierra body
    parts.append('</div>')  # cierra card
    return "".join(parts)


# --------------------------------------------------------------------------
# Orquestación
# --------------------------------------------------------------------------

def _render_alternatives(result: dict, compact: bool = False) -> None:
    ranking = result.get("ranking") or []
    cards = ranking[1:]
    if not cards:
        return
    payload = st.session_state.get(STATE_PAYLOAD) or {}
    # Todas las tarjetas en UN SOLO bloque HTML (rejilla CSS), no en st.columns
    # de número variable: ese patrón rompía el DOM de React (removeChild).
    # En modo compacto (opciones 2 y 3 en la vista del asistente) se añade una
    # clase modificadora a la rejilla y al título para reducir su tamaño; como
    # todo va en el mismo bloque HTML, el escalado por CSS es fiable.
    grid_cls = "alt-grid alt-grid--compact" if compact else "alt-grid"
    title_cls = "alt-title alt-title--compact" if compact else "alt-title"
    grid = f'<div class="{grid_cls}">' + "".join(
        _card_html(row, position + 1, compact=compact, payload=payload)
        for position, row in enumerate(cards)
    ) + "</div>"
    st.markdown(
        f'<div class="{title_cls}">Otras opciones que encajan</div>' + grid,
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

    # El motor a veces no consigue mapear tres destinos distintos a dbo.places
    # (p. ej. filtros muy estrechos o poca cobertura). No es un fallo del
    # sistema: se explica en lenguaje de usuario y se sugiere ampliar filtros.
    low = message.lower()
    if kind == "validation" and (
        "tres destinos" in low
        or "menos de tres" in low
        or ("mapping" in low and "places" in low)
    ):
        st.info(
            "El modelo no encontró tres destinos distintos que encajen con estos "
            "filtros. Prueba a ampliar el rango (menos restricciones de región, "
            "clima o popularidad) para obtener más opciones. Si aun así solo hay "
            "una o dos, se mostrarán igualmente."
        )
        return

    if kind == "validation":
        st.warning(message)
    elif kind == "not_configured":
        st.info(message)
    else:
        st.error(message)

    if kind == "not_configured":
        st.markdown(
            "Configura el endpoint en `.streamlit/secrets.toml` (hay una plantilla "
            "en `.streamlit/secrets.toml.example`) o como variable de entorno:"
        )
        st.code(
            'TUI_MODELO_API_BASE = "https://<app>.azurecontainerapps.io"',
            language="toml",
        )


def _is_too_few_destinations(result: dict) -> bool:
    """Detecta el rechazo del modelo por no mapear tres destinos distintos."""
    if result.get("ok") or result.get("error_kind") != "validation":
        return False
    low = str(result.get("error") or "").lower()
    return (
        "tres destinos" in low
        or "menos de tres" in low
        or ("mapping" in low and "places" in low)
    )


def _relax_payload(payload: dict) -> dict:
    """Afloja la petición para maximizar candidatos: quita exclusiones, el
    filtro de categoría y el de presupuesto. Conserva la consulta de texto y el
    objetivo de popularidad. Sirve para reintentar en el caso (poco habitual con
    la API nueva) de que no lleguen destinos."""
    relaxed = json.loads(json.dumps(payload))  # copia profunda simple
    relaxed["excluir_destinos"] = []
    relaxed.pop("categoria", None)
    relaxed.pop("presupuesto_max", None)
    form = relaxed.setdefault("_form", {})
    form["categoria"] = None
    form["presupuesto_max"] = None
    return relaxed


def _run(payload: dict, is_custom: bool) -> dict:
    """Llama a la API, guarda el resultado en sesión y registra el evento.

    Si el modelo rechaza la petición por no encontrar tres destinos, se reintenta
    UNA vez con los filtros relajados (clima indiferente, sin restricciones de
    región). El contrato admite de 1 a 3 destinos, así que basta con que el
    reintento devuelva al menos uno para no mostrar el error al usuario.
    """
    # El modelo corre en la nube con arranque en frío: la primera consulta del
    # día puede tardar. Se avisa para que la espera no parezca un cuelgue.
    with st.spinner("Consultando el modelo…"):
        result = reco.fetch_recommendations(payload)
        if _is_too_few_destinations(result):
            relaxed = _relax_payload(payload)
            retry = reco.fetch_recommendations(relaxed)
            if retry.get("ok"):
                payload = relaxed
                result = retry
    st.session_state[STATE_KEY] = result
    st.session_state[STATE_PAYLOAD] = payload
    st.session_state[STATE_CUSTOM] = is_custom

    form = payload.get("_form") or {}
    register_event(
        st.session_state.session_id,
        "recommendation_request",
        VIEW_LABEL,
        metadata={
            "ok": bool(result.get("ok")),
            "error_kind": result.get("error_kind"),
            "origin": "formulario" if is_custom else "automatica",
            "interests": form.get("interests"),
            "categoria": form.get("categoria"),
            "presupuesto_max": form.get("presupuesto_max"),
            "objetivo_popularidad": payload.get("objetivo_popularidad"),
            "recommendation_id": result.get("recommendation_id"),
            "engine_version": (result.get("engine") or {}).get("version"),
        },
    )
    return result


def _autorun_if_needed() -> None:
    """Pide una recomendación la primera vez que se abre la vista, usando el
    escenario de redistribución activo (por defecto, «Equilibrado»)."""
    if st.session_state.get(STATE_AUTORUN):
        return
    st.session_state[STATE_AUTORUN] = True
    _run(_policy_to_payload(_current_policy_name()), is_custom=False)


def _render_advanced_form() -> None:
    """Expander compacto con el formulario de filtros (modelo real Azure).

    Vive ENCIMA de los resultados, en la columna derecha. Al enviar, corre la
    petición real contra el motor y refresca el ranking mostrado debajo.
    """
    if not reco.is_configured():
        st.markdown("### Ajustar filtros")
        _render_error({
            "error_kind": "not_configured",
            "error": "El recomendador no está conectado.",
        })
        st.caption("Este es el contrato que se enviaría al motor:")
        _render_form()
        return

    # Una vez que ya hay una recomendación en pantalla, los filtros se colapsan
    # para dar protagonismo al resultado. Mientras no hay resultado, el expander
    # arranca abierto para invitar a ajustar la búsqueda.
    result = st.session_state.get(STATE_KEY) or {}
    has_recommendation = bool(result.get("ok") and (result.get("ranking") or []))
    expander_label = "🔍 Ajustar filtros" if has_recommendation else "🔍 ¿A qué tipo de viaje quieres escaparte?"
    with st.expander(expander_label, expanded=not has_recommendation):
        new_payload = _render_form()
    if new_payload is not None:
        _run(new_payload, is_custom=True)
        st.rerun()


def _render_featured(result: dict, compact: bool = False) -> None:
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
    if not st.session_state.get(STATE_CUSTOM) and not compact:
        st.caption(
            "Propuesta con preferencias por defecto. Ajusta los filtros de "
            "arriba para adaptarla a tu viaje."
        )
    _render_hero(
        ranking[0],
        payload=st.session_state.get(STATE_PAYLOAD) or {},
        compact=compact,
    )


def render_assistant_chat_view() -> None:
    """Vista «Asistente de viajes»: chat a la izquierda, recomendación a la derecha.

    Disposición en dos columnas: el copiloto conversacional
    (``render_recommender_chat``) a la izquierda y la recomendación destacada
    (opción 1) a la derecha. Debajo, a lo ancho y en formato compacto, las
    alternativas (opciones 2 y 3).
    """
    st.markdown(
        '<div class="reco-header">'
        '<div class="reco-kicker reco-kicker--title">TUI Travel Assistant</div>'
        '<p class="reco-hero-lead">Cuéntale al asistente cómo te gusta viajar '
        '—el ambiente, las fechas, con quién vas— y te irá orientando hacia '
        'destinos que encajan contigo, con el motivo de cada elección.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Precalcula una recomendación por defecto (autorun) para que el asistente
    # pueda citar destinos verosímiles del último ranking en sesión.
    if reco.is_configured():
        _autorun_if_needed()

    # Layout de dos columnas: a la IZQUIERDA la conversación (chat) y a la
    # DERECHA la recomendación destacada (opción 1). Las alternativas (opciones
    # 2 y 3) van DEBAJO, a lo ancho y más compactas.
    col_chat, col_reco = st.columns([1.35, 1], gap="large")

    with col_chat:
        render_recommender_chat()

    # El estado se lee DESPUÉS de render_recommender_chat: si el turno del chat
    # produjo (o disparó) una recomendación, aquí ya está actualizada, así la
    # opción 1 (derecha) y las alternativas (abajo) reflejan lo que acaba de
    # decir el asistente y no la propuesta anterior.
    result = st.session_state.get(STATE_KEY) or {}
    ranking = result.get("ranking") or []

    with col_reco:
        if result.get("ok") and ranking:
            _render_featured(result, compact=True)
        else:
            # Estado vacío: invitar al usuario a conversar con el asistente
            st.markdown(
                '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;'
                'min-height:260px;border:1px dashed rgba(17,24,39,.15);border-radius:20px;'
                'background:linear-gradient(180deg,#FBFCFE,#F4F7FA);padding:2rem;text-align:center;">'
                '<div style="font-size:2rem;margin-bottom:.8rem">🌍</div>'
                '<div style="font-size:.95rem;font-weight:700;color:rgb(27,17,92);margin-bottom:.4rem">'
                'Tu recomendación aparecerá aquí</div>'
                '<div style="font-size:.78rem;color:var(--muted);max-width:220px;line-height:1.5">'
                'Cuéntale al asistente qué viaje buscas y te propondrá destinos personalizados.'
                '</div>'
                '</div>',
                unsafe_allow_html=True,
            )

    # Opciones 2 y 3, a lo ancho y en formato compacto (tarjetas más pequeñas
    # para que la opción 1 siga siendo la protagonista).
    if result.get("ok") and len(ranking) > 1:
        _render_alternatives(result, compact=True)


def _render_policy_selector() -> None:
    """Selector de escenario de redistribución (Tradicional / Equilibrado /
    Redistribuido). Al cambiar de escenario, relanza la recomendación contra el
    modelo con el ``popularity_target`` e intereses de ese escenario."""
    current = _current_policy_name()
    with st.container(border=True):
        cols = st.columns(3, gap="medium")
        for idx, name in enumerate(POLICIES):
            icon_url = SCENARIO_ICON_URLS.get(POLICY_ICON_BY_NAME[name], "")
            cols[idx].markdown(
                f'<div class="scenario-icon-wrap">'
                f'<img class="scenario-icon" src="{escape(icon_url, quote=True)}" '
                f'alt="{escape(name, quote=True)}"></div>',
                unsafe_allow_html=True,
            )
            clicked = cols[idx].button(
                name,
                key=f"reco_policy_btn_{name}",
                width="stretch",
                type="primary" if current == name else "secondary",
            )
            if clicked and current != name:
                st.session_state[STATE_POLICY] = name
                _run(_policy_to_payload(name), is_custom=False)
                st.rerun()




def _render_random_placeholder() -> None:
    """Muestra 3 destinos aleatorios como contenido inicial antes de que el
    usuario llame al modelo. Solo se usa cuando no hay resultado en sesión."""
    nombres = list(_DESTINOS_CONOCIDOS_MAP.values())
    muestra = random.sample(nombres, min(3, len(nombres)))

    # Textos de inspiración por destino para el placeholder
    _HEADLINES: dict[str, str] = {
        "Barcelona": "Arquitectura modernista, playa y vida nocturna",
        "Madrid": "Museos de clase mundial y gastronomía sin igual",
        "Sevilla": "Flamenco, tapas y la Giralda bajo el sol andaluz",
        "Granada": "La Alhambra, el Albaicín y noches de tapas gratis",
        "Málaga": "Costa del Sol, Picasso y el mejor boquerón frito",
        "Mallorca": "Calas de agua turquesa y sierra de Tramuntana",
        "Ibiza": "Puestas de sol legendarias y fiestas hasta el alba",
        "Tenerife": "Volcán Teide, playas negras y clima todo el año",
        "Fuerteventura": "Las mejores dunas de Europa y viento para el surf",
        "Lanzarote": "Paisajes volcánicos y arquitectura de César Manrique",
        "Gran Canaria": "Mini continente con playas, cumbres y carnaval",
        "Menorca": "Calas vírgenes, calma y Patrimonio de la Humanidad",
        "Santorini": "Casas blancas, volcán y atardeceres inigualables",
        "Creta": "Minoicos, playas salvajes y cocina mediterránea pura",
        "Dubrovnik": "La Perla del Adriático y escenario de Juego de Tronos",
        "Split": "Palacio de Diocleciano y nightlife junto al mar",
        "Bali": "Templos entre arrozales y olas para todos los niveles",
        "Cancún": "Playas del Caribe y ruinas mayas a un paso",
        "Punta Cana": "Resorts todo incluido en aguas cristalinas",
        "Algarve": "Acantilados dorados y las mejores playas de Portugal",
        "Antalya": "Mar turquesa, ruinas romanas y gastronomía turca",
        "Dubai": "Rascacielos futuristas y desierto en el mismo día",
        "Maldivas": "Bungalows sobre el agua y arrecifes de coral",
        "Cabo Verde": "Capoeira, música morna y playas de arena volcánica",
        "Hurghada": "Mar Rojo, submarinismo y sol garantizado",
        "Túnez": "Medinas declaradas patrimonio y playas del Mediterráneo",
        "Zadar": "Órgano marino y el atardecer más bello del mundo",
        "Rodas": "Ciudad medieval amurallada y 300 días de sol al año",
        "Naxos": "La isla más verde de las Cícladas y queso local",
        "Bilbao": "Guggenheim, pintxos y la ría renovada",
        "San Sebastián": "La Concha, txakoli y la mejor gastronomía de Europa",
        "Cádiz": "La ciudad más antigua de Occidente y carnaval único",
        "Córdoba": "La Mezquita-Catedral y patios llenos de flores",
        "Alicante": "Castillo de Santa Bárbara y playas del Mediterráneo",
        "Cerdeña": "Aguas esmeraldas, nuraghe y queso pecorino",
        "Costa Amalfitana": "Limones, acantilados y pueblos de postal",
    }
    default_headline = "Descubre este destino con TUI"

    cards_html = ""
    for nombre in muestra:
        foto = get_local_destination_image(nombre)
        headline = _HEADLINES.get(nombre, default_headline)
        if foto:
            img_html = (
                f'<img class="reco-photo" src="{escape(foto["url"], quote=True)}" '
                f'alt="{escape(foto["alt"], quote=True)}" loading="lazy">'
            )
        else:
            img_html = f'<div class="reco-photo-fallback">{escape(nombre)}</div>'
        cards_html += (
            f'<div class="reco-card">'
            f'<div class="reco-photo-wrap">{img_html}</div>'
            f'<div class="reco-body">'
            f'<div class="reco-name">{escape(nombre)}</div>'
            f'<p class="reco-headline">{escape(headline)}</p>'
            f'<a class="reco-cta" href="https://es.tui.com/es/" target="_blank" rel="noopener noreferrer">Ver opciones</a>'
            f'</div>'
            f'</div>'
        )
    st.markdown(
        '<div class="alt-title">Inspírate — destinos destacados</div>'
        f'<div class="alt-grid">{cards_html}</div>'
        '<p style="font-size:.72rem;color:var(--muted);margin-top:.6rem">'
        '✦ Ajusta los filtros y pulsa <strong>Buscar destinos</strong> para ver recomendaciones personalizadas.'
        '</p>',
        unsafe_allow_html=True,
    )


def render_recommender() -> None:
    st.markdown(
        '<div class="reco-header">'
        '<div class="reco-kicker">TUI Travel Assistant</div>'
        '<p class="reco-hero-lead">Dinos qué buscas en tu próximo viaje y el motor '
        'te propone los destinos que mejor encajan, con el motivo de cada elección. '
        'Elige un escenario o ajusta los filtros a tu medida.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    _render_policy_selector()

    result = st.session_state.get(STATE_KEY) or {}
    ranking = result.get("ranking") or []

    # Filtros (fijos) + destacada + alternativas. El chat conversacional vive en
    # la vista «Asistente de viajes». No se envuelven los widgets en <div>
    # propios: hacerlo rompe el árbol DOM de React de Streamlit (removeChild).
    _render_advanced_form()

    # Layout horizontal: Opción 1 (mitad izquierda) + opciones secundarias (mitad derecha)
    # Si no hay resultado del modelo todavía, se muestran destinos aleatorios como placeholder.
    if result.get("ok") and ranking:
        col_hero, col_alts = st.columns([1, 1], gap="medium")
        with col_hero:
            _render_featured(result, compact=True)
        with col_alts:
            if len(ranking) > 1:
                _render_alternatives(result, compact=True)
    else:
        _render_random_placeholder()
