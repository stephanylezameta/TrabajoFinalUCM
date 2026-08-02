"""
Módulo de limpieza, deduplicación y validación de registros de paquetes turísticos.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Estructuras de datos
# ---------------------------------------------------------------------------

@dataclass
class ExclusionLog:
    """Registro de exclusión de un paquete durante la limpieza de datos."""

    id_paquete: str
    motivo: str
    campos_vacios: list[str]
    porcentaje_vacios: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ValidationResult:
    """Resultado de la validación de esquema de un registro."""

    es_valido: bool
    errores: list[str]


# ---------------------------------------------------------------------------
# Excepciones
# ---------------------------------------------------------------------------

class ValidationError(ValueError):
    """Excepción tipada para datos fuera de rango en campos numéricos críticos."""

    def __init__(self, campo: str, valor: float, mensaje: str) -> None:
        self.campo = campo
        self.valor = valor
        super().__init__(
            f"ValidationError en '{campo}': {mensaje} (valor={valor})"
        )


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------

class DataCleaner:
    """Limpia, deduplica y valida registros de paquetes turísticos.

    El pipeline de limpieza sigue este orden:
        1. ``deduplicate``   → elimina duplicados por clave compuesta
        2. ``validate_schema`` → verifica tipos y rangos obligatorios
        3. ``exclude_invalid``  → excluye registros con demasiados campos vacíos
        4. ``normalize_minmax`` → normaliza columnas numéricas a [0, 1]
    """

    # Campos que deben estar presentes en cada paquete
    CAMPOS_OBLIGATORIOS: list[str] = [
        "destino_nombre",
        "destino_pais",
        "categoria",
        "nombre_paquete",
        "nombre_hotel",
        "ciudad_salida",
        "fecha_salida",
        "fecha_vuelta",
        "duracion_dias",
        "precio_base_eur",
        "nivel_ocupacion",
    ]

    # Columnas numéricas que se normalizan por defecto en el pipeline
    _COLUMNAS_NUMERICAS_DEFAULT: list[str] = [
        "precio_base_eur",
        "duracion_dias",
        "nivel_ocupacion",
    ]

    def __init__(self, umbral_exclusion: float = 0.30) -> None:
        """
        Inicializa el DataCleaner.

        Args:
            umbral_exclusion: Fracción máxima de campos obligatorios vacíos
                              permitida antes de excluir el registro (default 0.30).
                              Un valor de 0.30 significa que si más del 30 % de
                              los campos obligatorios están vacíos, el registro
                              se excluye.
        """
        if not (0.0 <= umbral_exclusion <= 1.0):
            raise ValueError(
                f"umbral_exclusion debe estar en [0, 1], se recibió {umbral_exclusion}"
            )
        self.umbral_exclusion = umbral_exclusion

    # ------------------------------------------------------------------
    # 1. Deduplicación
    # ------------------------------------------------------------------

    def deduplicate(self, records: list[dict]) -> list[dict]:
        """Elimina registros duplicados por clave compuesta de unicidad.

        La clave de unicidad es:
            ``(destino_nombre, nombre_hotel, fecha_salida, fecha_vuelta, ciudad_salida)``

        Cuando hay duplicados, se conserva el registro cuyo campo
        ``fecha_extraccion`` sea el más reciente.  Si el campo
        ``fecha_extraccion`` no está presente o no es convertible a
        ``datetime``, se usa el último registro visto.

        Args:
            records: Lista de registros (dicts) crudos.

        Returns:
            Lista de registros sin duplicados.
        """
        if not records:
            return []

        _CLAVE_UNICIDAD = (
            "destino_nombre",
            "nombre_hotel",
            "fecha_salida",
            "fecha_vuelta",
            "ciudad_salida",
        )

        seen: dict[tuple, dict] = {}

        for record in records:
            clave = tuple(str(record.get(k, "")) for k in _CLAVE_UNICIDAD)

            if clave not in seen:
                seen[clave] = record
            else:
                # Resolver por fecha_extraccion más reciente
                existing = seen[clave]
                fecha_nueva = self._parse_fecha(record.get("fecha_extraccion"))
                fecha_existente = self._parse_fecha(existing.get("fecha_extraccion"))

                if fecha_nueva is not None and fecha_existente is not None:
                    if fecha_nueva > fecha_existente:
                        seen[clave] = record
                else:
                    # Sin fecha comparable → conservar el último visto
                    seen[clave] = record

        resultado = list(seen.values())
        n_eliminados = len(records) - len(resultado)

        if n_eliminados > 0:
            logger.info(
                "deduplicate: %d registro(s) duplicado(s) eliminado(s); "
                "%d registro(s) conservado(s).",
                n_eliminados,
                len(resultado),
            )
        else:
            logger.debug("deduplicate: no se encontraron duplicados.")

        return resultado

    # ------------------------------------------------------------------
    # 2. Normalización min-max
    # ------------------------------------------------------------------

    def normalize_minmax(
        self, df: pd.DataFrame, columns: list[str]
    ) -> pd.DataFrame:
        """Aplica normalización min-max a las columnas especificadas.

        Postcondición: todos los valores de las columnas procesadas ∈ [0, 1].

        Caso especial: si ``min == max`` para una columna, se asigna el valor
        0.5 a todos sus elementos para evitar división por cero.

        Args:
            df: DataFrame de entrada.
            columns: Lista de nombres de columna a normalizar.

        Returns:
            DataFrame con las columnas indicadas normalizadas in-place
            (se devuelve una copia).
        """
        df = df.copy()

        for col in columns:
            if col not in df.columns:
                logger.warning(
                    "normalize_minmax: columna '%s' no encontrada en el DataFrame; "
                    "se omite.",
                    col,
                )
                continue

            col_min = df[col].min()
            col_max = df[col].max()

            if col_min == col_max:
                logger.debug(
                    "normalize_minmax: columna '%s' tiene min==max (%.4f); "
                    "se asigna 0.5 a todos los valores.",
                    col,
                    col_min,
                )
                df[col] = 0.5
            else:
                df[col] = (df[col] - col_min) / (col_max - col_min)

        return df

    # ------------------------------------------------------------------
    # 3. Validación de esquema
    # ------------------------------------------------------------------

    def validate_schema(self, record: dict) -> ValidationResult:
        """Verifica presencia y tipo correcto de los atributos obligatorios.

        Comprobaciones realizadas:
        - Todos los ``CAMPOS_OBLIGATORIOS`` deben estar presentes y no vacíos.
        - ``nivel_ocupacion`` ∈ [0, 1].
        - ``precio_base_eur`` ≥ 0.
        - ``duracion_dias`` ≥ 1.
        - ``estrellas_hotel`` ∈ [1, 5] si está presente.

        Lanza:
            ValidationError: Si ``nivel_ocupacion > 1``, ``nivel_ocupacion < 0``,
                ``precio_base_eur < 0``, ``duracion_dias < 1`` o
                ``estrellas_hotel`` está fuera de [1, 5].

        Returns:
            :class:`ValidationResult` con ``es_valido=True`` y lista de errores
            vacía si el registro es válido, o ``es_valido=False`` con la lista
            de errores correspondiente.
        """
        errores: list[str] = []

        # 3.1 Comprobación de presencia de campos obligatorios
        for campo in self.CAMPOS_OBLIGATORIOS:
            valor = record.get(campo)
            if valor is None or (isinstance(valor, str) and valor.strip() == ""):
                errores.append(f"Campo obligatorio ausente o vacío: '{campo}'")

        # 3.2 Validaciones de rango (lanzar ValidationError inmediatamente)
        self._validar_rango_nivel_ocupacion(record)
        self._validar_precio_base_eur(record)
        self._validar_duracion_dias(record)
        self._validar_estrellas_hotel(record)

        return ValidationResult(es_valido=len(errores) == 0, errores=errores)

    # ------------------------------------------------------------------
    # 4. Exclusión de registros inválidos
    # ------------------------------------------------------------------

    def exclude_invalid(
        self,
        records: list[dict],
        threshold: float | None = None,
    ) -> tuple[list[dict], list[ExclusionLog]]:
        """Excluye registros con demasiados campos obligatorios vacíos.

        Primero valida rangos críticos mediante :meth:`validate_schema` —
        lanzando :class:`ValidationError` si algún registro contiene
        ``nivel_ocupacion > 1``, ``nivel_ocupacion < 0`` o
        ``precio_base_eur < 0``.

        Después, excluye los registros cuya fracción de campos obligatorios
        vacíos supera ``threshold`` (o ``self.umbral_exclusion`` si no se
        especifica).

        Args:
            records: Lista de registros a filtrar.
            threshold: Umbral de fracción de vacíos.  Si es ``None`` se usa
                ``self.umbral_exclusion``.

        Returns:
            Tupla ``(registros_validos, logs_exclusion)``.
        """
        if threshold is None:
            threshold = self.umbral_exclusion

        # Validación de rangos críticos — lanzar inmediatamente si hay error
        for record in records:
            self._validar_rango_nivel_ocupacion(record)
            self._validar_precio_base_eur(record)

        validos: list[dict] = []
        logs: list[ExclusionLog] = []
        total_campos = len(self.CAMPOS_OBLIGATORIOS)

        for record in records:
            campos_vacios = [
                campo
                for campo in self.CAMPOS_OBLIGATORIOS
                if record.get(campo) is None
                or (
                    isinstance(record.get(campo), str)
                    and record.get(campo).strip() == ""
                )
            ]
            porcentaje_vacios = len(campos_vacios) / total_campos

            if porcentaje_vacios > threshold:
                id_paquete = str(
                    record.get("id_paquete")
                    or record.get("nombre_paquete")
                    or "<sin_id>"
                )
                motivo = (
                    f"Más del {threshold * 100:.0f}% de campos obligatorios "
                    f"vacíos ({porcentaje_vacios * 100:.1f}%)"
                )
                logs.append(
                    ExclusionLog(
                        id_paquete=id_paquete,
                        motivo=motivo,
                        campos_vacios=campos_vacios,
                        porcentaje_vacios=porcentaje_vacios,
                    )
                )
                logger.info(
                    "exclude_invalid: registro '%s' excluido — %s",
                    id_paquete,
                    motivo,
                )
            else:
                validos.append(record)

        logger.info(
            "exclude_invalid: %d registro(s) válido(s), %d excluido(s).",
            len(validos),
            len(logs),
        )
        return validos, logs

    # ------------------------------------------------------------------
    # 5. Pipeline completo
    # ------------------------------------------------------------------

    def clean_pipeline(
        self, records: list[dict]
    ) -> tuple[list[dict], list[ExclusionLog]]:
        """Ejecuta el pipeline completo de limpieza.

        Orden de ejecución:
            1. :meth:`deduplicate`
            2. :meth:`validate_schema` (informativo; registros inválidos se
               excluyen en el paso siguiente)
            3. :meth:`exclude_invalid`
            4. :meth:`normalize_minmax`

        Args:
            records: Lista de registros crudos.

        Returns:
            Tupla ``(registros_limpios, logs_exclusion)``.
        """
        logger.info("clean_pipeline: iniciando con %d registro(s).", len(records))

        # Paso 1: deduplicar
        records = self.deduplicate(records)
        logger.debug("clean_pipeline: tras deduplicar → %d registro(s).", len(records))

        # Paso 2: validar esquema (registros con errores de rango lanzan excepción;
        # los errores de campos faltantes se manejan en exclude_invalid)
        registros_pre_exclusion: list[dict] = []
        for record in records:
            result = self.validate_schema(record)  # puede lanzar ValidationError
            if not result.es_valido:
                logger.debug(
                    "clean_pipeline: registro con errores de esquema (se evaluará en exclude_invalid): %s",
                    result.errores,
                )
            registros_pre_exclusion.append(record)

        # Paso 3: excluir inválidos
        validos, logs = self.exclude_invalid(registros_pre_exclusion)
        logger.debug(
            "clean_pipeline: tras exclusión → %d válido(s), %d excluido(s).",
            len(validos),
            len(logs),
        )

        if not validos:
            logger.warning("clean_pipeline: no quedan registros válidos tras la limpieza.")
            return [], logs

        # Paso 4: normalizar columnas numéricas presentes
        df = pd.DataFrame(validos)
        columnas_a_normalizar = [
            col
            for col in self._COLUMNAS_NUMERICAS_DEFAULT
            if col in df.columns
        ]
        if columnas_a_normalizar:
            df = self.normalize_minmax(df, columnas_a_normalizar)

        registros_limpios = df.to_dict(orient="records")
        logger.info(
            "clean_pipeline: pipeline completado → %d registro(s) limpio(s).",
            len(registros_limpios),
        )
        return registros_limpios, logs

    # ------------------------------------------------------------------
    # Métodos auxiliares privados
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_fecha(valor: object) -> datetime | None:
        """Intenta convertir *valor* a :class:`datetime`.

        Acepta instancias de ``datetime``, cadenas ISO 8601 y enteros/floats
        de tipo timestamp UNIX.  Devuelve ``None`` si la conversión falla.
        """
        if isinstance(valor, datetime):
            return valor
        if isinstance(valor, (int, float)):
            try:
                return datetime.utcfromtimestamp(valor)
            except (OSError, OverflowError, ValueError):
                return None
        if isinstance(valor, str):
            for fmt in (
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    return datetime.strptime(valor, fmt)
                except ValueError:
                    continue
        return None

    @staticmethod
    def _validar_rango_nivel_ocupacion(record: dict) -> None:
        """Lanza :class:`ValidationError` si ``nivel_ocupacion`` está fuera de [0, 1]."""
        valor = record.get("nivel_ocupacion")
        if valor is None:
            return
        try:
            v = float(valor)
        except (TypeError, ValueError):
            return
        if v > 1.0:
            raise ValidationError(
                campo="nivel_ocupacion",
                valor=v,
                mensaje="nivel_ocupacion debe ser ≤ 1.0",
            )
        if v < 0.0:
            raise ValidationError(
                campo="nivel_ocupacion",
                valor=v,
                mensaje="nivel_ocupacion debe ser ≥ 0.0",
            )

    @staticmethod
    def _validar_precio_base_eur(record: dict) -> None:
        """Lanza :class:`ValidationError` si ``precio_base_eur`` es negativo."""
        valor = record.get("precio_base_eur")
        if valor is None:
            return
        try:
            v = float(valor)
        except (TypeError, ValueError):
            return
        if v < 0.0:
            raise ValidationError(
                campo="precio_base_eur",
                valor=v,
                mensaje="precio_base_eur no puede ser negativo",
            )

    @staticmethod
    def _validar_duracion_dias(record: dict) -> None:
        """Lanza :class:`ValidationError` si ``duracion_dias`` es menor que 1."""
        valor = record.get("duracion_dias")
        if valor is None:
            return
        try:
            v = float(valor)
        except (TypeError, ValueError):
            return
        if v < 1:
            raise ValidationError(
                campo="duracion_dias",
                valor=v,
                mensaje="duracion_dias debe ser ≥ 1",
            )

    @staticmethod
    def _validar_estrellas_hotel(record: dict) -> None:
        """Lanza :class:`ValidationError` si ``estrellas_hotel`` está fuera de [1, 5]."""
        valor = record.get("estrellas_hotel")
        if valor is None:
            return
        try:
            v = float(valor)
        except (TypeError, ValueError):
            return
        if not (1.0 <= v <= 5.0):
            raise ValidationError(
                campo="estrellas_hotel",
                valor=v,
                mensaje="estrellas_hotel debe estar en el rango [1, 5]",
            )
