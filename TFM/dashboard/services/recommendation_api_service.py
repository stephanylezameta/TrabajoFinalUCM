from __future__ import annotations


import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

# Contrato interno (el que consume la UI). Se mantiene el nombre por
# compatibilidad con los helpers de presentación, aunque ahora el backend real
# es la API FastAPI del motor (endpoint /recomendar) y no la antigua Function.
REQUEST_CONTRACT = "recomendar-request-v1"
RESPONSE_CONTRACT = "recomendar-response-v1"

# Vocabulario admitido por el formulario del dashboard. La API nueva recibe una
# consulta en texto libre (texto_consulta); estos intereses se traducen a una
# frase de búsqueda semántica en build_payload().
INTEREST_LABELS: dict[str, str] = {
    "coast_beach": "Costa y playa",
    "nature_mountains": "Naturaleza y montaña",
    "sports_outdoors": "Deporte y aire libre",
    "gastronomy_wine": "Gastronomía y vino",
    "history_culture": "Historia y cultura",
    "rural": "Rural",
    "wellness": "Bienestar",
}
INTERESTS = tuple(INTEREST_LABELS)

# Frase de búsqueda por interés, para componer el texto_consulta que espera la
# API nueva a partir de las casillas del formulario.
INTEREST_QUERY_TERMS: dict[str, str] = {
    "coast_beach": "playa y costa",
    "nature_mountains": "naturaleza y montaña",
    "sports_outdoors": "deporte y aire libre",
    "gastronomy_wine": "gastronomía y vino",
    "history_culture": "historia y cultura",
    "rural": "turismo rural",
    "wellness": "bienestar y relax",
}

TEMPERATURE_LABELS: dict[str, str] = {
    "warm_sunny": "Cálido y soleado",
    "mild": "Templado",
    "cool": "Fresco",
    "any": "Indiferente",
}
TEMPERATURE_PREFERENCES = tuple(TEMPERATURE_LABELS)

# Frase de clima para enriquecer la consulta de texto.
TEMPERATURE_QUERY_TERMS: dict[str, str] = {
    "warm_sunny": "con buen clima cálido y soleado",
    "mild": "con clima templado",
    "cool": "con clima fresco",
    "any": "",
}

ACCOMMODATION_LABELS: dict[str, str] = {
    "hotel": "Hotel",
    "apartment": "Apartamento",
    "any": "Indiferente",
}
ACCOMMODATION_TYPES = tuple(ACCOMMODATION_LABELS)

# Categorias de experiencia que admite POST /recomendar en el campo `categoria`.
# La API hace coincidencia EXACTA contra experiencias.category (valores reales
# de la base de datos del motor), por eso las claves son las cadenas exactas.
# Las etiquetas en español son solo para mostrar en el formulario.
CATEGORY_LABELS: dict[str, str] = {
    "Food & Drink Experiences": "Gastronomía y bebida",
    "Cultural Experiences": "Cultura",
    "Excursions & Day Trips": "Excursiones y escapadas",
    "Attractions & Guided Tours": "Atracciones y visitas guiadas",
    "Wellness & Spa": "Bienestar y spa",
    "Adventure & Outdoor": "Aventura y aire libre",
    "Local Experiences": "Experiencias locales",
    "Night Tours & Entertainment": "Ocio nocturno",
    "Transport & Transfers": "Transporte y traslados",
    "Water Activities": "Actividades acuáticas",
}
CATEGORIES = tuple(CATEGORY_LABELS)

# Comunidades autónomas (se conservan para los filtros de región de la UI; la
# API nueva no filtra por región, así que hoy son informativas).
AUTONOMOUS_COMMUNITIES = (
    "Andalucía",
    "Aragón",
    "Canarias",
    "Cantabria",
    "Castilla-La Mancha",
    "Castilla y León",
    "Cataluña",
    "Comunidad de Madrid",
    "Comunidad Foral de Navarra",
    "Comunitat Valenciana",
    "Extremadura",
    "Galicia",
    "Illes Balears",
    "La Rioja",
    "País Vasco",
    "Principado de Asturias",
    "Región de Murcia",
)

