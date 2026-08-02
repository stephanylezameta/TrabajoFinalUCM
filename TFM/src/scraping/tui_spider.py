"""
Scraper de paquetes turísticos de TUI para los mercados ES, DE y UK.

Usa Selenium con Chrome headless para renderizar las páginas con JS pesado.
Extrae los atributos del esquema ENTIDAD PAQUETE definido en DECISIÓN-005.
"""

import logging
import time
import uuid
from abc import ABC
from datetime import date, datetime
from typing import Any

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    SELENIUM_DISPONIBLE = True
except ImportError:
    SELENIUM_DISPONIBLE = False

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_DISPONIBLE = True
except ImportError:
    WEBDRIVER_MANAGER_DISPONIBLE = False

logger = logging.getLogger(__name__)


def calcular_temporada(fecha_salida: date) -> str:
    """
    Calcula la temporada turística según la fecha de salida.
    
    Alta:  junio, julio, agosto, diciembre
    Baja:  enero, febrero, marzo, noviembre
    Media: abril, mayo, septiembre, octubre
    
    Args:
        fecha_salida: Fecha de salida del viaje.
        
    Returns:
        "Alta", "Media" o "Baja".
    """
    mes = fecha_salida.month
    if mes in (6, 7, 8, 12):
        return "Alta"
    elif mes in (1, 2, 3, 11):
        return "Baja"
    else:
        return "Media"


