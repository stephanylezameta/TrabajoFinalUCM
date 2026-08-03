"""
Recolector de posts de Reddit sobre destinos turísticos con Selenium.

Usa un enfoque simple y robusto: navega a old.reddit.com (más fácil de parsear
que la interfaz nueva) y extrae títulos y textos de posts.
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
    SELENIUM_DISPONIBLE = True
except ImportError:
    SELENIUM_DISPONIBLE = False


class RedditCollector:
    """Recolector de posts de Reddit sobre destinos turísticos."""

    subreddits = ["travel", "solotravel", "backpacking", "Flights", "TravelHacks", "vacation"]

    def __init__(self, subreddits=None, timeout: int = 15, headless: bool = True):
        if subreddits is not None:
            self.subreddits = subreddits
        self.timeout = timeout
        self.headless = headless

    def _crear_driver(self):
        """Crea Chrome headless."""
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
            opciones.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            )
            driver = webdriver.Chrome(options=opciones)
            driver.set_page_load_timeout(self.timeout)
            driver.implicitly_wait(5)
            return driver
        except Exception as exc:
            logger.warning("RedditCollector: no se pudo crear driver: %s", exc)
            return None

    def collect_posts(self, destino: str, limite: int = 100) -> list[dict[str, Any]]:
        """Recolecta posts de Reddit sobre un destino usando old.reddit.com.
        
        old.reddit.com tiene HTML estático más fácil de parsear que la interfaz nueva.
        """
        if not SELENIUM_DISPONIBLE:
            logger.warning("RedditCollector: Selenium no disponible.")
            return []

        driver = self._crear_driver()
        if not driver:
            return []

        posts = []
        try:
            # Usar old.reddit.com que es HTML puro (no SPA)
            query = f"{destino} travel"
            url = f"https://old.reddit.com/search?q={query}&sort=relevance&t=year"
            
            logger.info("RedditCollector: buscando '%s' en old.reddit.com...", destino)
            driver.get(url)
            time.sleep(3)

            # En old.reddit.com los posts están en <div class="search-result">
            # o en <div class="search-result-link">
            elementos = driver.find_elements(By.CSS_SELECTOR, 
                ".search-result, .search-result-link, .thing"
            )
            
            if not elementos:
                # Fallback: buscar cualquier link con título largo
                elementos = driver.find_elements(By.CSS_SELECTOR, "a.search-title, a.title")

            for elem in elementos[:limite]:
                try:
                    post = self._parsear_post(elem, destino, driver.current_url)
                    if post:
                        posts.append(post)
                except Exception:
                    continue

            # Si old.reddit no dio resultados, intentar con la búsqueda normal
            if not posts:
                logger.info("RedditCollector: probando reddit.com nuevo...")
                url_nuevo = f"https://www.reddit.com/search/?q={query}&type=link"
                driver.get(url_nuevo)
                time.sleep(4)
                
                # Extraer textos largos de la página
                textos = driver.find_elements(By.XPATH,
                    "//*[string-length(normalize-space(text())) > 30 and "
                    "not(self::script) and not(self::style)]"
                )
                
                vistos = set()
                for elem in textos[:limite * 3]:
                    try:
                        texto = elem.text.strip()
                        if (30 < len(texto) < 500 
                            and texto not in vistos
                            and not any(kw in texto.lower() for kw in [
                                "cookie", "privacy", "sign", "log in", "reddit inc"
                            ])):
                            vistos.add(texto)
                            posts.append({
                                "destino_nombre": destino,
                                "fuente": "reddit",
                                "texto_original": texto,
                                "idioma": self._detectar_idioma(texto),
                                "puntuacion": None,
                                "fecha_publicacion": None,
                                "url_fuente": driver.current_url,
                                "fecha_extraccion": datetime.utcnow().isoformat(),
                            })
                            if len(posts) >= limite:
                                break
                    except Exception:
                        continue

            logger.info("RedditCollector: %d post(s) para '%s'", len(posts), destino)

        except Exception as exc:
            logger.warning("RedditCollector: error para '%s': %s", destino, exc)
        finally:
            try:
                driver.quit()
            except Exception:
                pass

        return posts

    def _parsear_post(self, elem, destino: str, url_pagina: str) -> dict[str, Any] | None:
        """Parsea un elemento de post de old.reddit.com."""
        try:
            # Extraer título
            titulo_elem = elem.find_elements(By.CSS_SELECTOR, "a.search-title, a.title, h3 a")
            titulo = ""
            url_post = url_pagina
            for t in titulo_elem:
                texto = t.text.strip()
                if len(texto) > 10:
                    titulo = texto
                    url_post = t.get_attribute("href") or url_pagina
                    break
            
            if not titulo:
                # Intentar texto directo del elemento
                titulo = elem.text.strip()[:200]
            
            if len(titulo) < 10:
                return None

            # Extraer snippet/preview si existe
            snippet_elems = elem.find_elements(By.CSS_SELECTOR, 
                ".search-result-body, .md, p, .search-expando"
            )
            snippet = ""
            for s in snippet_elems:
                texto_s = s.text.strip()
                if len(texto_s) > 20:
                    snippet = texto_s[:500]
                    break

            texto_final = titulo
            if snippet:
                texto_final = f"{titulo}\n\n{snippet}"

            return {
                "destino_nombre": destino,
                "fuente": "reddit",
                "texto_original": texto_final,
                "idioma": self._detectar_idioma(texto_final),
                "puntuacion": None,
                "fecha_publicacion": None,
                "url_fuente": url_post,
                "fecha_extraccion": datetime.utcnow().isoformat(),
            }
        except Exception:
            return None

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
