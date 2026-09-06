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


def test_recommender_shows_visible_recommendation(monkeypatch):
    """Con la API configurada, la vista muestra una recomendación sin pedirla.

    No debe hacer falta rellenar el formulario: el destino recomendado aparece
    destacado en cuanto se abre la vista.
    """
    from services import recommendation_api_service as reco
    from tests.test_recommendation_api import SAMPLE_RESPONSE

    monkeypatch.setenv("TUI_RECO_API_BASE", "https://example.invalid/api/recommendations")
    monkeypatch.setenv("TUI_RECO_API_KEY", "clave-de-prueba")
    reco.reset_state()
    monkeypatch.setattr(
        reco, "fetch_recommendations",
        lambda payload, use_cache=True: {
            "ok": True, "error": None, "error_kind": None,
            "recommendation_id": "abc-123",
            "contract_version": "recommendation-response-v1",
            "generated_at": "2026-09-05T12:00:00+00:00",
            "engine": SAMPLE_RESPONSE["engine"],
            "normalized_input": {},
            "ranking": SAMPLE_RESPONSE["ranking"],
            "warnings": [], "from_cache": False,
        },
    )

    app = _run("Recomendador España")
    assert not app.exception, [str(e) for e in app.exception]

    # El nombre del destino recomendado aparece en el bloque destacado.
    rendered = " ".join(block.value for block in app.markdown)
    assert "hero-reco" in rendered, "falta el bloque de recomendación destacada"
    assert "Níjar" in rendered, "el destino recomendado no se muestra"
    reco.reset_state()


def test_recommender_form_offers_documented_vocabulary():
    """El selector ofrece exactamente los siete intereses que acepta la API."""
    from services.recommendation_api_service import INTEREST_LABELS

    app = _run("Recomendador España")
    interests = app.multiselect[0]
    # AppTest expone las opciones ya formateadas con `format_func`.
    assert set(interests.options) == set(INTEREST_LABELS.values())
    assert len(interests.options) == 7
