"""
Jerarquía de excepciones para el módulo de scraping.
"""


class ScrapingError(Exception):
    """Error base para todos los fallos durante el scraping."""
    ...


class RateLimitError(ScrapingError):
    """La fuente ha devuelto un error de límite de peticiones (HTTP 429 o similar)."""
    ...


class ParseError(ScrapingError):
    """Error al analizar (parsear) la respuesta HTML/JSON de una fuente."""
    ...


class RobotsTxtError(ScrapingError):
    """La ruta solicitada está prohibida por el fichero robots.txt de la fuente."""
    ...
