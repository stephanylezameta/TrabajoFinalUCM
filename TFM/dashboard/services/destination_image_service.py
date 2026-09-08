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
    # Premios, galardones y carteles que se cuelan por homonimia
    # (p. ej. "Palme d'Or"/Cannes al buscar "Palma").
    "palme", "cannes", "award", "premio", "trophy", "medal", "poster",
    "cartel", "festival", "diploma",
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


# --------------------------------------------------------------------------
# Resolución desambiguada para municipios españoles.
#
# El motor de la API devuelve nombres de municipio que, a secas, son ambiguos en
# Wikipedia: "Palma" resuelve a la Palma de Oro de Cannes, "Santiago" a la ciudad
# de Chile, etc. Con la provincia y la comunidad que la propia API entrega se
# construyen consultas cada vez menos específicas, de modo que la primera que
# acierte gane. Así no hay que mantener imágenes locales ni redesplegar la app
# cuando el modelo devuelve un municipio nuevo: la foto se resuelve en vivo.
# --------------------------------------------------------------------------

# Municipios cuyo nombre "a secas" es ambiguo en Wikipedia (un homónimo más
# famoso gana): se fija el título exacto del artículo del municipio español.
# Para el resto, el propio nombre ya resuelve al artículo correcto en es.wikipedia.
_CANONICAL_TITLES: dict[str, str] = {
    "palma": "Palma de Mallorca",
    "donostia/san sebastián": "San Sebastián (España)",
    "donostia/san sebastian": "San Sebastián (España)",
    "vitoria-gasteiz": "Vitoria",
    "a coruña": "La Coruña",
    "santiago": "Santiago de Compostela",
    "cartagena": "Cartagena (España)",
    "córdoba": "Córdoba (España)",
    "cordoba": "Córdoba (España)",
    "guadalajara": "Guadalajara (España)",
    "león": "León (España)",
    "leon": "León (España)",
    "valencia": "Valencia (España)",
    "valència": "Valencia (España)",
    "cuenca": "Cuenca (España)",
    "santa cruz de tenerife": "Santa Cruz de Tenerife",
    "ávila": "Ávila",
    "soria": "Soria",
    "murcia": "Murcia",
}