# Límites del formulario del dashboard.
MONTH_RANGE = (1, 12)
TRIP_LENGTH_RANGE = (1, 30)
POPULARITY_RANGE = (0.0, 1.0)
SUNNY_DAYS_RANGE = (0, 31)
PRECIPITATION_DAYS_RANGE = (0, 31)

RESULTS_PER_CALL = 3
MIN_RESULTS_USABLE = 1

MONTH_NAMES = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)

# Escenarios (rankings) que devuelve la API nueva. La UI usa "personalizado"
# cuando se envía objetivo_popularidad, y "moderado" como valor por defecto.
DEFAULT_SCENARIO = "moderado"
SCENARIO_PERSONALIZADO = "personalizado"

BREAKDOWN_LABELS: dict[str, str] = {
    "interest_match": "Afinidad con intereses",
    "climate_fit": "Ajuste climático",
    "popularity_fit": "Ajuste de popularidad",
    "tourism_offer": "Oferta turística",
    "accommodation_fit": "Ajuste de alojamiento",
}

COVERAGE_LABELS: dict[str, str] = {
    "catalog": "Catálogo",
    "osm": "OpenStreetMap",
    "youtube": "YouTube",
    "aemet": "AEMET",
}

REASON_CODE_LABELS: dict[str, str] = {
    "INTEREST_MATCH": "Coincide con tus intereses",
    "TUI_HYBRID_MATCH": "Afinidad del modelo entrenado",
    "PRECIPITATION_MATCH": "Precipitación dentro de tu tolerancia",
    "SUNNY_DAYS_MATCH": "Cumple tus días de sol",
    "POPULARITY_CLOSE_TO_TARGET": "Popularidad cercana a la solicitada",
    "TOURISM_OFFER_AVAILABLE": "Oferta turística disponible",
    "ACCOMMODATION_MATCH": "Alojamiento del tipo solicitado",
}

CONFIDENCE_LABELS: dict[str, str] = {
    "high": "Alta",
    "medium": "Media",
    "low": "Baja",
}

# Cortacircuitos: tras un fallo de red se evita reintentar durante unos segundos
# para que la interfaz no acumule timeouts en reruns sucesivos.
_NETWORK_COOLDOWN_SECONDS = 8.0
_network_disabled_until = 0.0

# Reintentos automáticos ante fallo de red / arranque en frío del motor.
_MAX_NETWORK_ATTEMPTS = 3
_RETRY_WAIT_SECONDS = 3.0

# Caché en proceso para no repetir la misma consulta en cada rerun de Streamlit.
_CACHE_MAX_ENTRIES = 32
_cache: dict[str, dict[str, Any]] = {}


# --------------------------------------------------------------------------
# Configuración de endpoint. La API nueva se localiza con TUI_MODELO_API_BASE
# (p. ej. https://<app>.azurecontainerapps.io). Los endpoints se cuelgan de
# esa base: /recomendar, /tdrs_ranking, /chat. Se mantiene compatibilidad con
# TUI_RECO_API_BASE / TUI_RECO_API_URL como respaldo.
# --------------------------------------------------------------------------

def _api_base() -> str | None:
    """URL base del motor, sin barra final. None si no está configurada."""
    base = os.getenv("TUI_MODELO_API_BASE", "").strip()
    if not base:
        # Respaldo: si solo está definida la variable antigua con la base.
        base = os.getenv("TUI_RECO_API_BASE", "").strip()
    if not base:
        return None
    return base.rstrip("/")


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    key = os.getenv("TUI_RECO_API_KEY", "").strip()
    if key:
        headers["x-functions-key"] = key
    return headers


def _endpoint(path: str) -> str | None:
    base = _api_base()
    if not base:
        return None
    return f"{base}/{path.lstrip('/')}"


def is_configured() -> bool:
    return _api_base() is not None


def api_status() -> str:
    """Estado declarativo para la interfaz: ``configured`` o ``not_configured``."""
    return "configured" if is_configured() else "not_configured"


def endpoint_host() -> str | None:
    """Host base del motor, para mostrarlo sin exponer nada sensible."""
    base = _api_base()
    if not base:
        return None
    return base.split("?", 1)[0]


def _timeout() -> float:
    for var in ("TUI_MODELO_API_TIMEOUT", "TUI_RECO_API_TIMEOUT"):
        raw = os.getenv(var)
        if raw:
            try:
                return float(raw)
            except ValueError:
                pass
    return 90.0


