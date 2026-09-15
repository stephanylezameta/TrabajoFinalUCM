from __future__ import annotations

"""Cargando..."""

import os

import streamlit as st

st.set_page_config(
    page_title="TUI Data Intelligence",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _bridge_secrets_to_env() -> None:
   
    keys = (
        "TUI_RECO_API_URL",
        "TUI_RECO_API_BASE",
        "TUI_RECO_API_KEY",
        "TUI_RECO_API_TIMEOUT",
        "TUI_AI_ENDPOINT",
        "TUI_AI_API_KEY",
        "TUI_AI_TIMEOUT",
        "TUI_IMAGE_USER_AGENT",
        "TUI_IMAGE_TIMEOUT_SECONDS",
        "TUI_DB_PATH",
        "TUI_MODEL_BACKEND",
        "TUI_MODELO_API_BASE",
    )
    try:
        secrets = st.secrets
    except Exception:  # noqa: BLE001 - sin secrets.toml no hay nada que puentear
        return
    for key in keys:
        if os.getenv(key):
            continue
        try:
            value = secrets[key]
        except Exception:  # noqa: BLE001 - clave ausente
            continue
        if value not in (None, ""):
            os.environ[key] = str(value)


_bridge_secrets_to_env()

from components.assets import LOGO_DATA_URI  # noqa: E402
from components.styles import inject_styles  # noqa: E402
from database.init_db import init_db  # noqa: E402
from services.data_control_service import (  # noqa: E402
    bootstrap_missing_sources,
    seed_data_sources,
)
from services.click_tracking import handle_pending_click  # noqa: E402
from services.tracking_service import create_session, register_event  # noqa: E402
from views.control_web import render_control_web  # noqa: E402
from views.recommender import render_assistant_chat_view, render_recommender  # noqa: E402

inject_styles()

NAV_ASSISTANT = "TUI Travel Assistant"
NAV_RECO = "Explora"
NAV_CONTROL = "Monitor performance "
NAV = [NAV_ASSISTANT, NAV_RECO, NAV_CONTROL]


@st.cache_resource(show_spinner=False)
def bootstrap() -> bool:
    """Crea el esquema, siembra las fuentes e importa las tablas vacías.

    Cacheado a nivel de proceso: es una operación de arranque, no de render. Sin
    la caché se reejecutaba en cada interacción del usuario.
    """
    init_db()
    seed_data_sources()
    bootstrap_missing_sources()
    return True


def render_sidebar_brand() -> None:
    st.sidebar.markdown(
        f"""
        <div class="tui-brand">
          <div class="tui-logo-wrap"><img class="tui-logo-img" src="{LOGO_DATA_URI}" alt="TUI logo"></div>
          <div><div class="tui-brand-title">TUI Travel</div><div class="tui-brand-sub">Assistant</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _track_page_view(view: str) -> None:
    """Registra la visita a una vista una sola vez por sesión (dedupe)."""
    if view not in st.session_state.page_views:
        register_event(
            st.session_state.session_id,
            "page_view",
            view,
            dedupe_key=f"page_view:{view}",
        )
        st.session_state.page_views.add(view)


# Páginas de navegación. Cada una registra su page_view y delega en la vista
# correspondiente. Los títulos coinciden con las etiquetas históricas del menú.
def page_assistant() -> None:
    _track_page_view(NAV_ASSISTANT)
    render_assistant_chat_view()


def page_explore() -> None:
    _track_page_view(NAV_RECO)
    render_recommender()


def page_control() -> None:
    _track_page_view(NAV_CONTROL)
    render_control_web()


def main() -> None:
    bootstrap()
    if "session_id" not in st.session_state:
        st.session_state.session_id = create_session(source="streamlit")
    if "page_views" not in st.session_state:
        st.session_state.page_views = set()

    # Instrumentación de clics: si la URL trae un clic pendiente en una CTA de
    # recomendación (la pestaña de TUI ya se abrió en el navegador), se registra
    # el evento recommendation_click y se limpia la URL.
    handle_pending_click()

    render_sidebar_brand()

    # Navegación multipágina con rutas limpias en la URL: /chat, /explorar y
    # /seguimiento. st.navigation pinta el selector en el sidebar y sincroniza la
    # ruta con la barra de direcciones (compartible y con historial de navegador).
    pages = [
        st.Page(page_assistant, title=NAV_ASSISTANT, url_path="chat", default=True),
        st.Page(page_explore, title=NAV_RECO, url_path="explorar"),
        st.Page(page_control, title=NAV_CONTROL, url_path="seguimiento"),
    ]
    st.navigation(pages).run()


main()
