"""
Módulo de scraping y limpieza de datos (Bloque 1).

Exportaciones públicas disponibles mediante import directo:
    - DataCleaner, ValidationError, ExclusionLog (sin dependencias externas)
    - ScrapingError, RateLimitError, ParseError, RobotsTxtError

Exportaciones lazy (se importan al acceder por primera vez):
    - TUISpider, calcular_temporada, crear_spider_es/de/uk (requiere selenium)
    - TripAdvisorScraper (requiere selenium)
    - RedditCollector (requiere selenium)
    - BookingOccupancyScraper (requiere selenium)
    - StatisticsClient (requiere requests)
    - ScraperOrchestrator, ExtractionReport
"""

# Imports directos (sin dependencias pesadas)
from src.scraping.cleaner import DataCleaner, ExclusionLog, ValidationError
from src.scraping.exceptions import ScrapingError, RateLimitError, ParseError, RobotsTxtError


def __getattr__(name: str):
    """Import lazy para componentes que dependen de librerías externas."""
    if name in ("TUISpider", "calcular_temporada", "crear_spider_es", "crear_spider_de", "crear_spider_uk"):
        from src.scraping.tui_spider import TUISpider, calcular_temporada, crear_spider_es, crear_spider_de, crear_spider_uk
        globals().update({
            "TUISpider": TUISpider,
            "calcular_temporada": calcular_temporada,
            "crear_spider_es": crear_spider_es,
            "crear_spider_de": crear_spider_de,
            "crear_spider_uk": crear_spider_uk,
        })
        return globals()[name]
    
    if name == "TripAdvisorScraper":
        from src.scraping.tripadvisor_scraper import TripAdvisorScraper
        globals()["TripAdvisorScraper"] = TripAdvisorScraper
        return TripAdvisorScraper
    
    if name == "RedditCollector":
        from src.scraping.reddit_collector import RedditCollector
        globals()["RedditCollector"] = RedditCollector
        return RedditCollector
    
    if name == "BookingOccupancyScraper":
        from src.scraping.booking_scraper import BookingOccupancyScraper
        globals()["BookingOccupancyScraper"] = BookingOccupancyScraper
        return BookingOccupancyScraper
    
    if name == "StatisticsClient":
        from src.scraping.statistics_client import StatisticsClient
        globals()["StatisticsClient"] = StatisticsClient
        return StatisticsClient
    
    if name in ("ScraperOrchestrator", "ExtractionReport"):
        from src.scraping.orchestrator import ScraperOrchestrator, ExtractionReport
        globals().update({
            "ScraperOrchestrator": ScraperOrchestrator,
            "ExtractionReport": ExtractionReport,
        })
        return globals()[name]
    
    raise AttributeError(f"module 'src.scraping' has no attribute '{name}'")


__all__ = [
    "DataCleaner",
    "ValidationError",
    "ExclusionLog",
    "ScrapingError",
    "RateLimitError",
    "ParseError",
    "RobotsTxtError",
    "TUISpider",
    "calcular_temporada",
    "crear_spider_es",
    "crear_spider_de",
    "crear_spider_uk",
    "TripAdvisorScraper",
    "RedditCollector",
    "BookingOccupancyScraper",
    "StatisticsClient",
    "ScraperOrchestrator",
    "ExtractionReport",
]
