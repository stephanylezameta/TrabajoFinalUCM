"""Tests del cliente de la API de recomendaciones. No hacen llamadas de red.

La API real es el motor FastAPI (endpoints /recomendar, /chat, /tdrs_ranking),
localizado con la variable TUI_MODELO_API_BASE.
"""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from services import recommendation_api_service as reco

# Un destino tal como lo devuelve POST /recomendar (contrato nuevo).
SAMPLE_DESTINO = {
    "id_paquete": "EXP_100514",
    "destino_nombre": "Costa del Sol",
    "afinidad": 0.5717,
    "tdrs": 0.3367,
    "sostenibilidad": 0.6,
    "precio_eur": 94.88,
    "score_final": 0.5271,
    "datos_humanos": {
        "dias_soleados_pct": 80.0,
        "precipitacion_pct": 21.4,
        "horas_sol_promedio_dia": 10.7,
        "pasajeros_anuales": 2283372,
        "camas_hospital_1000hab": 2.97,
        "tasa_homicidios_100mil": 0.63,
        "sentimiento_real": 0.62,
        "n_resenas_reales": 188,
    },
    "log_id": "cbb85ffd",
}

SAMPLE_RESPONSE = {
    "session_id": "abc-123",
    "rankings": {
        "tradicional": [SAMPLE_DESTINO],
        "moderado": [SAMPLE_DESTINO, {**SAMPLE_DESTINO, "destino_nombre": "Antalya"}],
        "intensivo": [SAMPLE_DESTINO],
        "personalizado": [{**SAMPLE_DESTINO, "destino_nombre": "Cerdeña"}],
    },
}

SAMPLE_TDRS = {
    "ranked": [
        {
            "destino_nombre": "Cabo Verde",
            "score": 0.7,
            "precio_referencia_eur": 11.72,
            "datos_humanos": {"dias_soleados_pct": 100.0},
            "contribuciones": [
                {"factor": "sunny_days_pct", "peso": 70.0, "valor": 1.0, "contribucion": 0.7},
            ],
        },
    ],
    "excluded": [],
    "señales_disponibles": ["sunny_days_pct", "popularity"],
    "fuente": "Datos reales del modelo TDRS",
}

SAMPLE_CHAT = {
    "respuesta": "Te recomiendo la Costa del Sol por su clima.",
    "historial": [{"role": "user", "content": "playa"}, {"role": "assistant", "content": "..."}],
    "session_id": "chat-1",
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
    monkeypatch.setenv("TUI_MODELO_API_BASE", "https://example.invalid")
    monkeypatch.delenv("TUI_RECO_API_BASE", raising=False)
    monkeypatch.delenv("TUI_RECO_API_URL", raising=False)
    monkeypatch.delenv("TUI_RECO_API_KEY", raising=False)
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


def test_is_configured_with_base():
    assert reco.is_configured() is True
    assert reco.api_status() == "configured"


def test_not_configured_without_env(monkeypatch):
    monkeypatch.delenv("TUI_MODELO_API_BASE", raising=False)
    monkeypatch.delenv("TUI_RECO_API_BASE", raising=False)
    assert reco.is_configured() is False
    assert reco.api_status() == "not_configured"
    result = reco.recommend(interests=["coast_beach"])
    assert result["ok"] is False
    assert result["error_kind"] == "not_configured"


def test_endpoint_uses_base_and_recomendar_path(monkeypatch):
    captured = _patch_urlopen(
        monkeypatch,
        lambda: _FakeResponse(json.dumps(SAMPLE_RESPONSE).encode("utf-8")),
    )
    reco.recommend(interests=["coast_beach"])
    assert captured["url"] == "https://example.invalid/recomendar"


def test_fallback_to_reco_base(monkeypatch):
    monkeypatch.delenv("TUI_MODELO_API_BASE", raising=False)
    monkeypatch.setenv("TUI_RECO_API_BASE", "https://legacy.invalid")
    assert reco.is_configured() is True
    assert reco.endpoint_host() == "https://legacy.invalid"


# --------------------------------------------------------------------------
# Validación en cliente
# --------------------------------------------------------------------------


def test_validate_request_accepts_valid_input():
    assert reco.validate_request(
        interests=["coast_beach"],
        temperature_preference="warm_sunny", popularity_target=0.6,
        presupuesto_max=500, categoria="Cultural Experiences",
    ) == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("interests", []),
        ("popularity_target", -0.1),
        ("popularity_target", 1.1),
        ("temperature_preference", "hot"),
        ("presupuesto_max", 0),
        ("categoria", "playa"),
    ],
)
def test_validate_request_rejects_out_of_contract(field, value):
    kwargs = {
        "interests": ["coast_beach"],
        "temperature_preference": "warm_sunny", "popularity_target": 0.6,
    }
    kwargs[field] = value
    assert reco.validate_request(**kwargs), f"{field}={value} debería ser rechazado"


