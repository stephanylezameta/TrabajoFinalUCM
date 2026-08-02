"""
Scraper de reseñas de TripAdvisor para destinos turísticos.

Extrae reseñas públicas mediante Selenium (Chrome headless), detecta el idioma
con langdetect y devuelve registros normalizados listos para persistir.

Requisitos cubiertos: RF-1.7 (fuentes externas de reseñas)
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Importación condicional de Selenium para que los tests no fallen sin él
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    SELENIUM_DISPONIBLE = True
except ImportError:
    SELENIUM_DISPONIBLE = False
    logger.debug(
        "TripAdvisorScraper: Selenium no está instalado. "
        "El scraper retornará listas vacías."
    )


class TripAdvisorScraper:
    """Scraper de reseñas de TripAdvisor para un destino turístico.

    Utiliza Selenium con Chrome headless para navegar TripAdvisor,
    buscar un destino y extraer reseñas con texto, puntuación y fecha.
    Es robusto ante fallos de red o del navegador: nunca lanza
    excepciones no controladas, devuelve lista vacía si falla.

    Attributes:
        timeout: Tiempo máximo de espera para carga de elementos en segundos.
        headless: Si True, ejecuta Chrome sin interfaz gráfica.
    """

    BASE_URL = "https://www.tripadvisor.es"

    def __init__(self, timeout: int = 15, headless: bool = True) -> None:
        """Inicializa el scraper con configuración de timeout.

        Args:
            timeout: Tiempo máximo de espera para carga de elementos (segundos).
            headless: Ejecutar Chrome sin interfaz gráfica.
        """
        self.timeout = timeout
        self.headless = headless
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

    def _crear_driver(self) -> Any | None:
        """Crea e inicializa un WebDriver de Chrome con opciones configuradas.

        Returns:
            Instancia de webdriver.Chrome configurada, o None si falla.
        """
        if not SELENIUM_DISPONIBLE:
            logger.warning(
                "TripAdvisorScraper: Selenium no disponible, no se puede crear driver."
            )
            return None

        try:
            opciones = Options()
            if self.headless:
                opciones.add_argument("--headless=new")
            opciones.add_argument("--no-sandbox")
            opciones.add_argument("--disable-dev-shm-usage")
            opciones.add_argument(f"--user-agent={self.user_agent}")
            opciones.add_argument("--disable-blink-features=AutomationControlled")
            opciones.add_argument("--disable-gpu")
            opciones.add_argument("--window-size=1920,1080")
            opciones.add_argument("--lang=es-ES")
            opciones.add_experimental_option(
                "excludeSwitches", ["enable-automation"]
            )

            driver = webdriver.Chrome(options=opciones)
            driver.set_page_load_timeout(self.timeout * 2)
            driver.implicitly_wait(3)

            logger.debug("TripAdvisorScraper: WebDriver creado correctamente.")
            return driver

        except Exception as exc:
            logger.warning(
                "TripAdvisorScraper: no se pudo crear WebDriver: %s", exc
            )
            return None

    def extraer_resenas(
        self, destino: str, limite: int = 50
    ) -> list[dict[str, Any]]:
        """Extrae reseñas de TripAdvisor para un destino dado.

        Navega a la búsqueda de TripAdvisor, localiza la página del destino,
        accede a las reseñas y extrae texto, puntuación y fecha hasta el límite.

        Args:
            destino: Nombre del destino turístico a buscar (e.g. "Mallorca").
            limite: Número máximo de reseñas a extraer. Por defecto 50.

        Returns:
            Lista de diccionarios con los campos:
                - destino_nombre (str): Nombre del destino buscado.
                - fuente (str): Siempre "tripadvisor".
                - texto_original (str): Texto completo de la reseña.
                - idioma (str): Código de idioma detectado (e.g. "es", "en").
                - puntuacion (float | None): Puntuación 1-5 si disponible.
                - fecha_publicacion (str | None): Fecha de publicación.
                - url_fuente (str): URL de la página donde se extrajo la reseña.
                - fecha_extraccion (str): Marca temporal ISO de extracción.

            Retorna lista vacía si Selenium no está disponible o la conexión falla.
        """
        if not SELENIUM_DISPONIBLE:
            logger.warning(
                "TripAdvisorScraper: Selenium no instalado. "
                "Retornando lista vacía para destino='%s'.",
                destino,
            )
            return []

        resenas: list[dict[str, Any]] = []
        driver = self._crear_driver()

        if driver is None:
            logger.warning(
                "TripAdvisorScraper: no se pudo crear WebDriver. "
                "Retornando lista vacía para destino='%s'.",
                destino,
            )
            return []

        try:
            logger.info(
                "TripAdvisorScraper: buscando reseñas para destino='%s' (limite=%d)",
                destino,
                limite,
            )

            # Paso 1: Buscar el destino
            url_busqueda = f"{self.BASE_URL}/Search?q={destino}"
            driver.get(url_busqueda)

            # Esperar a que carguen los resultados de búsqueda
            wait = WebDriverWait(driver, self.timeout)
            wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)  # Pausa para renderizado dinámico

            # Paso 2: Buscar links a páginas de destino/hotel
            url_destino = self._encontrar_link_destino(driver, destino)

            if url_destino:
                # Paso 3: Navegar a la página del destino/reseñas
                driver.get(url_destino)
                time.sleep(2)

                # Paso 4: Extraer reseñas de la página
                resenas = self._extraer_resenas_pagina(driver, destino, limite)
            else:
                # Intentar extraer reseñas directamente de la página de búsqueda
                resenas = self._extraer_resenas_pagina(driver, destino, limite)

            logger.info(
                "TripAdvisorScraper: %d reseña(s) extraída(s) para '%s'",
                len(resenas),
                destino,
            )

        except Exception as exc:
            logger.warning(
                "TripAdvisorScraper: error inesperado para destino='%s': %s",
                destino,
                exc,
            )

        finally:
            try:
                driver.quit()
            except Exception:
                pass

        return resenas

    def _encontrar_link_destino(
        self, driver: Any, destino: str
    ) -> str | None:
        """Busca el link a la página principal del destino en los resultados.

        Args:
            driver: Instancia de WebDriver con la página de búsqueda cargada.
            destino: Nombre del destino buscado.

        Returns:
            URL completa de la página del destino, o None si no se encontró.
        """
        try:
            # Buscar links que apunten a páginas de destino, hotel o atracción
            links = driver.find_elements(By.TAG_NAME, "a")
            destino_lower = destino.lower()

            patrones_url = [
                "/Tourism-",
                "/Hotel_Review-",
                "/Attraction_Review-",
                "/ShowUserReviews-",
            ]

            for link in links:
                try:
                    href = link.get_attribute("href") or ""
                    texto_link = link.text.lower()

                    # Verificar si el link es relevante para el destino
                    if any(patron in href for patron in patrones_url):
                        if destino_lower in texto_link or destino_lower in href.lower():
                            return href
                except Exception:
                    continue

            # Buscar cualquier link con el nombre del destino
            for link in links:
                try:
                    href = link.get_attribute("href") or ""
                    if (
                        self.BASE_URL in href
                        and any(patron in href for patron in patrones_url)
                    ):
                        return href
                except Exception:
                    continue

        except Exception as exc:
            logger.debug(
                "TripAdvisorScraper: error buscando link de destino: %s", exc
            )

        return None

    def _extraer_resenas_pagina(
        self, driver: Any, destino: str, limite: int
    ) -> list[dict[str, Any]]:
        """Extrae reseñas de la página actualmente cargada en el driver.

        Busca contenedores de reseñas con diversos selectores CSS y extrae
        texto, puntuación y fecha de cada una.

        Args:
            driver: Instancia de WebDriver con una página cargada.
            destino: Nombre del destino para incluir en los registros.
            limite: Número máximo de reseñas a extraer.

        Returns:
            Lista de diccionarios con los campos de reseña.
        """
        resenas: list[dict[str, Any]] = []
        url_actual = driver.current_url

        try:
            # Selectores para contenedores de reseña en TripAdvisor
            selectores_resena = [
                "[data-reviewid]",
                "[class*='review-container']",
                "[class*='reviewSelector']",
                "[class*='Review__container']",
                "div[class*='review']",
                "[class*='_T'] [class*='biGQs']",
            ]

            contenedores = []
            for selector in selectores_resena:
                try:
                    contenedores = driver.find_elements(By.CSS_SELECTOR, selector)
                    if contenedores:
                        break
                except Exception:
                    continue

            if not contenedores:
                # Último intento: buscar por XPath elementos con texto largo
                contenedores = driver.find_elements(
                    By.XPATH,
                    "//div[.//span[string-length(text()) > 50]]"
                )

            for contenedor in contenedores[:limite]:
                resena = self._parsear_resena_elemento(contenedor, destino, url_actual)
                if resena is not None:
                    resenas.append(resena)
                if len(resenas) >= limite:
                    break

        except Exception as exc:
            logger.debug(
                "TripAdvisorScraper: error extrayendo reseñas de página: %s", exc
            )

        return resenas

    def _parsear_resena_elemento(
        self, elemento: Any, destino: str, url_actual: str
    ) -> dict[str, Any] | None:
        """Parsea un elemento HTML de reseña individual.

        Args:
            elemento: Elemento WebElement que contiene la reseña.
            destino: Nombre del destino.
            url_actual: URL de la página actual.

        Returns:
            Diccionario con los campos de la reseña, o None si no es parseable.
        """
        try:
            # Extraer texto de la reseña
            texto = self._extraer_texto_resena(elemento)
            if not texto or len(texto.strip()) < 20:
                return None

            # Extraer puntuación (burbujas/estrellas)
            puntuacion = self._extraer_puntuacion(elemento)

            # Extraer fecha
            fecha_publicacion = self._extraer_fecha(elemento)

            # Detectar idioma
            idioma = self._detectar_idioma(texto)

            return {
                "destino_nombre": destino,
                "fuente": "tripadvisor",
                "texto_original": texto.strip(),
                "idioma": idioma,
                "puntuacion": puntuacion,
                "fecha_publicacion": fecha_publicacion,
                "url_fuente": url_actual,
                "fecha_extraccion": datetime.utcnow().isoformat(),
            }

        except Exception as exc:
            logger.debug(
                "TripAdvisorScraper: no se pudo parsear elemento de reseña: %s", exc
            )
            return None

    def _extraer_texto_resena(self, elemento: Any) -> str | None:
        """Extrae el texto principal de una reseña desde un elemento HTML.

        Args:
            elemento: Elemento WebElement que contiene la reseña.

        Returns:
            Texto de la reseña o None si no se encuentra.
        """
        # Selectores para texto de reseña
        selectores_texto = [
            "q",
            "span[class*='QewHA']",
            "span[class*='review-text']",
            "[class*='partial_entry']",
            "[class*='reviewText']",
            "p",
            "span",
        ]

        for selector in selectores_texto:
            try:
                elems = elemento.find_elements(By.CSS_SELECTOR, selector)
                for elem in elems:
                    texto = elem.text.strip()
                    if len(texto) >= 20:
                        return texto
            except Exception:
                continue

        # Último intento: texto completo del contenedor
        try:
            texto_completo = elemento.text.strip()
            if len(texto_completo) >= 20:
                # Tomar solo las primeras líneas que suelen ser la reseña
                lineas = texto_completo.split("\n")
                texto_resena = " ".join(
                    linea for linea in lineas if len(linea) > 15
                )
                if len(texto_resena) >= 20:
                    return texto_resena
        except Exception:
            pass

        return None

    def _extraer_puntuacion(self, elemento: Any) -> float | None:
        """Extrae la puntuación numérica (burbujas) de un elemento de reseña.

        TripAdvisor usa clases CSS como 'bubble_50' (= 5.0 estrellas) o
        atributos aria-label con la puntuación.

        Args:
            elemento: Elemento WebElement que contiene la reseña.

        Returns:
            Puntuación como float (1.0-5.0) o None si no se encuentra.
        """
        try:
            # Buscar SVG o span con clase 'bubble' (sistema de burbujas)
            bubble_elems = elemento.find_elements(
                By.CSS_SELECTOR,
                "[class*='bubble'], [class*='rating'], [class*='Bubble'], svg[class*='UctUV']"
            )
            for bubble in bubble_elems:
                # Intentar extraer del atributo class
                clases = bubble.get_attribute("class") or ""
                match = re.search(r"bubble_(\d+)", clases)
                if match:
                    valor = int(match.group(1))
                    return valor / 10.0

                # Intentar desde aria-label
                aria = bubble.get_attribute("aria-label") or ""
                match_aria = re.search(r"(\d[.,]?\d?)\s*(de|of|out)", aria)
                if match_aria:
                    valor_str = match_aria.group(1).replace(",", ".")
                    valor_f = float(valor_str)
                    if 1.0 <= valor_f <= 5.0:
                        return valor_f

                # Intentar desde title
                title = bubble.get_attribute("title") or ""
                match_title = re.search(r"(\d[.,]?\d?)", title)
                if match_title:
                    valor_str = match_title.group(1).replace(",", ".")
                    valor_f = float(valor_str)
                    if 1.0 <= valor_f <= 5.0:
                        return valor_f

        except Exception as exc:
            logger.debug(
                "TripAdvisorScraper: error extrayendo puntuación: %s", exc
            )

        return None

    def _extraer_fecha(self, elemento: Any) -> str | None:
        """Extrae la fecha de publicación de una reseña.

        Args:
            elemento: Elemento WebElement que contiene la reseña.

        Returns:
            Fecha como string o None si no se encuentra.
        """
        try:
            # Buscar elementos con clase que contenga 'date'
            selectores_fecha = [
                "[class*='date']",
                "[class*='Date']",
                "[class*='ratingDate']",
                "time",
                "span[class*='teHYY']",
            ]

            for selector in selectores_fecha:
                try:
                    elems = elemento.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elems:
                        # Intentar atributo datetime
                        dt = elem.get_attribute("datetime")
                        if dt:
                            return dt

                        # Intentar atributo title
                        title = elem.get_attribute("title")
                        if title and re.search(r"\d", title):
                            return title

                        # Intentar texto del elemento
                        texto = elem.text.strip()
                        if texto and re.search(r"\d", texto):
                            return texto
                except Exception:
                    continue

        except Exception as exc:
            logger.debug(
                "TripAdvisorScraper: error extrayendo fecha: %s", exc
            )

        return None

    @staticmethod
    def _detectar_idioma(texto: str) -> str:
        """Detecta el idioma de un texto usando langdetect.

        Args:
            texto: Texto a analizar.

        Returns:
            Código de idioma de 2 caracteres (e.g. "es", "en", "de").
            Retorna "unknown" si la detección falla.
        """
        try:
            from langdetect import detect

            if len(texto.strip()) < 10:
                return "unknown"
            return detect(texto)
        except Exception:
            return "unknown"
