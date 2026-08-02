"""
Política de reintentos con backoff exponencial.

Implementa la estrategia de reintentos definida en DECISIÓN-001 y el Requisito 4.6:
máximo 3 intentos con intervalos exponenciales de 1s, 2s y 4s.

Proporciona dos modos de ejecución:
- ``execute_with_retry``: versión asíncrona para uso con asyncio.
- ``execute_sync``: versión síncrona para contextos sin event loop.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class RetryPolicy:
    """
    Ejecuta operaciones con reintentos automáticos y backoff exponencial.

    Atributos:
        max_attempts: Número máximo de intentos (incluye el primero). Por defecto 3.
        delays: Lista de tiempos de espera en segundos entre reintentos.
                El elemento i-ésimo es la espera antes del intento i+1.
    """

    max_attempts: int
    delays: list[float]

    def __init__(
        self,
        max_attempts: int = 3,
        delays: list[float] | None = None,
    ) -> None:
        """
        Inicializa la política de reintentos.

        Args:
            max_attempts: Número máximo de intentos. Por defecto 3.
            delays: Intervalos de espera en segundos entre reintentos sucesivos.
                    Por defecto [1.0, 2.0, 4.0] según configuración del sistema.
        """
        self.max_attempts = max_attempts
        self.delays = delays if delays is not None else [1.0, 2.0, 4.0]

    async def execute_with_retry(
        self,
        operation: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Ejecuta una operación asíncrona con reintentos en caso de fallo.

        Reintenta la operación hasta ``max_attempts`` veces. Entre cada intento
        espera de forma no bloqueante usando ``asyncio.sleep``. Si la operación
        es una coroutine, se ``await``ea; si es síncrona, se invoca directamente.

        Args:
            operation: Función o callable (sync o async) a ejecutar.
            *args: Argumentos posicionales para ``operation``.
            **kwargs: Argumentos de palabra clave para ``operation``.

        Returns:
            El valor devuelto por ``operation`` en caso de éxito.

        Raises:
            Exception: Relanza la excepción del último intento fallido tras
                       agotar todos los reintentos.
        """
        ultimo_error: Exception | None = None

        for intento in range(1, self.max_attempts + 1):
            try:
                logger.debug(
                    "Ejecutando operación '%s' (intento %d/%d)",
                    getattr(operation, "__name__", str(operation)),
                    intento,
                    self.max_attempts,
                )
                resultado = operation(*args, **kwargs)
                # Si el resultado es una coroutine, esperarla
                if asyncio.iscoroutine(resultado):
                    resultado = await resultado

                if intento > 1:
                    logger.info(
                        "Operación '%s' completada en el intento %d",
                        getattr(operation, "__name__", str(operation)),
                        intento,
                    )
                return resultado

            except Exception as exc:
                ultimo_error = exc
                logger.warning(
                    "Intento %d/%d fallido para la operación '%s': %s",
                    intento,
                    self.max_attempts,
                    getattr(operation, "__name__", str(operation)),
                    exc,
                )

                if intento < self.max_attempts:
                    indice_delay = min(intento - 1, len(self.delays) - 1)
                    espera = self.delays[indice_delay]
                    logger.debug(
                        "Esperando %.1f segundos antes del siguiente intento...",
                        espera,
                    )
                    await asyncio.sleep(espera)

        logger.error(
            "Operación '%s' fallida definitivamente tras %d intentos. Último error: %s",
            getattr(operation, "__name__", str(operation)),
            self.max_attempts,
            ultimo_error,
        )
        raise ultimo_error  # type: ignore[misc]

    def execute_sync(
        self,
        operation: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Ejecuta una operación síncrona con reintentos en caso de fallo.

        Versión síncrona para contextos sin event loop de asyncio.
        Reintenta la operación hasta ``max_attempts`` veces con ``time.sleep``
        entre intentos.

        Args:
            operation: Función o callable síncrono a ejecutar.
            *args: Argumentos posicionales para ``operation``.
            **kwargs: Argumentos de palabra clave para ``operation``.

        Returns:
            El valor devuelto por ``operation`` en caso de éxito.

        Raises:
            Exception: Relanza la excepción del último intento fallido tras
                       agotar todos los reintentos.
        """
        ultimo_error: Exception | None = None

        for intento in range(1, self.max_attempts + 1):
            try:
                logger.debug(
                    "Ejecutando operación '%s' (intento %d/%d)",
                    getattr(operation, "__name__", str(operation)),
                    intento,
                    self.max_attempts,
                )
                resultado = operation(*args, **kwargs)
                if intento > 1:
                    logger.info(
                        "Operación '%s' completada en el intento %d",
                        getattr(operation, "__name__", str(operation)),
                        intento,
                    )
                return resultado

            except Exception as exc:
                ultimo_error = exc
                logger.warning(
                    "Intento %d/%d fallido para la operación '%s': %s",
                    intento,
                    self.max_attempts,
                    getattr(operation, "__name__", str(operation)),
                    exc,
                )

                if intento < self.max_attempts:
                    indice_delay = min(intento - 1, len(self.delays) - 1)
                    espera = self.delays[indice_delay]
                    logger.debug(
                        "Esperando %.1f segundos antes del siguiente intento...",
                        espera,
                    )
                    time.sleep(espera)

        logger.error(
            "Operación '%s' fallida definitivamente tras %d intentos. Último error: %s",
            getattr(operation, "__name__", str(operation)),
            self.max_attempts,
            ultimo_error,
        )
        raise ultimo_error  # type: ignore[misc]
