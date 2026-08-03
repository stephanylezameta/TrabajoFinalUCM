"""
Scraper de reseñas de TripAdvisor para destinos turísticos.

Usa Selenium (Chrome headless) con un enfoque robusto:
- Intenta TripAdvisor directamente primero
- Si falla o no encuentra reseñas, usa Google como fallback
- Timeout corto para no quedarse colgado
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    SELENIUM_DISPONIBLE = True
except ImportError:
    SELENIUM_DISPONIBLE = False


class TripAdvisorScraper:
    """Scraper de reseñas turísticas con Selenium."""

    def __init__(self, timeout: int = 15, headless: bool = True) -> None:
        self.timeout = timeout
        self.headless = headless

    def _crear_driver(self):
        """Crea Chrome headless con opciones anti-detección."""
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
            opciones.add_argument("--disable-blink-features=AutomationControlled")
            opciones.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            )
            driver = webdriver.Chrome(options=opciones)
            driver.set_page_load_timeout(self.timeout)
            driver.implicitly_wait(5)
            return driver
        except Exception as exc:
            logger.warning("TripAdvisorScraper: no se pudo crear driver: %s", exc)
            return None

    def extraer_resenas(self, destino: str, limite: int = 50) -> list[dict[str, Any]]:
        """Extrae reseñas sobre un destino turístico.
        
        Estrategia:
        1. Intenta buscar en TripAdvisor directamente
        2. Si falla, busca en Google con site:tripadvisor
        3. Extrae cualquier texto relevante > 30 caracteres
        """
        if not SELENIUM_DISPONIBLE:
            logger.warning("TripAdvisorScraper: Selenium no disponible.")
            return []

        driver = self._crear_driver()
        if not driver:
            return []

        resenas = []
        try:
            # Estrategia 1: Buscar directamente en TripAdvisor
            logger.info("TripAdvisorScraper: buscando '%s' en TripAdvisor...", destino)
            url = f"https://www.tripadvisor.es/Search?q={destino}"
            driver.get(url)
            time.sleep(3)
            
            # Extraer textos largos que parezcan reseñas
            resenas = self._extraer_textos_pagina(driver, destino, limite)
            
            if not resenas:
                # Estrategia 2: Buscar via Google
                logger.info("TripAdvisorScraper: sin resultados directos, probando Google...")
                url_google = f"https://www.google.com/search?q=site:tripadvisor.es+{destino}+opiniones"
                driver.get(url_google)
                time.sleep(2)
                resenas = self._extraer_textos_pagina(driver, destino, limite)

            logger.info("TripAdvisorScraper: %d reseña(s) extraída(s) para '%s'", len(resenas), destino)

        except Exception as exc:
            logger.warning("TripAdvisorScraper: error para '%s': %s", destino, exc)
        finally:
            try:
                driver.quit()
            except Exception:
                pass

        return resenas

    def _extraer_textos_pagina(self, driver, destino: str, limite: int) -> list[dict[str, Any]]:
        """Extrae textos que parezcan reseñas de la página actual."""
        resenas = []
        try:
            # Buscar TODOS los elementos con texto largo (probable reseña)
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
                    # Filtrar: debe ser texto largo, no repetido, no ser menú/nav
                    if (len(texto) > 50 
                        and len(texto) < 2000
                        and texto not in textos_vistos
                        and not any(kw in texto.lower() for kw in [
                            "cookie", "privacy", "copyright", "sign in", 
                            "iniciar sesión", "registr", "accept"
                        ])):
                        textos_vistos.add(texto)
                        resenas.append({
                            "destino_nombre": destino,
                            "fuente": "tripadvisor",
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
            logger.debug("TripAdvisorScraper: error extrayendo textos: %s", exc)
        
        return resenas

    @staticmethod
    def _detectar_idioma(texto: str) -> str:
        """Detecta idioma con langdetect."""
        try:
            from langdetect import detect
            if len(texto.strip()) < 10:
                return "unknown"
            return detect(texto)
        except Exception:
            return "unknown"
