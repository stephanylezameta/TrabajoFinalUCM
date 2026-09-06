from services.geospatial_service import get_geospatial_metrics


def test_geospatial_reference_has_coordinates():
    rows = get_geospatial_metrics()
    assert rows
    assert all(-90 <= row["latitude"] <= 90 for row in rows)
    assert all(-180 <= row["longitude"] <= 180 for row in rows)
    assert all("clicks" in row and "bookings" in row and "revenue_eur" in row for row in rows)


def test_coordinates_are_plausible():
    """Las coordenadas deben caer en el hemisferio y rango correctos.

    Detecta los errores gruesos típicos de un fichero curado a mano: latitud y
    longitud intercambiadas, o signo invertido.
    """
    import pandas as pd

    from services.geospatial_service import COORDINATES_PATH

    coords = pd.read_csv(COORDINATES_PATH)
    assert not coords.empty

    # Todos los destinos del catálogo están en el hemisferio norte, y entre el
    # Atlántico occidental (Cancún) y el Índico (Maldivas).
    for _, row in coords.iterrows():
        name = row["destination"]
        lat, lon = float(row["latitude"]), float(row["longitude"])
        assert -90 <= lat <= 90, f"{name}: latitud fuera de rango"
        assert -180 <= lon <= 180, f"{name}: longitud fuera de rango"
        assert 0 < lat < 60, f"{name}: latitud {lat} implausible para el catálogo"
        assert -90 < lon < 90, f"{name}: longitud {lon} implausible para el catálogo"


def test_coordinates_have_no_duplicates():
    import pandas as pd

    from services.geospatial_service import COORDINATES_PATH
    from utils.text import normalize_text

    coords = pd.read_csv(COORDINATES_PATH)
    keys = [normalize_text(d) for d in coords["destination"]]
    assert len(keys) == len(set(keys)), "hay destinos repetidos en el fichero"


def test_coordinate_source_is_declared():
    """Cada coordenada declara su procedencia, para poder auditarla."""
    import pandas as pd

    from services.geospatial_service import COORDINATES_PATH

    coords = pd.read_csv(COORDINATES_PATH)
    assert coords["coordinate_source"].notna().all()
    assert (coords["coordinate_source"].str.strip() != "").all()


def test_unmapped_destinations_are_reported():
    """Los destinos sin coordenada se declaran en lugar de desaparecer."""
    from services.geospatial_service import get_unmapped_destinations

    rows = get_unmapped_destinations()
    assert isinstance(rows, list)
    for row in rows:
        assert row["destination"]
        assert row["destination"] != "Sin destino"
        assert row["clicks"] >= 0


def test_coordinate_coverage_contract():
    from services.geospatial_service import coordinate_coverage

    coverage = coordinate_coverage()
    assert coverage["coordinates_available"] > 0
    assert coverage["unmapped_destinations"] == len(coverage["unmapped_names"])
    assert coverage["source_path"].endswith("destination_coordinates.csv")
