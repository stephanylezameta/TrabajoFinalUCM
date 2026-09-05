from __future__ import annotations

import json
from typing import Any, Iterable

from database.connection import db_session


def _rows(cursor) -> list[dict[str, Any]]:
    return [dict(r) for r in cursor.fetchall()]


class ProductRepository:
    def upsert_many(self, products: Iterable[dict[str, Any]]) -> int:
        sql = """
        INSERT INTO products (
            product_id,title,destination,hotel,price,currency,duration_days,nights,
            departure_date,return_date,rating,board_basis,transport,airline,
            availability,discount,description,image_url,detail_url,source,extra_data,updated_at
        ) VALUES (
            :product_id,:title,:destination,:hotel,:price,:currency,:duration_days,:nights,
            :departure_date,:return_date,:rating,:board_basis,:transport,:airline,
            :availability,:discount,:description,:image_url,:detail_url,:source,:extra_data,CURRENT_TIMESTAMP
        )
        ON CONFLICT(product_id) DO UPDATE SET
            title=excluded.title,destination=excluded.destination,hotel=excluded.hotel,
            price=excluded.price,currency=excluded.currency,duration_days=excluded.duration_days,
            nights=excluded.nights,departure_date=excluded.departure_date,return_date=excluded.return_date,
            rating=excluded.rating,board_basis=excluded.board_basis,transport=excluded.transport,
            airline=excluded.airline,availability=excluded.availability,discount=excluded.discount,
            description=excluded.description,image_url=excluded.image_url,detail_url=excluded.detail_url,
            source=excluded.source,extra_data=excluded.extra_data,updated_at=CURRENT_TIMESTAMP
        """
        items = list(products)
        if not items:
            return 0
        with db_session() as conn:
            conn.executemany(sql, items)
        return len(items)

    def list(self, query: str | None = None, destination: str | None = None,
             max_price: float | None = None, min_rating: float | None = None) -> list[dict[str, Any]]:
        clauses, params = [], []
        if query:
            clauses.append("(LOWER(title) LIKE ? OR LOWER(destination) LIKE ? OR LOWER(COALESCE(hotel,'')) LIKE ?)")
            q = f"%{query.lower()}%"
            params.extend([q, q, q])
        if destination and destination != "Todos":
            clauses.append("destination = ?")
            params.append(destination)
        if max_price is not None:
            clauses.append("price <= ?")
            params.append(max_price)
        if min_rating is not None:
            clauses.append("rating >= ?")
            params.append(min_rating)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with db_session() as conn:
            return _rows(conn.execute(f"SELECT * FROM products{where} ORDER BY price IS NULL, price, title", params))

    def get(self, product_id: str) -> dict[str, Any] | None:
        with db_session() as conn:
            row = conn.execute("SELECT * FROM products WHERE product_id=?", (product_id,)).fetchone()
            return dict(row) if row else None

    def destinations(self) -> list[str]:
        with db_session() as conn:
            return [r[0] for r in conn.execute("SELECT DISTINCT destination FROM products WHERE destination IS NOT NULL ORDER BY destination")]

    def count(self) -> int:
        with db_session() as conn:
            return conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]


class DestinationRepository:
    def upsert_many(self, rows: Iterable[dict[str, Any]]) -> int:
        sql = """
        INSERT INTO destinations (
            destination_id,name,zone,country_label,country_name,affinity,demand,occupancy,
            local_impact,seasonality,accessibility,sustainability,reference_price_eur,co2_kg,
            source,extra_data,updated_at
        ) VALUES (
            :destination_id,:name,:zone,:country_label,:country_name,:affinity,:demand,:occupancy,
            :local_impact,:seasonality,:accessibility,:sustainability,:reference_price_eur,:co2_kg,
            :source,:extra_data,CURRENT_TIMESTAMP
        )
        ON CONFLICT(destination_id) DO UPDATE SET
            name=excluded.name,zone=excluded.zone,country_label=excluded.country_label,
            country_name=excluded.country_name,affinity=excluded.affinity,demand=excluded.demand,
            occupancy=excluded.occupancy,local_impact=excluded.local_impact,
            seasonality=excluded.seasonality,accessibility=excluded.accessibility,
            sustainability=excluded.sustainability,reference_price_eur=excluded.reference_price_eur,
            co2_kg=excluded.co2_kg,source=excluded.source,extra_data=excluded.extra_data,
            updated_at=CURRENT_TIMESTAMP
        """
        items = list(rows)
        if not items:
            return 0
        with db_session() as conn:
            conn.executemany(sql, items)
        return len(items)

    def list(self) -> list[dict[str, Any]]:
        with db_session() as conn:
            return _rows(conn.execute("SELECT * FROM destinations ORDER BY name"))

    def count(self) -> int:
        with db_session() as conn:
            return conn.execute("SELECT COUNT(*) FROM destinations").fetchone()[0]


class TrackingRepository:
    def create_session(self, row: dict[str, Any]) -> None:
        with db_session() as conn:
            conn.execute("""
            INSERT OR IGNORE INTO sessions(session_id,user_id,source,medium,campaign,device,country)
            VALUES(:session_id,:user_id,:source,:medium,:campaign,:device,:country)
            """, row)

    def insert_event(self, row: dict[str, Any]) -> bool:
        with db_session() as conn:
            cur = conn.execute("""
            INSERT OR IGNORE INTO events(
                event_id,session_id,user_id,page,event_type,element_id,product_id,destination,
                source,medium,campaign,device,country,response_time_ms,metadata,dedupe_key
            ) VALUES(
                :event_id,:session_id,:user_id,:page,:event_type,:element_id,:product_id,:destination,
                :source,:medium,:campaign,:device,:country,:response_time_ms,:metadata,:dedupe_key
            )
            """, row)
            return cur.rowcount > 0


class BookingRepository:
    def create(self, row: dict[str, Any]) -> None:
        with db_session() as conn:
            conn.execute("""
            INSERT INTO bookings(
                booking_id,session_id,user_id,product_id,passengers,room_nights,
                revenue_eur,cost_eur,margin_eur,status
            ) VALUES(
                :booking_id,:session_id,:user_id,:product_id,:passengers,:room_nights,
                :revenue_eur,:cost_eur,:margin_eur,:status
            )
            """, row)

    def cancel(self, booking_id: str) -> None:
        with db_session() as conn:
            conn.execute("UPDATE bookings SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP WHERE booking_id=?", (booking_id,))


class AnalyticsRepository:
    def scalar(self, sql: str, params: tuple = ()):
        with db_session() as conn:
            return conn.execute(sql, params).fetchone()[0]

    def rows(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with db_session() as conn:
            return _rows(conn.execute(sql, params))
