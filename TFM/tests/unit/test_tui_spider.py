"""
Tests unitarios para src/scraping/tui_spider.py.

Valida la lógica pura (helpers de parseo, temporada, inferencias)
sin necesidad de Selenium ni conexión a internet.
"""

from datetime import date

import pytest

from src.scraping.tui_spider import (
    TUISpider,
    calcular_temporada,
    crear_spider_es,
    crear_spider_de,
    crear_spider_uk,
)


# ---------------------------------------------------------------------------
# calcular_temporada
# ---------------------------------------------------------------------------

class TestCalcularTemporada:
    """Tests para la función calcular_temporada."""

    @pytest.mark.parametrize("mes,expected", [
        (6, "Alta"), (7, "Alta"), (8, "Alta"), (12, "Alta"),
    ])
    def test_temporada_alta(self, mes, expected):
        assert calcular_temporada(date(2025, mes, 15)) == expected

    @pytest.mark.parametrize("mes,expected", [
        (1, "Baja"), (2, "Baja"), (3, "Baja"), (11, "Baja"),
    ])
    def test_temporada_baja(self, mes, expected):
        assert calcular_temporada(date(2025, mes, 15)) == expected

    @pytest.mark.parametrize("mes,expected", [
        (4, "Media"), (5, "Media"), (9, "Media"), (10, "Media"),
    ])
    def test_temporada_media(self, mes, expected):
        assert calcular_temporada(date(2025, mes, 15)) == expected


# ---------------------------------------------------------------------------
# _parsear_precio
# ---------------------------------------------------------------------------

class TestParsearPrecio:
    """Tests para el parser de precios."""

    def test_precio_simple(self):
        assert TUISpider._parsear_precio("1234") == 1234.0

    def test_precio_con_euro(self):
        assert TUISpider._parsear_precio("€1.234,56") == 1234.56

    def test_precio_formato_anglosajon(self):
        assert TUISpider._parsear_precio("£1,234.56") == 1234.56

    def test_precio_solo_coma_decimal(self):
        assert TUISpider._parsear_precio("899,99") == 899.99

    def test_precio_solo_coma_miles(self):
        assert TUISpider._parsear_precio("1,234") == 1234.0

    def test_precio_none(self):
        assert TUISpider._parsear_precio(None) is None

    def test_precio_vacio(self):
        assert TUISpider._parsear_precio("") is None

    def test_precio_sin_numeros(self):
        assert TUISpider._parsear_precio("Desde") is None


# ---------------------------------------------------------------------------
# _parsear_duracion
# ---------------------------------------------------------------------------

class TestParsearDuracion:
    """Tests para el parser de duración."""

    def test_noches_espanol(self):
        assert TUISpider._parsear_duracion("7 noches") == 7

    def test_nights_ingles(self):
        assert TUISpider._parsear_duracion("14 nights") == 14

    def test_nachte_aleman(self):
        assert TUISpider._parsear_duracion("7 Nächte") == 7

    def test_dias_espanol(self):
        assert TUISpider._parsear_duracion("8 días") == 8

    def test_solo_numero(self):
        assert TUISpider._parsear_duracion("7") == 7

    def test_none(self):
        assert TUISpider._parsear_duracion(None) is None

    def test_sin_numero(self):
        assert TUISpider._parsear_duracion("sin duración") is None


# ---------------------------------------------------------------------------
# _parsear_fecha
# ---------------------------------------------------------------------------

class TestParsearFecha:
    """Tests para el parser de fechas."""

    def test_formato_europeo_barra(self):
        assert TUISpider._parsear_fecha("15/07/2025") == date(2025, 7, 15)

    def test_formato_europeo_guion(self):
        assert TUISpider._parsear_fecha("15-07-2025") == date(2025, 7, 15)

    def test_formato_iso(self):
        assert TUISpider._parsear_fecha("2025-07-15") == date(2025, 7, 15)

    def test_none(self):
        assert TUISpider._parsear_fecha(None) is None

    def test_texto_invalido(self):
        assert TUISpider._parsear_fecha("próximamente") is None


# ---------------------------------------------------------------------------
# _inferir_pais
# ---------------------------------------------------------------------------

class TestInferirPais:
    """Tests para la inferencia de país."""

    def test_mallorca(self):
        assert TUISpider._inferir_pais("Mallorca") == "España"

    def test_creta(self):
        assert TUISpider._inferir_pais("Creta") == "Grecia"

    def test_cancun(self):
        assert TUISpider._inferir_pais("Cancún") == "México"

    def test_desconocido(self):
        assert TUISpider._inferir_pais("Lugar inventado") == "Desconocido"


# ---------------------------------------------------------------------------
# _inferir_categoria
# ---------------------------------------------------------------------------

class TestInferirCategoria:
    """Tests para la inferencia de categoría."""

    def test_playa(self):
        assert TUISpider._inferir_categoria("Beach Resort", "Mallorca") == "playa"

    def test_cultura(self):
        assert TUISpider._inferir_categoria("City Tour", "Roma") == "cultura"

    def test_aventura(self):
        assert TUISpider._inferir_categoria("Safari Adventure", "Kenia") == "aventura"

    def test_default_playa(self):
        assert TUISpider._inferir_categoria("Hotel bonito", "Lugar") == "playa"


# ---------------------------------------------------------------------------
# _determinar_zona
# ---------------------------------------------------------------------------

class TestDeterminarZona:
    """Tests para la determinación de zona geográfica."""

    def test_caribe(self):
        assert TUISpider._determinar_zona("caribe", "Punta Cana") == "Caribe"

    def test_mediterraneo(self):
        assert TUISpider._determinar_zona("mediterraneo", "Mallorca") == "Mediterráneo"

    def test_mexico_como_caribe(self):
        assert TUISpider._determinar_zona("america", "Cancun") == "Caribe"


# ---------------------------------------------------------------------------
# Factories de spiders
# ---------------------------------------------------------------------------

class TestFactories:
    """Tests para las funciones factory de spiders."""

    def test_crear_spider_es(self):
        spider = crear_spider_es()
        assert spider.market == "es"
        assert spider.base_url == "https://www.tui.es"
        assert spider.moneda == "EUR"
        assert spider.tipo_cambio_eur == 1.0

    def test_crear_spider_de(self):
        spider = crear_spider_de()
        assert spider.market == "de"
        assert spider.base_url == "https://www.tui.com"
        assert spider.moneda == "EUR"
        assert spider.idioma == "de"

    def test_crear_spider_uk(self):
        spider = crear_spider_uk()
        assert spider.market == "uk"
        assert spider.base_url == "https://www.tui.co.uk"
        assert spider.moneda == "GBP"
        assert spider.tipo_cambio_eur == 1.17

    def test_ciudad_salida_es(self):
        spider = crear_spider_es()
        assert spider._ciudad_salida_default() == "Madrid"

    def test_ciudad_salida_de(self):
        spider = crear_spider_de()
        assert spider._ciudad_salida_default() == "Frankfurt"

    def test_ciudad_salida_uk(self):
        spider = crear_spider_uk()
        assert spider._ciudad_salida_default() == "London Gatwick"
