from __future__ import annotations

"""Enlaces «Ver opciones» de las recomendaciones hacia las ofertas de TUI.

Cada tarjeta enlaza DIRECTAMENTE a la oferta real de TUI del destino y se abre
en una pestaña nueva. Se evita a propósito el patrón de *click-through* (pasar
por la propia app para registrar el clic y luego redirigir): ese enfoque
dependía de un iframe de ``st.components.v1.html`` para ejecutar el salto de
página, y ese iframe no funciona de forma fiable en todos los entornos
(quedaba la página en blanco sin redirigir). El enlace directo siempre navega.

El mapa destino → URL vive en ``services.offer_links``.
"""

from services.offer_links import FALLBACK_URL, get_offer_url

# Destino externo por defecto si no se resuelve una oferta concreta.
TUI_TARGET_URL = FALLBACK_URL


def _is_safe_tui_url(url: str) -> bool:
    """Solo se consideran válidas URLs de dominios de TUI."""
    return isinstance(url, str) and (
        url.startswith("https://es.tui.com/")
        or url.startswith("https://viajeonline.es.tui.com/")
        or url.startswith("http://viajeonline.es.tui.com/")
    )


def build_click_href(destination: str, recommendation_id: str = "",
                     position: int | None = None, origin: str = "") -> str:
    """Devuelve el enlace de oferta de TUI para el destino recomendado.

    Es la URL real y definitiva del ``<a>`` de la tarjeta: al pulsarla el
    navegador va directo a la oferta de TUI (en pestaña nueva). Los parámetros
    ``recommendation_id``/``position``/``origin`` se mantienen por compatibilidad
    con las llamadas existentes, pero ya no se usan para instrumentar el salto.
    """
    target_url = get_offer_url(str(destination or ""))
    if not _is_safe_tui_url(target_url):
        target_url = TUI_TARGET_URL
    return target_url


def handle_pending_click() -> None:
    """Compatibilidad: ya no hay click-through que procesar.

    Se conserva la función (la invoca ``streamlit_app.py`` al arrancar) para no
    romper el import, pero no hace nada: los enlaces van directos a TUI.
    """
    return
