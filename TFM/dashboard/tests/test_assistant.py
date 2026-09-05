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
    assert set(weights) == {
        "sunny_days_pct",
        "low_precipitation_pct",
        "popularity",
        "hospital_beds",
        "safety",
    }
    assert weights["sunny_days_pct"] >= 80
    assert weights["popularity"] <= 40