def test_validation_error_does_not_reach_network(monkeypatch):
    def explode(*args, **kwargs):  # noqa: ARG001
        raise AssertionError("no debería llamarse a la red con una petición inválida")

    monkeypatch.setattr("urllib.request.urlopen", explode)
    # Sin intereses la petición es inválida y no debe salir a la red.
    result = reco.recommend(interests=[])
    assert result["ok"] is False
    assert result["error_kind"] == "validation"


def test_vocabulary_matches_form_contract():
    assert set(reco.INTERESTS) == {
        "coast_beach", "nature_mountains", "sports_outdoors",
        "gastronomy_wine", "history_culture", "rural", "wellness",
    }
    assert set(reco.TEMPERATURE_PREFERENCES) == {"warm_sunny", "mild", "cool", "any"}
    assert set(reco.ACCOMMODATION_TYPES) == {"hotel", "apartment", "any"}
    # Categorías: coincidencia exacta con experiencias.category del motor.
    assert "Cultural Experiences" in reco.CATEGORIES
    assert "Water Activities" in reco.CATEGORIES


# --------------------------------------------------------------------------
# Construcción de la petición (traducción formulario -> contrato /recomendar)
# --------------------------------------------------------------------------


def test_build_payload_translates_to_text_query(monkeypatch):
    captured = _patch_urlopen(
        monkeypatch,
        lambda: _FakeResponse(json.dumps(SAMPLE_RESPONSE).encode("utf-8")),
    )
    reco.recommend(
        interests=["coast_beach"],
        temperature_preference="warm_sunny", popularity_target=0.3,
        presupuesto_max=200, categoria="Water Activities",
    )
    body = captured["body"]
    # El cuerpo enviado a la API solo lleva los campos del contrato nuevo.
    assert "texto_consulta" in body
    assert "playa" in body["texto_consulta"].lower()
    assert body["objetivo_popularidad"] == 0.3
    assert body["presupuesto_max"] == 200.0
    assert body["categoria"] == "Water Activities"
    # No se filtran los campos internos del formulario.
    assert "_form" not in body


def test_build_payload_keeps_form_fields_internally():
    payload = reco.build_payload(
        interests=["coast_beach"],
        popularity_target=0.6, presupuesto_max=300,
    )
    assert payload["_form"]["interests"] == ["coast_beach"]
    assert payload["_form"]["presupuesto_max"] == 300
    assert payload["objetivo_popularidad"] == 0.6
    assert payload["presupuesto_max"] == 300.0


# --------------------------------------------------------------------------
# Respuestas correctas: adaptación del nuevo contrato al formato de la UI
# --------------------------------------------------------------------------


