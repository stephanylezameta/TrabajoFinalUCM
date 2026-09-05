from __future__ import annotations

"""Recursos gráficos de la interfaz.

Los PNG locales se embeben en base64 para no depender de rutas servidas por
Streamlit. Las fotografías del Top 3 se sirven desde Wikimedia Commons con su
atribución; los créditos completos están en ``docs/image_credits.md``.
"""

import base64
from functools import lru_cache
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
LOGO_PATH = ASSETS_DIR / "tui_logo.png"


@lru_cache(maxsize=16)
def get_png_data_uri(path: Path) -> str:
    """Devuelve una imagen PNG local embebida para usarla en HTML de Streamlit."""
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def get_logo_data_uri() -> str:
    return get_png_data_uri(LOGO_PATH)


LOGO_DATA_URI = get_logo_data_uri()

# Ranking: se conservan los minerales de oro, plata y bronce solicitados.
RANK_ICON_URLS = [
    "https://img.icons8.com/color/1200/gold-ore.jpg",
    "https://img.icons8.com/color/1200/silver-ore.jpg",
    "https://img.icons8.com/color/1200/bronze-ore.jpg",
]

# Escenarios: imágenes aportadas por el usuario y empaquetadas localmente.
# Esto evita depender de URLs externas para los tres accesos principales.
SCENARIO_ICON_URLS = {
    "Popular": get_png_data_uri(ASSETS_DIR / "scenario_popular_van_gogh.png"),
    "Equilibrado": get_png_data_uri(ASSETS_DIR / "scenario_equilibrado_coliseo.png"),
    "Explorador": get_png_data_uri(ASSETS_DIR / "scenario_explorador_brujula.png"),
}

# Fotografías del Top 3. Se sirven desde Wikimedia Commons para que la app
# mantenga imágenes reales de los destinos sin inflar el paquete local.
# Créditos/licencias se muestran dentro de cada tarjeta.
DESTINATION_IMAGES = {
    "Algarve": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/2/23/Algarve_coast_of_Portugal.jpg",
        "alt": "Costa del Algarve, Portugal",
        "credit": "Ned Dwyer · Wikimedia Commons · CC BY-SA 4.0",
    },
    "Mallorca": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/4/46/Mallorca_Coast_R01.jpg",
        "alt": "Costa norte de Mallorca, España",
        "credit": "Marc Ryckaert · Wikimedia Commons · CC BY 3.0",
    },
    "Split": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/b/bd/Split_harbor_view.jpg",
        "alt": "Vista del puerto de Split, Croacia",
        "credit": "Ryan Matzner y Rachel Pestik · Wikimedia Commons · dominio público",
    },
    "Dubrovnik": {
        "url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/d/dc/View_of_Dubrovnik_Old_Town_at_night.jpg/960px-View_of_Dubrovnik_Old_Town_at_night.jpg",
        "alt": "Vista del casco histórico de Dubrovnik, Croacia",
        "credit": "hozinja · Wikimedia Commons · CC BY 2.0",
    },
    "Zadar": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b7/A_view_to_the_historical_center_of_Zadar%2C_Croatia_surrounded_by_the_Adriatic_Sea_%2848607828812%29.jpg/1280px-A_view_to_the_historical_center_of_Zadar%2C_Croatia_surrounded_by_the_Adriatic_Sea_%2848607828812%29.jpg",
        "alt": "Vista del centro histórico de Zadar, Croacia",
        "credit": "dronepicr · Wikimedia Commons · CC BY 2.0",
    },
}
