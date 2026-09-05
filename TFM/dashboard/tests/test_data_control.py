from database.models import SCHEMA_SQL
from services.data_control_service import format_interval


def test_schema_contains_update_runs():
    assert "CREATE TABLE IF NOT EXISTS update_runs" in SCHEMA_SQL


def test_format_interval():
    assert format_interval(24) == "Cada 1 día"
    assert format_interval(168) == "Cada 1 semana"