# --------------------------------------------------------------------------
# Formulario: estado inicial, validación y construcción del payload.
# --------------------------------------------------------------------------

def default_request() -> dict[str, Any]:
    """Petición por defecto, útil como estado inicial del formulario."""
    return {
        "interests": ["coast_beach"],
        "temperature_preference": "any",
        "popularity_target": 0.5,
        "presupuesto_max": None,
        "categoria": None,
    }


def validate_request(
    interests: list[str],
    temperature_preference: str,
    popularity_target: float,
    presupuesto_max: float | None = None,
    categoria: str | None = None,
) -> list[str]:
    """Validación en cliente del formulario. Lista vacía = petición válida.

    Solo valida los campos que la API nueva respeta de verdad.
    """
    errors: list[str] = []

    if not interests:
        errors.append("Selecciona al menos un interés.")
    unknown = [i for i in interests if i not in INTEREST_LABELS]
    if unknown:
        errors.append("Intereses no admitidos: " + ", ".join(unknown) + ".")
    if temperature_preference not in TEMPERATURE_LABELS:
        errors.append(
            "La preferencia de temperatura debe ser una de: "
            + ", ".join(TEMPERATURE_PREFERENCES)
            + "."
        )
    if not POPULARITY_RANGE[0] <= float(popularity_target) <= POPULARITY_RANGE[1]:
        errors.append("El objetivo de popularidad debe estar entre 0 y 1.")
    if presupuesto_max is not None and float(presupuesto_max) <= 0:
        errors.append("El presupuesto máximo debe ser mayor que 0.")
    if categoria is not None and categoria not in CATEGORY_LABELS:
        errors.append("Categoría no admitida: " + str(categoria) + ".")
    return errors


def _texto_consulta(
    interests: list[str],
    temperature_preference: str,
) -> str:
    """Compone la consulta en lenguaje natural que espera /recomendar a partir
    de los intereses y la preferencia de clima del formulario."""
    terminos = [INTEREST_QUERY_TERMS.get(code, "") for code in interests]
    terminos = [t for t in terminos if t]
    frase = ", ".join(terminos) if terminos else "destinos de viaje"
    clima = TEMPERATURE_QUERY_TERMS.get(temperature_preference, "")
    if clima:
        frase = f"{frase} {clima}"
    return frase.strip()


def build_payload(
    interests: list[str],
    temperature_preference: str = "any",
    popularity_target: float = 0.5,
    presupuesto_max: float | None = None,
    categoria: str | None = None,
    exclude_destinations: list[str] | None = None,
    locale: str = "es-ES",
) -> dict[str, Any]:
    """Construye el cuerpo de la petición para POST /recomendar.

    Solo se usan campos que la API nueva respeta de verdad:
      - intereses + clima  -> texto_consulta (búsqueda semántica)
      - popularity_target  -> objetivo_popularidad
      - presupuesto_max    -> precio_eur <= presupuesto_max
      - categoria          -> coincidencia exacta con experiencias.category
      - exclude_destinations -> excluir_destinos

    Se conserva una copia legible en ``_form`` para la UI y el tracking.
    """
    payload: dict[str, Any] = {
        "_contract_version": REQUEST_CONTRACT,
        "texto_consulta": _texto_consulta(list(interests), temperature_preference),
        "objetivo_popularidad": float(popularity_target),
        "excluir_destinos": list(exclude_destinations or []),
        "_form": {
            "interests": list(interests),
            "temperature_preference": temperature_preference,
            "presupuesto_max": presupuesto_max,
            "categoria": categoria,
            "locale": locale,
        },
    }
    if presupuesto_max is not None:
        payload["presupuesto_max"] = float(presupuesto_max)
    if categoria:
        payload["categoria"] = categoria
    return payload


def _api_body(payload: dict[str, Any], session_id: str | None) -> dict[str, Any]:
    """Extrae del payload interno solo los campos que entiende POST /recomendar."""
    body: dict[str, Any] = {
        "texto_consulta": payload.get("texto_consulta") or "",
        "objetivo_popularidad": payload.get("objetivo_popularidad"),
    }
    if payload.get("presupuesto_max") is not None:
        body["presupuesto_max"] = float(payload["presupuesto_max"])
    if payload.get("categoria"):
        body["categoria"] = payload["categoria"]
    excluir = payload.get("excluir_destinos")
    if excluir:
        body["excluir_destinos"] = list(excluir)
    if session_id:
        body["session_id"] = session_id
    if payload.get("incluir_descripcion_ia"):
        body["incluir_descripcion_ia"] = True
    return body


