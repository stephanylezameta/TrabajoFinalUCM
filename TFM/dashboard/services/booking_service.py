from __future__ import annotations

import uuid

from database.repositories import BookingRepository, ProductRepository
from services.tracking_service import register_event

_repo = BookingRepository()
_products = ProductRepository()


def create_booking(session_id: str, product_id: str, passengers: int = 1, room_nights: int | None = None,
                   cost_eur: float | None = None, user_id: str | None = None) -> str:
    product = _products.get(product_id)
    if not product:
        raise ValueError("Producto no encontrado")
    price = product.get("price")
    revenue = float(price) * passengers if price is not None else None
    margin = revenue - cost_eur if revenue is not None and cost_eur is not None else None
    booking_id = str(uuid.uuid4())
    _repo.create({
        "booking_id": booking_id, "session_id": session_id, "user_id": user_id,
        "product_id": product_id, "passengers": passengers,
        "room_nights": room_nights if room_nights is not None else product.get("nights"),
        "revenue_eur": revenue, "cost_eur": cost_eur, "margin_eur": margin, "status": "confirmed",
    })
    register_event(session_id, "booking", "propuesta_7", product_id=product_id,
                   destination=product.get("destination"), metadata={"booking_id": booking_id, "revenue_eur": revenue})
    return booking_id


def cancel_booking(booking_id: str, session_id: str | None = None) -> None:
    _repo.cancel(booking_id)
    if session_id:
        register_event(session_id, "cancellation", "propuesta_7", metadata={"booking_id": booking_id})
