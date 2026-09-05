from __future__ import annotations

"""Cliente del recomendador externo de destinos de España (Azure Functions).

Este servicio consume un motor de recomendación independiente del TDRS. No lo
sustituye: el TDRS ranquea el catálogo internacional de TUI a partir del SQLite
local, mientras que esta API ranquea municipios españoles combinando catálogo
turístico, OpenStreetMap, señales de YouTube y clima histórico de AEMET.

Configuración por entorno (o ``.streamlit/secrets.toml``):

- ``TUI_RECO_API_BASE`` + ``TUI_RECO_API_KEY``: opción recomendada. La clave
  viaja en la cabecera ``x-functions-key`` y no queda en el querystring.
- ``TUI_RECO_API_URL``: alternativa con la URL completa, incluido ``?code=``.
- ``TUI_RECO_API_TIMEOUT``: segundos de espera (30 por defecto, la Function
  tiene arranque en frío).

El módulo nunca lanza excepciones hacia la interfaz: devuelve siempre un
diccionario con ``ok`` y, si algo falla, un ``error`` legible. Igual que el
resto de la app, degrada en lugar de romper.

El contrato aquí declarado se ha verificado contra la API real. La validación se
replica en cliente para no gastar una llamada de red en un error evitable.
"""

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

REQUEST_CONTRACT = "recommendation-request-v1"
RESPONSE_CONTRACT = "recommendation-response-v1"

# Vocabulario admitido por la API. Los valores no listados devuelven HTTP 400.
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

TEMPERATURE_LABELS: dict[str, str] = {
    "warm_sunny": "Cálido y soleado",
    "mild": "Templado",
    "cool": "Fresco",
    "any": "Indiferente",
}
TEMPERATURE_PREFERENCES = tuple(TEMPERATURE_LABELS)

ACCOMMODATION_LABELS: dict[str, str] = {
    "hotel": "Hotel",
    "apartment": "Apartamento",
    "any": "Indiferente",
}
ACCOMMODATION_TYPES = tuple(ACCOMMODATION_LABELS)

# Comunidades autónomas aceptadas por los filtros de región.
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

# Límites verificados contra la API.
MONTH_RANGE = (1, 12)
TRIP_LENGTH_RANGE = (1, 30)
POPULARITY_RANGE = (0.0, 1.0)
SUNNY_DAYS_RANGE = (0, 31)
PRECIPITATION_DAYS_RANGE = (0, 31)

# La API devuelve siempre tres destinos: ignora top_n, limit y max_results.
RESULTS_PER_CALL = 3

MONTH_NAMES = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)

# Etiquetas de las cinco dimensiones de `score_breakdown`.
BREAKDOWN_LABELS: dict[str, str] = {
    "interest_match": "Afinidad con intereses",
    "climate_fit": "Ajuste climático",
    "popularity_fit": "Ajuste de popularidad",
    "tourism_offer": "Oferta turística",
    "accommodation_fit": "Ajuste de alojamiento",
}

# Fuentes declaradas en `data_coverage`.
COVERAGE_LABELS: dict[str, str] = {
    "catalog": "Catálogo",
    "osm": "OpenStreetMap",
    "youtube": "YouTube",
    "aemet": "AEMET",
}

