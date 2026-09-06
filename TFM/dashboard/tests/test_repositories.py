"""Tests de la capa de persistencia y de los servicios que la envuelven.

Corren sobre la base de datos temporal que construye ``conftest.py``, así que
pueden escribir sin ensuciar ``data/app.db``.
"""

from __future__ import annotations

import uuid

import pytest

from database.repositories import (
    AnalyticsRepository,
    BookingRepository,
    DestinationRepository,
    ProductRepository,
    TrackingRepository,
)
from services.booking_service import cancel_booking, create_booking
from services.tracking_service import create_session, register_event


@pytest.fixture
def product_id() -> str:
    """Inserta un producto de prueba y devuelve su identificador."""
    pid = f"test-{uuid.uuid4().hex[:10]}"
    ProductRepository().upsert_many([{
        "product_id": pid, "title": "Paquete de prueba", "destination": "Testlandia",
        "hotel": None, "price": 500.0, "currency": "EUR", "duration_days": 7, "nights": 6,
        "departure_date": None, "return_date": None, "rating": 4.5, "board_basis": None,
        "transport": None, "airline": None, "availability": None, "discount": None,
        "description": None, "image_url": None, "detail_url": None,
        "source": "test", "extra_data": "{}",
    }])
    return pid


# --------------------------------------------------------------------------
# ProductRepository
# --------------------------------------------------------------------------


def test_product_upsert_is_idempotent(product_id):
    repo = ProductRepository()
    before = repo.count()
    repo.upsert_many([{
        "product_id": product_id, "title": "Paquete actualizado", "destination": "Testlandia",
        "hotel": None, "price": 650.0, "currency": "EUR", "duration_days": 7, "nights": 6,
        "departure_date": None, "return_date": None, "rating": 4.5, "board_basis": None,
        "transport": None, "airline": None, "availability": None, "discount": None,
        "description": None, "image_url": None, "detail_url": None,
        "source": "test", "extra_data": "{}",
    }])
    assert repo.count() == before, "un upsert del mismo id no debe crear una fila nueva"
    stored = repo.get(product_id)
    assert stored["title"] == "Paquete actualizado"
    assert stored["price"] == 650.0


def test_product_upsert_empty_returns_zero():
    assert ProductRepository().upsert_many([]) == 0


def test_product_get_unknown_returns_none():
    assert ProductRepository().get("no-existe-jamas") is None


def test_product_list_filters_by_price_and_rating(product_id):
    repo = ProductRepository()
    cheap = repo.list(max_price=1)
    assert all(r["price"] <= 1 for r in cheap if r["price"] is not None)
    rated = repo.list(min_rating=4.0)
    assert all(r["rating"] >= 4.0 for r in rated if r["rating"] is not None)
    found = repo.list(destination="Testlandia")
    assert any(r["product_id"] == product_id for r in found)


def test_product_list_query_is_case_insensitive(product_id):
    results = ProductRepository().list(query="PAQUETE DE PRUEBA")
    assert any(r["product_id"] == product_id for r in results)


def test_product_destinations_has_no_nulls():
    destinations = ProductRepository().destinations()
    assert all(d is not None for d in destinations)
    assert destinations == sorted(destinations)


# --------------------------------------------------------------------------
# DestinationRepository
# --------------------------------------------------------------------------


def test_destinations_are_loaded_and_sorted():
    rows = DestinationRepository().list()
    assert rows, "el build del modelo debería haber cargado destinos"
    names = [r["name"] for r in rows]
    assert names == sorted(names)
    assert DestinationRepository().count() == len(rows)


def test_destination_upsert_empty_returns_zero():
    assert DestinationRepository().upsert_many([]) == 0


# --------------------------------------------------------------------------
# TrackingRepository / tracking_service
# --------------------------------------------------------------------------


def test_create_session_returns_id():
    sid = create_session(source="test")
    assert sid
    assert AnalyticsRepository().scalar(
        "SELECT COUNT(*) FROM sessions WHERE session_id=?", (sid,)
    ) == 1


def test_create_session_is_idempotent_for_same_id():
    sid = str(uuid.uuid4())
    create_session(session_id=sid, source="test")
    create_session(session_id=sid, source="test")
    assert AnalyticsRepository().scalar(
        "SELECT COUNT(*) FROM sessions WHERE session_id=?", (sid,)
    ) == 1


