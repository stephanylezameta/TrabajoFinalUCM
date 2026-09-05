"""Tests del parseo de los HTML de referencia.

El extractor de ``var DESTINOS = [...]`` era el punto más frágil del proyecto:
un ``re.search`` no voraz se rompía en cuanto un literal contenía ``];`` o una
llave. Aquí se fija el comportamiento del escáner con emparejamiento real.
"""

from __future__ import annotations

import pytest

from services.reference_service import (
    ReferenceParseError,
    _extract_js_array,
    _iter_js_objects,
    _parse_js_object,
    _scan_balanced,
)


def test_scan_balanced_matches_nested_brackets():
    text = "x = [1, [2, 3], 4];"
    start = text.index("[")
    assert text[_scan_balanced(text, start)] == "]"
    assert text[start:_scan_balanced(text, start) + 1] == "[1, [2, 3], 4]"


def test_scan_balanced_ignores_delimiters_inside_strings():
    text = "x = ['a];b', 'c'];"
    start = text.index("[")
    end = _scan_balanced(text, start)
    assert text[start:end + 1] == "['a];b', 'c']"


def test_scan_balanced_respects_escapes():
    text = r"x = ['it\'s ]', 2];"
    start = text.index("[")
    end = _scan_balanced(text, start)
    assert text[end] == "]"


def test_scan_balanced_raises_when_unclosed():
    with pytest.raises(ReferenceParseError):
        _scan_balanced("x = [1, 2", 4)


def test_extract_js_array_accepts_var_let_const():
    for keyword in ("var", "let", "const"):
        html = f"<script>{keyword} DESTINOS = [{{n:'A'}}];</script>"
        assert "n:'A'" in _extract_js_array(html, "DESTINOS")


def test_extract_js_array_survives_bracket_inside_string():
    # Este es el caso que rompía la versión anterior basada en `\[(.*?)\];`.
    html = "<script>var DESTINOS = [{n:'Costa ];', precio:100},{n:'B', precio:200}];</script>"
    body = _extract_js_array(html, "DESTINOS")
    objects = list(_iter_js_objects(body))
    assert len(objects) == 2
    assert _parse_js_object(objects[0])["n"] == "Costa ];"
    assert _parse_js_object(objects[1])["n"] == "B"


def test_extract_js_array_does_not_match_similar_names():
    html = "<script>var TOTAL_DESTINOS = [1]; var DESTINOS = [{n:'Real'}];</script>"
    body = _extract_js_array(html, "DESTINOS")
    assert _parse_js_object(next(iter(_iter_js_objects(body))))["n"] == "Real"


def test_extract_js_array_raises_when_absent():
    with pytest.raises(ReferenceParseError):
        _extract_js_array("<html><body>sin datos</body></html>", "DESTINOS")


def test_parse_js_object_handles_scalar_types():
    parsed = _parse_js_object(
        "n:'Algarve', pais:\"Portugal - Sur\", precio:1250.5, co2:-3, "
        "activo:true, oculto:false, nota:null, exp:1.2e3"
    )
    assert parsed["n"] == "Algarve"
    assert parsed["pais"] == "Portugal - Sur"
    assert parsed["precio"] == 1250.5
    assert parsed["co2"] == -3
    assert parsed["activo"] is True
    assert parsed["oculto"] is False
    assert parsed["nota"] is None
    assert parsed["exp"] == 1200.0


def test_parse_js_object_accepts_quoted_keys():
    parsed = _parse_js_object("'n':'A', \"precio\":10")
    assert parsed == {"n": "A", "precio": 10.0}


def test_iter_js_objects_skips_whitespace_and_commas():
    body = "  {n:'A'} ,\n  {n:'B'}  "
    names = [_parse_js_object(obj)["n"] for obj in _iter_js_objects(body)]
    assert names == ["A", "B"]


def test_real_proposal_html_still_parses():
    """El fichero real de la propuesta debe seguir produciendo destinos."""
    from config import RAW_DIR

    path = RAW_DIR / "propuesta_7.html"
    if not path.exists():
        pytest.skip("propuesta_7.html no disponible")
    body = _extract_js_array(
        path.read_text(encoding="utf-8", errors="replace"), "DESTINOS"
    )
    parsed = [_parse_js_object(obj) for obj in _iter_js_objects(body)]
    named = [p for p in parsed if p.get("n")]
    assert len(named) >= 10
    assert all(isinstance(p["n"], str) for p in named)
