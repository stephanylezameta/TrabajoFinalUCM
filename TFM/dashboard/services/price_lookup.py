from __future__ import annotations

"""Cruce de precio orientativo por destino.

El recomendador devuelve municipios españoles (Níjar, Ronda...) que no siempre
coinciden con el catálogo comercial (`destinations`). Aquí se cruza el nombre
—normalizado (minúsculas, sin acentos)— contra ese catálogo para recuperar un
``reference_price_eur`` cuando exista.

IMPORTANTE: ese precio es ORIENTATIVO, no un precio de paquete real. Se deriva de
la mediana de precios de experiencias del destino (ver
``scripts/export_catalog.py``). La vista lo etiqueta como tal y solo lo muestra
cuando hay coincidencia; para la mayoría de municipios no habrá precio y la
tarjeta cae con elegancia a los datos del modelo.
"""

from typing import Any

from database.connection import db_session
from utils.text import normalize_text

# Caché en memoria del catálogo: {nombre_normalizado: precio}. Se llena una vez
# por proceso; el catálogo cambia con muy poca frecuencia.
_price_by_name: dict[str, float] | None = None


def _load_catalog() -> dict[str, float]:
    global _price_by_name
    if _price_by_name is not None:
        return _price_by_name

    prices: dict[str, float] = {}
    try:
        with db_session() as conn:
            rows = conn.execute(
                "SELECT name, reference_price_eur FROM destinations "
                "WHERE reference_price_eur IS NOT NULL"
            ).fetchall()
    except Exception:  # noqa: BLE001 - sin BD/catálogo, simplemente no hay precio
        rows = []

    for row in rows:
        try:
            price = float(row["reference_price_eur"])
        except (TypeError, ValueError, KeyError):
            continue
        if price > 0:
            prices[normalize_text(row["name"])] = price

    _price_by_name = prices
    return prices


def reset_cache() -> None:
    """Limpia la caché del catálogo (pensado para tests)."""
    global _price_by_name
    _price_by_name = None


def reference_price(destination: dict[str, Any] | None) -> float | None:
    """Precio orientativo del destino, o ``None`` si no hay coincidencia.

    Cruza por nombre y, como respaldo, por provincia y comunidad autónoma. Todo
    normalizado (sin acentos ni mayúsculas) para tolerar variantes como
    «Málaga»/«Malaga».
    """
    if not destination:
        return None

    catalog = _load_catalog()
    if not catalog:
        return None

    for key in (
        destination.get("name"),
        destination.get("province"),
        destination.get("autonomous_community"),
    ):
        if not key:
            continue
        price = catalog.get(normalize_text(key))
        if price is not None:
            return price
    return None
