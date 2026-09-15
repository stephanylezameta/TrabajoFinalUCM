"""Smoke test de la interfaz con el runner oficial de Streamlit.

``AppTest`` ejecuta la app sin navegador y expone las excepciones que se
produzcan. Cubre el hueco que dejaba la suite anterior: el render no se probaba
en absoluto, así que un fallo de import o de plantilla solo aparecía al abrir la
app a mano.

La app usa navegación multipágina (``st.navigation`` con rutas /chat, /explorar
y /seguimiento). ``AppTest`` no permite cambiar de página programáticamente, así
que cada vista se prueba de forma aislada ejecutando su función-página con
``AppTest.from_function``. El arranque compartido (sesión, page_views) se
replica en un pequeño envoltorio de test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit.testing.v1", reason="Requiere Streamlit >= 1.28")

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"

# El arranque hace bootstrap de la base y puede buscar imágenes, así que se da
# margen suficiente para evitar falsos negativos por timeout.
TIMEOUT = 120

# Etiquetas de navegación reales de la app (ver NAV en streamlit_app.py).
NAV_ASSISTANT = "TUI Travel Assistant"
NAV_RECO = "Explora"
NAV_CONTROL = "Monitor performance "

# Nombre de la función-página en streamlit_app por cada vista.
PAGE_FUNCS = {
    NAV_ASSISTANT: "page_assistant",
    NAV_RECO: "page_explore",
    NAV_CONTROL: "page_control",
}


def _run_default() -> AppTest:
    """Ejecuta la app completa: st.navigation abre la página por defecto (chat)."""
    app = AppTest.from_file(str(APP), default_timeout=TIMEOUT)
    app.run()
    return app


def _page_script() -> None:
    """Script de AppTest que ejecuta una función-página aislada.

    ``AppTest.from_function`` ejecuta este script en un contexto propio sin
    clausura, así que la página a ejecutar se pasa por ``query_params`` (que
    AppTest sí permite fijar antes de correr). Replica el arranque mínimo de
    ``main`` (sesión y set de page_views).
    """
    import streamlit as st

    import streamlit_app as app
    from services.tracking_service import create_session

    func_name = st.query_params.get("_page_func", "page_assistant")

    app.bootstrap()
    if "session_id" not in st.session_state:
        # Se crea una sesión real: los eventos (page_view) referencian
        # sessions.session_id por clave foránea, así que debe existir en la tabla.
        st.session_state.session_id = create_session(source="test")
    if "page_views" not in st.session_state:
        st.session_state.page_views = set()
    getattr(app, func_name)()


def _run_page(view: str) -> AppTest:
    """Ejecuta una vista concreta de forma aislada.

    Evita depender del cambio de página en AppTest (no soportado): ejecuta
    directamente la función-página, seleccionada por query param.
    """
    at = AppTest.from_function(_page_script, default_timeout=TIMEOUT)
    at.query_params["_page_func"] = PAGE_FUNCS[view]
    at.run()
    return at


def test_app_starts_without_exception():
    app = _run_default()
    assert not app.exception, [str(e) for e in app.exception]


def test_default_page_renders_the_assistant():
    """La página por defecto (/chat) es el asistente y renderiza su cabecera."""
    app = _run_default()
    rendered = " ".join(block.value for block in app.markdown)
    assert NAV_ASSISTANT in rendered


@pytest.mark.parametrize("view", list(PAGE_FUNCS))
def test_every_view_renders_without_exception(view):
    app = _run_page(view)
    assert not app.exception, f"{view}: {[str(e) for e in app.exception]}"


def test_control_web_shows_performance_dashboard():
    """El panel «Monitor performance» muestra sus secciones y KPIs de analítica.

    Los KPIs se renderizan como tarjetas HTML (no st.metric) para controlar la
    jerarquía visual, así que se comprueban sobre el markdown renderizado junto
    a los títulos de sección del panel.
    """
    app = _run_page(NAV_CONTROL)
    rendered = " ".join(block.value for block in app.markdown)
    # Secciones clave del panel de analítica turística.
    for section in (
        "KPIs principales",
        "Mapa de interés turístico",
        "Funnel de interacción",
        "Saturación vs. interés",
    ):
        assert section in rendered, f"falta la sección «{section}»"
    # KPIs principales presentes como tarjetas.
    for kpi in ("Recomendaciones", "Clics", "CTR"):
        assert kpi in rendered, f"falta el KPI «{kpi}»"


def test_recommender_view_degrades_without_endpoint():
    """Sin API configurada la vista informa, no rompe ni inventa resultados."""
    app = _run_page(NAV_RECO)
    assert not app.exception
    # El formulario sigue disponible para que el usuario vea el contrato.
    assert app.multiselect, "debería existir el selector de intereses"


def test_recommender_shows_visible_recommendation(monkeypatch):
    """Con la API configurada, la vista muestra una recomendación sin pedirla.

    No debe hacer falta rellenar el formulario: el destino recomendado aparece
    destacado en cuanto se abre la vista.
    """
    from services import recommendation_api_service as reco
    from tests.test_recommendation_api import SAMPLE_RESPONSE

    monkeypatch.setenv("TUI_MODELO_API_BASE", "https://example.invalid")
    reco.reset_state()
    # Se simula la respuesta ya normalizada al formato interno de la UI (lo que
    # devuelve fetch_recommendations): rankings adaptados a filas destination/*.
    payload = reco.build_payload(["coast_beach"])
    normalizado = reco._normalize_response(SAMPLE_RESPONSE, payload)
    monkeypatch.setattr(
        reco, "fetch_recommendations",
        lambda payload, use_cache=True, session_id=None: {
            **normalizado, "from_cache": False,
        },
    )

    app = _run_page(NAV_RECO)
    assert not app.exception, [str(e) for e in app.exception]

    # El nombre del destino recomendado aparece en el bloque destacado.
    rendered = " ".join(block.value for block in app.markdown)
    assert "offer-media" in rendered, "falta el bloque de recomendación destacada"
    assert "Cerdeña" in rendered, "el destino recomendado no se muestra"
    reco.reset_state()


def test_recommender_form_offers_documented_vocabulary():
    """El selector ofrece exactamente los siete intereses que acepta la API."""
    from services.recommendation_api_service import INTEREST_LABELS

    app = _run_page(NAV_RECO)
    interests = app.multiselect[0]
    # AppTest expone las opciones ya formateadas con `format_func`.
    assert set(interests.options) == set(INTEREST_LABELS.values())
    assert len(interests.options) == 7
