from __future__ import annotations

"""Referencia geográfica de los destinos españoles del catálogo.

Datos geográficos objetivos (coordenadas del centroide, provincia, comunidad
autónoma y tipo de destino) para los destinos españoles que maneja la app. NO
contiene métricas de uso: las cifras de clics, impresiones o CTR se calculan en
``analytics_service`` a partir de los eventos reales y se unen aquí por nombre.

Sirve a «Monitor performance» para:
  - dibujar el mapa de interés turístico de España,
  - ofrecer los filtros de comunidad autónoma y tipo de destino,
  - relacionar el interés del usuario con la saturación del destino.

Las coordenadas son centroides de referencia (grado de precisión suficiente para
un mapa de puntos), en línea con ``data/destination_coordinates.csv``.
"""

from utils.text import normalize_text

# nombre -> (lat, lon, provincia, comunidad autónoma, tipo)
# Tipos: "Costa", "Ciudad", "Isla", "Interior".
SPAIN_DESTINATIONS: dict[str, dict] = {
    "Madrid": {"lat": 40.4168, "lon": -3.7038, "province": "Madrid", "ccaa": "Comunidad de Madrid", "type": "Ciudad"},
    "Barcelona": {"lat": 41.3874, "lon": 2.1686, "province": "Barcelona", "ccaa": "Cataluña", "type": "Ciudad"},
    "Sevilla": {"lat": 37.3891, "lon": -5.9845, "province": "Sevilla", "ccaa": "Andalucía", "type": "Ciudad"},
    "Granada": {"lat": 37.1773, "lon": -3.5986, "province": "Granada", "ccaa": "Andalucía", "type": "Ciudad"},
    "Córdoba": {"lat": 37.8882, "lon": -4.7794, "province": "Córdoba", "ccaa": "Andalucía", "type": "Ciudad"},
    "Málaga": {"lat": 36.7213, "lon": -4.4214, "province": "Málaga", "ccaa": "Andalucía", "type": "Costa"},
    "Costa del Sol": {"lat": 36.5100, "lon": -4.8826, "province": "Málaga", "ccaa": "Andalucía", "type": "Costa"},
    "Cádiz": {"lat": 36.5271, "lon": -6.2886, "province": "Cádiz", "ccaa": "Andalucía", "type": "Costa"},
    "Ronda": {"lat": 36.7462, "lon": -5.1612, "province": "Málaga", "ccaa": "Andalucía", "type": "Interior"},
    "Carmona": {"lat": 37.4713, "lon": -5.6461, "province": "Sevilla", "ccaa": "Andalucía", "type": "Interior"},
    "Osuna": {"lat": 37.2376, "lon": -5.1031, "province": "Sevilla", "ccaa": "Andalucía", "type": "Interior"},
    "Alicante": {"lat": 38.3452, "lon": -0.4810, "province": "Alicante", "ccaa": "Comunitat Valenciana", "type": "Costa"},
    "Valencia": {"lat": 39.4699, "lon": -0.3763, "province": "Valencia", "ccaa": "Comunitat Valenciana", "type": "Ciudad"},
    "Bilbao": {"lat": 43.2630, "lon": -2.9350, "province": "Bizkaia", "ccaa": "País Vasco", "type": "Ciudad"},
    "San Sebastián": {"lat": 43.3183, "lon": -1.9812, "province": "Gipuzkoa", "ccaa": "País Vasco", "type": "Costa"},
    "Mallorca": {"lat": 39.6953, "lon": 3.0176, "province": "Illes Balears", "ccaa": "Illes Balears", "type": "Isla"},
    "Menorca": {"lat": 39.9496, "lon": 4.1100, "province": "Illes Balears", "ccaa": "Illes Balears", "type": "Isla"},
    "Ibiza": {"lat": 38.9067, "lon": 1.4206, "province": "Illes Balears", "ccaa": "Illes Balears", "type": "Isla"},
    "Tenerife": {"lat": 28.2916, "lon": -16.6291, "province": "Santa Cruz de Tenerife", "ccaa": "Canarias", "type": "Isla"},
    "Santa Cruz de Tenerife": {"lat": 28.4636, "lon": -16.2518, "province": "Santa Cruz de Tenerife", "ccaa": "Canarias", "type": "Isla"},
    "Gran Canaria": {"lat": 27.9202, "lon": -15.5474, "province": "Las Palmas", "ccaa": "Canarias", "type": "Isla"},
    "Lanzarote": {"lat": 29.0469, "lon": -13.5899, "province": "Las Palmas", "ccaa": "Canarias", "type": "Isla"},
    "Fuerteventura": {"lat": 28.3587, "lon": -14.0537, "province": "Las Palmas", "ccaa": "Canarias", "type": "Isla"},
}

# Índice por nombre normalizado (sin tildes ni mayúsculas) para casar con los
# nombres libres que llegan en los eventos ("Córdoba", "M├ílaga" ya arreglado…).
_NORMALIZED_INDEX: dict[str, str] = {
    normalize_text(name): name for name in SPAIN_DESTINATIONS
}


def match_spain_destination(name: str) -> str | None:
    """Devuelve el nombre canónico del destino español para un nombre libre.

    Casa por forma normalizada e inclusión conservadora (p. ej. «Playa de
    Alicante» → «Alicante»). No inventa: si no reconoce el destino, devuelve
    ``None`` y quien llame decide cómo tratarlo.
    """
    key = normalize_text(name)
    if not key:
        return None
    if key in _NORMALIZED_INDEX:
        return _NORMALIZED_INDEX[key]
    for norm, canonical in _NORMALIZED_INDEX.items():
        if norm and (norm in key or key in norm):
            return canonical
    return None


def get_reference(name: str) -> dict | None:
    """Ficha geográfica del destino (coordenadas, provincia, CCAA, tipo)."""
    canonical = match_spain_destination(name)
    if canonical is None:
        return None
    data = dict(SPAIN_DESTINATIONS[canonical])
    data["destination"] = canonical
    return data


def community_options() -> list[str]:
    """Comunidades autónomas presentes en la referencia, ordenadas."""
    return sorted({d["ccaa"] for d in SPAIN_DESTINATIONS.values()})


def type_options() -> list[str]:
    """Tipos de destino presentes en la referencia, ordenados."""
    return sorted({d["type"] for d in SPAIN_DESTINATIONS.values()})
