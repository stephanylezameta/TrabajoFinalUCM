from services import destination_image_service as svc


def test_image_from_pages_prefers_search_order():
    payload = {
        "query": {
            "pages": [
                {"index": 2, "title": "Otro", "thumbnail": {"source": "https://img/other.jpg"}},
                {"index": 1, "title": "Ronda", "fullurl": "https://es.wikipedia.org/wiki/Ronda", "thumbnail": {"source": "https://img/ronda.jpg"}},
            ]
        }
    }
    image = svc._image_from_pages(payload, "Ronda")
    assert image["url"] == "https://img/ronda.jpg"
    assert image["matched_title"] == "Ronda"


def test_get_destination_image_falls_back_to_search(monkeypatch):
    svc.get_destination_image.cache_clear()
    # Otro test pudo activar el cortacircuitos de red; se desactiva para este.
    svc._NETWORK_DISABLED_UNTIL = 0.0

    calls = []

    def fake_exact(api_url, destination):
        calls.append(("exact", api_url, destination))
        return None

    def fake_search(api_url, destination):
        calls.append(("search", api_url, destination))
        return {"url": "https://img.example/test.jpg", "alt": "Imagen"}

    monkeypatch.setattr(svc, "_exact_lookup", fake_exact)
    monkeypatch.setattr(svc, "_search_lookup", fake_search)
    image = svc.get_destination_image("Destino nuevo")

    assert image["url"] == "https://img.example/test.jpg"
    assert calls[0][0] == "exact"
    assert calls[1][0] == "search"


# --------------------------------------------------------------------------
# Filtro de banderas, escudos y mapas
# --------------------------------------------------------------------------


def _payload(*sources: str, size: tuple[int, int] = (1200, 800)) -> dict:
    width, height = size
    return {
        "query": {
            "pages": [
                {
                    "index": i,
                    "title": f"P{i}",
                    "thumbnail": {"source": src, "width": width, "height": height},
                }
                for i, src in enumerate(sources)
            ]
        }
    }


def test_rejects_municipal_flags_and_shields():
    """Un municipio no se ilustra con su bandera: es identificación, no paisaje."""
    rejected = [
        "https://img/Bandera_de_Nijar.svg.png",
        "https://img/Flag_of_Seville.svg.png",
        "https://img/Escudo_de_Mijas.svg.png",
        "https://img/Coat_of_arms_of_Madrid.png",
        "https://img/Mapa_de_situacion.png",
        "https://img/Spain_location_map.png",
        "https://img/Wappen_Berlin.png",
    ]
    for url in rejected:
        assert svc._image_from_pages(_payload(url), "X") is None, f"no se descartó {url}"


def test_prefers_photo_over_flag_in_same_result_set():
    payload = _payload(
        "https://img/Bandera_de_Nijar.svg.png",
        "https://img/Arrecife_de_las_Sirenas.jpg",
    )
    image = svc._image_from_pages(payload, "Níjar")
    assert image["url"].endswith("Arrecife_de_las_Sirenas.jpg")


def test_rejects_portrait_images():
    """Los escudos y banderas son verticales o cuadrados; un paisaje es panorámico."""
    assert svc._image_from_pages(_payload("https://img/torre.jpg", size=(600, 900)), "X") is None
    assert svc._image_from_pages(_payload("https://img/cuadro.jpg", size=(800, 800)), "X") is None
    assert svc._image_from_pages(_payload("https://img/vista.jpg", size=(1200, 700)), "X")


def test_accepts_image_without_dimensions():
    """Sin dimensiones no se puede juzgar la proporción: decide el nombre."""
    payload = {
        "query": {"pages": [{"index": 0, "title": "P", "thumbnail": {"source": "https://img/v.jpg"}}]}
    }
    assert svc._image_from_pages(payload, "X")


def test_accepted_image_keeps_attribution():
    image = svc._image_from_pages(_payload("https://img/panorama.jpg"), "Sevilla")
    assert image["credit"] == "Wikipedia / Wikimedia Commons"
    assert image["alt"] == "Imagen de Sevilla"
