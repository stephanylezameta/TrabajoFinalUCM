from __future__ import annotations

import ast
import hashlib
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from database.repositories import DestinationRepository, ProductRepository
from utils.text import slugify


class ReferenceParseError(RuntimeError):
    """El HTML de referencia no tiene la estructura esperada."""


# Delimitadores de cadena admitidos en los literales JavaScript de la propuesta.
_QUOTES = ("'", '"', "`")


def _scan_balanced(text: str, start: int) -> int:
    """Devuelve el índice del delimitador que cierra el que abre en ``start``.

    Recorre el texto respetando cadenas y escapes, de modo que un corchete o una
    llave dentro de un string no rompe el emparejamiento. Es lo que falla con un
    ``re.search`` no voraz cuando el contenido incluye ``];`` o ``}``.
    """
    pairs = {"[": "]", "{": "}", "(": ")"}
    opener = text[start]
    closer = pairs.get(opener)
    if closer is None:
        raise ReferenceParseError(f"'{opener}' no es un delimitador de apertura")

    depth = 0
    index = start
    quote: str | None = None
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in _QUOTES:
            quote = char
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise ReferenceParseError(f"No se encontró el cierre de '{opener}' abierto en {start}")


def _extract_js_array(text: str, variable: str) -> str:
    """Extrae el cuerpo del array asignado a ``variable`` en el HTML."""
    declaration = re.search(
        rf"(?:var|let|const)?\s*\b{re.escape(variable)}\b\s*=\s*\[",
        text,
    )
    if not declaration:
        raise ReferenceParseError(
            f"No se encontró la declaración de '{variable}' en el fichero"
        )
    open_index = declaration.end() - 1
    close_index = _scan_balanced(text, open_index)
    return text[open_index + 1:close_index]


def _iter_js_objects(array_body: str) -> Iterator[str]:
    """Itera los literales de objeto de primer nivel dentro de un array JS."""
    index = 0
    while index < len(array_body):
        if array_body[index] == "{":
            end = _scan_balanced(array_body, index)
            yield array_body[index + 1:end]
            index = end + 1
            continue
        index += 1


_KEY_VALUE = re.compile(
    r"""
    (?P<key>[A-Za-z_$][\w$]*|'[^']*'|"[^"]*")   # clave, con o sin comillas
    \s*:\s*
    (?P<value>
        '(?:[^'\\]|\\.)*'                        # cadena simple
      | "(?:[^"\\]|\\.)*"                        # cadena doble
      | [-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?  # número
      | true | false | null | undefined
    )
    """,
    re.VERBOSE,
)


def _parse_js_value(raw: str) -> Any:
    if raw[0] in ("'", '"'):
        return ast.literal_eval(raw)
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "undefined"}:
        return None
    return float(raw)


def _parse_js_object(js_obj: str) -> dict[str, Any]:
    """Parsea un literal de objeto JavaScript con valores escalares.

    Admite claves con y sin comillas, cadenas con comilla simple o doble,
    números en notación científica y ``true``/``false``/``null``. No admite
    valores anidados: la propuesta no los usa y aceptarlos silenciosamente
    ocultaría un cambio de formato que conviene detectar.
    """
    out: dict[str, Any] = {}
    for match in _KEY_VALUE.finditer(js_obj):
        key = match.group("key")
        if key[0] in ("'", '"'):
            key = key[1:-1]
        out[key] = _parse_js_value(match.group("value"))
    return out


