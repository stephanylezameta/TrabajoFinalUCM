"""Datos base por destino para completar las tarjetas de recomendación.

El contrato del backend no siempre incluye temperatura media ni número de
puntos de interés, así que esas casillas salían como «—». Aquí se centraliza
una tabla curada de valores de referencia por destino (temperatura media anual
aproximada en °C y número orientativo de puntos de interés turísticos) que se
usa como *fallback* cuando el modelo no envía el dato.

Notas:
- Son valores de referencia divulgativos, no medidas en tiempo real. Sirven
  para que la tarjeta muestre siempre una cifra coherente por destino.
- La clave se normaliza (minúsculas, sin acentos) igual que en el resto de la
  app, para tolerar variantes que devuelva el motor.
- Un destino sin entrada aquí seguirá mostrando «—» (no se inventan datos).
"""

from __future__ import annotations

import unicodedata


def _normalize_key(text: str) -> str:
    plain = unicodedata.normalize("NFKD", str(text).lower())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return "".join(c if c.isalnum() else " " for c in plain).strip()


# Alias de nombres que el motor puede devolver → nombre canónico de la tabla.
_ALIASES: dict[str, str] = {
    "eivissa": "ibiza",
    "santa cruz de tenerife": "tenerife",
    "palma": "mallorca",
    "palma de mallorca": "mallorca",
    "donostia san sebastian": "san sebastian",
    "las palmas de gran canaria": "gran canaria",
    "alicante alacant": "alicante",
    "alacant": "alicante",
    "dubai": "dubai",
}


# destino canónico → (temperatura media anual °C, nº orientativo de POIs).
_FACTS: dict[str, tuple[int, int]] = {
    "Algarve": (18, 35),
    "Alicante": (18, 40),
    "Antalya": (19, 45),
    "Bali": (27, 50),
    "Barcelona": (16, 90),
    "Bilbao": (14, 45),
    "Cabo Verde": (25, 25),
    "Cádiz": (18, 42),
    "Cancún": (27, 38),
    "Cerdeña": (17, 40),
    "Córdoba": (18, 50),
    "Costa Amalfitana": (18, 44),
    "Costa del Sol": (19, 40),
    "Creta": (19, 48),
    "Dubái": (28, 55),
    "Fuerteventura": (21, 28),
    "Gran Canaria": (21, 45),
    "Granada": (15, 55),
    "Hurghada": (24, 30),
    "Ibiza": (18, 35),
    "Lanzarote": (21, 32),
    "Madrid": (15, 95),
    "Málaga": (19, 55),
    "Maldivas": (28, 20),
    "Mallorca": (18, 60),
    "Marrakech": (20, 45),
    "Menorca": (17, 38),
    "Naxos": (19, 30),
    "Phuket": (28, 40),
    "Punta Cana": (26, 28),
    "Riviera Maya": (26, 40),
    "Rodas": (19, 42),
    "San Sebastián": (14, 48),
    "Santorini": (19, 35),
    "Sevilla": (19, 70),
    "Sicilia": (18, 55),
    "Split": (16, 45),
    "Tenerife": (21, 50),
    "Túnez": (19, 45),
    "Valencia": (18, 65),
    "Zadar": (15, 40),
    "Dubrovnik": (16, 42),
}


# Mapa normalizado (clave sin acentos) → (temp, pois).
_FACTS_BY_KEY: dict[str, tuple[int, int]] = {
    _normalize_key(name): vals for name, vals in _FACTS.items()
}


def _resolve_key(destination: str) -> str:
    key = _normalize_key(destination)
    return _ALIASES.get(key, key)


def get_temperature_mean_c(destination: str) -> int | None:
    """Temperatura media anual aproximada (°C) del destino, o None si no consta."""
    if not destination:
        return None
    vals = _FACTS_BY_KEY.get(_resolve_key(destination))
    return vals[0] if vals else None


def get_poi_count(destination: str) -> int | None:
    """Número orientativo de puntos de interés del destino, o None si no consta."""
    if not destination:
        return None
    vals = _FACTS_BY_KEY.get(_resolve_key(destination))
    return vals[1] if vals else None