def _dedup(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in seq:
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _candidate_queries(destination: dict) -> list[str]:
    """Consultas de imagen para un destino, de la más precisa a la más general.

    La estrategia es apuntar al **artículo del municipio**, no hacer búsquedas
    difusas: en es.wikipedia el título del municipio (o su forma canónica con
    "(provincia)"/"(España)") tiene la foto correcta. Pegar la comunidad autónoma
    como texto libre traía artículos tangenciales (carreras, mapas), así que no
    se usa como consulta de búsqueda.
    """
    name = " ".join(str(destination.get("name") or "").split()).strip()
    if not name:
        return []
    province = str(destination.get("province") or "").strip()

    canonical = _CANONICAL_TITLES.get(name.lower())
    queries: list[str] = []
    if canonical:
        # Con título canónico conocido, es la apuesta más segura: va primero.
        queries.append(canonical)
    # Desambiguación estándar de Wikipedia en es: "Municipio (provincia)". Se
    # prioriza sobre el nombre pelado porque este cae en homónimos genéricos
    # ("Cuenca" → cuenca hidrográfica, "San Sebastián" → una carrera).
    if province and province.lower() != name.lower():
        queries.append(f"{name} ({province})")
    queries.append(f"{name} (España)")
    # El nombre a secas, como último recurso.
    queries.append(name)
    return _dedup(queries)


def resolve_destination_image(destination: dict) -> dict | None:
    """Imagen de un municipio español a partir del bloque ``destination`` de la API.

    Prueba consultas desambiguadas (con provincia y comunidad) antes que el
    nombre a secas, para no traer la imagen de un homónimo famoso. Devuelve el
    mismo formato que :func:`get_destination_image`.
    """
    for query in _candidate_queries(destination):
        image = get_destination_image(query)
        if image:
            return image
    return None


# --------------------------------------------------------------------------
# Set curado de fotografías de municipios españoles.
#
# En lugar de adivinar en Wikipedia (que trae homónimos: la Palma de Oro de
# Cannes, un tren de Renfe en San Sebastián, un mapa para Cuenca), se fija una
# URL de Wikimedia Commons verificada para los municipios que el modelo devuelve
# con más frecuencia. Son fotografías reales del lugar, con licencia libre. Es
# la opción fiable para una app pública: no depende de búsquedas ni de tener la
# imagen descargada, y nunca muestra una foto equivocada.
#
# Clave: nombre del municipio normalizado (minúsculas, sin acentos).
# --------------------------------------------------------------------------

def _norm(text: str) -> str:
    import unicodedata

    plain = unicodedata.normalize("NFKD", str(text or "").lower())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return " ".join(plain.split())


CURATED_SPAIN_IMAGES: dict[str, dict[str, str]] = {
    "madrid": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/85/Puerta_de_Alcal%C3%A1_%28Madrid%29_01.jpg/1280px-Puerta_de_Alcal%C3%A1_%28Madrid%29_01.jpg",
        "credit": "Diego Delso · Wikimedia Commons · CC BY-SA",
    },
    "barcelona": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e6/Sagrada_Fam%C3%ADlia_01.jpg/1280px-Sagrada_Fam%C3%ADlia_01.jpg",
        "credit": "Wikimedia Commons · CC BY-SA",
    },
    "granada": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/85/Vista_de_la_Alhambra.jpg/1280px-Vista_de_la_Alhambra.jpg",
        "credit": "Wikimedia Commons · CC BY-SA",
    },
    "sevilla": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/13/Plaza_de_Espa%C3%B1a_-_Sevilla%2C_Spain_-_Sept_2009.jpg/1280px-Plaza_de_Espa%C3%B1a_-_Sevilla%2C_Spain_-_Sept_2009.jpg",
        "credit": "Wikimedia Commons · CC BY-SA",
    },
    "cordoba": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a3/Mezquita_de_C%C3%B3rdoba_desde_el_aire_%28C%C3%B3rdoba%2C_Espa%C3%B1a%29.jpg/1280px-Mezquita_de_C%C3%B3rdoba_desde_el_aire_%28C%C3%B3rdoba%2C_Espa%C3%B1a%29.jpg",
        "credit": "Toni Castillo Quero · Wikimedia Commons · CC BY-SA",
    },
    "malaga": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Malaga_aerea.jpg/1280px-Malaga_aerea.jpg",
        "credit": "Wikimedia Commons · CC BY-SA",
    },
    "donostia/san sebastian": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9a/Bah%C3%ADa_de_La_Concha%2C_San_Sebasti%C3%A1n%2C_Espa%C3%B1a%2C_2012-05-19%2C_DD_04.jpg/1280px-Bah%C3%ADa_de_La_Concha%2C_San_Sebasti%C3%A1n%2C_Espa%C3%B1a%2C_2012-05-19%2C_DD_04.jpg",
        "credit": "Diego Delso · Wikimedia Commons · CC BY-SA",
    },
    "palma": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/Kathedrale_von_Palma_II.jpg/1280px-Kathedrale_von_Palma_II.jpg",
        "credit": "Wikimedia Commons · CC BY-SA",
    },
    "marbella": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/Marbella_-_Casco_antiguo.jpg/1280px-Marbella_-_Casco_antiguo.jpg",
        "credit": "Wikimedia Commons · CC BY-SA",
    },
    "cartagena": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/Puerto_de_Cartagena%2C_Espa%C3%B1a.jpg/1280px-Puerto_de_Cartagena%2C_Espa%C3%B1a.jpg",
        "credit": "Wikimedia Commons · CC BY-SA",
    },
    "benidorm": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/Benidorm_-_Playa_de_Levante.jpg/1280px-Benidorm_-_Playa_de_Levante.jpg",
        "credit": "Wikimedia Commons · CC BY-SA",
    },
    "nijar": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/95/Cabo_de_Gata_-_Playa_de_M%C3%B3nsul.jpg/1280px-Cabo_de_Gata_-_Playa_de_M%C3%B3nsul.jpg",
        "credit": "Wikimedia Commons · CC BY-SA",
    },
    "benasque": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Benasque_desde_la_carretera_de_Anciles.jpg/1280px-Benasque_desde_la_carretera_de_Anciles.jpg",
        "credit": "Wikimedia Commons · CC BY-SA",
    },
    "vigo": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2a/Vigo_desde_A_Guia.jpg/1280px-Vigo_desde_A_Guia.jpg",
        "credit": "Wikimedia Commons · CC BY-SA",
    },
    "murcia": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1e/Catedral_de_Murcia_-_fachada.jpg/1280px-Catedral_de_Murcia_-_fachada.jpg",
        "credit": "Wikimedia Commons · CC BY-SA",
    },
    "cuenca": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6d/Casas_Colgadas_de_Cuenca%2C_Espa%C3%B1a.jpg/1280px-Casas_Colgadas_de_Cuenca%2C_Espa%C3%B1a.jpg",
        "credit": "Wikimedia Commons · CC BY-SA",
    },
    "valencia": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Ciudad_de_las_Artes_y_las_Ciencias_de_Valencia.jpg/1280px-Ciudad_de_las_Artes_y_las_Ciencias_de_Valencia.jpg",
        "credit": "Wikimedia Commons · CC BY-SA",
    },
    "bilbao": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Guggenheim-bilbao-jan05.jpg/1280px-Guggenheim-bilbao-jan05.jpg",
        "credit": "Wikimedia Commons · CC BY-SA",
    },
    "toledo": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/Toledo_Skyline_Panorama%2C_Spain_-_Dec_2006.jpg/1280px-Toledo_Skyline_Panorama%2C_Spain_-_Dec_2006.jpg",
        "credit": "Diliff · Wikimedia Commons · CC BY-SA",
    },
    "santiago de compostela": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7a/Cathedral_of_Santiago_de_Compostela.jpg/1280px-Cathedral_of_Santiago_de_Compostela.jpg",
        "credit": "Wikimedia Commons · CC BY-SA",
    },
    "santa cruz de tenerife": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/Auditorio_de_Tenerife%2C_Santa_Cruz_de_Tenerife%2C_Espa%C3%B1a%2C_2012-12-15%2C_DD_02.jpg/1280px-Auditorio_de_Tenerife%2C_Santa_Cruz_de_Tenerife%2C_Espa%C3%B1a%2C_2012-12-15%2C_DD_02.jpg",
        "credit": "Diego Delso · Wikimedia Commons · CC BY-SA",
    },
    "zaragoza": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Basilica_del_Pilar%2C_Zaragoza.jpg/1280px-Basilica_del_Pilar%2C_Zaragoza.jpg",
        "credit": "Wikimedia Commons · CC BY-SA",
    },
    "salamanca": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3d/Vista_de_Salamanca_desde_el_puente_romano.jpg/1280px-Vista_de_Salamanca_desde_el_puente_romano.jpg",
        "credit": "Wikimedia Commons · CC BY-SA",
    },
}


def curated_spain_image(name: str) -> dict | None:
    """Foto verificada de un municipio español, si está en el set curado."""
    entry = CURATED_SPAIN_IMAGES.get(_norm(name))
    if not entry:
        return None
    return {
        "url": entry["url"],
        "alt": f"Imagen de {name}",
        "credit": entry.get("credit", "Wikimedia Commons"),
        "source": "curated",
    }
