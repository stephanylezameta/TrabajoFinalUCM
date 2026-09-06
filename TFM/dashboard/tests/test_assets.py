"""Tests de los recursos gráficos locales."""

from __future__ import annotations

from components import assets


def test_local_image_returns_none_for_unknown():
    assert assets.get_local_destination_image("Destino Que No Existe 123") is None


def test_local_image_returns_none_for_empty():
    assert assets.get_local_destination_image("") is None


def test_local_image_normalizes_name(tmp_path, monkeypatch):
    """El nombre con acentos y mayúsculas encuentra el fichero por su slug."""
    dest_dir = tmp_path / "destinations"
    dest_dir.mkdir()
    # PNG mínimo válido (1x1 transparente) sirve como contenido de prueba.
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000d49444154789c6360000002000100ffff03000006000557bfabd400"
        "00000049454e44ae426082"
    )
    (dest_dir / "sevilla.jpg").write_bytes(png)
    (dest_dir / "credits.json").write_text(
        '{"Sevilla": {"file": "sevilla.jpg", "credit": "Autor de prueba"}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(assets, "DESTINATIONS_DIR", dest_dir)
    assets.get_local_destination_image.cache_clear()
    assets._local_destination_credits.cache_clear()

    image = assets.get_local_destination_image("Sevilla")
    assert image is not None
    assert image["url"].startswith("data:image/jpeg;base64,")
    assert image["source"] == "local"
    assert image["credit"] == "Autor de prueba"
    # Con acentos y en minúsculas debe resolver al mismo fichero.
    assert assets.get_local_destination_image("SEVILLA") is not None

    assets.get_local_destination_image.cache_clear()
    assets._local_destination_credits.cache_clear()


def test_rank_icon_urls_removed():
    """Los iconos de mineral oro/plata/bronce ya no forman parte de los recursos."""
    assert not hasattr(assets, "RANK_ICON_URLS")
