"""Tests del cliente de la API de recomendaciones. No hacen llamadas de red."""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from services import recommendation_api_service as reco

SAMPLE_ROW = {
    "rank": 1,
    "destination": {
        "place_id": "ES-127",
        "ine_code": "04066",
        "name": "Níjar",
        "province": "Almería",
        "autonomous_community": "Andalucía",
        "primary_typology": "Naturaleza y costa",
    },
    "recommendation_score": 0.8572,
    "confidence": {"score": 1.0, "level": "high"},
    "headline": "Destino con afinidad para costa y playa.",
    "reason_codes": ["INTEREST_MATCH", "PRECIPITATION_MATCH"],
    "preference_match": {
        "sunny_days": {"requested_minimum": 25.0, "historical_average": 21.83, "matched": False},
        "precipitation_days": {"requested_maximum": 2.0, "historical_average": 0.17, "matched": True},
    },
    "score_breakdown": {
        "interest_match": 0.8865,
        "climate_fit": 0.9493,
        "popularity_fit": 0.9077,
        "tourism_offer": 0.8434,
        "accommodation_fit": 0.459,
    },
    "what_it_offers": {"poi_count": 490, "hotel_poi_count": 33, "apartment_poi_count": 8},
    "climate_profile": {
        "sunny_days": 21.83,
        "precipitation_days": 0.17,
        "temperature_mean_c": 27.68,
        "sunshine_hours": None,
    },
    "popularity_profile": {"index": 0.7077, "basis": "relative_youtube_signal", "video_count": 47},
    "strengths": ["Buena afinidad con costa y playa."],
    "tradeoffs": ["No alcanza el minimo solicitado de dias soleados."],
    "data_coverage": {"catalog": True, "osm": True, "youtube": True, "aemet": False},
    "data_warnings": [],
}

SAMPLE_RESPONSE = {
    "recommendation_id": "abc-123",
    "contract_version": "recommendation-response-v1",
    "generated_at": "2026-09-05T12:58:27.177001+00:00",
    "engine": {"type": "deterministic_heuristic", "version": "heuristic-v1", "trained_model_used": False},
    "normalized_input": {},
    "ranking": [SAMPLE_ROW, {**SAMPLE_ROW, "rank": 3}, {**SAMPLE_ROW, "rank": 2}],
    "global_warnings": ["El clima representa promedios historicos."],
}


class _FakeResponse(io.BytesIO):
    """Sustituto mínimo del objeto que devuelve ``urlopen``."""

    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    """Cada test arranca con caché vacía y endpoint configurado."""
    monkeypatch.setenv("TUI_RECO_API_BASE", "https://example.invalid/api/recommendations")
    monkeypatch.setenv("TUI_RECO_API_KEY", "clave-de-prueba")
    monkeypatch.delenv("TUI_RECO_API_URL", raising=False)
    reco.reset_state()
    yield
    reco.reset_state()


def _patch_urlopen(monkeypatch, handler):
    captured: dict = {}

    def fake_urlopen(request, timeout=None):  # noqa: ARG001
        captured["url"] = request.full_url
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return handler()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return captured


# --------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------


def test_is_configured_with_base_and_key():
    assert reco.is_configured() is True
    assert reco.api_status() == "configured"


def test_not_configured_without_env(monkeypatch):
    monkeypatch.delenv("TUI_RECO_API_BASE", raising=False)
    monkeypatch.delenv("TUI_RECO_API_URL", raising=False)
    assert reco.is_configured() is False
    assert reco.api_status() == "not_configured"
    result = reco.recommend(month=7, trip_length_days=7, interests=["coast_beach"])
    assert result["ok"] is False
    assert result["error_kind"] == "not_configured"


def test_endpoint_host_hides_querystring(monkeypatch):
    monkeypatch.delenv("TUI_RECO_API_BASE", raising=False)
    monkeypatch.setenv("TUI_RECO_API_URL", "https://example.invalid/api/recommendations?code=secreto")
    assert reco.endpoint_host() == "https://example.invalid/api/recommendations"
    assert "secreto" not in reco.endpoint_host()


def test_key_travels_in_header_not_in_url(monkeypatch):
    captured = _patch_urlopen(
        monkeypatch,
        lambda: _FakeResponse(json.dumps(SAMPLE_RESPONSE).encode("utf-8")),
    )
    reco.recommend(month=7, trip_length_days=7, interests=["coast_beach"])
    assert "code=" not in captured["url"]
    # urllib capitaliza los nombres de cabecera.
    assert captured["headers"].get("X-functions-key") == "clave-de-prueba"


