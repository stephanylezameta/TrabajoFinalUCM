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
