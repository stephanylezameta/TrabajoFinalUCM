from services.tdrs_service import gini


def test_gini_uniform_is_zero():
    assert abs(gini([1,1,1,1])) < 1e-12


def test_gini_nonnegative():
    assert gini([0,0,1,1]) >= 0