def _cache_key(payload: dict[str, Any]) -> str:
    return json.dumps(_api_body(payload, None), sort_keys=True, ensure_ascii=False)


def _error(kind: str, message: str, **extra: Any) -> dict[str, Any]:
    return {
        "ok": False,
        "error": message,
        "error_kind": kind,
        "ranking": [],
        "warnings": [],
        "engine": {},
        "session_id": None,
        **extra,
    }


def _extract_api_error(raw: str, status: int) -> str:
    """La API devuelve ``{"detail": ...}`` (FastAPI) o ``{"error": ...}``."""
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            for key in ("detail", "error", "message"):
                if data.get(key):
                    return str(data[key])
    except (ValueError, json.JSONDecodeError):
        pass
    return f"La API respondió con HTTP {status}."


# --------------------------------------------------------------------------
# Adaptación del nuevo contrato al formato interno que ya pinta la UI.
# La UI espera cada fila con: destination.{name,province,autonomous_community,
# primary_typology}, recommendation_score, headline, strengths, tradeoffs,
# climate_profile.{sunny_days,precipitation_days,temperature_mean_c,sunshine_hours},
# what_it_offers.poi_count, popularity_profile.index, confidence.level.
# El nuevo destino trae: destino_nombre, precio_eur, score_final, descripcion_ia?,
# datos_humanos.{dias_soleados_pct, precipitacion_pct, horas_sol_promedio_dia,
# pasajeros_anuales, camas_hospital_1000hab, tasa_homicidios_100mil,
# sentimiento_real, n_resenas_reales}.
# --------------------------------------------------------------------------

def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _pct_to_unit(value: Any) -> float | None:
    """Convierte un porcentaje 0-100 a índice 0-1 (para popularity_profile)."""
    n = _num(value)
    if n is None:
        return None
    return max(0.0, min(1.0, n / 100.0))


def _adapt_destino(dest: dict[str, Any], rank: int) -> dict[str, Any]:
    """Traduce un destino del nuevo contrato al formato de fila de la UI."""
    dh = dest.get("datos_humanos") or {}
    nombre = str(dest.get("destino_nombre") or "Destino")

    dias_soleados = _num(dh.get("dias_soleados_pct"))
    # dias_soleados_pct es un % del mes; la UI lo muestra como "días de sol".
    dias_sol_mes = round(dias_soleados / 100.0 * 30, 0) if dias_soleados is not None else None

    strengths: list[str] = []
    if dias_soleados is not None and dias_soleados >= 70:
        strengths.append("Muchos días de sol")
    sentimiento = _num(dh.get("sentimiento_real"))
    if sentimiento is not None and sentimiento >= 0.6:
        strengths.append("Buenas reseñas de viajeros")
    n_resenas = _num(dh.get("n_resenas_reales"))
    if n_resenas is not None and n_resenas >= 100:
        strengths.append("Opinión contrastada")

    tradeoffs: list[str] = []
    precip = _num(dh.get("precipitacion_pct"))
    if precip is not None and precip >= 40:
        tradeoffs.append("Puede llover con frecuencia")

    headline = str(dest.get("descripcion_ia") or "")

    return {
        "rank": rank,
        "destination": {
            "place_id": dest.get("id_paquete"),
            "name": nombre,
            "province": None,
            "autonomous_community": None,
            "primary_typology": None,
        },
        "recommendation_score": _num(dest.get("score_final")),
        "confidence": {"score": None, "level": None},
        "headline": headline,
        "reason_codes": [],
        "preference_match": {},
        "score_breakdown": {},
        "what_it_offers": {"poi_count": None},
        "climate_profile": {
            "sunny_days": dias_sol_mes,
            "precipitation_days": None,
            "temperature_mean_c": None,
            "sunshine_hours": _num(dh.get("horas_sol_promedio_dia")),
        },
        "popularity_profile": {
            "index": None,
            "basis": "pasajeros_anuales",
            "video_count": None,
        },
        "strengths": strengths,
        "tradeoffs": tradeoffs,
        "data_coverage": {},
        "data_warnings": [],
        # Campos nuevos, disponibles para quien quiera pintarlos:
        "precio_eur": _num(dest.get("precio_eur")),
        "descripcion_ia": dest.get("descripcion_ia"),
        "datos_humanos": dict(dh),
    }


