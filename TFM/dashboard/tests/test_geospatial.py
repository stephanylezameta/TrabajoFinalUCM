from services.geospatial_service import get_geospatial_metrics


def test_geospatial_reference_has_coordinates():
    rows = get_geospatial_metrics()
    assert rows
    assert all(-90 <= row["latitude"] <= 90 for row in rows)
    assert all(-180 <= row["longitude"] <= 180 for row in rows)
    assert all("clicks" in row and "bookings" in row and "revenue_eur" in row for row in rows)
