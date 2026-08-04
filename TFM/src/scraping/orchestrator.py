"""
Orquestador del pipeline de scraping y extracción de datos.

Coordina la ejecución de todos los scrapers (TUI, TripAdvisor, Reddit,
Booking, fuentes estadísticas), aplica limpieza mediante DataCleaner y
persiste los resultados en el Repositorio. Cada fuente se ejecuta en un
bloque try/except independiente para no abortar el ciclo completo.

Requisitos cubiertos: RF-1.7, RF-1.8 (orquestación y persistencia)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.data.repository import Repositorio
from src.scraping.cleaner import DataCleaner

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclass de reporte
# ---------------------------------------------------------------------------

@dataclass
class ExtractionReport:
    """Reporte de un ciclo completo de extracción de datos.

    Attributes:
        fecha_inicio: Marca temporal del inicio del ciclo.
        fecha_fin: Marca temporal del fin del ciclo.
        fuentes_ejecutadas: Lista de nombres de fuentes procesadas con éxito.
        fuentes_fallidas: Lista de nombres de fuentes que fallaron.
        total_resenas: Número total de reseñas extraídas.
        total_indicadores: Número total de indicadores extraídos.
        total_excluidos: Número de registros excluidos por limpieza.
        errores: Lista de mensajes de error registrados durante el ciclo.
    """

    fecha_inicio: datetime = field(default_factory=datetime.utcnow)
    fecha_fin: datetime | None = None
    fuentes_ejecutadas: list[str] = field(default_factory=list)
    fuentes_fallidas: list[str] = field(default_factory=list)
    total_resenas: int = 0
    total_indicadores: int = 0
    total_excluidos: int = 0
    errores: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Fuentes disponibles
# ---------------------------------------------------------------------------

FUENTES_DISPONIBLES: list[str] = [
    "tripadvisor",
    "reddit",
    "reddit_arctic",
    "booking",
    "eurostat",
    "ine",
    "unwto",
]


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------

class ScraperOrchestrator:
    """Orquestador principal del pipeline de scraping.

    Coordina la ejecución de todos los scrapers disponibles, aplica
    la limpieza de datos con DataCleaner y persiste los resultados
    en el Repositorio central.

    Attributes:
        repositorio: Instancia del Repositorio para persistencia.
        cleaner: Instancia del DataCleaner para limpieza.
        config: Configuración adicional (opciones de scrapers).
        last_report: Último reporte de ejecución generado.
    """

    def __init__(
        self,
        database_url: str,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Inicializa el orquestador con conexión a BD y configuración.

        Args:
            database_url: URL de conexión SQLAlchemy para el Repositorio.
            config: Diccionario de configuración adicional. Claves opcionales:
                - umbral_exclusion (float): Umbral para el DataCleaner.
                - timeout (int): Timeout para peticiones HTTP.
                - selenium_headless (bool): Si usar Selenium headless.
                - regiones_default (list[str]): Regiones por defecto.
        """
        self.config = config or {}
        self.repositorio = Repositorio(database_url)
        self.repositorio.crear_tablas()

        umbral = self.config.get("umbral_exclusion", 0.30)
        self.cleaner = DataCleaner(umbral_exclusion=umbral)

        self.last_report: ExtractionReport | None = None

        logger.info(
            "ScraperOrchestrator inicializado (database_url=%s)", database_url
        )

    def run_cycle(
        self,
        sources: list[str] | None = None,
        regiones: list[str] | None = None,
    ) -> ExtractionReport:
        """Ejecuta un ciclo completo de extracción de datos.

        Para cada fuente seleccionada, instancia el scraper correspondiente,
        extrae datos para las regiones indicadas, aplica limpieza y persiste
        en la base de datos. Cada fuente se ejecuta en un bloque try/except
        independiente para garantizar que un fallo en una fuente no aborta
        el ciclo completo.

        Args:
            sources: Lista de fuentes a ejecutar. Si es None, ejecuta todas.
                     Valores válidos: "tripadvisor", "reddit", "booking",
                     "eurostat", "ine", "unwto".
            regiones: Lista de destinos/regiones a buscar. Si es None, usa
                      las regiones por defecto de la configuración.

        Returns:
            ExtractionReport con los resultados del ciclo.
        """
        report = ExtractionReport(fecha_inicio=datetime.utcnow())

        # Determinar fuentes a ejecutar
        fuentes = sources or FUENTES_DISPONIBLES
        fuentes = [f.lower().strip() for f in fuentes if f.lower().strip() in FUENTES_DISPONIBLES]

        # Determinar regiones
        destinos = regiones or self.config.get(
            "regiones_default", ["Mallorca", "Tenerife", "Cancún"]
        )

        logger.info(
            "ScraperOrchestrator: iniciando ciclo con fuentes=%s, destinos=%s",
            fuentes,
            destinos,
        )

        for fuente in fuentes:
            try:
                logger.info("ScraperOrchestrator: ejecutando fuente '%s'", fuente)

                if fuente == "tripadvisor":
                    self._ejecutar_tripadvisor(destinos, report)
                elif fuente == "reddit":
                    self._ejecutar_reddit(destinos, report)
                elif fuente == "reddit_arctic":
                    self._ejecutar_reddit_arctic(destinos, report)
                elif fuente == "booking":
                    self._ejecutar_booking(destinos, report)
                elif fuente in ("eurostat", "ine", "unwto"):
                    self._ejecutar_estadisticas(fuente, destinos, report)

                report.fuentes_ejecutadas.append(fuente)

            except Exception as exc:
                msg = f"Error en fuente '{fuente}': {exc}"
                logger.error("ScraperOrchestrator: %s", msg, exc_info=True)
                report.fuentes_fallidas.append(fuente)
                report.errores.append(msg)

        report.fecha_fin = datetime.utcnow()
        self.last_report = report

        # Registrar en log de auditoría
        self.repositorio.log_run(self._report_to_dict(report))

        logger.info(
            "ScraperOrchestrator: ciclo completado. "
            "Fuentes OK=%d, fallidas=%d, reseñas=%d, indicadores=%d",
            len(report.fuentes_ejecutadas),
            len(report.fuentes_fallidas),
            report.total_resenas,
            report.total_indicadores,
        )

        return report

    def get_last_run_status(self) -> dict[str, Any]:
        """Retorna el estado del último ciclo de extracción ejecutado.

        Returns:
            Diccionario con información del último ciclo:
                - fecha_inicio (str): ISO timestamp del inicio.
                - fecha_fin (str | None): ISO timestamp del fin.
                - fuentes_ok (list[str]): Fuentes ejecutadas con éxito.
                - fuentes_error (list[str]): Fuentes que fallaron.
                - total_resenas (int): Reseñas extraídas.
                - total_indicadores (int): Indicadores extraídos.
                - errores (list[str]): Mensajes de error.

            Retorna dict vacío si no se ha ejecutado ningún ciclo.
        """
        if self.last_report is None:
            return {}

        return self._report_to_dict(self.last_report)

    # ------------------------------------------------------------------
    # Métodos privados: ejecución de scrapers individuales
    # ------------------------------------------------------------------

    def _ejecutar_tripadvisor(
        self, destinos: list[str], report: ExtractionReport
    ) -> None:
        """Ejecuta el scraper de TripAdvisor para los destinos dados."""
        from src.scraping.tripadvisor_scraper import TripAdvisorScraper

        scraper = TripAdvisorScraper(
            timeout=self.config.get("timeout", 15)
        )

        for destino in destinos:
            resenas = scraper.extraer_resenas(destino, limite=50)
            if resenas:
                self._persistir_resenas(resenas, report)

    def _ejecutar_reddit(
        self, destinos: list[str], report: ExtractionReport
    ) -> None:
        """Ejecuta el recolector de Reddit para los destinos dados."""
        from src.scraping.reddit_collector import RedditCollector

        collector = RedditCollector()

        for destino in destinos:
            posts = collector.collect_posts(destino, limite=100)
            if posts:
                self._persistir_resenas(posts, report)

    def _ejecutar_reddit_arctic(
        self, destinos: list[str], report: ExtractionReport
    ) -> None:
        """Ejecuta el recolector de Reddit basado en Arctic Shift."""
        from src.scraping.reddit_collector_arctic_shift import (
            RedditCollectorArcticShift,
        )

        collector = RedditCollectorArcticShift()

        for destino in destinos:
            posts = collector.collect_posts(destino, limite=100)
            if posts:
                self._persistir_resenas(posts, report)

    def _ejecutar_booking(
        self, destinos: list[str], report: ExtractionReport
    ) -> None:
        """Ejecuta el scraper de Booking para los destinos dados."""
        from src.scraping.booking_scraper import BookingOccupancyScraper

        headless = self.config.get("selenium_headless", True)
        scraper = BookingOccupancyScraper(headless=headless)

        for destino in destinos:
            indicadores = scraper.extraer_ocupacion(destino)
            if indicadores:
                self._persistir_indicadores(indicadores, report)

    def _ejecutar_estadisticas(
        self, fuente: str, destinos: list[str], report: ExtractionReport
    ) -> None:
        """Ejecuta el cliente de estadísticas para los destinos dados."""
        from src.scraping.statistics_client import StatisticsClient

        client = StatisticsClient(fuente=fuente, timeout=self.config.get("timeout", 30))
        year = datetime.utcnow().year

        for destino in destinos:
            # Obtener ocupación
            indicadores = client.fetch_occupancy(destino, year)
            if indicadores:
                self._persistir_indicadores(indicadores, report)

            # Obtener llegadas
            llegadas = client.fetch_arrivals(destino, year)
            if llegadas:
                self._persistir_indicadores(llegadas, report)

    # ------------------------------------------------------------------
    # Métodos privados: persistencia
    # ------------------------------------------------------------------

    def _persistir_resenas(
        self, resenas_raw: list[dict[str, Any]], report: ExtractionReport
    ) -> None:
        """Limpia y persiste reseñas en el Repositorio.

        Args:
            resenas_raw: Lista de reseñas en formato diccionario.
            report: Reporte donde acumular contadores.
        """
        from src.data.models import Resena

        for resena_dict in resenas_raw:
            try:
                kwargs = dict(
                    destino_nombre=resena_dict.get("destino_nombre", ""),
                    fuente=resena_dict.get("fuente", ""),
                    texto_original=resena_dict.get("texto_original"),
                    idioma=resena_dict.get("idioma", "unknown"),
                    puntuacion=resena_dict.get("puntuacion"),
                    fecha_publicacion=self._parse_datetime(
                        resena_dict.get("fecha_publicacion")
                    ),
                    url_fuente=resena_dict.get("url_fuente"),
                    fecha_extraccion=datetime.utcnow(),
                )
                if resena_dict.get("id_resena"):
                    kwargs["id_resena"] = resena_dict["id_resena"]

                resena = Resena(**kwargs)
                self.repositorio.upsert_resena(resena)
                report.total_resenas += 1

            except Exception as exc:
                logger.warning(
                    "ScraperOrchestrator: error al persistir reseña: %s", exc
                )

    def _persistir_indicadores(
        self, indicadores_raw: list[dict[str, Any]], report: ExtractionReport
    ) -> None:
        """Persiste indicadores de destino en el Repositorio.

        Args:
            indicadores_raw: Lista de indicadores en formato diccionario.
            report: Reporte donde acumular contadores.
        """
        from src.data.models import IndicadorDestino

        for ind_dict in indicadores_raw:
            try:
                indicador = IndicadorDestino(
                    destino_nombre=ind_dict.get("destino_nombre", ""),
                    fuente=ind_dict.get("fuente", ""),
                    tipo_indicador=ind_dict.get("tipo_indicador", ""),
                    valor=float(ind_dict.get("valor", 0)),
                    anio=int(ind_dict.get("anio", datetime.utcnow().year)),
                    mes=ind_dict.get("mes"),
                    fecha_extraccion=datetime.utcnow(),
                )
                self.repositorio.upsert_indicador(indicador)
                report.total_indicadores += 1

            except Exception as exc:
                logger.warning(
                    "ScraperOrchestrator: error al persistir indicador: %s", exc
                )

    # ------------------------------------------------------------------
    # Métodos privados: utilidades
    # ------------------------------------------------------------------

    @staticmethod
    def _report_to_dict(report: ExtractionReport) -> dict[str, Any]:
        """Convierte un ExtractionReport a diccionario serializable."""
        return {
            "fecha_inicio": report.fecha_inicio.isoformat(),
            "fecha_fin": report.fecha_fin.isoformat() if report.fecha_fin else None,
            "fuentes_ok": report.fuentes_ejecutadas,
            "fuentes_error": report.fuentes_fallidas,
            "total_resenas": report.total_resenas,
            "total_indicadores": report.total_indicadores,
            "total_excluidos": report.total_excluidos,
            "errores": report.errores,
        }

    @staticmethod
    def _parse_datetime(valor: Any) -> datetime | None:
        """Intenta convertir un valor a datetime.

        Args:
            valor: Cadena ISO, timestamp o None.

        Returns:
            Instancia datetime o None si la conversión falla.
        """
        if valor is None:
            return None
        if isinstance(valor, datetime):
            return valor
        if isinstance(valor, str):
            try:
                return datetime.fromisoformat(valor)
            except (ValueError, TypeError):
                pass
        return None
