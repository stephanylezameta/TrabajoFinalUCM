from services.tdrs_service import CSV_FACTORS, PRESETS, gini


def test_gini_uniform_is_zero():
    assert abs(gini([1, 1, 1, 1])) < 1e-12


def test_gini_nonnegative():
    assert gini([0, 0, 1, 1]) >= 0


def test_tdrs_v3_uses_requested_factor_keys():
    expected = {
        "sunny_days_pct",
        "low_precipitation_pct",
        "popularity",
        "hospital_beds",
        "safety",
    }
    assert {key for key, _, _ in CSV_FACTORS} == expected
    assert set(PRESETS["Equilibrado"]) == expected


def test_knn_imputation_marks_missing_fields():
    from services.tdrs_service import compute_scores
    result = compute_scores(PRESETS["Equilibrado"], max_price=2500, max_stay_days=365)
    assert result["factor_model"].endswith("KNN")
    assert all("knn_imputed_fields" in row for row in result["ranked"])
    assert all(row.get("model_coverage", 0) == 1.0 for row in result["ranked"])
