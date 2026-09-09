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

NAV_OPTIONS = ["Panel de redistribución", "Recomendador", "Control Web"]

# Respuesta simulada del modelo para el panel de redistribución.
_TDRS_RANKING = [
    {
        "rank": 1,
        "destination": {"name": "Cadaqués", "province": "Girona",
                        "autonomous_community": "Cataluña", "primary_typology": "Costa"},
        "recommendation_score": 0.71,
        "popularity_profile": {"index": 0.22},
        "climate_profile": {"sunny_days": 24, "temperature_mean_c": 25},
        "what_it_offers": {"poi_count": 120},
    },
    {
        "rank": 2,
        "destination": {"name": "Comillas", "province": "Cantabria",
                        "autonomous_community": "Cantabria", "primary_typology": "Costa"},
        "recommendation_score": 0.66,
        "popularity_profile": {"index": 0.31},
        "climate_profile": {"sunny_days": 17, "temperature_mean_c": 22},
        "what_it_offers": {"poi_count": 90},
    },
    {
        "rank": 3,
        "destination": {"name": "Ronda", "province": "Málaga",
                        "autonomous_community": "Andalucía", "primary_typology": "Interior"},
        "recommendation_score": 0.6,
        "popularity_profile": {"index": 0.45},
        "climate_profile": {"sunny_days": 27, "temperature_mean_c": 28},
        "what_it_offers": {"poi_count": 140},
    },
]


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


def test_sidebar_exposes_the_three_views():
    app = _run()
    assert app.sidebar.radio[0].options == NAV_OPTIONS


@pytest.mark.parametrize("view", NAV_OPTIONS)
def test_every_view_renders_without_exception(view):
    app = _run(view)
    assert not app.exception, f"{view}: {[str(e) for e in app.exception]}"


def test_tdrs_view_shows_policy_sliders():
    app = _run("Panel de redistribución")
    assert not app.exception
    # Dial de popularidad + siete pesos de interés + mes de referencia.
    assert len(app.sidebar.slider) >= 7


def test_tdrs_view_renders_redistribution_metrics(monkeypatch):
    """Con el modelo conectado, el panel muestra métricas útiles para el viajero.

    Tras el rediseño el panel dejó de mostrar tecnicismos (índice de Gini,
    popularidad media) y muestra señales de decisión de viaje: días de sol,
    satisfacción y cuántas alternativas con menos gente hay. Las métricas de
    precio solo aparecen si el modelo envía precio, así que aquí no se exigen.
    """
    from services import recommendation_api_service as reco

    monkeypatch.setenv("TUI_RECO_API_BASE", "https://example.invalid/api/recommendations")
    monkeypatch.setenv("TUI_RECO_API_KEY", "clave-de-prueba")
    monkeypatch.setenv("TUI_MODEL_BACKEND", "azure")
    reco.reset_state()
    monkeypatch.setattr(
        reco, "fetch_recommendations",
        lambda payload, use_cache=True: {
            "ok": True, "error": None, "error_kind": None,
            "recommendation_id": "tdrs-1", "ranking": _TDRS_RANKING,
            "warnings": [], "from_cache": False,
        },
    )

    app = _run("Panel de redistribución")
    assert not app.exception, [str(e) for e in app.exception]
    labels = [m.label for m in app.metric]
    assert "Días de sol" in labels
    assert "Alternativas con menos gente" in labels
    # El tecnicismo de concentración ya no se muestra al viajero.
    assert "Concentración Gini" not in labels
    reco.reset_state()


def test_tdrs_view_degrades_without_model(monkeypatch):
    """Sin modelo conectado el panel informa, no rompe ni deja pantalla vacía."""
    from services import recommendation_api_service as reco

    monkeypatch.delenv("TUI_RECO_API_BASE", raising=False)
    monkeypatch.delenv("TUI_RECO_API_URL", raising=False)
    reco.reset_state()
    app = _run("Panel de redistribución")
    assert not app.exception, [str(e) for e in app.exception]
    # Los controles de política siguen visibles aunque no haya modelo.
    assert len(app.sidebar.slider) >= 7


def test_control_web_shows_commercial_kpis():
    app = _run("Control Web")
    labels = [m.label for m in app.metric]
    for expected in ("Sesiones", "Clics", "Reservas", "Ingresos", "ROI"):
        assert expected in labels


def test_recommender_view_degrades_without_endpoint():
    """Sin API configurada la vista informa, no rompe ni inventa resultados."""
    app = _run("España")
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

    app = _run("España")
    assert not app.exception, [str(e) for e in app.exception]

    # El nombre del destino recomendado aparece en el bloque destacado.
    rendered = " ".join(block.value for block in app.markdown)
    assert "offer-media" in rendered, "falta el bloque de recomendación destacada"
    assert "Níjar" in rendered, "el destino recomendado no se muestra"
    reco.reset_state()


def test_recommender_form_offers_documented_vocabulary():
    """El selector ofrece exactamente los siete intereses que acepta la API."""
    from services.recommendation_api_service import INTEREST_LABELS

    app = _run("España")
    interests = app.multiselect[0]
    # AppTest expone las opciones ya formateadas con `format_func`.
    assert set(interests.options) == set(INTEREST_LABELS.values())
    assert len(interests.options) == 7

