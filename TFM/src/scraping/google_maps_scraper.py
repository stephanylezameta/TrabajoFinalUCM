"""
Scraper de reseñas de Google Maps para destinos turísticos.

Busca el destino en Google Maps, accede a las reseñas y extrae
texto, puntuación y fecha. Usa Selenium Chrome headless.
"""
from __future__ import annotations

import logging
import time
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.common.keys import Keys
    SELENIUM_DISPONIBLE = True
except ImportError:
    SELENIUM_DISPONIBLE = False


class GoogleMapsScraper:
    """Scraper de reseñas de destinos turísticos en Google Maps."""

    def __init__(self, timeout: int = 15, headless: bool = True):
        self.timeout = timeout
        self.headless = headless

    def _crear_driver(self):
        if not SELENIUM_DISPONIBLE:
            return None
        try:
            opciones = Options()
            if self.headless:
                opciones.add_argument("--headless=new")
            opciones.add_argument("--no-sandbox")
            opciones.add_argument("--disable-dev-shm-usage")
            opciones.add_argument("--disable-gpu")
            opciones.add_argument("--window-size=1920,1080")
            opciones.add_argument("--lang=es-ES")
            opciones.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            )
            driver = webdriver.Chrome(options=opciones)
            driver.set_page_load_timeout(self.timeout * 2)
            driver.implicitly_wait(5)
            return driver
        except Exception as exc:
            logger.warning("GoogleMapsScraper: no se pudo crear driver: %s", exc)
            return None

    def extraer_resenas(self, destino: str, limite: int = 50) -> list[dict[str, Any]]:
        """
        Extrae reseñas de Google Maps para un destino turístico.
        
        Busca "{destino} turismo" en Google Maps y extrae reseñas visibles.
        """
        if not SELENIUM_DISPONIBLE:
            logger.warning("GoogleMapsScraper: Selenium no disponible.")
            return []

        driver = self._crear_driver()
        if not driver:
            return []

        resenas = []
        try:
            logger.info("GoogleMapsScraper: buscando '%s' en Google Maps...", destino)
            
            # Navegar a Google Maps con búsqueda
            url = f"https://www.google.com/maps/search/{destino}+turismo"
            driver.get(url)
            time.sleep(4)

            # Intentar hacer clic en el primer resultado
            try:
                primer_resultado = WebDriverWait(driver, self.timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/maps/place/']"))
                )
                primer_resultado.click()
                time.sleep(3)
            except Exception:
                logger.debug("GoogleMapsScraper: no se encontró resultado clickeable")

            # Buscar y hacer clic en la pestaña/botón de reseñas
            try:
                # Buscar botón de reseñas
                botones_resenas = driver.find_elements(By.XPATH, 
                    "//*[contains(text(), 'reseña') or contains(text(), 'review') or contains(text(), 'opinión')]"
                )
                for boton in botones_resenas:
                    try:
                        if boton.is_displayed():
                            boton.click()
                            time.sleep(2)
                            break
                    except Exception:
                        continue
            except Exception:
                pass

            # Scroll para cargar más reseñas
            self._scroll_resenas(driver)

            # Extraer reseñas de la página
            resenas = self._extraer_resenas_pagina(driver, destino, limite)

            # Si no encontró reseñas en Maps, buscar en Google Search
            if not resenas:
                logger.info("GoogleMapsScraper: probando Google Search para '%s'...", destino)
                url_search = f"https://www.google.com/search?q={destino}+opiniones+turismo+reseñas"
                driver.get(url_search)
                time.sleep(3)
                resenas = self._extraer_textos_google(driver, destino, limite)

            logger.info("GoogleMapsScraper: %d reseña(s) para '%s'", len(resenas), destino)

        except Exception as exc:
            logger.warning("GoogleMapsScraper: error para '%s': %s", destino, exc)
        finally:
            try:
                driver.quit()
            except Exception:
                pass

        return resenas

    def _scroll_resenas(self, driver) -> None:
        """Hace scroll en el panel de reseñas para cargar más."""
        try:
            # Buscar el panel scrolleable de reseñas
            scrollable = driver.find_elements(By.CSS_SELECTOR, 
                "div[class*='review'], div[class*='section-scrollbox'], div[role='main']"
            )
            for panel in scrollable[:1]:
                for _ in range(3):
                    driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", panel)
                    time.sleep(1)
        except Exception:
            # Scroll general de página
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)

    def _extraer_resenas_pagina(self, driver, destino: str, limite: int) -> list[dict[str, Any]]:
        """Extrae reseñas del panel de Google Maps."""
        resenas = []
        try:
            # Selectores para reseñas en Google Maps
            selectores = [
                "div[data-review-id]",
                "div[class*='review-text']",
                "span[class*='wiI7pd']",  # Texto de reseña en Maps nuevo
                "div[class*='MyEned']",   # Contenedor de reseña
                "div[class*='jftiEf']",   # Otro contenedor
            ]
            
            elementos = []
            for selector in selectores:
                elementos = driver.find_elements(By.CSS_SELECTOR, selector)
                if elementos:
                    break

            if not elementos:
                # Fallback: buscar cualquier texto largo en la página
                elementos = driver.find_elements(By.XPATH,
                    "//*[string-length(normalize-space(text())) > 40 and "
                    "not(self::script) and not(self::style)]"
                )

            textos_vistos = set()
            for elem in elementos:
                if len(resenas) >= limite:
                    break
                try:
                    texto = elem.text.strip()
                    if (len(texto) > 40 and len(texto) < 2000
                        and texto.lower() not in textos_vistos
                        and not any(kw in texto.lower() for kw in [
                            "cookie", "privacy", "google", "iniciar sesión",
                            "terms", "report", "menú", "cómo llegar"
                        ])):
                        textos_vistos.add(texto.lower())
                        
                        # Intentar extraer puntuación
                        puntuacion = self._extraer_puntuacion_cercana(elem, driver)
                        
                        resenas.append({
                            "destino_nombre": destino,
                            "fuente": "google_maps",
                            "texto_original": texto,
                            "idioma": self._detectar_idioma(texto),
                            "puntuacion": puntuacion,
                            "fecha_publicacion": None,
                            "url_fuente": driver.current_url,
                            "fecha_extraccion": datetime.utcnow().isoformat(),
                        })
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("GoogleMapsScraper: error extrayendo reseñas: %s", exc)

        return resenas

    def _extraer_textos_google(self, driver, destino: str, limite: int) -> list[dict[str, Any]]:
        """Extrae textos de resultados de Google Search como fallback."""
        resenas = []
        try:
            elementos = driver.find_elements(By.XPATH,
                "//*[string-length(normalize-space(text())) > 50 and "
                "not(self::script) and not(self::style) and not(self::noscript)]"
            )
            textos_vistos = set()
            for elem in elementos:
                if len(resenas) >= limite:
                    break
                try:
                    texto = elem.text.strip()
                    if (len(texto) > 50 and len(texto) < 1500
                        and texto.lower() not in textos_vistos
                        and not any(kw in texto.lower() for kw in [
                            "cookie", "privacy", "google", "sign in",
                            "accept", "configuración", "búsqueda"
                        ])):
                        textos_vistos.add(texto.lower())
                        resenas.append({
                            "destino_nombre": destino,
                            "fuente": "google_maps",
                            "texto_original": texto,
                            "idioma": self._detectar_idioma(texto),
                            "puntuacion": None,
                            "fecha_publicacion": None,
                            "url_fuente": driver.current_url,
                            "fecha_extraccion": datetime.utcnow().isoformat(),
                        })
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("GoogleMapsScraper: error en Google Search: %s", exc)
        return resenas

    def _extraer_puntuacion_cercana(self, elem, driver) -> float | None:
        """Intenta extraer puntuación de estrellas cerca del elemento."""
        try:
            # Buscar aria-label con estrellas en el padre o hermanos
            parent = elem.find_element(By.XPATH, "./..")
            stars = parent.find_elements(By.CSS_SELECTOR, "[aria-label*='estrella'], [aria-label*='star']")
            for star in stars:
                aria = star.get_attribute("aria-label") or ""
                match = re.search(r"(\d[.,]?\d?)", aria)
                if match:
                    val = float(match.group(1).replace(",", "."))
                    if 1.0 <= val <= 5.0:
                        return val
        except Exception:
            pass
        return None

    @staticmethod
    def _detectar_idioma(texto: str) -> str:
        try:
            from langdetect import detect
            if len(texto.strip()) < 10:
                return "unknown"
            return detect(texto)
        except Exception:
            return "unknown"
