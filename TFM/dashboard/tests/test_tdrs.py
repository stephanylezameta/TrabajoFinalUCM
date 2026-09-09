"""Tests del Panel de redistribución (TDRS) y de su gateway al modelo.

Tras la reconversión, el panel ya no calcula el ranking por su cuenta: traduce
una política de redistribución a una llamada al modelo real a través de
``services.model_gateway`` (que hoy resuelve contra la Function de Azure). Los
tests cubren esa traducción, las métricas de reparto y la compatibilidad que se
conserva para el asistente conversacional de pesos.
"""

from __future__ import annotations

import pytest

from services import model_gateway
from services import recommendation_api_service as reco
from services.tdrs_service import (
    CSV_FACTORS,
    POLICY_PRESETS,
    PRESETS,
    gini,
    redistribution_metrics,
)


# --------------------------------------------------------------------------
# Utilidad de concentración
# --------------------------------------------------------------------------

def test_gini_uniform_is_zero():
    assert abs(gini([1, 1, 1, 1])) < 1e-12


def test_gini_nonnegative():
    assert gini([0, 0, 1, 1]) >= 0


def test_gini_grows_with_concentration():
    uniforme = gini([0.5, 0.5, 0.5, 0.5])
    concentrado = gini([0.9, 0.1, 0.05, 0.02])
    assert concentrado > uniforme


# --------------------------------------------------------------------------
# Compatibilidad con el asistente conversacional de pesos
# --------------------------------------------------------------------------

def test_weight_factor_keys_are_preserved_for_the_assistant():
    """El asistente sigue traduciendo lenguaje natural a estas seis señales."""
    expected = {
        "sunny_days_pct",
        "low_precipitation_pct",
        "popularity",
        "hospital_beds",
        "safety",
        "satisfaction",
    }
    assert {key for key, _, _ in CSV_FACTORS} == expected
    for scenario in ("Popular", "Equilibrado", "Explorador", "Personalizado"):
        assert set(PRESETS[scenario]) == expected, f"faltan pesos en {scenario}"


# --------------------------------------------------------------------------
# Escenarios de política de redistribución
# --------------------------------------------------------------------------

def test_policy_presets_span_from_traditional_to_redistributed():
    """El dial de popularidad separa turismo tradicional de demanda repartida."""
    assert set(POLICY_PRESETS) == {"Tradicional", "Equilibrado", "Redistribuido"}
    tradicional = POLICY_PRESETS["Tradicional"]["popularity_target"]
    redistribuido = POLICY_PRESETS["Redistribuido"]["popularity_target"]
    equilibrado = POLICY_PRESETS["Equilibrado"]["popularity_target"]
    # Menos popularidad = más redistribución.
    assert tradicional > equilibrado > redistribuido
    for name, preset in POLICY_PRESETS.items():
        assert 0.0 <= preset["popularity_target"] <= 1.0, name
        assert preset["interests"], f"{name} sin intereses de política"


# --------------------------------------------------------------------------
# Traducción de política -> contrato del modelo (gateway)
# --------------------------------------------------------------------------

def test_policy_to_payload_maps_popularity_target():
    payload = model_gateway.policy_to_payload({"popularity_target": 0.12})
    assert payload["preferences"]["popularity_target"] == 0.12
    assert payload["contract_version"] == reco.REQUEST_CONTRACT


def test_policy_to_payload_clamps_popularity_target():
    assert model_gateway.policy_to_payload(
        {"popularity_target": 2.5}
    )["preferences"]["popularity_target"] == 1.0
    assert model_gateway.policy_to_payload(
        {"popularity_target": -1.0}
    )["preferences"]["popularity_target"] == 0.0


def test_policy_to_payload_only_sends_active_interests():
    """Solo los intereses por encima del umbral llegan al modelo."""
    payload = model_gateway.policy_to_payload({
        "interests": {"coast_beach": 90, "rural": 80, "wellness": 10},
    })
    interests = payload["preferences"]["interests"]
    assert "coast_beach" in interests
    assert "rural" in interests
    assert "wellness" not in interests
    # Ordenados por peso descendente: el más ponderado primero.
    assert interests[0] == "coast_beach"


def test_policy_to_payload_falls_back_to_a_default_interest():
    """El contrato exige al menos un interés; sin ninguno activo se usa el
    interés por defecto en lugar de romper la llamada."""
    payload = model_gateway.policy_to_payload({"interests": {"coast_beach": 0}})
    assert payload["preferences"]["interests"], "debería haber al menos un interés"


def test_policy_to_payload_caps_interests_at_three():
    """El contrato de Azure admite entre 1 y 3 intereses. Aunque el gestor
    active más sliders por encima del umbral, solo deben viajar los tres de
    mayor peso: mandar más provoca un HTTP 400 del modelo."""
    payload = model_gateway.policy_to_payload({
        "interests": {
            "coast_beach": 90,
            "nature_mountains": 85,
            "history_culture": 80,
            "gastronomy_wine": 70,
            "wellness": 60,
        },
    })
    interests = payload["preferences"]["interests"]
    assert len(interests) == 3, "no puede enviar más de tres intereses"
    # Se conservan los tres de mayor peso, en orden descendente.
    assert interests == ["coast_beach", "nature_mountains", "history_culture"]


@pytest.mark.parametrize("weights", [
    {"coast_beach": 100, "nature_mountains": 100, "history_culture": 100,
     "gastronomy_wine": 100, "rural": 100, "wellness": 100, "sports_outdoors": 100},
    {"coast_beach": 55, "rural": 51},
    {"coast_beach": 0},
    {},
])
def test_policy_interests_always_within_contract(weights):
    """Sea cual sea la política, el nº de intereses queda en el rango [1, 3]
    que exige el contrato del modelo."""
    payload = model_gateway.policy_to_payload({"interests": weights})
    interests = payload["preferences"]["interests"]
    assert 1 <= len(interests) <= 3


