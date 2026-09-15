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

import json
from html import escape

import streamlit.components.v1 as components

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


def render_cta(destination: str, label: str = "Ver opciones",
               key: str = "", height: int = 52) -> None:
    """Renderiza una CTA que abre la oferta de TUI en una PESTAÑA NUEVA real.

    Por qué así y no un ``<a>`` ni ``st.link_button``:

    En Streamlit Cloud la app se sirve dentro de un ``<iframe>``. Un
    ``<a target="_blank">`` puesto con ``st.markdown`` (documento principal) o un
    ``st.link_button`` acababan navegando DENTRO del iframe de la app, y como
    ``es.tui.com`` no permite mostrarse en un iframe (``X-Frame-Options``), el
    navegador mostraba «es.tui.com rechazó la conexión».

    ``st.components.v1.html`` crea su PROPIO iframe con ``sandbox`` que incluye
    ``allow-popups``/``allow-popups-to-escape-sandbox``. Desde ahí,
    ``window.open(url, "_blank")`` abre una pestaña nueva de navegador de verdad
    (fuera de cualquier iframe), que es lo único que TUI acepta. Es el patrón
    fiable para enlaces externos en Streamlit Cloud.
    """
    target_url = get_offer_url(str(destination or ""))
    if not _is_safe_tui_url(target_url):
        target_url = TUI_TARGET_URL

    url_js = json.dumps(target_url)
    label_html = escape(str(label))
    components.html(
        f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8">
        <style>
          html,body{{margin:0;padding:0;background:transparent}}
          .tui-cta{{
            display:flex;align-items:center;justify-content:center;
            width:100%;box-sizing:border-box;
            font-family:'Gotham','Segoe UI',Arial,sans-serif;
            font-weight:700;font-size:.92rem;letter-spacing:.01em;
            background:#0064c8;color:#fff;border:none;border-radius:10px;
            padding:.62rem 1rem;cursor:pointer;text-decoration:none;
            transition:background .15s ease, transform .15s ease;
          }}
          .tui-cta:hover{{background:#004f9e;transform:translateY(-1px)}}
          .tui-cta:active{{transform:translateY(0)}}
        </style>
        </head>
        <body>
          <a class="tui-cta" href={url_js} target="_blank" rel="noopener noreferrer"
             onclick="try{{window.open({url_js},'_blank','noopener');return false;}}catch(e){{}}">
            {label_html} ↗
          </a>
        </body>
        </html>
        """,
        height=height,
    )


def handle_pending_click() -> None:
    """Compatibilidad: ya no hay click-through que procesar.

    Se conserva la función (la invoca ``streamlit_app.py`` al arrancar) para no
    romper el import, pero no hace nada: los enlaces van directos a TUI.
    """
    return