def _pick_scenario(rankings: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Elige la lista de destinos a mostrar: 'personalizado' si se envió
    objetivo_popularidad, si no 'moderado' (con caídas de respaldo)."""
    if not isinstance(rankings, dict):
        return []
    envio_objetivo = payload.get("objetivo_popularidad") is not None
    orden = (
        [SCENARIO_PERSONALIZADO, DEFAULT_SCENARIO]
        if envio_objetivo
        else [DEFAULT_SCENARIO, SCENARIO_PERSONALIZADO]
    )
    orden += ["tradicional", "intensivo"]
    for clave in orden:
        lista = rankings.get(clave)
        if isinstance(lista, list) and lista:
            return lista
    return []


def _normalize_response(data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    rankings = data.get("rankings") or {}
    destinos = _pick_scenario(rankings, payload)
    ranking = [
        _adapt_destino(dest, idx + 1)
        for idx, dest in enumerate(destinos)
        if isinstance(dest, dict)
    ]
    return {
        "ok": True,
        "error": None,
        "error_kind": None,
        "recommendation_id": data.get("session_id"),
        "contract_version": RESPONSE_CONTRACT,
        "generated_at": None,
        "engine": {"version": "fastapi-recomendador"},
        "normalized_input": {},
        "ranking": ranking,
        "warnings": [],
        "session_id": data.get("session_id"),
    }


def _post_json(endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    """POST con reintentos ante fallo de red / arranque en frío.

    Devuelve el JSON decodificado, o un dict de error normalizado (con clave
    ``__error__``) para que el llamador lo transforme según su contrato.
    """
    global _network_disabled_until

    if time.monotonic() < _network_disabled_until:
        return {"__error__": _error(
            "cooldown",
            "La API no respondió en el último intento. Se reintentará en unos "
            "segundos para no acumular esperas.",
        )}

    headers = _headers()
    timeout = _timeout()
    body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")

    data: dict[str, Any] | None = None
    last_network_exc: Exception | None = None
    for attempt in range(_MAX_NETWORK_ATTEMPTS):
        request = urllib.request.Request(
            endpoint, data=body_bytes, headers=headers, method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
            data = json.loads(raw)
            break
        except urllib.error.HTTPError as exc:
            try:
                raw_err = exc.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                raw_err = ""
            message = _extract_api_error(raw_err, exc.code)
            kind = "validation" if exc.code in {400, 422} else "http"
            if exc.code >= 500 and attempt < _MAX_NETWORK_ATTEMPTS - 1:
                time.sleep(_RETRY_WAIT_SECONDS)
                continue
            return {"__error__": _error(kind, message, status_code=exc.code)}
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_network_exc = exc
            if attempt < _MAX_NETWORK_ATTEMPTS - 1:
                time.sleep(_RETRY_WAIT_SECONDS)
                continue
        except (ValueError, json.JSONDecodeError):
            return {"__error__": _error(
                "payload", "La API devolvió una respuesta que no es JSON válido."
            )}

    if data is None:
        _network_disabled_until = time.monotonic() + _NETWORK_COOLDOWN_SECONDS
        name = last_network_exc.__class__.__name__ if last_network_exc else "URLError"
        return {"__error__": _error(
            "network",
            f"No se pudo contactar con el modelo tras varios intentos ({name}). "
            "El servicio puede estar arrancando; espera unos segundos y reintenta.",
        )}

    if not isinstance(data, dict):
        return {"__error__": _error(
            "payload", "La respuesta de la API no tiene el formato esperado."
        )}
    return data


def fetch_recommendations(
    payload: dict[str, Any],
    use_cache: bool = True,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Llama a POST /recomendar y devuelve la respuesta normalizada al formato
    interno de la UI. No lanza excepciones."""
    endpoint = _endpoint("recomendar")
    if not endpoint:
        return _error(
            "not_configured",
            "La API de recomendaciones no está configurada. Define "
            "TUI_MODELO_API_BASE con la URL del motor.",
        )

    key = _cache_key(payload)
    if use_cache and session_id is None and key in _cache:
        return {**_cache[key], "from_cache": True}

    body = _api_body(payload, session_id)
    data = _post_json(endpoint, body)
    if "__error__" in data:
        return {**data["__error__"], "from_cache": False}

    if "rankings" not in data:
        return _error("payload", "La respuesta de la API no contiene rankings.")

    result = _normalize_response(data, payload)
    if use_cache and session_id is None:
        if len(_cache) >= _CACHE_MAX_ENTRIES:
            _cache.pop(next(iter(_cache)))
        _cache[key] = result
    return {**result, "from_cache": False}


def recommend(
    interests: list[str],
    **kwargs: Any,
) -> dict[str, Any]:
    """Atajo que valida, construye la petición y llama a la API."""
    errors = validate_request(
        interests=interests,
        temperature_preference=kwargs.get("temperature_preference", "any"),
        popularity_target=kwargs.get("popularity_target", 0.5),
        presupuesto_max=kwargs.get("presupuesto_max"),
        categoria=kwargs.get("categoria"),
    )
    if errors:
        return _error("validation", " ".join(errors))
    payload = build_payload(interests, **kwargs)
    return fetch_recommendations(payload)


# --------------------------------------------------------------------------
# Asistente conversacional: POST /chat
# --------------------------------------------------------------------------

def chat(
    mensaje: str,
    historial: list[dict[str, Any]] | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Llama a POST /chat. Devuelve {ok, respuesta, historial, session_id,
    error, error_kind, reco_result}. ``reco_result`` es la recomendación
    estructurada (formato interno de la UI, igual que fetch_recommendations) que
    el chat citó en este turno, o None si el turno fue solo conversacional. No
    lanza excepciones."""
    endpoint = _endpoint("chat")
    if not endpoint:
        return {
            "ok": False,
            "error_kind": "not_configured",
            "error": "El asistente no está configurado (falta TUI_MODELO_API_BASE).",
            "respuesta": "",
            "historial": list(historial or []),
            "session_id": session_id,
            "reco_result": None,
        }

    body: dict[str, Any] = {
        "mensaje": mensaje,
        "historial": list(historial or []),
        "session_id": session_id,
    }
    data = _post_json(endpoint, body)
    if "__error__" in data:
        err = data["__error__"]
        return {
            "ok": False,
            "error_kind": err.get("error_kind"),
            "error": err.get("error"),
            "respuesta": "",
            "historial": list(historial or []),
            "session_id": session_id,
            "reco_result": None,
        }

    # Si el chat llamó a la herramienta de recomendación, el backend devuelve el
    # ranking estructurado (mismo formato que /recomendar). Se normaliza igual
    # que la tarjeta destacada para que muestre EXACTAMENTE los destinos que el
    # chat recomienda (opción 1 = destacada, 2 y 3 = alternativas). Si el turno
    # fue solo conversacional (sin herramienta), rankings viene vacío y no se
    # toca la tarjeta.
    reco_result: dict[str, Any] | None = None
    rankings = data.get("rankings")
    if isinstance(rankings, dict) and rankings:
        pseudo_payload = {"objetivo_popularidad": data.get("objetivo_popularidad")}
        reco_result = _normalize_response({"rankings": rankings, "session_id": data.get("session_id")}, pseudo_payload)

    return {
        "ok": True,
        "error_kind": None,
        "error": None,
        "respuesta": str(data.get("respuesta") or ""),
        "historial": list(data.get("historial") or []),
        "session_id": data.get("session_id") or session_id,
        "reco_result": reco_result,
    }


# --------------------------------------------------------------------------
# Simulador TDRS: POST /tdrs_ranking
# --------------------------------------------------------------------------

def tdrs_ranking(
    weights: dict[str, float],
    max_price: float | None = None,
    max_stay_days: int | None = None,
) -> dict[str, Any]:
    """Llama a POST /tdrs_ranking. Devuelve {ok, ranked, excluded,
    senales_disponibles, fuente, error, error_kind}. No lanza excepciones."""
    endpoint = _endpoint("tdrs_ranking")
    if not endpoint:
        return {
            "ok": False,
            "error_kind": "not_configured",
            "error": "El simulador TDRS no está configurado (falta TUI_MODELO_API_BASE).",
            "ranked": [],
            "excluded": [],
        }

    body: dict[str, Any] = {"weights": {k: float(v) for k, v in weights.items()}}
    if max_price is not None:
        body["max_price"] = float(max_price)
    if max_stay_days is not None:
        body["max_stay_days"] = int(max_stay_days)

    data = _post_json(endpoint, body)
    if "__error__" in data:
        err = data["__error__"]
        return {
            "ok": False,
            "error_kind": err.get("error_kind"),
            "error": err.get("error"),
            "ranked": [],
            "excluded": [],
        }
    return {
        "ok": True,
        "error_kind": None,
        "error": None,
        "ranked": list(data.get("ranked") or []),
        "excluded": list(data.get("excluded") or []),
        # La API devuelve la clave con eñe ("señales_disponibles"); se expone con
        # nombre ASCII para el resto del dashboard.
        "senales_disponibles": data.get("señales_disponibles")
        or data.get("senales_disponibles")
        or [],
        "fuente": data.get("fuente"),
    }


# --------------------------------------------------------------------------
# Ayudas de presentación.
# --------------------------------------------------------------------------

def interest_label(code: str) -> str:
    return INTEREST_LABELS.get(code, code)


def month_name(month: int) -> str:
    index = int(month) - 1
    return MONTH_NAMES[index] if 0 <= index < 12 else str(month)


def confidence_label(level: str | None) -> str:
    return CONFIDENCE_LABELS.get(str(level or "").lower(), str(level or "—"))


def reason_label(code: str) -> str:
    return REASON_CODE_LABELS.get(code, code.replace("_", " ").capitalize())


def coverage_summary(coverage: dict[str, Any] | None) -> tuple[int, int, list[str]]:
    """Devuelve (fuentes disponibles, fuentes totales, nombres de las que faltan)."""
    coverage = coverage or {}
    if not coverage:
        return 0, 0, []
    total = len(coverage)
    available = sum(1 for value in coverage.values() if value)
    missing = [
        COVERAGE_LABELS.get(name, name)
        for name, value in coverage.items()
        if not value
    ]
    return available, total, missing


def breakdown_rows(breakdown: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Convierte ``score_breakdown`` en filas ordenadas listas para tabla."""
    breakdown = breakdown or {}
    rows = [
        {
            "Dimensión": BREAKDOWN_LABELS.get(code, code),
            "code": code,
            "Valor": float(value) if isinstance(value, (int, float)) else None,
        }
        for code, value in breakdown.items()
    ]
    rows.sort(key=lambda row: (row["Valor"] is not None, row["Valor"] or 0), reverse=True)
    return rows


def ranking_table(ranking: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resumen tabular del ranking. Los datos ausentes se dejan como ``None``."""
    rows: list[dict[str, Any]] = []
    for row in ranking:
        destination = row.get("destination") or {}
        climate = row.get("climate_profile") or {}
        offers = row.get("what_it_offers") or {}
        popularity = row.get("popularity_profile") or {}
        available, total, _ = coverage_summary(row.get("data_coverage"))
        rows.append({
            "Opción": row.get("rank"),
            "Destino": destination.get("name"),
            "Provincia": destination.get("province"),
            "Comunidad": destination.get("autonomous_community"),
            "Tipología": destination.get("primary_typology"),
            "Precio (€)": row.get("precio_eur"),
            "Score": row.get("recommendation_score"),
            "Confianza": confidence_label((row.get("confidence") or {}).get("level")),
            "Días de sol": climate.get("sunny_days"),
            "Días de lluvia": climate.get("precipitation_days"),
            "Temp. media °C": climate.get("temperature_mean_c"),
            "Popularidad": popularity.get("index"),
            "POIs": offers.get("poi_count"),
            "Cobertura": f"{available}/{total}" if total else None,
        })
    return rows


def reset_state() -> None:
    """Limpia caché y cortacircuitos. Pensado para los tests."""
    global _network_disabled_until
    _network_disabled_until = 0.0
    _cache.clear()