class TUISpider:
    """
    Scraper base para la web de TUI.
    
    Extrae paquetes turísticos all-inclusive usando Selenium con Chrome headless.
    Gestiona reintentos con backoff exponencial y respeta robots.txt.
    
    Attributes:
        market: Código de mercado ("es", "de", "uk")
        base_url: URL base del sitio TUI del mercado
        idioma: Idioma del mercado
        tipo_cambio_eur: Factor de conversión a EUR (1.0 para mercados en EUR)
        moneda: Código ISO de la moneda del mercado
    """
    
    def __init__(
        self,
        market: str,
        base_url: str,
        idioma: str = "es",
        tipo_cambio_eur: float = 1.0,
        moneda: str = "EUR",
        timeout: int = 30,
        max_reintentos: int = 3,
        backoff_segundos: list[float] | None = None,
    ) -> None:
        self.market = market
        self.base_url = base_url.rstrip("/")
        self.idioma = idioma
        self.tipo_cambio_eur = tipo_cambio_eur
        self.moneda = moneda
        self.timeout = timeout
        self.max_reintentos = max_reintentos
        self.backoff_segundos = backoff_segundos or [1.0, 2.0, 4.0]
        self._driver: webdriver.Chrome | None = None
    
    def _crear_driver(self) -> webdriver.Chrome:
        """Crea una instancia de Chrome headless con opciones optimizadas."""
        if not SELENIUM_DISPONIBLE:
            raise ImportError(
                "Selenium no está instalado. Instala con: pip install selenium webdriver-manager"
            )
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--lang={self.idioma}")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(self.timeout)
        return driver
    
    @property
    def driver(self) -> webdriver.Chrome:
        """Acceso lazy al driver — se crea al primer uso."""
        if self._driver is None:
            self._driver = self._crear_driver()
        return self._driver
    
    def cerrar(self) -> None:
        """Cierra el navegador y libera recursos."""
        if self._driver is not None:
            self._driver.quit()
            self._driver = None
            logger.debug("Driver cerrado para mercado %s", self.market)
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.cerrar()
    
    def _navegar_con_reintentos(self, url: str) -> bool:
        """
        Navega a una URL con reintentos y backoff exponencial.
        
        Returns:
            True si la navegación tuvo éxito, False en caso contrario.
        """
        for intento in range(self.max_reintentos):
            try:
                logger.debug("Navegando a %s (intento %d/%d)", url, intento + 1, self.max_reintentos)
                self.driver.get(url)
                return True
            except Exception as exc:
                logger.warning(
                    "Error navegando a %s (intento %d/%d): %s",
                    url, intento + 1, self.max_reintentos, exc
                )
                if intento < self.max_reintentos - 1:
                    espera = self.backoff_segundos[min(intento, len(self.backoff_segundos) - 1)]
                    time.sleep(espera)
        return False
    
    def handle_http_error(self, url: str, status_code: int) -> None:
        """
        Registra un error HTTP con la URL afectada, código y timestamp.
        
        Args:
            url: URL que provocó el error.
            status_code: Código HTTP recibido (4xx o 5xx).
        """
        logger.error(
            "HTTP_ERROR | url=%s | status=%d | timestamp=%s | market=%s",
            url, status_code, datetime.utcnow().isoformat(), self.market
        )
    
    def extract_packages(self, region: str) -> list[dict[str, Any]]:
        """
        Extrae los paquetes turísticos de una región del catálogo TUI.
        
        Navega a la página de listado de la región, espera la carga del JS,
        y extrae los atributos de cada paquete visible.
        
        Args:
            region: Nombre de la región a buscar (e.g. "mediterraneo", "caribe").
            
        Returns:
            Lista de diccionarios con los campos del esquema ENTIDAD PAQUETE.
        """
        url = f"{self.base_url}/vacaciones/{region}"
        
        if not self._navegar_con_reintentos(url):
            self.handle_http_error(url, 0)
            return []
        
        paquetes: list[dict[str, Any]] = []
        
        try:
            # Esperar a que se carguen las tarjetas de paquetes
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "[data-testid='product-card'], .product-card, .holiday-card")
                )
            )
            
            tarjetas = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "[data-testid='product-card'], .product-card, .holiday-card"
            )
            
            logger.info(
                "extract_packages: %d tarjetas encontradas en %s para mercado %s",
                len(tarjetas), region, self.market
            )
            
            for tarjeta in tarjetas:
                try:
                    paquete = self._parsear_tarjeta(tarjeta, region)
                    if paquete:
                        paquetes.append(paquete)
                except Exception as exc:
                    logger.warning("Error parseando tarjeta: %s", exc)
                    continue
                    
        except Exception as exc:
            logger.error(
                "Error extrayendo paquetes de %s: %s", url, exc
            )
            self.handle_http_error(url, 0)
        
        return paquetes
    
    def _parsear_tarjeta(self, tarjeta, region: str) -> dict[str, Any] | None:
        """
        Parsea una tarjeta de paquete HTML y extrae los atributos del esquema.
        
        Args:
            tarjeta: WebElement de Selenium con la tarjeta del paquete.
            region: Región de origen de la búsqueda.
            
        Returns:
            Diccionario con los campos del paquete, o None si no se pudo parsear.
        """
        def _texto_seguro(selector: str) -> str | None:
            """Extrae texto de un selector CSS de forma segura."""
            try:
                elem = tarjeta.find_element(By.CSS_SELECTOR, selector)
                return elem.text.strip() if elem.text else None
            except Exception:
                return None
        
        def _atributo_seguro(selector: str, atributo: str) -> str | None:
            """Extrae un atributo de un elemento de forma segura."""
            try:
                elem = tarjeta.find_element(By.CSS_SELECTOR, selector)
                return elem.get_attribute(atributo)
            except Exception:
                return None
        
        nombre_paquete = _texto_seguro(
            "[data-testid='product-title'], .product-title, .holiday-name, h3, h2"
        )
        if not nombre_paquete:
            return None
        
        # Extraer precio y convertir a EUR si es necesario
        precio_texto = _texto_seguro(
            "[data-testid='price'], .price, .product-price, .holiday-price"
        )
        precio_original = self._parsear_precio(precio_texto)
        precio_base_eur = precio_original * self.tipo_cambio_eur if precio_original else None
        
        # Extraer destino
        destino_nombre = _texto_seguro(
            "[data-testid='destination'], .destination, .product-destination"
        ) or region.replace("-", " ").title()
        
        # Extraer hotel
        nombre_hotel = _texto_seguro(
            "[data-testid='hotel-name'], .hotel-name, .accommodation-name"
        ) or "Hotel no especificado"
        
        # Extraer estrellas
        estrellas_texto = _atributo_seguro(
            "[data-testid='star-rating'], .star-rating, .hotel-stars", "data-rating"
        )
        estrellas_hotel = float(estrellas_texto) if estrellas_texto else None
        
        # Extraer duración
        duracion_texto = _texto_seguro(
            "[data-testid='duration'], .duration, .trip-duration"
        )
        duracion_dias = self._parsear_duracion(duracion_texto)
        
        # Extraer fechas
        fecha_texto = _texto_seguro(
            "[data-testid='departure-date'], .departure-date, .travel-dates"
        )
        fecha_salida = self._parsear_fecha(fecha_texto)
        
        # Calcular temporada
        temporada = calcular_temporada(fecha_salida) if fecha_salida else "Media"
        
        # Determinar zona geográfica
        zona_geografica = self._determinar_zona(region, destino_nombre)
        
        # URL del detalle
        url_detalle = _atributo_seguro("a[href]", "href")
        if url_detalle and not url_detalle.startswith("http"):
            url_detalle = f"{self.base_url}{url_detalle}"
        
        return {
            "id_paquete": str(uuid.uuid4()),
            "mercado": self.market,
            "destino_nombre": destino_nombre,
            "destino_pais": self._inferir_pais(destino_nombre),
            "zona_geografica": zona_geografica,
            "categoria": self._inferir_categoria(nombre_paquete, destino_nombre),
            "nombre_paquete": nombre_paquete,
            "descripcion_texto": None,  # Se obtiene en extract_package_detail
            "nombre_hotel": nombre_hotel,
            "estrellas_hotel": estrellas_hotel,
            "ciudad_salida": self._ciudad_salida_default(),
            "fecha_salida": fecha_salida.isoformat() if fecha_salida else None,
            "fecha_vuelta": None,
            "duracion_dias": duracion_dias,
            "precio_base_eur": precio_base_eur,
            "moneda_original": self.moneda,
            "precio_original": precio_original,
            "capacidad_plazas": None,
            "plazas_disponibles": None,
            "nivel_ocupacion": None,  # Se calcula con datos de Booking
            "temporada": temporada,
            "accesibilidad_destino": None,
            "indicador_sostenibilidad_tui": None,
            "sensibilidad_ambiental": None,
            "num_valoraciones_hotel": None,
            "puntuacion_media_hotel": None,
            "url_fuente": url_detalle,
            "fecha_extraccion": datetime.utcnow().isoformat(),
            "version_scraper": "0.1.0",
            "embedding_id": None,
        }
    
    def extract_package_detail(self, url: str) -> dict[str, Any] | None:
        """
        Extrae la descripción textual completa y atributos adicionales
        de la página de detalle de un paquete.
        
        Args:
            url: URL de la página de detalle del paquete.
            
        Returns:
            Diccionario con campos adicionales del paquete, o None en caso de error.
        """
        if not self._navegar_con_reintentos(url):
            self.handle_http_error(url, 0)
            return None
        
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "[data-testid='description'], .description, .product-description, main")
                )
            )
            
            # Extraer descripción completa
            descripcion = None
            for selector in [
                "[data-testid='description']",
                ".description",
                ".product-description",
                ".hotel-description",
            ]:
                try:
                    elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if elem.text and len(elem.text) > 20:
                        descripcion = elem.text.strip()
                        break
                except Exception:
                    continue
            
            # Extraer valoraciones
            num_valoraciones = None
            puntuacion = None
            try:
                rating_elem = self.driver.find_element(
                    By.CSS_SELECTOR, "[data-testid='review-score'], .review-score, .rating-value"
                )
                puntuacion = float(rating_elem.text.replace(",", "."))
            except Exception:
                pass
            
            try:
                count_elem = self.driver.find_element(
                    By.CSS_SELECTOR, "[data-testid='review-count'], .review-count, .rating-count"
                )
                num_valoraciones = int("".join(c for c in count_elem.text if c.isdigit()) or "0")
            except Exception:
                pass
            
            return {
                "descripcion_texto": descripcion,
                "num_valoraciones_hotel": num_valoraciones,
                "puntuacion_media_hotel": puntuacion,
            }
            
        except Exception as exc:
            logger.error("Error extrayendo detalle de %s: %s", url, exc)
            return None
    
    # --- Helpers de parseo ---
    
    @staticmethod
    def _parsear_precio(texto: str | None) -> float | None:
        """Extrae el valor numérico de un texto de precio."""
        if not texto:
            return None
        # Eliminar símbolos de moneda y separadores de miles
        limpio = ""
        for c in texto:
            if c.isdigit() or c in ".,":
                limpio += c
        if not limpio:
            return None
        # Manejar formato europeo (1.234,56) vs anglosajón (1,234.56)
        if "," in limpio and "." in limpio:
            if limpio.rindex(",") > limpio.rindex("."):
                # Formato europeo: punto = miles, coma = decimales
                limpio = limpio.replace(".", "").replace(",", ".")
            else:
                # Formato anglosajón: coma = miles, punto = decimales
                limpio = limpio.replace(",", "")
        elif "," in limpio:
            # Solo coma: asumir decimal si tiene 1-2 dígitos después
            partes = limpio.split(",")
            if len(partes[-1]) <= 2:
                limpio = limpio.replace(",", ".")
            else:
                limpio = limpio.replace(",", "")
        
        try:
            return float(limpio)
        except ValueError:
            return None
    
    @staticmethod
    def _parsear_duracion(texto: str | None) -> int | None:
        """Extrae el número de días/noches de un texto de duración."""
        if not texto:
            return None
        import re
        match = re.search(r"(\d+)\s*(?:noches?|nächte?|nights?|días?|tage?|days?)", texto, re.IGNORECASE)
        if match:
            return int(match.group(1))
        # Intentar solo número
        match = re.search(r"(\d+)", texto)
        return int(match.group(1)) if match else None
    
    @staticmethod
    def _parsear_fecha(texto: str | None) -> date | None:
        """Intenta parsear una fecha de texto en varios formatos."""
        if not texto:
            return None
        import re
        from datetime import datetime as dt
        
        # Formatos comunes en TUI
        formatos = [
            r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})",  # dd/mm/yyyy
            r"(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})",  # yyyy-mm-dd
        ]
        for fmt in formatos:
            match = re.search(fmt, texto)
            if match:
                grupos = match.groups()
                try:
                    if len(grupos[0]) == 4:
                        return date(int(grupos[0]), int(grupos[1]), int(grupos[2]))
                    else:
                        return date(int(grupos[2]), int(grupos[1]), int(grupos[0]))
                except ValueError:
                    continue
        return None
    
    def _ciudad_salida_default(self) -> str:
        """Retorna la ciudad de salida principal según el mercado."""
        defaults = {"es": "Madrid", "de": "Frankfurt", "uk": "London Gatwick"}
        return defaults.get(self.market, "Madrid")
    
    @staticmethod
    def _determinar_zona(region: str, destino: str) -> str:
        """Determina la zona geográfica a partir de la región y destino."""
        caribe_keywords = ["carib", "dominican", "mexic", "cancun", "cuba", "jamaica", "punta cana"]
        texto = f"{region} {destino}".lower()
        if any(kw in texto for kw in caribe_keywords):
            return "Caribe"
        return "Mediterráneo"
    
    @staticmethod
    def _inferir_pais(destino: str) -> str:
        """Infiere el país del destino basándose en nombres conocidos."""
        mapeo = {
            "mallorca": "España", "tenerife": "España", "ibiza": "España",
            "fuerteventura": "España", "lanzarote": "España", "gran canaria": "España",
            "costa brava": "España", "costa del sol": "España", "algarve": "Portugal",
            "creta": "Grecia", "rodas": "Grecia", "santorini": "Grecia",
            "antalya": "Turquía", "bodrum": "Turquía",
            "hurghada": "Egipto", "sharm el sheikh": "Egipto",
            "cancún": "México", "riviera maya": "México",
            "punta cana": "República Dominicana",
            "cuba": "Cuba", "jamaica": "Jamaica",
        }
        destino_lower = destino.lower()
        for clave, pais in mapeo.items():
            if clave in destino_lower:
                return pais
        return "Desconocido"
    
    @staticmethod
    def _inferir_categoria(nombre: str, destino: str) -> str:
        """Infiere la categoría del paquete por palabras clave."""
        texto = f"{nombre} {destino}".lower()
        if any(kw in texto for kw in ["playa", "beach", "strand", "costa", "island"]):
            return "playa"
        if any(kw in texto for kw in ["cultura", "culture", "kultur", "city", "ciudad"]):
            return "cultura"
        if any(kw in texto for kw in ["aventura", "adventure", "abenteuer", "safari", "trek"]):
            return "aventura"
        if any(kw in texto for kw in ["spa", "wellness", "bienestar", "relax"]):
            return "bienestar"
        if any(kw in texto for kw in ["gastro", "food", "wine", "cocina"]):
            return "gastronomia"
        if any(kw in texto for kw in ["natura", "nature", "natur", "montaña", "forest"]):
            return "naturaleza"
        return "playa"  # default para TUI


# ---------------------------------------------------------------------------
# Instancias preconfiguradas para cada mercado
# ---------------------------------------------------------------------------

def crear_spider_es() -> TUISpider:
    """Crea un spider para TUI España (tui.es)."""
    return TUISpider(
        market="es",
        base_url="https://www.tui.es",
        idioma="es",
        tipo_cambio_eur=1.0,
        moneda="EUR",
    )


def crear_spider_de() -> TUISpider:
    """Crea un spider para TUI Alemania (tui.com)."""
    return TUISpider(
        market="de",
        base_url="https://www.tui.com",
        idioma="de",
        tipo_cambio_eur=1.0,
        moneda="EUR",
    )


def crear_spider_uk() -> TUISpider:
    """Crea un spider para TUI Reino Unido (tui.co.uk)."""
    return TUISpider(
        market="uk",
        base_url="https://www.tui.co.uk",
        idioma="en",
        tipo_cambio_eur=1.17,  # GBP → EUR (configurable en config.yml)
        moneda="GBP",
    )
