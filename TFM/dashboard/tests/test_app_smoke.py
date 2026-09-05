"""Smoke test de la interfaz con el runner oficial de Streamlit.

``AppTest`` ejecuta ``streamlit_app.py`` sin navegador y expone las excepciones
que se produzcan. Cubre el hueco que dejaba la suite anterior: el render no se
probaba en absoluto, así que un fallo de import o de plantilla solo aparecía al
abrir la app a mano.
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

NAV_OPTIONS = ["Simulador TDRS", "Recomendador España", "Control Web", "Datos / modelo"]


def _run(view: str | None = None) -> AppTest:
    app = AppTest.from_file(str(APP), default_timeout=TIMEOUT)
    # Sin endpoint configurado la vista del recomendador queda en modo
    # informativo y no se hacen llamadas de red durante los tests.
    app.run()
    if view is not None:
        app.session_state["sidebar_view"] = view
        app.run()
    return app


def test_app_starts_without_exception():
    app = _run()
    assert not app.exception, [str(e) for e in app.exception]


def test_sidebar_exposes_the_four_views():
    app = _run()
    assert app.sidebar.radio[0].options == NAV_OPTIONS


@pytest.mark.parametrize("view", NAV_OPTIONS)
def test_every_view_renders_without_exception(view):
    app = _run(view)
    assert not app.exception, f"{view}: {[str(e) for e in app.exception]}"


def test_tdrs_view_shows_weight_sliders():
    app = _run("Simulador TDRS")
    assert not app.exception
    # Cinco pesos del modelo más las dos restricciones.
    assert len(app.sidebar.slider) >= 7


def test_tdrs_view_renders_metrics():
    app = _run("Simulador TDRS")
    labels = [m.label for m in app.metric]
    assert "Elegibles" in labels


def test_control_web_shows_commercial_kpis():
    app = _run("Control Web")
    labels = [m.label for m in app.metric]
    for expected in ("Sesiones", "Clics", "Reservas", "Ingresos", "ROI"):
        assert expected in labels


def test_data_model_shows_technical_kpis():
    app = _run("Datos / modelo")
    labels = [m.label for m in app.metric]
    for expected in ("SQLite", "Tablas", "Fuentes activas"):
        assert expected in labels


def test_recommender_view_degrades_without_endpoint():
    """Sin API configurada la vista informa, no rompe ni inventa resultados."""
    app = _run("Recomendador España")
    assert not app.exception
    # El formulario sigue disponible para que el usuario vea el contrato.
    assert app.multiselect, "debería existir el selector de intereses"


def test_recommender_form_offers_documented_vocabulary():
    """El selector ofrece exactamente los siete intereses que acepta la API."""
    from services.recommendation_api_service import INTEREST_LABELS

    app = _run("Recomendador España")
    interests = app.multiselect[0]
    # AppTest expone las opciones ya formateadas con `format_func`.
    assert set(interests.options) == set(INTEREST_LABELS.values())
    assert len(interests.options) == 7
