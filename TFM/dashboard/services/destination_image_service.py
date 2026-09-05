from __future__ import annotations

import json
import os
import time
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

WIKIPEDIA_APIS = (
    "https://es.wikipedia.org/w/api.php",
    "https://en.wikipedia.org/w/api.php",
)

DEFAULT_USER_AGENT = (
    "TUI-TDRS-DestinationImages/1.0 "
    "(automatic destination image lookup; contact the application administrator)"
)

# Pequeño cortacircuitos: si la máquina donde corre Streamlit no tiene salida a
# Internet, evitamos bloquear la interfaz repitiendo timeouts para cada tarjeta.
_NETWORK_DISABLED_UNTIL = 0.0


def _request_json(api_url: str, params: dict[str, object]) -> dict:
    query = urlencode({k: v for k, v in params.items() if v is not None})
    req = Request(
        f"{api_url}?{query}",
        headers={
            "User-Agent": os.getenv("TUI_IMAGE_USER_AGENT", DEFAULT_USER_AGENT),
            "Accept": "application/json",
        },
    )
    timeout = float(os.getenv("TUI_IMAGE_TIMEOUT_SECONDS", "2"))
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


# Los artículos de municipios usan como miniatura principal la bandera o el
# escudo del infobox. Sirven para identificar, no para ilustrar: como fotografía
# de un destino quedan mal y además suelen ser verticales.
_REJECTED_PATTERNS = (
    "bandera", "flag", "escudo", "coat_of_arms", "coat of arms", "crest",
    "seal_of", "shield", "blason", "blazon", "wappen",
    "mapa", "_map", "map_of", "location", "locator", "ubicacion", "ubicación",
    "logo", "icon", "signature", "firma", "spain_location", "localizacion",
)

# Un escudo o una bandera son claramente más altos que anchos, o cuadrados.
# Una fotografía de paisaje o de conjunto urbano es panorámica.
_MIN_ASPECT_RATIO = 1.15


def _is_decorative_symbol(url: str) -> bool:
    lowered = url.lower()
    return any(pattern in lowered for pattern in _REJECTED_PATTERNS)


def _is_landscape(thumbnail: dict) -> bool:
    width = thumbnail.get("width")
    height = thumbnail.get("height")
    if not width or not height:
        # Sin dimensiones no se puede juzgar: se acepta y decide el nombre.
        return True
    try:
        return (float(width) / float(height)) >= _MIN_ASPECT_RATIO
    except (TypeError, ValueError, ZeroDivisionError):
        return True


def _image_from_pages(payload: dict, destination: str) -> dict | None:
    """Primera miniatura que parezca una fotografía del destino.

    Descarta banderas, escudos y mapas de localización, tanto por el nombre del
    fichero como por su proporción. Es preferible no mostrar imagen y caer en el
    fondo sólido que ilustrar un destino con su escudo municipal.
    """
    pages = (payload.get("query") or {}).get("pages") or []
    if isinstance(pages, dict):
        pages = list(pages.values())

    # generator=search incluye "index"; respetarlo conserva el orden de relevancia.
    pages = sorted(pages, key=lambda p: p.get("index", 10_000))
    for page in pages:
        thumbnail = page.get("thumbnail") or {}
        source = thumbnail.get("source")
        if not source:
            continue
        if _is_decorative_symbol(source) or not _is_landscape(thumbnail):
            continue
        title = str(page.get("title") or destination)
        return {
            "url": source,
            "alt": f"Imagen de {destination}",
            "credit": "Wikipedia / Wikimedia Commons",
            "source_page": page.get("fullurl"),
            "matched_title": title,
            "source": "wikipedia",
        }
    return None


def _exact_lookup(api_url: str, destination: str) -> dict | None:
    payload = _request_json(
        api_url,
        {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "redirects": 1,
            "prop": "pageimages|info",
            "inprop": "url",
            "piprop": "thumbnail|name",
            "pithumbsize": 1200,
            "titles": destination,
        },
    )
    return _image_from_pages(payload, destination)


def _search_lookup(api_url: str, destination: str) -> dict | None:
    payload = _request_json(
        api_url,
        {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "generator": "search",
            "gsrsearch": destination,
            "gsrnamespace": 0,
            # Se piden más candidatos que antes porque ahora se descartan
            # banderas y escudos: con 5 resultados a menudo no quedaba ninguno.
            "gsrlimit": 12,
            "prop": "pageimages|info",
            "inprop": "url",
            "piprop": "thumbnail|name",
            "pithumbsize": 1200,
        },
    )
    return _image_from_pages(payload, destination)


@lru_cache(maxsize=256)
def get_destination_image(destination: str) -> dict | None:
    """Busca una imagen representativa de un destino en Wikipedia.

    Primero intenta el artículo cuyo título coincide con el destino y, si la
    consulta respondió correctamente pero no tiene imagen, usa la búsqueda de
    Wikipedia. Empieza por español y puede usar inglés como respaldo.

    El resultado (incluidos los fallos por destino) queda cacheado durante la
    vida del proceso. Si hay un error real de red, activa brevemente un
    cortacircuitos para que las siguientes tarjetas no acumulen timeouts.
    """
    global _NETWORK_DISABLED_UNTIL

    destination = " ".join(str(destination or "").split()).strip()
    if not destination:
        return None
    if time.monotonic() < _NETWORK_DISABLED_UNTIL:
        return None

    for api_url in WIKIPEDIA_APIS:
        try:
            image = _exact_lookup(api_url, destination)
            if image:
                return image
            image = _search_lookup(api_url, destination)
            if image:
                return image
        except (HTTPError, URLError, TimeoutError, OSError):
            _NETWORK_DISABLED_UNTIL = time.monotonic() + 30.0
            return None
        except (ValueError, json.JSONDecodeError):
            # Respuesta inválida: probamos la siguiente Wikipedia sin bloquear red.
            continue
    return None
