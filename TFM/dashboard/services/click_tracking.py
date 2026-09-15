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

import streamlit as st
import streamlit.components.v1 as components

from services.offer_links import FALLBACK_URL, get_offer_url

# Destino externo por defecto si no se resuelve una oferta concreta.
TUI_TARGET_URL = FALLBACK_URL

# Prefijo de los parámetros de URL que instrumentan el clic en una CTA de
# recomendación. El <a> abre TUI en pestaña nueva (gesto nativo) y, además,
# escribe estos parámetros en la URL de la app (documento padre) para que
# ``handle_pending_click`` registre el evento en el siguiente rerun.
_CLICK_PARAM = "cta_click"       # destino clicado
_CLICK_RID_PARAM = "cta_rid"     # recommendation_id (une clic con impresión)
_CLICK_POS_PARAM = "cta_pos"     # posición en el ranking
_CLICK_ORIGIN_PARAM = "cta_origin"


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


def _click_onclick_js(destination: str, recommendation_id: str = "",
                      position: int | None = None, origin: str = "") -> str:
    """Fragmento JS para el atributo ``onclick`` del ``<a>`` de la CTA.

    Al pulsar, además de abrir TUI en pestaña nueva (comportamiento nativo del
    ``<a target="_blank">``, que NO se cancela), escribe en la URL del documento
    PADRE (la app) unos parámetros que identifican el clic. El siguiente rerun de
    Streamlit los lee en ``handle_pending_click`` y registra el evento
    ``recommendation_click``. No redirige el iframe ni la app: solo añade
    parámetros y deja que el enlace haga su trabajo.

    Envuelto en ``try/catch`` para que, si el navegador bloquea el acceso al
    padre (p. ej. políticas de iframe muy estrictas), el enlace a TUI siga
    funcionando igual: la instrumentación es best-effort, la navegación no.
    """
    params = {
        _CLICK_PARAM: str(destination or ""),
        _CLICK_RID_PARAM: str(recommendation_id or ""),
        _CLICK_POS_PARAM: "" if position is None else str(position),
        _CLICK_ORIGIN_PARAM: str(origin or ""),
    }
    # Serializamos a JSON y lo escapamos para incrustarlo con seguridad en el
    # atributo HTML (comillas dobles → &quot;). El JS lo parsea y arma la query.
    payload = escape(json.dumps(params, ensure_ascii=False), quote=True)
    return (
        "try{"
        f"var p={payload};"
        "var w=window.parent;"
        "var u=new URL(w.location.href);"
        "Object.keys(p).forEach(function(k){"
        "if(p[k]!==''){u.searchParams.set(k,p[k]);}"
        "});"
        "w.history.replaceState(null,'',u.toString());"
        "w.dispatchEvent(new Event('popstate'));"
        "}catch(e){}"
    )


