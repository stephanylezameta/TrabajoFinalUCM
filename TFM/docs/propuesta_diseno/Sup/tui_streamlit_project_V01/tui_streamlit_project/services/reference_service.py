from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from database.repositories import DestinationRepository, ProductRepository
from utils.text import slugify


def _parse_js_object(js_obj: str) -> dict[str, Any]:
    # Parser intencionalmente limitado: solo admite los objetos literales simples de DESTINOS.
    out: dict[str, Any] = {}
    for key, raw in re.findall(r"(\w+)\s*:\s*('(?:[^'\\]|\\.)*'|[-+]?\.?\d+(?:\.\d+)?)", js_obj):
        if raw.startswith("'"):
            out[key] = ast.literal_eval(raw)
        else:
            out[key] = float(raw)
    return out


def import_destinations_from_proposal_html(path: str | Path) -> int:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    match = re.search(r"var\s+DESTINOS\s*=\s*\[(.*?)\];", text, flags=re.S)
    if not match:
        return 0
    rows = []
    for obj_text in re.findall(r"\{([^{}]+)\}", match.group(1)):
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


def import_products_from_experience_html(path: str | Path) -> int:
    """Extrae las tarjetas visibles del HTML sin ejecutar JavaScript."""
    html = Path(path).read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    products = []
    for idx, card in enumerate(soup.select(".offer"), start=1):
        title_el = card.select_one(".offer-name")
        if not title_el:
            continue
        title = title_el.get_text(" ", strip=True)
        destination = (card.select_one(".offer-dest").get_text(" ", strip=True)
                       if card.select_one(".offer-dest") else None)
        meta = card.select_one(".offer-meta").get_text(" ", strip=True) if card.select_one(".offer-meta") else ""
        description = card.select_one(".offer-ai-txt").get_text(" ", strip=True) if card.select_one(".offer-ai-txt") else None
        route = card.select_one(".offer-route").get_text(" ", strip=True) if card.select_one(".offer-route") else None
        img = card.select_one("img")
        image_url = img.get("src") if img else None
        rating_text = card.select_one(".offer-rating").get_text(" ", strip=True) if card.select_one(".offer-rating") else ""
        price_text = card.select_one(".offer-price .new").get_text(" ", strip=True) if card.select_one(".offer-price .new") else ""
        days = re.search(r"(\d+)\s*dias", meta, re.I)
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
