"""
Scraper de reseñas de TripAdvisor para destinos turísticos.

Extrae reseñas públicas mediante BeautifulSoup + requests, detecta el idioma
con langdetect y devuelve registros normalizados listos para persistir.

Requisitos cubiertos: RF-1.7 (fuentes externas de reseñas)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class TripAdvisorScraper:
    """Scraper de reseñas de TripAdvisor para un destino turístico.

    Realiza búsquedas en TripAdvisor y extrae el texto, puntuación y fecha
    de las reseñas públicas disponibles. Es robusto ante fallos de red:
    nunca lanza excepciones no controladas, devuelve lista vacía si falla.

    Attributes:
        base_url: URL base de TripAdvisor para búsquedas.
        timeout: Tiempo máximo de espera por petición HTTP en segundos.
        headers: Cabeceras HTTP utilizadas en las peticiones.
    """

    BASE_URL = "https://www.tripadvisor.es"

    def __init__(self, timeout: int = 15) -> None:
        """Inicializa el scraper con configuración de timeout y cabeceras.

        Args:
            timeout: Tiempo máximo de espera por petición HTTP en segundos.
        """
        self.timeout = timeout
        self.headers: dict[str, str] = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        }

    def extraer_resenas(
        self, destino: str, limite: int = 50
    ) -> list[dict[str, Any]]:
        """Extrae reseñas de TripAdvisor para un destino dado.

        Busca el destino en TripAdvisor, navega a la página de reseñas
        y extrae texto, puntuación y fecha hasta alcanzar el límite.

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
                - fecha_publicacion (str | None): Fecha de publicación ISO.
                - url_fuente (str): URL de la página de la reseña.
                - fecha_extraccion (str): Marca temporal ISO de extracción.

            Retorna lista vacía si la conexión falla o no se encuentran reseñas.
        """
        resenas: list[dict[str, Any]] = []

        try:
            # Paso 1: Buscar el destino
            url_busqueda = f"{self.BASE_URL}/Search"
            params = {"q": destino, "searchSessionId": "", "sid": ""}

            logger.info(
                "TripAdvisorScraper: buscando reseñas para destino='%s' (limite=%d)",
                destino,
                limite,
            )

            response = requests.get(
                url_busqueda,
                params=params,
                headers=self.headers,
                timeout=self.timeout,
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Paso 2: Extraer reseñas de la página de resultados
            # Buscamos contenedores de reseñas típicos de TripAdvisor
            review_containers = soup.find_all(
                "div", class_=lambda c: c and "review" in c.lower()
            )

            if not review_containers:
                # Intentar selectores alternativos
                review_containers = soup.find_all("div", attrs={"data-reviewid": True})

            for container in review_containers[:limite]:
                resena = self._parsear_resena(container, destino)
                if resena is not None:
                    resenas.append(resena)

                if len(resenas) >= limite:
                    break

            logger.info(
                "TripAdvisorScraper: %d reseña(s) extraída(s) para '%s'",
                len(resenas),
                destino,
            )

        except requests.exceptions.ConnectionError as exc:
            logger.warning(
                "TripAdvisorScraper: error de conexión para destino='%s': %s",
                destino,
                exc,
            )
        except requests.exceptions.Timeout as exc:
            logger.warning(
                "TripAdvisorScraper: timeout para destino='%s': %s",
                destino,
                exc,
            )
        except requests.exceptions.HTTPError as exc:
            logger.warning(
                "TripAdvisorScraper: error HTTP para destino='%s': %s",
                destino,
                exc,
            )
        except Exception as exc:
            logger.warning(
                "TripAdvisorScraper: error inesperado para destino='%s': %s",
                destino,
                exc,
            )

        return resenas

    def _parsear_resena(
        self, container: Any, destino: str
    ) -> dict[str, Any] | None:
        """Extrae los datos de una reseña individual desde un contenedor HTML.

        Args:
            container: Elemento BeautifulSoup con la reseña.
            destino: Nombre del destino para incluir en el registro.

        Returns:
            Diccionario con los campos de la reseña, o None si no se pudo parsear.
        """
        try:
            # Extraer texto de la reseña
            texto_elem = container.find(
                "q", class_=lambda c: c and "review" in str(c).lower()
            )
            if texto_elem is None:
                texto_elem = container.find("p")
            if texto_elem is None:
                texto_elem = container.find("span", class_=lambda c: c and "text" in str(c).lower())

            if texto_elem is None or not texto_elem.get_text(strip=True):
                return None

            texto = texto_elem.get_text(strip=True)

            # Extraer puntuación (típicamente en un span con clase bubble_rating)
            puntuacion = self._extraer_puntuacion(container)

            # Extraer fecha de publicación
            fecha_publicacion = self._extraer_fecha(container)

            # Extraer URL
            link_elem = container.find("a", href=True)
            url_fuente = (
                f"{self.BASE_URL}{link_elem['href']}"
                if link_elem
                else self.BASE_URL
            )

            # Detectar idioma
            idioma = self._detectar_idioma(texto)

            return {
                "destino_nombre": destino,
                "fuente": "tripadvisor",
                "texto_original": texto,
                "idioma": idioma,
                "puntuacion": puntuacion,
                "fecha_publicacion": fecha_publicacion,
                "url_fuente": url_fuente,
                "fecha_extraccion": datetime.utcnow().isoformat(),
            }

        except Exception as exc:
            logger.debug(
                "TripAdvisorScraper: no se pudo parsear reseña: %s", exc
            )
            return None

    def _extraer_puntuacion(self, container: Any) -> float | None:
        """Extrae la puntuación numérica de un contenedor de reseña.

        Args:
            container: Elemento BeautifulSoup con la reseña.

        Returns:
            Puntuación como float (1-5) o None si no se encuentra.
        """
        # Buscar span con clase que contenga 'bubble' o 'rating'
        rating_elem = container.find(
            "span", class_=lambda c: c and ("bubble" in str(c) or "rating" in str(c))
        )
        if rating_elem:
            # Intentar extraer del atributo class (e.g. "bubble_50" = 5.0)
            for clase in rating_elem.get("class", []):
                if "bubble_" in clase:
                    try:
                        valor = int(clase.split("_")[-1])
                        return valor / 10.0
                    except (ValueError, IndexError):
                        pass

        # Buscar en atributo aria-label o title
        for attr in ("aria-label", "title"):
            elem = container.find(attrs={attr: True})
            if elem:
                texto_attr = elem.get(attr, "")
                for parte in texto_attr.split():
                    try:
                        valor = float(parte.replace(",", "."))
                        if 1.0 <= valor <= 5.0:
                            return valor
                    except ValueError:
                        continue

        return None

    def _extraer_fecha(self, container: Any) -> str | None:
        """Extrae la fecha de publicación de una reseña.

        Args:
            container: Elemento BeautifulSoup con la reseña.

        Returns:
            Fecha en formato ISO string o None si no se encuentra.
        """
        # Buscar elementos con clase que contenga 'date'
        fecha_elem = container.find(
            "span", class_=lambda c: c and "date" in str(c).lower()
        )
        if fecha_elem:
            return fecha_elem.get_text(strip=True)

        # Buscar en atributo title o datetime
        elem_time = container.find("time")
        if elem_time and elem_time.get("datetime"):
            return elem_time["datetime"]

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
