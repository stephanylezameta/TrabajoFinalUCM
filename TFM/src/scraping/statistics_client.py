"""
Cliente para fuentes estadísticas turísticas públicas (Eurostat, INE, UNWTO).

Proporciona acceso uniforme a indicadores de ocupación y llegadas de turistas
desde APIs REST públicas, con manejo robusto de errores de conexión.

Requisitos cubiertos: RF-1.7 (fuentes estadísticas externas)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import requests

logger = logging.getLogger(__name__)

# URLs base por defecto de las fuentes estadísticas
_FUENTES_CONFIG: dict[str, dict[str, str]] = {
    "eurostat": {
        "base_url": "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0",
        "dataset_tourism": "tour_occ_nim",
    },
    "ine": {
        "base_url": "https://servicios.ine.es/wstempus/js/ES",
        "operation_id": "EOH",
    },
    "unwto": {
        "base_url": "https://www.unwto.org/tourism-statistics/key-tourism-statistics",
    },
}

# Fuentes soportadas
FUENTES_VALIDAS: list[str] = ["eurostat", "ine", "unwto"]


class StatisticsClient:
    """Cliente unificado para fuentes estadísticas turísticas.

    Proporciona métodos para obtener indicadores de ocupación hotelera
    y llegadas de turistas desde Eurostat, INE o UNWTO. Es robusto
    ante fallos de conexión: retorna lista vacía si la API no responde.

    Attributes:
        fuente: Nombre de la fuente estadística ("eurostat", "ine", "unwto").
        base_url: URL base de la API de la fuente.
        timeout: Tiempo máximo de espera por petición HTTP.
    """

    def __init__(
        self,
        fuente: str,
        base_url: str | None = None,
        timeout: int = 30,
    ) -> None:
        """Inicializa el cliente para una fuente estadística.

        Args:
            fuente: Nombre de la fuente: "eurostat", "ine" o "unwto".
            base_url: URL base personalizada. Si no se pasa, se usa la
                      URL por defecto de la fuente.
            timeout: Tiempo máximo de espera por petición HTTP en segundos.

        Raises:
            ValueError: Si la fuente no es una de las válidas.
        """
        fuente_lower = fuente.lower().strip()
        if fuente_lower not in FUENTES_VALIDAS:
            raise ValueError(
                f"Fuente '{fuente}' no soportada. "
                f"Fuentes válidas: {FUENTES_VALIDAS}"
            )

        self.fuente = fuente_lower
        self.timeout = timeout

        config = _FUENTES_CONFIG.get(self.fuente, {})
        self.base_url = base_url or config.get("base_url", "")
        self._config = config

        logger.info(
            "StatisticsClient inicializado para fuente='%s' (base_url=%s)",
            self.fuente,
            self.base_url,
        )

    def fetch_occupancy(
        self,
        destino: str,
        year: int,
        month: int | None = None,
    ) -> list[dict[str, Any]]:
        """Obtiene indicadores de ocupación hotelera de la fuente configurada.

        Args:
            destino: Nombre del destino turístico (e.g. "España", "Mallorca").
            year: Año del indicador.
            month: Mes del indicador (1-12). Si es None, retorna datos anuales.

        Returns:
            Lista de diccionarios con los campos:
                - destino_nombre (str): Nombre del destino.
                - fuente (str): Nombre de la fuente estadística.
                - tipo_indicador (str): "nivel_ocupacion".
                - valor (float): Nivel de ocupación en [0, 1].
                - anio (int): Año del indicador.
                - mes (int | None): Mes del indicador.
                - fecha_extraccion (str): Marca temporal ISO.

            Retorna lista vacía si la API no responde o hay error de conexión.
        """
        logger.info(
            "StatisticsClient[%s]: solicitando ocupación para '%s' (%d/%s)",
            self.fuente,
            destino,
            year,
            month or "anual",
        )

        try:
            if self.fuente == "eurostat":
                return self._fetch_occupancy_eurostat(destino, year, month)
            elif self.fuente == "ine":
                return self._fetch_occupancy_ine(destino, year, month)
            elif self.fuente == "unwto":
                return self._fetch_occupancy_unwto(destino, year, month)
            else:
                return []

        except requests.exceptions.ConnectionError as exc:
            logger.warning(
                "StatisticsClient[%s]: error de conexión: %s",
                self.fuente,
                exc,
            )
        except requests.exceptions.Timeout as exc:
            logger.warning(
                "StatisticsClient[%s]: timeout: %s", self.fuente, exc
            )
        except requests.exceptions.HTTPError as exc:
            logger.warning(
                "StatisticsClient[%s]: error HTTP: %s", self.fuente, exc
            )
        except Exception as exc:
            logger.warning(
                "StatisticsClient[%s]: error inesperado en fetch_occupancy: %s",
                self.fuente,
                exc,
            )

        return []

    def fetch_arrivals(
        self,
        country: str,
        year: int,
    ) -> list[dict[str, Any]]:
        """Obtiene indicadores de llegadas de turistas de la fuente configurada.

        Args:
            country: Nombre del país (e.g. "España", "Spain").
            year: Año del indicador.

        Returns:
            Lista de diccionarios con los campos:
                - destino_nombre (str): Nombre del país.
                - fuente (str): Nombre de la fuente estadística.
                - tipo_indicador (str): "llegadas_turistas".
                - valor (float): Número de llegadas (en miles o millones según fuente).
                - anio (int): Año del indicador.
                - mes (int | None): None (dato anual).
                - fecha_extraccion (str): Marca temporal ISO.

            Retorna lista vacía si la API no responde o hay error de conexión.
        """
        logger.info(
            "StatisticsClient[%s]: solicitando llegadas para '%s' (%d)",
            self.fuente,
            country,
            year,
        )

        try:
            if self.fuente == "eurostat":
                return self._fetch_arrivals_eurostat(country, year)
            elif self.fuente == "ine":
                return self._fetch_arrivals_ine(country, year)
            elif self.fuente == "unwto":
                return self._fetch_arrivals_unwto(country, year)
            else:
                return []

        except requests.exceptions.ConnectionError as exc:
            logger.warning(
                "StatisticsClient[%s]: error de conexión: %s",
                self.fuente,
                exc,
            )
        except requests.exceptions.Timeout as exc:
            logger.warning(
                "StatisticsClient[%s]: timeout: %s", self.fuente, exc
            )
        except requests.exceptions.HTTPError as exc:
            logger.warning(
                "StatisticsClient[%s]: error HTTP: %s", self.fuente, exc
            )
        except Exception as exc:
            logger.warning(
                "StatisticsClient[%s]: error inesperado en fetch_arrivals: %s",
                self.fuente,
                exc,
            )

        return []

    # ------------------------------------------------------------------
    # Eurostat
    # ------------------------------------------------------------------

    def _fetch_occupancy_eurostat(
        self, destino: str, year: int, month: int | None
    ) -> list[dict[str, Any]]:
        """Consulta la API de Eurostat para obtener ocupación hotelera."""
        dataset = self._config.get("dataset_tourism", "tour_occ_nim")
        url = f"{self.base_url}/data/{dataset}"

        params: dict[str, str] = {
            "format": "JSON",
            "lang": "EN",
            "sinceTimePeriod": f"{year}M01" if month is None else f"{year}M{month:02d}",
            "untilTimePeriod": f"{year}M12" if month is None else f"{year}M{month:02d}",
        }

        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()

        data = response.json()
        return self._parsear_eurostat_occupancy(data, destino, year, month)

    def _parsear_eurostat_occupancy(
        self,
        data: dict[str, Any],
        destino: str,
        year: int,
        month: int | None,
    ) -> list[dict[str, Any]]:
        """Parsea la respuesta JSON de Eurostat para indicadores de ocupación."""
        indicadores: list[dict[str, Any]] = []
        ahora = datetime.utcnow().isoformat()

        # La API de Eurostat devuelve datos en formato SDMX-JSON
        values = data.get("value", {})

        if values:
            for idx, valor in values.items():
                try:
                    # Normalizar a [0, 1] asumiendo que el valor es porcentaje
                    valor_normalizado = float(valor) / 100.0
                    valor_normalizado = max(0.0, min(1.0, valor_normalizado))

                    indicadores.append({
                        "destino_nombre": destino,
                        "fuente": "eurostat",
                        "tipo_indicador": "nivel_ocupacion",
                        "valor": round(valor_normalizado, 4),
                        "anio": year,
                        "mes": month,
                        "fecha_extraccion": ahora,
                    })
                except (ValueError, TypeError):
                    continue

        return indicadores

    def _fetch_arrivals_eurostat(
        self, country: str, year: int
    ) -> list[dict[str, Any]]:
        """Consulta Eurostat para llegadas de turistas."""
        url = f"{self.base_url}/data/tour_dem_tttot"
        params: dict[str, str] = {
            "format": "JSON",
            "lang": "EN",
            "sinceTimePeriod": str(year),
            "untilTimePeriod": str(year),
        }

        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()

        data = response.json()
        indicadores: list[dict[str, Any]] = []
        ahora = datetime.utcnow().isoformat()

        values = data.get("value", {})
        if values:
            # Tomar el primer valor disponible como total de llegadas
            for idx, valor in values.items():
                try:
                    indicadores.append({
                        "destino_nombre": country,
                        "fuente": "eurostat",
                        "tipo_indicador": "llegadas_turistas",
                        "valor": float(valor),
                        "anio": year,
                        "mes": None,
                        "fecha_extraccion": ahora,
                    })
                    break  # Solo necesitamos el total anual
                except (ValueError, TypeError):
                    continue

        return indicadores

    # ------------------------------------------------------------------
    # INE
    # ------------------------------------------------------------------

    def _fetch_occupancy_ine(
        self, destino: str, year: int, month: int | None
    ) -> list[dict[str, Any]]:
        """Consulta la API del INE para obtener ocupación hotelera en España."""
        operation_id = self._config.get("operation_id", "EOH")
        # Endpoint de series temporales del INE
        url = f"{self.base_url}/DATOS_SERIE/{operation_id}"

        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()

        data = response.json()
        return self._parsear_ine_occupancy(data, destino, year, month)

    def _parsear_ine_occupancy(
        self,
        data: Any,
        destino: str,
        year: int,
        month: int | None,
    ) -> list[dict[str, Any]]:
        """Parsea la respuesta JSON del INE para indicadores de ocupación."""
        indicadores: list[dict[str, Any]] = []
        ahora = datetime.utcnow().isoformat()

        # El INE devuelve un array de objetos con "Fecha" y "Valor"
        if isinstance(data, list):
            for item in data:
                try:
                    fecha_str = item.get("Fecha", "")
                    valor = item.get("Valor")

                    if valor is None:
                        continue

                    # Filtrar por año
                    if str(year) not in str(fecha_str):
                        continue

                    # Normalizar a [0, 1]
                    valor_normalizado = float(valor) / 100.0
                    valor_normalizado = max(0.0, min(1.0, valor_normalizado))

                    indicadores.append({
                        "destino_nombre": destino,
                        "fuente": "ine",
                        "tipo_indicador": "nivel_ocupacion",
                        "valor": round(valor_normalizado, 4),
                        "anio": year,
                        "mes": month,
                        "fecha_extraccion": ahora,
                    })
                except (ValueError, TypeError, KeyError):
                    continue

        return indicadores

    def _fetch_arrivals_ine(
        self, country: str, year: int
    ) -> list[dict[str, Any]]:
        """Consulta INE para llegadas de turistas a España."""
        # Frontur: Encuesta de Movimientos Turísticos en Fronteras
        url = f"{self.base_url}/DATOS_SERIE/FRONTUR"

        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()

        data = response.json()
        indicadores: list[dict[str, Any]] = []
        ahora = datetime.utcnow().isoformat()

        if isinstance(data, list):
            for item in data:
                try:
                    fecha_str = item.get("Fecha", "")
                    valor = item.get("Valor")

                    if valor is None or str(year) not in str(fecha_str):
                        continue

                    indicadores.append({
                        "destino_nombre": country,
                        "fuente": "ine",
                        "tipo_indicador": "llegadas_turistas",
                        "valor": float(valor),
                        "anio": year,
                        "mes": None,
                        "fecha_extraccion": ahora,
                    })
                    break
                except (ValueError, TypeError, KeyError):
                    continue

        return indicadores

    # ------------------------------------------------------------------
    # UNWTO
    # ------------------------------------------------------------------

    def _fetch_occupancy_unwto(
        self, destino: str, year: int, month: int | None
    ) -> list[dict[str, Any]]:
        """Consulta UNWTO para indicadores de ocupación (datos públicos)."""
        # UNWTO no tiene API REST pública gratuita estándar;
        # se hace un intento con el endpoint de datos abiertos
        url = f"{self.base_url}"

        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()

        # Si la respuesta es HTML (no JSON), retornar vacío
        content_type = response.headers.get("Content-Type", "")
        if "json" not in content_type:
            logger.debug(
                "StatisticsClient[unwto]: respuesta no es JSON, "
                "la fuente no provee API REST estándar."
            )
            return []

        data = response.json()
        indicadores: list[dict[str, Any]] = []
        ahora = datetime.utcnow().isoformat()

        # Intentar parsear si hay datos disponibles
        if isinstance(data, dict) and "data" in data:
            for item in data["data"]:
                try:
                    indicadores.append({
                        "destino_nombre": destino,
                        "fuente": "unwto",
                        "tipo_indicador": "nivel_ocupacion",
                        "valor": round(float(item.get("value", 0)) / 100.0, 4),
                        "anio": year,
                        "mes": month,
                        "fecha_extraccion": ahora,
                    })
                except (ValueError, TypeError, KeyError):
                    continue

        return indicadores

    def _fetch_arrivals_unwto(
        self, country: str, year: int
    ) -> list[dict[str, Any]]:
        """Consulta UNWTO para llegadas internacionales de turistas."""
        url = f"{self.base_url}"

        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "json" not in content_type:
            logger.debug(
                "StatisticsClient[unwto]: respuesta no es JSON para llegadas."
            )
            return []

        data = response.json()
        indicadores: list[dict[str, Any]] = []
        ahora = datetime.utcnow().isoformat()

        if isinstance(data, dict) and "data" in data:
            for item in data["data"]:
                try:
                    indicadores.append({
                        "destino_nombre": country,
                        "fuente": "unwto",
                        "tipo_indicador": "llegadas_turistas",
                        "valor": float(item.get("value", 0)),
                        "anio": year,
                        "mes": None,
                        "fecha_extraccion": ahora,
                    })
                    break
                except (ValueError, TypeError, KeyError):
                    continue

        return indicadores
