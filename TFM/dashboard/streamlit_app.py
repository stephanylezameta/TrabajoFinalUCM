from __future__ import annotations

"""Punto de entrada de TUI Data Intelligence."""

import os
from html import escape

import streamlit as st

st.set_page_config(
    page_title="TUI Data Intelligence",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _bridge_secrets_to_env() -> None:
    """Publica los secretos de Streamlit como variables de entorno.

    Los servicios se configuran con ``os.getenv`` para poder usarse sin
    Streamlit (tests, notebook, scripts). En Streamlit Community Cloud la
    configuración llega por ``st.secrets``, así que aquí se tiende el puente.
    Las variables de entorno ya definidas tienen prioridad.
    """
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
from components.ui import fmt_ts, status_copy  # noqa: E402
from database.init_db import init_db  # noqa: E402
from services.alert_service import get_system_status  # noqa: E402
from services.data_control_service import (  # noqa: E402
    bootstrap_missing_sources,
    seed_data_sources,
)
from services.tracking_service import create_session, register_event  # noqa: E402
from views.control_web import render_control_web  # noqa: E402
from views.data_model import render_data_model  # noqa: E402
from views.recommender import render_recommender  # noqa: E402
from views.tdrs import render_tdrs, render_tdrs_sidebar_controls  # noqa: E402

inject_styles()

NAV_TDRS = "Simulador TDRS"
NAV_RECO = "Recomendador España"
NAV_CONTROL = "Control Web"
NAV_DATA = "Datos / modelo"
NAV = [NAV_TDRS, NAV_RECO, NAV_CONTROL, NAV_DATA]


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
          <div><div class="tui-brand-title">Data Intelligence</div><div class="tui-brand-sub">Madrid UI · Operations</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_status() -> None:
    system = get_system_status()
    status_text, status_css = status_copy(system["status"])
    st.sidebar.markdown(
        f"""
        <div class="sidebar-status">
          <div class="sidebar-status-row"><span class="status-dot dot-{status_css}"></span>{escape(status_text)}</div>
          <div class="sidebar-time">Última actualización · {escape(fmt_ts(system.get('last_update')))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    bootstrap()
    if "session_id" not in st.session_state:
        st.session_state.session_id = create_session(source="streamlit")
    if "page_views" not in st.session_state:
        st.session_state.page_views = set()

    render_sidebar_brand()
    view = st.sidebar.radio("Vista", NAV, index=0, key="sidebar_view")

    # El sidebar del simulador solo existe dentro de su propia vista.
    tdrs_controls = None
    if view == NAV_TDRS:
        if "tdrs_scenario" not in st.session_state:
            st.session_state.tdrs_scenario = "Equilibrado"
        tdrs_controls = render_tdrs_sidebar_controls()

    render_sidebar_status()

    # La app se instrumenta a sí misma: cada vista visitada queda registrada.
    if view not in st.session_state.page_views:
        register_event(
            st.session_state.session_id,
            "page_view",
            view,
            dedupe_key=f"page_view:{view}",
        )
        st.session_state.page_views.add(view)

    if view == NAV_TDRS:
        render_tdrs(tdrs_controls)
    elif view == NAV_RECO:
        render_recommender()
    elif view == NAV_CONTROL:
        render_control_web()
    else:
        render_data_model()


main()
