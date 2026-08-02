"""
Recolector de posts de Reddit sobre destinos turísticos con Selenium.

Navega la web de Reddit con Chrome headless para buscar posts en
subreddits de viajes y extraer opiniones sobre destinos. No requiere
credenciales de API de Reddit (no usa PRAW).

Requisitos cubiertos: RF-1.7 (fuentes externas de reseñas), DECISIÓN-004
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
        "RedditCollector: Selenium no está instalado. "
        "El collector retornará listas vacías."
    )


class RedditCollector:
    """Recolector de posts de Reddit sobre destinos turísticos con Selenium.

    Navega la búsqueda de Reddit en modo headless para encontrar posts
    relevantes sobre destinos de viaje. No requiere autenticación OAuth2
    ni cuenta de desarrollador de Reddit.

    Attributes:
        subreddits: Lista de subreddits de referencia (para contexto).
        timeout: Tiempo máximo de espera para carga de elementos en segundos.
        headless: Si True, ejecuta Chrome sin interfaz gráfica.
    """

    # Subreddits de viaje por defecto (DECISIÓN-004)
    subreddits: list[str] = [
        "travel",
        "solotravel",
        "backpacking",
        "Flights",
        "TravelHacks",
        "vacation",
    ]

    def __init__(
        self,
        subreddits: list[str] | None = None,
        timeout: int = 15,
        headless: bool = True,
    ) -> None:
        """Inicializa el recolector de Reddit con Selenium.

        Args:
            subreddits: Lista de subreddits donde buscar. Si no se pasa,
                        se usan los subreddits por defecto de DECISIÓN-004.
            timeout: Tiempo máximo de espera para carga de elementos (segundos).
            headless: Ejecutar Chrome sin interfaz gráfica.
        """
        if subreddits is not None:
            self.subreddits = subreddits
        self.timeout = timeout
        self.headless = headless
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

    def _crear_driver(self) -> Any | None:
        """Crea e inicializa un WebDriver de Chrome con las opciones configuradas.

        Returns:
            Instancia de webdriver.Chrome configurada, o None si falla.
        """
        if not SELENIUM_DISPONIBLE:
            logger.warning(
                "RedditCollector: Selenium no disponible, no se puede crear driver."
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
            opciones.add_experimental_option(
                "excludeSwitches", ["enable-automation"]
            )

            driver = webdriver.Chrome(options=opciones)
            driver.set_page_load_timeout(self.timeout * 2)
            driver.implicitly_wait(3)

            logger.debug("RedditCollector: WebDriver creado correctamente.")
            return driver

        except Exception as exc:
            logger.warning(
                "RedditCollector: no se pudo crear WebDriver: %s", exc
            )
            return None

    def collect_posts(
        self, destino: str, limite: int = 100
    ) -> list[dict[str, Any]]:
        """Recolecta posts de Reddit que mencionan un destino turístico.

        Navega la búsqueda de Reddit para encontrar posts que contengan
        el nombre del destino junto con "travel" y extrae título, texto
        preview, score y fecha.

        Args:
            destino: Nombre del destino turístico a buscar (e.g. "Mallorca").
            limite: Número máximo total de posts a recolectar. Por defecto 100.

        Returns:
            Lista de diccionarios con los campos:
                - destino_nombre (str): Nombre del destino buscado.
                - fuente (str): Siempre "reddit".
                - texto_original (str): Título + texto preview del post.
                - idioma (str): Código de idioma detectado.
                - puntuacion (float | None): Score normalizado del post (0-5).
                - fecha_publicacion (str | None): Fecha de publicación.
                - url_fuente (str): URL permanente del post en Reddit.
                - fecha_extraccion (str): Marca temporal ISO de extracción.

            Retorna lista vacía si Selenium no está disponible o la conexión falla.
        """
        if not SELENIUM_DISPONIBLE:
            logger.warning(
                "RedditCollector: Selenium no instalado. "
                "Retornando lista vacía para destino='%s'.",
                destino,
            )
            return []

        posts: list[dict[str, Any]] = []
        driver = self._crear_driver()

        if driver is None:
            logger.warning(
                "RedditCollector: no se pudo crear WebDriver. "
                "Retornando lista vacía para destino='%s'.",
                destino,
            )
            return []

        try:
            logger.info(
                "RedditCollector: buscando '%s' en Reddit (limite=%d)",
                destino,
                limite,
            )

            # Navegar a la búsqueda de Reddit
            query = f"{destino} travel"
            url_busqueda = (
                f"https://www.reddit.com/search/?q={query}&type=link"
            )
            driver.get(url_busqueda)

            # Esperar a que carguen los resultados
            wait = WebDriverWait(driver, self.timeout)
            wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(3)  # Pausa para renderizado dinámico de Reddit

            # Scroll para cargar más resultados si es necesario
            self._scroll_para_cargar(driver, limite)

            # Extraer posts de la página
            posts = self._extraer_posts_pagina(driver, destino, limite)

            logger.info(
                "RedditCollector: %d post(s) recolectado(s) para '%s'",
                len(posts),
                destino,
            )

        except Exception as exc:
            logger.warning(
                "RedditCollector: error inesperado para destino='%s': %s",
                destino,
                exc,
            )

        finally:
            try:
                driver.quit()
            except Exception:
                pass

        return posts

    def _scroll_para_cargar(self, driver: Any, limite: int) -> None:
        """Realiza scroll en la página para cargar más resultados.

        Reddit usa carga infinita (infinite scroll). Se hacen varios scrolls
        para intentar cargar suficientes posts.

        Args:
            driver: Instancia de WebDriver.
            limite: Número de posts deseados (controla cuántos scrolls hacer).
        """
        try:
            scrolls_necesarios = min(5, limite // 20)
            for _ in range(scrolls_necesarios):
                driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )
                time.sleep(1.5)
        except Exception as exc:
            logger.debug(
                "RedditCollector: error durante scroll: %s", exc
            )

    def _extraer_posts_pagina(
        self, driver: Any, destino: str, limite: int
    ) -> list[dict[str, Any]]:
        """Extrae posts de la página de resultados de búsqueda de Reddit.

        Args:
            driver: Instancia de WebDriver con la página cargada.
            destino: Nombre del destino buscado.
            limite: Número máximo de posts a extraer.

        Returns:
            Lista de diccionarios con los datos de cada post.
        """
        posts: list[dict[str, Any]] = []

        try:
            # Selectores para posts en Reddit (interfaz nueva y antigua)
            selectores_post = [
                "div[data-testid='post-container']",
                "faceplate-tracker[source='search']",
                "article",
                "div[class*='Post']",
                "a[data-testid='post-title']",
                "[data-click-id='body']",
                "search-telemetry-tracker",
            ]

            elementos_post: list[Any] = []
            for selector in selectores_post:
                try:
                    elementos_post = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elementos_post:
                        break
                except Exception:
                    continue

            if not elementos_post:
                # Intentar con XPath genérico
                elementos_post = driver.find_elements(
                    By.XPATH,
                    "//div[.//a[contains(@href, '/r/')]]"
                )

            for elemento in elementos_post[:limite]:
                post = self._parsear_post_elemento(elemento, destino)
                if post is not None:
                    posts.append(post)
                if len(posts) >= limite:
                    break

        except Exception as exc:
            logger.debug(
                "RedditCollector: error extrayendo posts de página: %s", exc
            )

        return posts

    def _parsear_post_elemento(
        self, elemento: Any, destino: str
    ) -> dict[str, Any] | None:
        """Parsea un elemento HTML de post de Reddit.

        Args:
            elemento: Elemento WebElement que contiene el post.
            destino: Nombre del destino para incluir en el registro.

        Returns:
            Diccionario con los campos del post, o None si no es parseable.
        """
        try:
            # Extraer título del post
            titulo = self._extraer_titulo(elemento)
            if not titulo:
                return None

            # Extraer texto preview (si existe)
            preview = self._extraer_preview(elemento)

            # Componer texto completo
            texto = titulo
            if preview and len(preview.strip()) > 5:
                texto = f"{titulo}\n\n{preview}"

            if len(texto.strip()) < 15:
                return None

            # Extraer score (upvotes)
            score = self._extraer_score(elemento)
            puntuacion = self._normalizar_score(score)

            # Extraer fecha de publicación
            fecha_publicacion = self._extraer_fecha(elemento)

            # Extraer URL permanente
            url_fuente = self._extraer_url(elemento)

            # Detectar idioma
            idioma = self._detectar_idioma(texto)

            return {
                "destino_nombre": destino,
                "fuente": "reddit",
                "texto_original": texto.strip(),
                "idioma": idioma,
                "puntuacion": puntuacion,
                "fecha_publicacion": fecha_publicacion,
                "url_fuente": url_fuente,
                "fecha_extraccion": datetime.utcnow().isoformat(),
            }

        except Exception as exc:
            logger.debug(
                "RedditCollector: no se pudo parsear post: %s", exc
            )
            return None

    def _extraer_titulo(self, elemento: Any) -> str | None:
        """Extrae el título de un post de Reddit.

        Args:
            elemento: Elemento WebElement del post.

        Returns:
            Título del post o None.
        """
        selectores_titulo = [
            "a[data-testid='post-title']",
            "h3",
            "a[class*='title']",
            "[slot='title']",
            "a[href*='/comments/']",
        ]

        for selector in selectores_titulo:
            try:
                elems = elemento.find_elements(By.CSS_SELECTOR, selector)
                for elem in elems:
                    texto = elem.text.strip()
                    if texto and len(texto) > 5:
                        return texto
            except Exception:
                continue

        return None

    def _extraer_preview(self, elemento: Any) -> str | None:
        """Extrae el texto preview/cuerpo de un post de Reddit.

        Args:
            elemento: Elemento WebElement del post.

        Returns:
            Texto preview o None.
        """
        selectores_preview = [
            "div[class*='RichTextJSON']",
            "div[data-testid='post-content']",
            "p",
            "[slot='text-body']",
            "div[class*='md']",
        ]

        for selector in selectores_preview:
            try:
                elems = elemento.find_elements(By.CSS_SELECTOR, selector)
                for elem in elems:
                    texto = elem.text.strip()
                    if texto and len(texto) > 10:
                        return texto
            except Exception:
                continue

        return None

    def _extraer_score(self, elemento: Any) -> int | None:
        """Extrae el score (upvotes) de un post de Reddit.

        Args:
            elemento: Elemento WebElement del post.

        Returns:
            Score como entero o None.
        """
        selectores_score = [
            "[data-testid='post-score']",
            "faceplate-number",
            "[class*='score']",
            "[class*='vote']",
            "[id*='vote-arrows']",
        ]

        for selector in selectores_score:
            try:
                elems = elemento.find_elements(By.CSS_SELECTOR, selector)
                for elem in elems:
                    texto = elem.text.strip()
                    if texto:
                        # Manejar sufijos como 'k' (miles)
                        texto_limpio = texto.lower().replace(",", "")
                        if "k" in texto_limpio:
                            try:
                                return int(float(texto_limpio.replace("k", "")) * 1000)
                            except ValueError:
                                continue
                        try:
                            return int(texto_limpio)
                        except ValueError:
                            continue
            except Exception:
                continue

        return None

    def _extraer_fecha(self, elemento: Any) -> str | None:
        """Extrae la fecha de publicación de un post de Reddit.

        Args:
            elemento: Elemento WebElement del post.

        Returns:
            Fecha como string o None.
        """
        try:
            # Buscar elementos time con atributo datetime
            time_elems = elemento.find_elements(By.TAG_NAME, "time")
            for time_elem in time_elems:
                dt = time_elem.get_attribute("datetime")
                if dt:
                    return dt
                title = time_elem.get_attribute("title")
                if title:
                    return title

            # Buscar elementos con texto de fecha relativa
            selectores_fecha = [
                "[class*='timestamp']",
                "[data-testid='post-timestamp']",
                "span[class*='time']",
                "faceplate-timeago",
            ]
            for selector in selectores_fecha:
                try:
                    elems = elemento.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elems:
                        dt = elem.get_attribute("datetime") or elem.get_attribute("ts")
                        if dt:
                            return dt
                        texto = elem.text.strip()
                        if texto and re.search(r"\d", texto):
                            return texto
                except Exception:
                    continue

        except Exception as exc:
            logger.debug(
                "RedditCollector: error extrayendo fecha: %s", exc
            )

        return None

    def _extraer_url(self, elemento: Any) -> str:
        """Extrae la URL permanente de un post de Reddit.

        Args:
            elemento: Elemento WebElement del post.

        Returns:
            URL del post o URL genérica de Reddit.
        """
        try:
            # Buscar links que apunten a posts específicos
            links = elemento.find_elements(By.TAG_NAME, "a")
            for link in links:
                href = link.get_attribute("href") or ""
                if "/comments/" in href:
                    # Asegurar URL completa
                    if href.startswith("/"):
                        return f"https://www.reddit.com{href}"
                    return href

            # Intentar con selectores específicos
            selectores_url = [
                "a[data-testid='post-title']",
                "a[class*='title']",
                "a[href*='/r/']",
            ]
            for selector in selectores_url:
                try:
                    elems = elemento.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elems:
                        href = elem.get_attribute("href") or ""
                        if href and "/r/" in href:
                            if href.startswith("/"):
                                return f"https://www.reddit.com{href}"
                            return href
                except Exception:
                    continue

        except Exception as exc:
            logger.debug(
                "RedditCollector: error extrayendo URL: %s", exc
            )

        return "https://www.reddit.com"

    @staticmethod
    def _normalizar_score(score: int | None) -> float | None:
        """Normaliza el score de Reddit a una escala de 0 a 5.

        Heurística: score <= 0 → 1.0, score >= 100 → 5.0, lineal entre ambos.

        Args:
            score: Puntuación (upvotes) del post.

        Returns:
            Puntuación normalizada en [1.0, 5.0] o None si score es None.
        """
        if score is None:
            return None
        if score <= 0:
            return 1.0
        if score >= 100:
            return 5.0
        # Interpolación lineal: 0→1, 100→5
        return 1.0 + (score / 100.0) * 4.0

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