def test_all_policy_presets_produce_valid_payloads():
    for name, preset in POLICY_PRESETS.items():
        payload = model_gateway.policy_to_payload(preset)
        errors = reco.validate_request(
            month=payload["travel"]["month"],
            trip_length_days=payload["travel"]["trip_length_days"],
            interests=payload["preferences"]["interests"],
            temperature_preference=payload["preferences"]["climate"]["temperature_preference"],
            minimum_sunny_days=payload["preferences"]["climate"]["minimum_sunny_days"],
            maximum_precipitation_days=payload["preferences"]["climate"]["maximum_precipitation_days"],
            popularity_target=payload["preferences"]["popularity_target"],
            accommodation_type=payload["preferences"]["accommodation_type"],
        )
        assert errors == [], f"{name} genera un payload inválido: {errors}"


# --------------------------------------------------------------------------
# El gateway consume el modelo, no reimplementa la red
# --------------------------------------------------------------------------

def test_recommend_by_policy_delegates_to_the_model(monkeypatch):
    captured = {}

    def fake_fetch(payload, use_cache=True):  # noqa: ARG001
        captured["payload"] = payload
        return {"ok": True, "ranking": [], "error": None, "from_cache": False}

    monkeypatch.setenv("TUI_MODEL_BACKEND", "azure")
    monkeypatch.setattr(reco, "fetch_recommendations", fake_fetch)

    result = model_gateway.recommend_by_policy({"popularity_target": 0.2})
    assert result["ok"] is True
    assert result["backend"] == "azure"
    # La política efectiva enviada al modelo queda expuesta para la vista.
    assert result["policy_payload"]["preferences"]["popularity_target"] == 0.2
    assert captured["payload"]["preferences"]["popularity_target"] == 0.2


def test_local_backend_hook_degrades_to_the_model(monkeypatch):
    """El gancho de la FASE 2 (backend local) no rompe: degrada al modelo."""
    calls = {"n": 0}

    def fake_fetch(payload, use_cache=True):  # noqa: ARG001
        calls["n"] += 1
        return {"ok": True, "ranking": [], "error": None, "from_cache": False}

    monkeypatch.setenv("TUI_MODEL_BACKEND", "local")
    monkeypatch.setattr(reco, "fetch_recommendations", fake_fetch)

    result = model_gateway.recommend_by_policy({"popularity_target": 0.5})
    assert result["backend"] == "local"
    assert calls["n"] == 1  # ha llamado al modelo aunque el backend sea "local"


# --------------------------------------------------------------------------
# Métricas de reparto de la demanda
# --------------------------------------------------------------------------

def _row(name: str, popularity: float | None, sunny=20, poi=100) -> dict:
    return {
        "destination": {"name": name, "primary_typology": "Costa"},
        "recommendation_score": 0.5,
        "popularity_profile": {"index": popularity},
        "climate_profile": {"sunny_days": sunny},
        "what_it_offers": {"poi_count": poi},
    }


def test_redistribution_metrics_summarize_the_ranking():
    ranking = [_row("A", 0.1), _row("B", 0.2), _row("C", 0.9)]
    metrics = redistribution_metrics(ranking)
    assert metrics["eligible"] == 3
    assert metrics["with_popularity"] == 3
    # Dos de tres están por debajo del umbral de baja popularidad (0.4).
    assert metrics["low_popularity_count"] == 2
    assert 0.0 <= metrics["popularity_gini"] <= 1.0
    assert metrics["avg_popularity"] == pytest.approx((0.1 + 0.2 + 0.9) / 3)


def test_redistribution_metrics_tolerate_missing_popularity():
    ranking = [_row("A", None), _row("B", 0.3)]
    metrics = redistribution_metrics(ranking)
    assert metrics["with_popularity"] == 1
    assert metrics["eligible"] == 2


def test_redistribution_metrics_none_for_empty_ranking():
    assert redistribution_metrics([]) is None


def test_lower_popularity_target_yields_less_popular_ranking():
    """Núcleo de la tesis: menor objetivo de popularidad = ranking menos masivo.

    Se simula el modelo devolviendo destinos coherentes con el objetivo pedido,
    para comprobar que las métricas del panel reflejan la redistribución.
    """
    def fake_fetch(payload, use_cache=True):  # noqa: ARG001
        target = payload["preferences"]["popularity_target"]
        # El modelo simulado devuelve destinos alrededor del objetivo.
        base = [target, min(1.0, target + 0.1), max(0.0, target - 0.1)]
        return {
            "ok": True,
            "ranking": [_row(f"D{i}", p) for i, p in enumerate(base)],
            "error": None,
            "from_cache": False,
        }

    import services.tdrs_service as svc
    original = model_gateway.reco.fetch_recommendations
    try:
        model_gateway.reco.fetch_recommendations = fake_fetch
        tradicional = redistribution_metrics(
            svc.recommend_policy({"popularity_target": 0.9})["ranking"]
        )
        redistribuido = redistribution_metrics(
            svc.recommend_policy({"popularity_target": 0.1})["ranking"]
        )
    finally:
        model_gateway.reco.fetch_recommendations = original

    assert redistribuido["avg_popularity"] < tradicional["avg_popularity"]
    assert redistribuido["low_popularity_count"] >= tradicional["low_popularity_count"]
