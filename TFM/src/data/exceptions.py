"""
Excepciones propias del módulo de datos.

Define la jerarquía de errores para operaciones de repositorio y base de datos.
"""


class RepositoryError(Exception):
    """Error base para todas las excepciones del módulo de datos."""

    def __init__(self, mensaje: str = "Error en el repositorio de datos") -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje

    def __str__(self) -> str:
        return self.mensaje


class RecordNotFoundError(RepositoryError):
    """Se lanza cuando no se encuentra un registro con el identificador solicitado."""

    def __init__(self, entidad: str, identificador: str) -> None:
        mensaje = f"No se encontró el registro '{identificador}' en la entidad '{entidad}'"
        super().__init__(mensaje)
        self.entidad = entidad
        self.identificador = identificador


class DuplicateRecordError(RepositoryError):
    """Se lanza cuando se intenta insertar un registro que ya existe en la base de datos."""

    def __init__(self, entidad: str, identificador: str) -> None:
        mensaje = f"Ya existe un registro con identificador '{identificador}' en la entidad '{entidad}'"
        super().__init__(mensaje)
        self.entidad = entidad
        self.identificador = identificador