# --------------------------------------------------------------------------
# Validación en cliente
# --------------------------------------------------------------------------


def test_validate_request_accepts_valid_input():
    assert reco.validate_request(
        month=7, trip_length_days=7, interests=["coast_beach"],
        temperature_preference="warm_sunny", minimum_sunny_days=20,
        maximum_precipitation_days=5, popularity_target=0.6,
        accommodation_type="hotel",
    ) == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("month", 0),
        ("month", 13),
        ("trip_length_days", 0),
        ("trip_length_days", 31),
        ("popularity_target", -0.1),
        ("popularity_target", 1.1),
        ("temperature_preference", "hot"),
        ("accommodation_type", "hostel"),
    ],
)
def test_validate_request_rejects_out_of_contract(field, value):
    kwargs = {
        "month": 7, "trip_length_days": 7, "interests": ["coast_beach"],
        "temperature_preference": "warm_sunny", "minimum_sunny_days": 20,
        "maximum_precipitation_days": 5, "popularity_target": 0.6,
        "accommodation_type": "hotel",
    }
    kwargs[field] = value
    assert reco.validate_request(**kwargs), f"{field}={value} debería ser rechazado"


def test_validate_request_requires_interests():
    errors = reco.validate_request(
        month=7, trip_length_days=7, interests=[],
        temperature_preference="any", minimum_sunny_days=0,
        maximum_precipitation_days=0, popularity_target=0.5,
        accommodation_type="any",
    )
    assert any("interés" in e for e in errors)


def test_validate_request_rejects_unknown_interest():
    errors = reco.validate_request(
        month=7, trip_length_days=7, interests=["esqui_alpino"],
        temperature_preference="any", minimum_sunny_days=0,
        maximum_precipitation_days=0, popularity_target=0.5,
        accommodation_type="any",
    )
    assert any("esqui_alpino" in e for e in errors)


def test_validation_error_does_not_reach_network(monkeypatch):
    def explode(*args, **kwargs):  # noqa: ARG001
        raise AssertionError("no debería llamarse a la red con una petición inválida")

    monkeypatch.setattr("urllib.request.urlopen", explode)
    result = reco.recommend(month=99, trip_length_days=7, interests=["coast_beach"])
    assert result["ok"] is False
    assert result["error_kind"] == "validation"


def test_vocabulary_matches_documented_contract():
    assert set(reco.INTERESTS) == {
        "coast_beach", "nature_mountains", "sports_outdoors",
        "gastronomy_wine", "history_culture", "rural", "wellness",
    }
    assert set(reco.TEMPERATURE_PREFERENCES) == {"warm_sunny", "mild", "cool", "any"}
    assert set(reco.ACCOMMODATION_TYPES) == {"hotel", "apartment", "any"}


# --------------------------------------------------------------------------
# Construcción de la petición
# --------------------------------------------------------------------------


def test_build_payload_matches_contract():
    payload = reco.build_payload(
        month=7, trip_length_days=7, interests=["coast_beach"],
        include_regions=["Andalucía"],
    )
    assert payload["contract_version"] == reco.REQUEST_CONTRACT
    assert payload["travel"] == {"month": 7, "trip_length_days": 7}
    assert payload["preferences"]["interests"] == ["coast_beach"]
    assert payload["preferences"]["climate"]["temperature_preference"] == "warm_sunny"
    assert payload["filters"]["include_regions"] == ["Andalucía"]
    assert payload["filters"]["exclude_regions"] == []
    assert payload["locale"] == "es-ES"


# --------------------------------------------------------------------------
# Respuestas correctas
# --------------------------------------------------------------------------


def test_fetch_normalizes_and_sorts_ranking(monkeypatch):
    _patch_urlopen(
        monkeypatch,
        lambda: _FakeResponse(json.dumps(SAMPLE_RESPONSE).encode("utf-8")),
    )
    result = reco.recommend(month=7, trip_length_days=7, interests=["coast_beach"])
    assert result["ok"] is True
    assert result["recommendation_id"] == "abc-123"
    assert result["engine"]["version"] == "heuristic-v1"
    assert result["warnings"]
    # El ranking llega desordenado y debe quedar ordenado por `rank`.
    assert [row["rank"] for row in result["ranking"]] == [1, 2, 3]