def import_destinations_from_proposal_html(path: str | Path) -> int:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    array_body = _extract_js_array(text, "DESTINOS")
    rows = []
    for obj_text in _iter_js_objects(array_body):
        d = _parse_js_object(obj_text)
        if not d.get("n"):
            continue
        country_label = str(d.get("pais", ""))
        country_name = country_label.split(" - ", 1)[0].strip() or None
        rows.append({
            "destination_id": slugify(d["n"]),
            "name": d["n"],
            "zone": d.get("zona"),
            "country_label": country_label or None,
            "country_name": country_name,
            "affinity": d.get("afinidad"),
            "demand": d.get("demanda"),
            "occupancy": d.get("ocupacion"),
            "local_impact": d.get("impacto"),
            "seasonality": d.get("temporada"),
            "accessibility": d.get("accesibilidad"),
            "sustainability": d.get("sostenibilidad"),
            "reference_price_eur": d.get("precio"),
            "co2_kg": d.get("co2"),
            "source": Path(path).name,
            "extra_data": json.dumps({"source_object": d}, ensure_ascii=False),
        })
    return DestinationRepository().upsert_many(rows)


def _float_from_text(text: str) -> float | None:
    if not text:
        return None
    m = re.search(r"(\d+(?:[\.,]\d+)?)", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def _card_text(card: Any, *selectors: str) -> str | None:
    """Primer texto no vacío entre varios selectores. ``None`` si no hay ninguno.

    Aceptar alternativas evita que un renombrado de clase en el HTML de origen
    vacíe la columna en silencio.
    """
    for selector in selectors:
        element = card.select_one(selector)
        if element is None:
            continue
        text = element.get_text(" ", strip=True)
        if text:
            return text
    return None


def import_products_from_experience_html(path: str | Path) -> int:
    """Extrae las tarjetas visibles del HTML sin ejecutar JavaScript."""
    html = Path(path).read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    products = []
    for card in soup.select(".offer"):
        title = _card_text(card, ".offer-name", ".offer-title", "h3")
        if not title:
            continue
        destination = _card_text(card, ".offer-dest", ".offer-destination")
        meta = _card_text(card, ".offer-meta") or ""
        description = _card_text(card, ".offer-ai-txt", ".offer-desc")
        route = _card_text(card, ".offer-route")
        img = card.select_one("img")
        image_url = img.get("src") if img else None
        rating_text = _card_text(card, ".offer-rating") or ""
        price_text = _card_text(card, ".offer-price .new", ".offer-price") or ""
        days = re.search(r"(\d+)\s*d[íi]as", meta, re.I)
        nights = re.search(r"(\d+)\s*noches", meta, re.I)
        parts = [p.strip() for p in re.split(r"\s*[-·]\s*", meta) if p.strip()]
        board = parts[1] if len(parts) > 1 else None
        source_city = parts[2] if len(parts) > 2 else None
        pid = "html-" + hashlib.sha1(f"{title}|{destination}".encode("utf-8")).hexdigest()[:12]
        products.append({
            "product_id": pid,
            "title": title,
            "destination": destination,
            "hotel": None,
            "price": _float_from_text(price_text),
            "currency": "EUR",
            "duration_days": int(days.group(1)) if days else None,
            "nights": int(nights.group(1)) if nights else None,
            "departure_date": None,
            "return_date": None,
            "rating": _float_from_text(rating_text),
            "board_basis": board,
            "transport": None,
            "airline": None,
            "availability": None,
            "discount": None,
            "description": description,
            "image_url": image_url,
            "detail_url": None,
            "source": Path(path).name,
            "extra_data": json.dumps({"route": route, "origin": source_city, "meta": meta}, ensure_ascii=False),
        })
    return ProductRepository().upsert_many(products)


def analyze_html(path: str | Path) -> dict[str, Any]:
    html = Path(path).read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    return {
        "title": soup.title.get_text(" ", strip=True) if soup.title else None,
        "h1": [x.get_text(" ", strip=True) for x in soup.find_all("h1")],
        "h2": [x.get_text(" ", strip=True) for x in soup.find_all("h2")],
        "h3": [x.get_text(" ", strip=True) for x in soup.find_all("h3")],
        "links": len(soup.find_all("a")),
        "forms": len(soup.find_all("form")),
        "inputs_selects": len(soup.find_all(["input", "select"])),
        "buttons": [x.get_text(" ", strip=True) for x in soup.find_all("button") if x.get_text(" ", strip=True)],
    }