def test_fetch_adapts_new_contract_to_ui_rows(monkeypatch):
    _patch_urlopen(
        monkeypatch,
        lambda: _FakeResponse(json.dumps(SAMPLE_RESPONSE).encode("utf-8")),
    )
    # recommend() envía objetivo_popularidad (0.6 por defecto), así que la UI
    # recibe el escenario 'personalizado' -> Cerdeña.
    result = reco.recommend(interests=["coast_beach"])
    assert result["ok"] is True
    assert result["session_id"] == "abc-123"
    assert result["recommendation_id"] == "abc-123"
    row = result["ranking"][0]
    # La UI lee estos campos: se adaptan desde destino_nombre/score_final/etc.
    assert row["destination"]["name"] == "Cerdeña"
    assert row["recommendation_score"] == pytest.approx(0.5271)
    assert row["precio_eur"] == pytest.approx(94.88)
    assert row["datos_humanos"]["n_resenas_reales"] == 188
    # dias_soleados_pct (80) -> "días de sol" del mes (~24).
    assert row["climate_profile"]["sunny_days"] == pytest.approx(24.0)
    # Con sol alto + buen sentimiento + muchas reseñas hay fortalezas.
    assert row["strengths"]


def test_default_scenario_moderado_without_popularity(monkeypatch):
    _patch_urlopen(
        monkeypatch,
        lambda: _FakeResponse(json.dumps(SAMPLE_RESPONSE).encode("utf-8")),
    )
    # build_payload siempre envía objetivo_popularidad, así que para probar el
    # escenario 'moderado' se construye un payload sin ese campo.
    payload = {"texto_consulta": "playa", "objetivo_popularidad": None}
    result = reco.fetch_recommendations(payload)
    nombres = [r["destination"]["name"] for r in result["ranking"]]
    assert nombres == ["Costa del Sol", "Antalya"]  # lista 'moderado'


def test_personalizado_scenario_when_popularity_sent(monkeypatch):
    _patch_urlopen(
        monkeypatch,
        lambda: _FakeResponse(json.dumps(SAMPLE_RESPONSE).encode("utf-8")),
    )
    result = reco.recommend(
        interests=["coast_beach"],
        popularity_target=0.2,
    )
    nombres = [r["destination"]["name"] for r in result["ranking"]]
    assert nombres == ["Cerdeña"]  # lista 'personalizado'


def test_cache_avoids_second_network_call(monkeypatch):
    calls = {"n": 0}

    def handler():
        calls["n"] += 1
        return _FakeResponse(json.dumps(SAMPLE_RESPONSE).encode("utf-8"))

    _patch_urlopen(monkeypatch, handler)
    payload = reco.build_payload(["coast_beach"])
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


def test_api_422_is_surfaced_as_validation(monkeypatch):
    _patch_urlopen(monkeypatch, _http_error(422, '{"detail": "texto_consulta requerido"}'))
    result = reco.recommend(interests=["coast_beach"])
    assert result["ok"] is False
    assert result["error_kind"] == "validation"
    assert "texto_consulta" in result["error"]


def test_network_error_degrades_without_raising(monkeypatch):
    monkeypatch.setattr(reco, "_RETRY_WAIT_SECONDS", 0)

    def handler():
        raise urllib.error.URLError("sin conexión")

    _patch_urlopen(monkeypatch, handler)
    result = reco.recommend(interests=["coast_beach"])
    assert result["ok"] is False
    assert result["error_kind"] == "network"
    assert result["ranking"] == []


def test_network_retries_then_activates_circuit_breaker(monkeypatch):
    monkeypatch.setattr(reco, "_RETRY_WAIT_SECONDS", 0)
    calls = {"n": 0}

    def handler():
        calls["n"] += 1
        raise urllib.error.URLError("sin conexión")

    _patch_urlopen(monkeypatch, handler)
    first = reco.recommend(interests=["coast_beach"])
    intentos_primera = calls["n"]
    second = reco.recommend(interests=["rural"])
    assert first["error_kind"] == "network"
    assert second["error_kind"] == "cooldown"
    assert intentos_primera == reco._MAX_NETWORK_ATTEMPTS
    assert calls["n"] == intentos_primera


def test_non_json_response_is_reported(monkeypatch):
    _patch_urlopen(monkeypatch, lambda: _FakeResponse(b"<html>error</html>"))
    result = reco.recommend(interests=["coast_beach"])
    assert result["ok"] is False
    assert result["error_kind"] == "payload"


