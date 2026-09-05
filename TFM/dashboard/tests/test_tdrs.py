from services.tdrs_service import CSV_FACTORS, PRESETS, gini


def test_gini_uniform_is_zero():
    assert abs(gini([1, 1, 1, 1])) < 1e-12


def test_gini_nonnegative():
    assert gini([0, 0, 1, 1]) >= 0


def test_tdrs_uses_requested_factor_keys():
    """Seis señales: las cinco originales más la satisfacción de viajeros."""
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


def test_knn_imputation_marks_missing_fields():
    from services.tdrs_service import compute_scores
    result = compute_scores(PRESETS["Equilibrado"], max_price=2500, max_stay_days=365)
    assert result["factor_model"].endswith("KNN")
    assert all("knn_imputed_fields" in row for row in result["ranked"])
    assert all(row.get("model_coverage", 0) == 1.0 for row in result["ranked"])


# --------------------------------------------------------------------------
# Sexto factor: satisfacción derivada del sentimiento de reseñas
# --------------------------------------------------------------------------


def test_sentiment_is_loaded_for_known_destinations():
    """El contexto trae el sentimiento real de los destinos que tienen reseñas."""
    from services.tdrs_service import get_destination_context

    context = get_destination_context()
    with_sentiment = [d for d in context if d.get("sentiment")]
    assert with_sentiment, "ningún destino ha recibido sentimiento del pipeline"
    for dest in with_sentiment:
        sentiment = dest["sentiment"]
        assert 0.0 <= float(sentiment["sentiment_score"]) <= 1.0
        # Una media sin su volumen no es auditable.
        assert int(sentiment["reviews_analyzed"]) >= 25
        assert sentiment["model"]


def test_satisfaction_factor_is_scored():
    from services.tdrs_service import compute_scores

    result = compute_scores(PRESETS["Equilibrado"])
    for row in result["ranked"]:
        factors = row["csv_factor_values"]
        assert "satisfaction" in factors
        assert factors["satisfaction"] is None or 0.0 <= factors["satisfaction"] <= 1.0
        contributions = {c["factor"] for c in row["contributions"]}
        assert "satisfaction" in contributions


def test_missing_sentiment_is_imputed_and_flagged():
    """Sin reseñas, el KNN estima el valor y lo deja marcado como imputado."""
    from services.tdrs_service import compute_scores

    result = compute_scores(PRESETS["Equilibrado"])
    for row in result["ranked"]:
        raw = (row.get("model_raw_values") or {}).get("sentiment_score")
        imputed = row.get("knn_imputed_fields") or []
        if raw is None:
            assert "sentiment_score" in imputed, f"{row['name']}: imputado sin marcar"
            # El modelo sí tiene un valor con el que calcular.
            assert (row.get("model_values") or {}).get("sentiment_score") is not None
        else:
            assert "sentiment_score" not in imputed


def test_satisfaction_weight_changes_the_ranking():
    """El factor influye de verdad: a peso 0 y a peso 100 el orden difiere."""
    from services.tdrs_service import compute_scores

    ignore = {**PRESETS["Equilibrado"], "satisfaction": 0}
    prioritize = {**PRESETS["Equilibrado"], "satisfaction": 100}
    order_ignored = [r["name"] for r in compute_scores(ignore)["ranked"]]
    order_prioritized = [r["name"] for r in compute_scores(prioritize)["ranked"]]
    assert order_ignored != order_prioritized


def test_scenario_metrics_report_sentiment_provenance():
    from services.tdrs_service import compute_scores, scenario_metrics

    metrics = scenario_metrics(compute_scores(PRESETS["Equilibrado"])["ranked"])
    assert "avg_top5_sentiment" in metrics
    assert 0 <= metrics["top5_sentiment_real"] <= 5