REASON_CODE_LABELS: dict[str, str] = {
    "INTEREST_MATCH": "Coincide con tus intereses",
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
_NETWORK_COOLDOWN_SECONDS = 20.0
_network_disabled_until = 0.0

# Caché en proceso para no repetir la misma consulta en cada rerun de Streamlit.
_CACHE_MAX_ENTRIES = 32
_cache: dict[str, dict[str, Any]] = {}


def _endpoint_and_headers() -> tuple[str | None, dict[str, str]]:
    """Resuelve la URL y las cabeceras según las variables de entorno."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    full_url = os.getenv("TUI_RECO_API_URL", "").strip()
    base = os.getenv("TUI_RECO_API_BASE", "").strip()
    key = os.getenv("TUI_RECO_API_KEY", "").strip()

    if base:
        if key:
            headers["x-functions-key"] = key
        return base, headers
    if full_url:
        return full_url, headers
    return None, headers


def is_configured() -> bool:
    endpoint, _ = _endpoint_and_headers()
    return bool(endpoint)


def api_status() -> str:
    """Estado declarativo para la interfaz: ``configured`` o ``not_configured``."""
    return "configured" if is_configured() else "not_configured"


def endpoint_host() -> str | None:
    """Host del endpoint, sin querystring, para mostrarlo sin exponer la clave."""
    endpoint, _ = _endpoint_and_headers()
    if not endpoint:
        return None
    return endpoint.split("?", 1)[0]


def default_request() -> dict[str, Any]:
    """Petición por defecto, útil como estado inicial del formulario."""
    return {
        "month": 7,
        "trip_length_days": 7,
        "interests": ["coast_beach"],
        "temperature_preference": "warm_sunny",
        "minimum_sunny_days": 20,
        "maximum_precipitation_days": 5,
        "popularity_target": 0.6,
        "accommodation_type": "hotel",
        "include_regions": [],
        "exclude_regions": [],
    }


def validate_request(
    month: int,
    trip_length_days: int,
    interests: list[str],
    temperature_preference: str,
    minimum_sunny_days: float,
    maximum_precipitation_days: float,
    popularity_target: float,
    accommodation_type: str,
) -> list[str]:
    """Replica en cliente la validación de la API. Lista vacía = petición válida."""
    errors: list[str] = []

    if not MONTH_RANGE[0] <= int(month) <= MONTH_RANGE[1]:
        errors.append(f"El mes debe estar entre {MONTH_RANGE[0]} y {MONTH_RANGE[1]}.")
    if not TRIP_LENGTH_RANGE[0] <= int(trip_length_days) <= TRIP_LENGTH_RANGE[1]:
        errors.append(
            f"La duración debe estar entre {TRIP_LENGTH_RANGE[0]} y "
            f"{TRIP_LENGTH_RANGE[1]} días."
        )
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
    if accommodation_type not in ACCOMMODATION_LABELS:
        errors.append(
            "El tipo de alojamiento debe ser uno de: "
            + ", ".join(ACCOMMODATION_TYPES)
            + "."
        )
    if not POPULARITY_RANGE[0] <= float(popularity_target) <= POPULARITY_RANGE[1]:
        errors.append("El objetivo de popularidad debe estar entre 0 y 1.")
    if float(minimum_sunny_days) < 0:
        errors.append("Los días de sol mínimos no pueden ser negativos.")
    if float(maximum_precipitation_days) < 0:
        errors.append("Los días de precipitación máximos no pueden ser negativos.")
    return errors


def build_payload(
    month: int,
    trip_length_days: int,
    interests: list[str],
    temperature_preference: str = "warm_sunny",
    minimum_sunny_days: float = 20,
    maximum_precipitation_days: float = 5,
    popularity_target: float = 0.6,
    accommodation_type: str = "hotel",
    include_regions: list[str] | None = None,
    exclude_regions: list[str] | None = None,
    exclude_destinations: list[str] | None = None,
    locale: str = "es-ES",
) -> dict[str, Any]:
    """Construye el cuerpo de la petición según el contrato de la API."""
    return {
        "contract_version": REQUEST_CONTRACT,
        "travel": {
            "month": int(month),
            "trip_length_days": int(trip_length_days),
        },
        "preferences": {
            "interests": list(interests),
            "climate": {
                "temperature_preference": temperature_preference,
                "minimum_sunny_days": float(minimum_sunny_days),
                "maximum_precipitation_days": float(maximum_precipitation_days),
            },
            "popularity_target": float(popularity_target),
            "accommodation_type": accommodation_type,
        },
        "filters": {
            "include_regions": list(include_regions or []),
            "exclude_regions": list(exclude_regions or []),
            "exclude_destinations": list(exclude_destinations or []),
        },
        "locale": locale,
    }


def _cache_key(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def _error(kind: str, message: str, **extra: Any) -> dict[str, Any]:
    return {
        "ok": False,
        "error": message,
        "error_kind": kind,
        "ranking": [],
        "warnings": [],
        "engine": {},
        **extra,
    }


def _extract_api_error(raw: str, status: int) -> str:
    """La API devuelve ``{"error": "..."}``; si no, se usa el cuerpo crudo."""
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("error"):
            return str(data["error"])
    except (ValueError, json.JSONDecodeError):
        pass
    return f"La API respondió con HTTP {status}."


def _normalize_response(data: dict[str, Any]) -> dict[str, Any]:
    ranking = [row for row in data.get("ranking", []) if isinstance(row, dict)]
    ranking.sort(key=lambda row: row.get("rank") or 0)
    return {
        "ok": True,
        "error": None,
        "error_kind": None,
        "recommendation_id": data.get("recommendation_id"),
        "contract_version": data.get("contract_version"),
        "generated_at": data.get("generated_at"),
        "engine": data.get("engine") or {},
        "normalized_input": data.get("normalized_input") or {},
        "ranking": ranking,
        "warnings": list(data.get("global_warnings") or []),
    }


def fetch_recommendations(
    payload: dict[str, Any],
    use_cache: bool = True,
) -> dict[str, Any]:
    """Llama a la API y devuelve la respuesta normalizada. No lanza excepciones.

    Claves de la salida: ``ok``, ``error``, ``error_kind``, ``ranking``,
    ``warnings``, ``engine``, ``recommendation_id``, ``generated_at``,
    ``normalized_input`` y ``from_cache``.
    """
    global _network_disabled_until

    endpoint, headers = _endpoint_and_headers()
    if not endpoint:
        return _error(
            "not_configured",
            "La API de recomendaciones no está configurada. Define "
            "TUI_RECO_API_BASE y TUI_RECO_API_KEY (o TUI_RECO_API_URL).",
        )

    key = _cache_key(payload)
    if use_cache and key in _cache:
        return {**_cache[key], "from_cache": True}

    if time.monotonic() < _network_disabled_until:
        return _error(
            "cooldown",
            "La API no respondió en el último intento. Se reintentará en unos "
            "segundos para no acumular esperas.",
        )

    try:
        timeout = float(os.getenv("TUI_RECO_API_TIMEOUT", "30"))
    except ValueError:
        timeout = 30.0

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
        data = json.loads(raw)
    except urllib.error.HTTPError as exc:
        # 400/422 son respuestas de negocio: la API está viva y ha rechazado la
        # petición. No activan el cortacircuitos.
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            body = ""
        message = _extract_api_error(body, exc.code)
        kind = "validation" if exc.code in {400, 422} else "http"
        if exc.code >= 500:
            _network_disabled_until = time.monotonic() + _NETWORK_COOLDOWN_SECONDS
        return _error(kind, message, status_code=exc.code)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        _network_disabled_until = time.monotonic() + _NETWORK_COOLDOWN_SECONDS
        return _error(
            "network",
            f"No se pudo contactar con la API de recomendaciones ({exc.__class__.__name__}). "
            "La Function puede estar arrancando en frío: vuelve a intentarlo.",
        )
    except (ValueError, json.JSONDecodeError):
        return _error("payload", "La API devolvió una respuesta que no es JSON válido.")

    if not isinstance(data, dict) or "ranking" not in data:
        return _error("payload", "La respuesta de la API no contiene un ranking.")

    result = _normalize_response(data)
    if use_cache:
        if len(_cache) >= _CACHE_MAX_ENTRIES:
            _cache.pop(next(iter(_cache)))
        _cache[key] = result
    return {**result, "from_cache": False}


def recommend(
    month: int,
    trip_length_days: int,
    interests: list[str],
    **kwargs: Any,
) -> dict[str, Any]:
    """Atajo que valida, construye la petición y llama a la API."""
    errors = validate_request(
        month=month,
        trip_length_days=trip_length_days,
        interests=interests,
        temperature_preference=kwargs.get("temperature_preference", "warm_sunny"),
        minimum_sunny_days=kwargs.get("minimum_sunny_days", 20),
        maximum_precipitation_days=kwargs.get("maximum_precipitation_days", 5),
        popularity_target=kwargs.get("popularity_target", 0.6),
        accommodation_type=kwargs.get("accommodation_type", "hotel"),
    )
    if errors:
        return _error("validation", " ".join(errors))
    payload = build_payload(month, trip_length_days, interests, **kwargs)
    return fetch_recommendations(payload)


# --------------------------------------------------------------------------
# Ayudas de presentación. Viven aquí para que la interfaz no interprete el
# contrato de la API, solo lo pinte.
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