def test_response_without_rankings_is_reported(monkeypatch):
    _patch_urlopen(monkeypatch, lambda: _FakeResponse(b'{"unexpected": true}'))
    result = reco.recommend(interests=["coast_beach"])
    assert result["ok"] is False
    assert result["error_kind"] == "payload"


# --------------------------------------------------------------------------
# Chat (/chat)
# --------------------------------------------------------------------------


def test_chat_returns_response_and_session(monkeypatch):
    captured = _patch_urlopen(
        monkeypatch,
        lambda: _FakeResponse(json.dumps(SAMPLE_CHAT).encode("utf-8")),
    )
    result = reco.chat("quiero playa", historial=[], session_id=None)
    assert captured["url"] == "https://example.invalid/chat"
    assert captured["body"]["mensaje"] == "quiero playa"
    assert result["ok"] is True
    assert result["respuesta"].startswith("Te recomiendo")
    assert result["session_id"] == "chat-1"
    assert len(result["historial"]) == 2


def test_chat_not_configured(monkeypatch):
    monkeypatch.delenv("TUI_MODELO_API_BASE", raising=False)
    result = reco.chat("hola")
    assert result["ok"] is False
    assert result["error_kind"] == "not_configured"


def test_chat_network_error_does_not_raise(monkeypatch):
    monkeypatch.setattr(reco, "_RETRY_WAIT_SECONDS", 0)

    def handler():
        raise urllib.error.URLError("sin conexión")

    _patch_urlopen(monkeypatch, handler)
    result = reco.chat("hola")
    assert result["ok"] is False
    assert result["error_kind"] == "network"


# --------------------------------------------------------------------------
# Simulador TDRS (/tdrs_ranking)
# --------------------------------------------------------------------------


def test_tdrs_ranking_returns_ranked_and_signals(monkeypatch):
    captured = _patch_urlopen(
        monkeypatch,
        lambda: _FakeResponse(json.dumps(SAMPLE_TDRS).encode("utf-8")),
    )
    result = reco.tdrs_ranking({"sunny_days_pct": 70, "popularity": 30}, max_price=1000)
    assert captured["url"] == "https://example.invalid/tdrs_ranking"
    assert captured["body"]["weights"] == {"sunny_days_pct": 70.0, "popularity": 30.0}
    assert captured["body"]["max_price"] == 1000.0
    assert result["ok"] is True
    assert result["ranked"][0]["destino_nombre"] == "Cabo Verde"
    # La clave con eñe del backend se expone como ASCII.
    assert result["senales_disponibles"] == ["sunny_days_pct", "popularity"]


def test_tdrs_ranking_not_configured(monkeypatch):
    monkeypatch.delenv("TUI_MODELO_API_BASE", raising=False)
    result = reco.tdrs_ranking({"sunny_days_pct": 70})
    assert result["ok"] is False
    assert result["error_kind"] == "not_configured"


# --------------------------------------------------------------------------
# Ayudas de presentación
# --------------------------------------------------------------------------


def test_ranking_table_reads_adapted_row(monkeypatch):
    _patch_urlopen(
        monkeypatch,
        lambda: _FakeResponse(json.dumps(SAMPLE_RESPONSE).encode("utf-8")),
    )
    result = reco.recommend(interests=["coast_beach"])
    table = reco.ranking_table(result["ranking"])
    # recommend() -> escenario 'personalizado' -> Cerdeña.
    assert table[0]["Destino"] == "Cerdeña"
    assert table[0]["Precio (€)"] == pytest.approx(94.88)


def test_labels_fall_back_to_raw_code():
    assert reco.interest_label("coast_beach") == "Costa y playa"
    assert reco.interest_label("desconocido") == "desconocido"
    assert reco.month_name(1) == "Enero"
    assert reco.month_name(99) == "99"
    assert reco.confidence_label("high") == "Alta"
    assert reco.reason_label("UNKNOWN_CODE") == "Unknown code"
