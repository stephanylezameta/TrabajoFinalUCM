"""
Scraper de comentarios de YouTube sobre destinos turísticos.

Busca vídeos de viajes sobre un destino y extrae los comentarios visibles.
Usa Selenium Chrome headless.
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


class YouTubeScraper:
    """Scraper de comentarios de vídeos de YouTube sobre destinos turísticos."""

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
            # Desactivar autoplay de vídeos
            opciones.add_argument("--autoplay-policy=no-user-gesture-required")
            driver = webdriver.Chrome(options=opciones)
            driver.set_page_load_timeout(self.timeout * 2)
            driver.implicitly_wait(5)
            return driver
        except Exception as exc:
            logger.warning("YouTubeScraper: no se pudo crear driver: %s", exc)
            return None

    def extraer_comentarios(self, destino: str, limite: int = 50) -> list[dict[str, Any]]:
        """
        Extrae comentarios de vídeos de YouTube sobre un destino turístico.
        
        Busca vídeos con "{destino} viaje turismo" y extrae comentarios.
        """
        if not SELENIUM_DISPONIBLE:
            logger.warning("YouTubeScraper: Selenium no disponible.")
            return []

        driver = self._crear_driver()
        if not driver:
            return []

        comentarios = []
        try:
            logger.info("YouTubeScraper: buscando vídeos de '%s'...", destino)
            
            # Buscar vídeos sobre el destino
            query = f"{destino} viaje turismo vacaciones"
            url = f"https://www.youtube.com/results?search_query={query}"
            driver.get(url)
            time.sleep(3)

            # Aceptar cookies si aparece
            try:
                accept_btn = driver.find_elements(By.XPATH, 
                    "//*[contains(text(), 'Acepta') or contains(text(), 'Accept') or contains(text(), 'Aceptar')]"
                )
                for btn in accept_btn[:1]:
                    if btn.is_displayed():
                        btn.click()
                        time.sleep(1)
            except Exception:
                pass

            # Obtener URLs de los primeros vídeos
            video_links = self._obtener_links_videos(driver, max_videos=3)
            
            if not video_links:
                logger.info("YouTubeScraper: no se encontraron vídeos para '%s'", destino)
                # Fallback: extraer títulos y descripciones de la búsqueda
                comentarios = self._extraer_de_busqueda(driver, destino, limite)
            else:
                # Navegar a cada vídeo y extraer comentarios
                for video_url in video_links:
                    if len(comentarios) >= limite:
                        break
                    nuevos = self._extraer_comentarios_video(driver, video_url, destino, limite - len(comentarios))
                    comentarios.extend(nuevos)
                    time.sleep(2)

            logger.info("YouTubeScraper: %d comentario(s) para '%s'", len(comentarios), destino)

        except Exception as exc:
            logger.warning("YouTubeScraper: error para '%s': %s", destino, exc)
        finally:
            try:
                driver.quit()
            except Exception:
                pass

        return comentarios

    def _obtener_links_videos(self, driver, max_videos: int = 3) -> list[str]:
        """Obtiene URLs de los primeros vídeos de la búsqueda."""
        links = []
        try:
            video_elements = driver.find_elements(By.CSS_SELECTOR, "a#video-title, ytd-video-renderer a#thumbnail")
            for elem in video_elements[:max_videos * 2]:
                href = elem.get_attribute("href")
                if href and "/watch?v=" in href and href not in links:
                    links.append(href)
                    if len(links) >= max_videos:
                        break
        except Exception as exc:
            logger.debug("YouTubeScraper: error obteniendo links: %s", exc)
        return links

    def _extraer_comentarios_video(self, driver, video_url: str, destino: str, limite: int) -> list[dict[str, Any]]:
        """Navega a un vídeo y extrae sus comentarios."""
        comentarios = []
        try:
            driver.get(video_url)
            time.sleep(3)

            # Scroll para cargar comentarios (YouTube los carga con scroll)
            for _ in range(5):
                driver.execute_script("window.scrollBy(0, 800);")
                time.sleep(1.5)

            # Buscar contenedores de comentarios
            selectores_comentario = [
                "#content-text",           # Selector principal de texto de comentario
                "yt-formatted-string#content-text",
                "span[class*='comment']",
                "ytd-comment-renderer #content-text",
            ]

            elementos = []
            for selector in selectores_comentario:
                elementos = driver.find_elements(By.CSS_SELECTOR, selector)
                if elementos:
                    break

            textos_vistos = set()
            for elem in elementos:
                if len(comentarios) >= limite:
                    break
                try:
                    texto = elem.text.strip()
                    if (len(texto) > 20 and len(texto) < 1500
                        and texto.lower() not in textos_vistos
                        and not any(kw in texto.lower() for kw in [
                            "suscri", "subscribe", "like", "notificación"
                        ])):
                        textos_vistos.add(texto.lower())
                        comentarios.append({
                            "destino_nombre": destino,
                            "fuente": "youtube",
                            "texto_original": texto,
                            "idioma": self._detectar_idioma(texto),
                            "puntuacion": None,
                            "fecha_publicacion": None,
                            "url_fuente": video_url,
                            "fecha_extraccion": datetime.utcnow().isoformat(),
                        })
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("YouTubeScraper: error en video %s: %s", video_url, exc)

        return comentarios

    def _extraer_de_busqueda(self, driver, destino: str, limite: int) -> list[dict[str, Any]]:
        """Extrae títulos y descripciones de vídeos como fallback."""
        resultados = []
        try:
            # Extraer títulos de vídeos (que contienen opiniones sobre el destino)
            titulos = driver.find_elements(By.CSS_SELECTOR, "#video-title, yt-formatted-string.ytd-video-renderer")
            textos_vistos = set()
            for elem in titulos:
                if len(resultados) >= limite:
                    break
                try:
                    texto = elem.text.strip()
                    if (len(texto) > 15 and len(texto) < 200
                        and texto.lower() not in textos_vistos):
                        textos_vistos.add(texto.lower())
                        resultados.append({
                            "destino_nombre": destino,
                            "fuente": "youtube",
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
            logger.debug("YouTubeScraper: error en búsqueda: %s", exc)
        return resultados

    @staticmethod
    def _detectar_idioma(texto: str) -> str:
        try:
            from langdetect import detect
            if len(texto.strip()) < 10:
                return "unknown"
            return detect(texto)
        except Exception:
            return "unknown"