def test_cache_avoids_second_network_call(monkeypatch):
    calls = {"n": 0}

    def handler():
        calls["n"] += 1
        return _FakeResponse(json.dumps(SAMPLE_RESPONSE).encode("utf-8"))

    _patch_urlopen(monkeypatch, handler)
    payload = reco.build_payload(7, 7, ["coast_beach"])
    first = reco.fetch_recommendations(payload)
    second = reco.fetch_recommendations(payload)
    assert calls["n"] == 1
    assert first["from_cache"] is False
    assert second["from_cache"] is True


# --------------------------------------------------------------------------
# Errores
# --------------------------------------------------------------------------


def _http_error(code: int, body: str):
    def handler():
        raise urllib.error.HTTPError(
            url="https://example.invalid", code=code, msg="err",
            hdrs=None, fp=io.BytesIO(body.encode("utf-8")),
        )

    return handler


def test_api_400_is_surfaced_as_validation(monkeypatch):
    _patch_urlopen(monkeypatch, _http_error(400, '{"error": "Intereses no admitidos: x."}'))
    result = reco.recommend(month=7, trip_length_days=7, interests=["coast_beach"])
    assert result["ok"] is False
    assert result["error_kind"] == "validation"
    assert "Intereses no admitidos" in result["error"]


def test_api_422_is_surfaced_as_validation(monkeypatch):
    _patch_urlopen(
        monkeypatch,
        _http_error(422, '{"error": "Los filtros dejan menos de tres destinos disponibles."}'),
    )
    result = reco.recommend(
        month=7, trip_length_days=7, interests=["coast_beach"],
        include_regions=["Narnia"],
    )
    assert result["ok"] is False
    assert result["error_kind"] == "validation"


def test_network_error_degrades_without_raising(monkeypatch):
    def handler():
        raise urllib.error.URLError("sin conexión")

    _patch_urlopen(monkeypatch, handler)
    result = reco.recommend(month=7, trip_length_days=7, interests=["coast_beach"])
    assert result["ok"] is False
    assert result["error_kind"] == "network"
    assert result["ranking"] == []


def test_circuit_breaker_blocks_immediate_retry(monkeypatch):
    calls = {"n": 0}

    def handler():
        calls["n"] += 1
        raise urllib.error.URLError("sin conexión")

    _patch_urlopen(monkeypatch, handler)
    first = reco.recommend(month=7, trip_length_days=7, interests=["coast_beach"])
    second = reco.recommend(month=8, trip_length_days=7, interests=["rural"])
    assert first["error_kind"] == "network"
    assert second["error_kind"] == "cooldown"
    # El segundo intento no ha vuelto a salir a la red.
    assert calls["n"] == 1


def test_non_json_response_is_reported(monkeypatch):
    _patch_urlopen(monkeypatch, lambda: _FakeResponse(b"<html>error</html>"))
    result = reco.recommend(month=7, trip_length_days=7, interests=["coast_beach"])
    assert result["ok"] is False
    assert result["error_kind"] == "payload"


def test_response_without_ranking_is_reported(monkeypatch):
    _patch_urlopen(monkeypatch, lambda: _FakeResponse(b'{"unexpected": true}'))
    result = reco.recommend(month=7, trip_length_days=7, interests=["coast_beach"])
    assert result["ok"] is False
    assert result["error_kind"] == "payload"


# --------------------------------------------------------------------------
# Ayudas de presentación
# --------------------------------------------------------------------------


def test_breakdown_rows_sorted_desc_with_labels():
    rows = reco.breakdown_rows(SAMPLE_ROW["score_breakdown"])
    assert rows[0]["Dimensión"] == "Ajuste climático"
    values = [row["Valor"] for row in rows]
    assert values == sorted(values, reverse=True)


def test_coverage_summary_reports_missing_sources():
    available, total, missing = reco.coverage_summary(SAMPLE_ROW["data_coverage"])
    assert (available, total) == (3, 4)
    assert missing == ["AEMET"]


def test_coverage_summary_handles_empty():
    assert reco.coverage_summary(None) == (0, 0, [])


def test_ranking_table_keeps_none_for_missing_values():
    table = reco.ranking_table([SAMPLE_ROW])
    assert table[0]["Destino"] == "Níjar"
    assert table[0]["Comunidad"] == "Andalucía"
    assert table[0]["Cobertura"] == "3/4"
    assert table[0]["Confianza"] == "Alta"


def test_labels_fall_back_to_raw_code():
    assert reco.interest_label("coast_beach") == "Costa y playa"
    assert reco.interest_label("desconocido") == "desconocido"
    assert reco.month_name(1) == "Enero"
    assert reco.month_name(99) == "99"
    assert reco.confidence_label("high") == "Alta"
    assert reco.reason_label("UNKNOWN_CODE") == "Unknown code"