def test_register_event_without_dedupe_always_inserts():
    sid = create_session(source="test")
    assert register_event(sid, "product_click", "pagina") is True
    assert register_event(sid, "product_click", "pagina") is True


def test_register_event_dedupe_key_blocks_repeats():
    sid = create_session(source="test")
    assert register_event(sid, "page_view", "Vista", dedupe_key="page_view:Vista") is True
    assert register_event(sid, "page_view", "Vista", dedupe_key="page_view:Vista") is False


def test_dedupe_key_is_scoped_per_session():
    first = create_session(source="test")
    second = create_session(source="test")
    assert register_event(first, "page_view", "Vista", dedupe_key="k") is True
    # La misma clave en otra sesión sí debe registrarse.
    assert register_event(second, "page_view", "Vista", dedupe_key="k") is True


def test_register_event_serializes_metadata():
    sid = create_session(source="test")
    register_event(sid, "custom", "pagina", metadata={"nested": {"a": 1}, "list": [1, 2]})
    stored = AnalyticsRepository().rows(
        "SELECT metadata FROM events WHERE session_id=? AND event_type='custom'", (sid,)
    )
    assert '"nested"' in stored[0]["metadata"]


# --------------------------------------------------------------------------
# BookingRepository / booking_service
# --------------------------------------------------------------------------


def test_create_booking_computes_revenue_and_margin(product_id):
    sid = create_session(source="test")
    booking_id = create_booking(sid, product_id, passengers=2, cost_eur=400.0)
    row = AnalyticsRepository().rows(
        "SELECT * FROM bookings WHERE booking_id=?", (booking_id,)
    )[0]
    assert row["revenue_eur"] == 1000.0  # 500 x 2 pasajeros
    assert row["margin_eur"] == 600.0    # 1000 - 400
    assert row["status"] == "confirmed"
    assert row["room_nights"] == 6       # hereda las noches del producto


def test_create_booking_registers_tracking_event(product_id):
    sid = create_session(source="test")
    create_booking(sid, product_id)
    events = AnalyticsRepository().rows(
        "SELECT event_type, destination FROM events WHERE session_id=? AND event_type='booking'",
        (sid,),
    )
    assert events
    assert events[0]["destination"] == "Testlandia"


def test_create_booking_without_cost_leaves_margin_null(product_id):
    sid = create_session(source="test")
    booking_id = create_booking(sid, product_id)
    row = AnalyticsRepository().rows(
        "SELECT margin_eur, cost_eur FROM bookings WHERE booking_id=?", (booking_id,)
    )[0]
    assert row["cost_eur"] is None
    assert row["margin_eur"] is None


def test_create_booking_rejects_unknown_product():
    sid = create_session(source="test")
    with pytest.raises(ValueError):
        create_booking(sid, "producto-inexistente")


def test_cancel_booking_updates_status(product_id):
    sid = create_session(source="test")
    booking_id = create_booking(sid, product_id)
    cancel_booking(booking_id, session_id=sid)
    row = AnalyticsRepository().rows(
        "SELECT status, cancelled_at FROM bookings WHERE booking_id=?", (booking_id,)
    )[0]
    assert row["status"] == "cancelled"
    assert row["cancelled_at"] is not None


def test_booking_repository_cancel_unknown_id_is_noop():
    # No debe lanzar: cancelar algo inexistente simplemente no afecta a ninguna fila.
    BookingRepository().cancel("no-existe")


# --------------------------------------------------------------------------
# AnalyticsRepository
# --------------------------------------------------------------------------


def test_analytics_repository_scalar_and_rows():
    repo = AnalyticsRepository()
    assert isinstance(repo.scalar("SELECT COUNT(*) FROM destinations"), int)
    rows = repo.rows("SELECT name FROM destinations LIMIT 3")
    assert all("name" in row for row in rows)


def test_tracking_repository_insert_event_reports_dedupe():
    sid = create_session(source="test")
    repo = TrackingRepository()
    row = {
        "event_id": str(uuid.uuid4()), "session_id": sid, "user_id": None,
        "page": "p", "event_type": "t", "element_id": None, "product_id": None,
        "destination": None, "source": None, "medium": None, "campaign": None,
        "device": None, "country": None, "response_time_ms": None,
        "metadata": "{}", "dedupe_key": "clave-unica-" + uuid.uuid4().hex,
    }
    assert repo.insert_event(row) is True
    assert repo.insert_event({**row, "event_id": str(uuid.uuid4())}) is False
