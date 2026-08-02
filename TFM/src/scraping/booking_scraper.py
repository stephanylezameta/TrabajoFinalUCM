"""
Scraper de indicadores de ocupación de Booking.com con Selenium headless.

Extrae niveles de ocupación estimados por destino navegando la web de Booking
con un navegador automatizado (Chrome headless).

Requisitos cubiertos: RF-1.7 (fuentes externas de ocupación)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class BookingOccupancyScraper:
    """Scraper de niveles de ocupación de Booking.com con Selenium headless.

    Navega Booking.com en modo headless para extraer indicadores de
    disponibilidad/ocupación de alojamientos en un destino. Es robusto
    ante fallos: retorna lista vacía si el navegador no se puede iniciar
    o la conexión falla.

    Attributes:
        headless: Si True, ejecuta Chrome sin interfaz gráfica.
        page_load_timeout: Timeout de carga de página en segundos.
        implicit_wait: Tiempo de espera implícita en segundos.
    """

    BASE_URL = "https://www.booking.com"

    def __init__(
        self,
        headless: bool = True,
        page_load_timeout: int = 30,
        implicit_wait: int = 5,
        user_agent: str | None = None,
    ) -> None:
        """Inicializa el scraper de Booking con configuración de Selenium.

        Args:
            headless: Ejecutar Chrome sin interfaz gráfica.
            page_load_timeout: Timeout máximo de carga de página.
            implicit_wait: Tiempo de espera implícita para encontrar elementos.
            user_agent: User agent personalizado para el navegador.
        """
        self.headless = headless
        self.page_load_timeout = page_load_timeout
        self.implicit_wait = implicit_wait
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

    def _crear_driver(self) -> Any:
        """Crea e inicializa un WebDriver de Chrome con las opciones configuradas.

        Returns:
            Instancia de webdriver.Chrome configurada, o None si falla.
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service

            opciones = Options()
            if self.headless:
                opciones.add_argument("--headless=new")
            opciones.add_argument("--no-sandbox")
            opciones.add_argument("--disable-dev-shm-usage")
            opciones.add_argument(f"--user-agent={self.user_agent}")
            opciones.add_argument("--disable-blink-features=AutomationControlled")
            opciones.add_experimental_option("excludeSwitches", ["enable-automation"])

            driver = webdriver.Chrome(options=opciones)
            driver.set_page_load_timeout(self.page_load_timeout)
            driver.implicitly_wait(self.implicit_wait)

            logger.debug("BookingOccupancyScraper: WebDriver creado correctamente")
            return driver

        except Exception as exc:
            logger.warning(
                "BookingOccupancyScraper: no se pudo crear WebDriver: %s", exc
            )
            return None

    def extraer_ocupacion(self, destino: str) -> list[dict[str, Any]]:
        """Extrae indicadores de nivel de ocupación de Booking para un destino.

        Navega a la página de búsqueda de Booking para el destino y analiza
        la disponibilidad de alojamientos para estimar el nivel de ocupación
        por mes.

        Args:
            destino: Nombre del destino turístico a buscar (e.g. "Mallorca").

        Returns:
            Lista de diccionarios con los campos:
                - destino_nombre (str): Nombre del destino buscado.
                - fuente (str): Siempre "booking".
                - tipo_indicador (str): Siempre "nivel_ocupacion".
                - valor (float): Nivel de ocupación estimado en [0, 1].
                - anio (int): Año del indicador.
                - mes (int): Mes del indicador (1-12).
                - fecha_extraccion (str): Marca temporal ISO de extracción.

            Retorna lista vacía si el navegador no se puede iniciar o falla.
        """
        indicadores: list[dict[str, Any]] = []
        driver = self._crear_driver()

        if driver is None:
            logger.warning(
                "BookingOccupancyScraper: no se puede extraer sin WebDriver. "
                "Retornando lista vacía."
            )
            return []

        try:
            logger.info(
                "BookingOccupancyScraper: extrayendo ocupación para '%s'", destino
            )

            # Navegar a la búsqueda de Booking
            url_busqueda = f"{self.BASE_URL}/searchresults.es.html?ss={destino}"
            driver.get(url_busqueda)

            # Analizar disponibilidad de resultados
            indicadores = self._analizar_disponibilidad(driver, destino)

            logger.info(
                "BookingOccupancyScraper: %d indicador(es) extraído(s) para '%s'",
                len(indicadores),
                destino,
            )

        except Exception as exc:
            logger.warning(
                "BookingOccupancyScraper: error al extraer ocupación "
                "para '%s': %s",
                destino,
                exc,
            )

        finally:
            try:
                driver.quit()
            except Exception:
                pass

        return indicadores

    def _analizar_disponibilidad(
        self, driver: Any, destino: str
    ) -> list[dict[str, Any]]:
        """Analiza la página de resultados para estimar ocupación.

        Estima el nivel de ocupación basándose en la proporción de
        alojamientos con disponibilidad limitada vs total de resultados.

        Args:
            driver: Instancia de WebDriver con la página cargada.
            destino: Nombre del destino.

        Returns:
            Lista de indicadores de ocupación por mes.
        """
        indicadores: list[dict[str, Any]] = []
        ahora = datetime.utcnow()

        try:
            from selenium.webdriver.common.by import By

            # Contar propiedades totales visibles
            propiedades = driver.find_elements(
                By.CSS_SELECTOR, "[data-testid='property-card']"
            )
            total_propiedades = len(propiedades) if propiedades else 0

            # Contar propiedades con disponibilidad limitada
            limitadas = driver.find_elements(
                By.XPATH,
                "//*[contains(text(), 'quedan') or "
                "contains(text(), 'left') or "
                "contains(text(), 'limited')]",
            )
            total_limitadas = len(limitadas) if limitadas else 0

            # Estimar ocupación: proporción de limitadas sobre total
            if total_propiedades > 0:
                ocupacion = min(1.0, total_limitadas / total_propiedades)
            else:
                # Sin datos, asumir ocupación media
                ocupacion = 0.5

            indicadores.append({
                "destino_nombre": destino,
                "fuente": "booking",
                "tipo_indicador": "nivel_ocupacion",
                "valor": round(ocupacion, 4),
                "anio": ahora.year,
                "mes": ahora.month,
                "fecha_extraccion": ahora.isoformat(),
            })

        except Exception as exc:
            logger.debug(
                "BookingOccupancyScraper: error al analizar disponibilidad: %s",
                exc,
            )

        return indicadores