def render_cta(destination: str, label: str = "Ver opciones",
               key: str = "", height: int = 52,
               recommendation_id: str = "", position: int | None = None,
               origin: str = "") -> None:
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

    url_attr = escape(target_url, quote=True)
    label_html = escape(str(label))
    onclick_attr = escape(
        _click_onclick_js(destination, recommendation_id, position, origin),
        quote=True,
    )
    # El botón es un <a target="_blank"> PURO dentro del iframe del componente.
    # El clic nativo de un enlace target="_blank" es un gesto de usuario que el
    # navegador permite: abre una pestaña NUEVA de nivel de navegador (fuera de
    # cualquier iframe), que es lo único que TUI acepta (X-Frame-Options).
    #
    # Clave: NO se usa onclick con window.open + return false. Eso cancelaba el
    # enlace y, dentro del iframe, window.open podía quedar atrapado o ser
    # bloqueado por el popup blocker. Dejando actuar al <a> nativo, funciona.
    components.html(
        f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8">
        <style>
          html,body{{margin:0;padding:0;background:transparent;overflow:hidden}}
          .tui-cta{{
            display:flex;align-items:center;justify-content:center;
            width:100%;height:40px;box-sizing:border-box;
            font-family:'Gotham','Segoe UI',Arial,sans-serif;
            font-weight:700;font-size:.9rem;letter-spacing:.01em;
            background:#0064c8;color:#fff;border-radius:10px;
            text-decoration:none;cursor:pointer;
            transition:background .15s ease, transform .15s ease;
          }}
          .tui-cta:hover{{background:#004f9e;transform:translateY(-1px)}}
          .tui-cta:active{{transform:translateY(0)}}
        </style>
        </head>
        <body>
          <a class="tui-cta" href="{url_attr}" target="_blank" rel="noopener noreferrer"
             onclick="{onclick_attr}">
            {label_html} ↗
          </a>
        </body>
        </html>
        """,
        height=height,
    )


def render_card_link(destination: str, inner_html: str, height: int,
                     extra_css: str = "", recommendation_id: str = "",
                     position: int | None = None, origin: str = "") -> None:
    """Renderiza una TARJETA COMPLETA clicable que abre la oferta de TUI.

    Toda la tarjeta (imagen + textos) es el contenido de un ``<a target="_blank">``
    dentro del iframe del componente (``components.html``). Al hacer clic en la
    imagen o en cualquier parte de la tarjeta, se abre una pestaña nueva de nivel
    de navegador con la oferta de TUI. Esto sustituye a los botones sueltos y es
    fiable en Streamlit Cloud (donde un ``<a>`` embebido con ``st.markdown``
    navegaba dentro del iframe de la app y TUI rechazaba la conexión).

    ``inner_html`` es el HTML de la tarjeta (sin el ``<a>`` envolvente) y
    ``extra_css`` los estilos de las clases usadas en ese HTML (se inyectan
    dentro del iframe del componente, que no hereda el CSS global de la app).
    """
    target_url = get_offer_url(str(destination or ""))
    if not _is_safe_tui_url(target_url):
        target_url = TUI_TARGET_URL
    url_attr = escape(target_url, quote=True)
    onclick_attr = escape(
        _click_onclick_js(destination, recommendation_id, position, origin),
        quote=True,
    )
    components.html(
        f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8">
        <style>
          html,body{{margin:0;padding:0;background:transparent;
            font-family:'Gotham','Segoe UI',Arial,sans-serif}}
          a.card-link{{display:block;text-decoration:none;color:inherit;cursor:pointer}}
          {extra_css}
        </style>
        </head>
        <body>
          <a class="card-link" href="{url_attr}" target="_blank" rel="noopener noreferrer"
             onclick="{onclick_attr}">
            {inner_html}
          </a>
        </body>
        </html>
        """,
        height=height,
    )


def handle_pending_click() -> None:
    """Registra el clic pendiente en una CTA de recomendación, si lo hay.

    Las CTAs abren TUI en pestaña nueva (``<a target="_blank">``) y, al pulsarse,
    escriben en la URL de la app unos parámetros (``cta_click`` y compañía). Al
    volver el foco a la app, Streamlit re-ejecuta el script y esta función lee
    esos parámetros, emite el evento real ``recommendation_click`` y limpia la
    URL para no volver a contarlo.

    La navegación a TUI ya ocurrió en el navegador (pestaña nueva); aquí solo se
    instrumenta. Es idempotente: el ``dedupe_key`` evita duplicar el mismo clic
    aunque el usuario recargue con los parámetros aún en la URL.
    """
    # Import diferido para evitar un ciclo de imports en el arranque.
    from services.tracking_service import register_event

    try:
        params = st.query_params
    except Exception:  # noqa: BLE001 - versiones antiguas / contexto sin sesión
        return

    destination = params.get(_CLICK_PARAM)
    if not destination:
        return

    recommendation_id = params.get(_CLICK_RID_PARAM) or ""
    position_raw = params.get(_CLICK_POS_PARAM) or ""
    origin = params.get(_CLICK_ORIGIN_PARAM) or ""
    try:
        position = int(position_raw) if position_raw else None
    except (TypeError, ValueError):
        position = None

    session_id = st.session_state.get("session_id")
    if session_id:
        register_event(
            session_id,
            "recommendation_click",
            "recomendacion",
            destination=str(destination),
            metadata={
                "recommendation_id": recommendation_id,
                "position": position,
                "origin": origin,
                "target": get_offer_url(str(destination)),
            },
            # Un mismo clic (misma reco + destino + posición) se cuenta una vez.
            dedupe_key=f"reco_click:{recommendation_id}:{position}:{destination}",
        )

    # Limpia los parámetros de la URL para no re-registrar en el siguiente rerun.
    for key in (_CLICK_PARAM, _CLICK_RID_PARAM, _CLICK_POS_PARAM, _CLICK_ORIGIN_PARAM):
        try:
            if key in st.query_params:
                del st.query_params[key]
        except Exception:  # noqa: BLE001 - best-effort
            pass
