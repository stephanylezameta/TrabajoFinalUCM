from services.assistant_service import build_weights, converse, extract_preferences
from services.tdrs_service import PRESETS


def test_assistant_extracts_natural_preferences():
    prefs = extract_preferences(
        "Quiero buen tiempo, mucha seguridad y lugares menos masificados"
    )
    assert prefs["climate"] >= 80
    assert prefs["safety"] >= 80
    assert prefs["popularity"] <= 40


def test_assistant_short_answer_updates_current_question():
    prefs = extract_preferences("Alta", {"health": None}, focus_field="health")
    assert prefs["health"] == 80


def test_assistant_builds_model_weight_proposal():
    result = converse(
        prompt="Quiero sol y destinos poco turísticos",
        messages=[],
        preferences={},
        scenario="Equilibrado",
        scenario_defaults=PRESETS["Equilibrado"],
    )
    weights = result["weights"]
    # El asistente debe producir un peso por cada señal del modelo, seis desde
    # que existe la satisfacción de viajeros.
    from services.tdrs_service import CSV_FACTORS

    assert set(weights) == {key for key, _, _ in CSV_FACTORS}
    assert weights["sunny_days_pct"] >= 80
    assert weights["popularity"] <= 40
    # Lo no conversado conserva el valor del escenario.
    assert weights["satisfaction"] == PRESETS["Equilibrado"]["satisfaction"]


def test_assistant_understands_satisfaction():
    """La satisfacción se puede pedir en lenguaje natural."""
    prefs = extract_preferences("Prefiero destinos bien valorados por otros viajeros")
    assert prefs["satisfaction"] >= 80


def test_assistant_detects_indifference_to_reviews():
    """Las expresiones negativas se detectan antes que las positivas."""
    prefs = extract_preferences("Las reseñas me dan igual, quiero sol")
    assert prefs["satisfaction"] <= 40
    assert prefs["climate"] >= 80


def test_assistant_asks_about_satisfaction_when_pending():
    from services.assistant_service import missing_preferences

    assert "satisfaction" in missing_preferences({})


def test_assistant_maps_satisfaction_into_weights():
    weights = build_weights({"satisfaction": 95}, PRESETS["Equilibrado"])
    assert weights["satisfaction"] == 95
