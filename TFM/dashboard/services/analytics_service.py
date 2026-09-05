from __future__ import annotations

from database.repositories import AnalyticsRepository

_repo = AnalyticsRepository()


def _safe_div(a, b):
    return (a / b) if b else None


def get_dashboard_metrics() -> dict:
    events = {r["event_type"]: r["n"] for r in _repo.rows("SELECT event_type, COUNT(*) n FROM events GROUP BY event_type")}
    sessions = _repo.scalar("SELECT COUNT(*) FROM sessions")
    users = _repo.scalar("SELECT COUNT(DISTINCT user_id) FROM sessions WHERE user_id IS NOT NULL")
    bookings = _repo.scalar("SELECT COUNT(*) FROM bookings WHERE status='confirmed'")
    cancellations = _repo.scalar("SELECT COUNT(*) FROM bookings WHERE status='cancelled'")
    revenue = _repo.scalar("SELECT COALESCE(SUM(revenue_eur),0) FROM bookings WHERE status='confirmed'") or 0
    cost = _repo.scalar("SELECT SUM(cost_eur) FROM bookings WHERE status='confirmed'")
    margin = _repo.scalar("SELECT SUM(margin_eur) FROM bookings WHERE status='confirmed'")
    passengers = _repo.scalar("SELECT COALESCE(SUM(passengers),0) FROM bookings WHERE status='confirmed'") or 0
    room_nights = _repo.scalar("SELECT COALESCE(SUM(room_nights),0) FROM bookings WHERE status='confirmed'") or 0
    avg_latency = _repo.scalar("SELECT AVG(response_time_ms) FROM events WHERE response_time_ms IS NOT NULL")
    impressions = events.get("product_impression", 0)
    clicks = events.get("product_click", 0)
    searches = events.get("search", 0)
    details = events.get("detail_view", 0)
    checkouts = events.get("checkout_start", 0)
    return {
        "impressions": impressions, "clicks": clicks, "ctr": _safe_div(clicks, impressions),
        "sessions": sessions, "users": users, "searches": searches, "detail_views": details,
        "checkout_starts": checkouts, "bookings": bookings, "conversion": _safe_div(bookings, sessions),
        "click_to_booking": _safe_div(bookings, clicks), "cancellations": cancellations,
        "cancellation_rate": _safe_div(cancellations, bookings + cancellations), "revenue_eur": revenue,
        "cost_eur": cost,
        "roas": _safe_div(revenue, cost) if cost is not None else None,
        "roi": _safe_div((revenue - cost), cost) if cost not in (None, 0) else None,
        "avg_ticket_eur": _safe_div(revenue, bookings), "revenue_per_session": _safe_div(revenue, sessions),
        "margin_eur": margin, "passengers": passengers, "room_nights": room_nights,
        "avg_response_time_ms": avg_latency,
    }


def get_funnel_metrics() -> list[dict]:
    m = get_dashboard_metrics()
    return [
        {"step": "Sesiones", "value": m["sessions"]},
        {"step": "Búsquedas", "value": m["searches"]},
        {"step": "Vistas de detalle", "value": m["detail_views"]},
        {"step": "Checkout", "value": m["checkout_starts"]},
        {"step": "Reservas", "value": m["bookings"]},
    ]


def get_destination_metrics() -> list[dict]:
    return _repo.rows("""
        WITH event_stats AS (
            SELECT COALESCE(destination,'Sin destino') destination,
                   SUM(CASE WHEN event_type='product_impression' THEN 1 ELSE 0 END) impressions,
                   SUM(CASE WHEN event_type='product_click' THEN 1 ELSE 0 END) clicks,
                   SUM(CASE WHEN event_type='detail_view' THEN 1 ELSE 0 END) detail_views
              FROM events
             GROUP BY COALESCE(destination,'Sin destino')
        ),
        booking_stats AS (
            SELECT COALESCE(p.destination,'Sin destino') destination,
                   SUM(CASE WHEN b.status='confirmed' THEN 1 ELSE 0 END) bookings,
                   COALESCE(SUM(CASE WHEN b.status='confirmed' THEN b.revenue_eur ELSE 0 END),0) revenue_eur
              FROM bookings b
              LEFT JOIN products p ON p.product_id=b.product_id
             GROUP BY COALESCE(p.destination,'Sin destino')
        ),
        all_destinations AS (
            SELECT destination FROM event_stats
            UNION
            SELECT destination FROM booking_stats
        )
        SELECT d.destination,
               COALESCE(e.impressions,0) impressions,
               COALESCE(e.clicks,0) clicks,
               COALESCE(e.detail_views,0) detail_views,
               COALESCE(b.bookings,0) bookings,
               COALESCE(b.revenue_eur,0) revenue_eur
          FROM all_destinations d
          LEFT JOIN event_stats e ON e.destination=d.destination
          LEFT JOIN booking_stats b ON b.destination=d.destination
         ORDER BY clicks DESC, bookings DESC, impressions DESC, d.destination
    """)


def instrumentation_status() -> list[dict]:
    m = get_dashboard_metrics()
    return [
        {"KPI": "CTR", "estado": "disponible" if m["impressions"] else "pendiente de instrumentar", "necesita": "product_impression + product_click"},
        {"KPI": "Conversión", "estado": "disponible" if m["sessions"] else "pendiente de instrumentar", "necesita": "sessions + bookings"},
        {"KPI": "ROI", "estado": "disponible" if m["cost_eur"] not in (None, 0) else "pendiente de instrumentar", "necesita": "cost_eur en bookings/campañas"},
        {"KPI": "Latencia", "estado": "disponible" if m["avg_response_time_ms"] is not None else "pendiente de instrumentar", "necesita": "response_time_ms en events"},
    ]
