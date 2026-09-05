"""Tests de las reglas de alertas y de los KPIs derivados.

Ambas capas no tenían cobertura. No se comprueba un resultado concreto (depende
de los datos cargados) sino el contrato: estructura, niveles válidos, ausencia de
duplicados y coherencia aritmética de los KPIs.
"""

from __future__ import annotations

import pytest

from services import alert_service
from services.alert_service import (
    LEVEL_ORDER,
    evaluate_database_integrity,
    evaluate_empty_datasets,
    evaluate_null_anomalies,
    evaluate_row_count_changes,
    evaluate_scraping_errors,
    evaluate_source_freshness,
    get_active_alerts,
    get_alerts,
    get_system_status,
)
from services.analytics_service import (
    get_dashboard_metrics,
    get_destination_metrics,
    get_funnel_metrics,
    instrumentation_status,
)

ALERT_KEYS = {"level", "title", "message", "source_id", "action"}

RULES = [
    evaluate_database_integrity,
    evaluate_empty_datasets,
    evaluate_scraping_errors,
    evaluate_source_freshness,
    evaluate_row_count_changes,
    evaluate_null_anomalies,
]


# --------------------------------------------------------------------------
# Alertas
# --------------------------------------------------------------------------


@pytest.mark.parametrize("rule", RULES, ids=[r.__name__ for r in RULES])
def test_every_rule_returns_normalized_alerts(rule):
    alerts = rule()
    assert isinstance(alerts, list)
    for item in alerts:
        assert set(item) == ALERT_KEYS, f"{rule.__name__} devuelve claves inesperadas"
        assert item["level"] in LEVEL_ORDER


def test_integrity_rule_is_quiet_on_healthy_database():
    # conftest construye la base desde cero, así que debe estar sana.
    assert evaluate_database_integrity() == []


def test_get_alerts_sorted_by_severity():
    alerts = get_alerts()
    levels = [LEVEL_ORDER[a["level"]] for a in alerts]
    assert levels == sorted(levels)


def test_get_alerts_has_no_duplicate_cause_per_source():
    alerts = get_alerts()
    keys = [(a["title"], a["source_id"]) for a in alerts]
    assert len(keys) == len(set(keys))


def test_get_alerts_emits_ok_when_nothing_to_report():
    alerts = get_alerts(include_ok=True)
    # O hay incidencias reales, o aparece exactamente la alerta OK de cierre.
    if all(a["level"] == "OK" for a in alerts):
        assert len(alerts) == 1
        assert alerts[0]["level"] == "OK"


def test_include_ok_false_never_returns_ok_level():
    assert all(a["level"] != "OK" for a in get_alerts(include_ok=False))


def test_get_active_alerts_excludes_ok():
    assert all(a["level"] in {"CRITICAL", "WARNING", "INFO"} for a in get_active_alerts())


def test_get_alerts_deduplicates_overlapping_rules(monkeypatch):
    duplicate = {
        "level": "WARNING", "title": "Misma causa", "message": "m",
        "source_id": "climate", "action": None,
    }
    monkeypatch.setattr(alert_service, "evaluate_database_integrity", lambda: [dict(duplicate)])
    monkeypatch.setattr(alert_service, "evaluate_empty_datasets", lambda: [dict(duplicate)])
    monkeypatch.setattr(alert_service, "evaluate_scraping_errors", lambda: [])
    monkeypatch.setattr(alert_service, "evaluate_source_freshness", lambda: [])
    monkeypatch.setattr(alert_service, "evaluate_row_count_changes", lambda: [])
    monkeypatch.setattr(alert_service, "evaluate_null_anomalies", lambda: [])
    alerts = get_alerts()
    assert len(alerts) == 1


def test_system_status_contract():
    status = get_system_status()
    assert status["status"] in {"ok", "warning", "critical"}
    assert status["open_alerts"] == status["critical_alerts"] + status["warnings"]
    assert status["healthy_sources"] <= status["active_sources"]
    assert status["overdue_sources"] <= status["active_sources"]
    assert status["total_rows"] >= 0
    assert status["database_integrity"] == "ok"


def test_system_status_escalates_with_critical(monkeypatch):
    monkeypatch.setattr(
        alert_service, "get_alerts",
        lambda include_ok=True: [{
            "level": "CRITICAL", "title": "t", "message": "m",
            "source_id": None, "action": None,
        }],
    )
    assert get_system_status()["status"] == "critical"


# --------------------------------------------------------------------------
# KPIs
# --------------------------------------------------------------------------


EXPECTED_METRIC_KEYS = {
    "impressions", "clicks", "ctr", "sessions", "users", "searches", "detail_views",
    "checkout_starts", "bookings", "conversion", "click_to_booking", "cancellations",
    "cancellation_rate", "revenue_eur", "cost_eur", "roas", "roi", "avg_ticket_eur",
    "revenue_per_session", "margin_eur", "passengers", "room_nights",
    "avg_response_time_ms",
}


def test_dashboard_metrics_contract():
    metrics = get_dashboard_metrics()
    assert EXPECTED_METRIC_KEYS <= set(metrics)
    assert metrics["sessions"] >= 0
    assert metrics["revenue_eur"] >= 0


def test_dashboard_metrics_ratios_are_none_when_denominator_is_zero():
    metrics = get_dashboard_metrics()
    if not metrics["impressions"]:
        assert metrics["ctr"] is None
    if metrics["cost_eur"] in (None, 0):
        assert metrics["roi"] is None, "ROI debe quedar pendiente si no hay coste"


def test_dashboard_metrics_ratios_within_range():
    metrics = get_dashboard_metrics()
    for field in ("ctr", "conversion", "cancellation_rate"):
        value = metrics[field]
        if value is not None:
            assert value >= 0


def test_funnel_steps_are_ordered_and_complete():
    funnel = get_funnel_metrics()
    assert [step["step"] for step in funnel] == [
        "Sesiones", "Búsquedas", "Vistas de detalle", "Checkout", "Reservas",
    ]
    assert all(step["value"] >= 0 for step in funnel)


def test_destination_metrics_never_lose_a_destination():
    rows = get_destination_metrics()
    for row in rows:
        assert row["destination"] is not None
        assert row["impressions"] >= 0
        assert row["clicks"] >= 0
        assert row["bookings"] >= 0
        assert row["revenue_eur"] >= 0


def test_instrumentation_status_declares_every_kpi():
    rows = instrumentation_status()
    assert {row["KPI"] for row in rows} == {"CTR", "Conversión", "ROI", "Latencia"}
    for row in rows:
        assert row["estado"] in {"disponible", "pendiente de instrumentar"}
        assert row["necesita"]
