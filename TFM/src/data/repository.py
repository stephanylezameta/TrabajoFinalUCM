"""
Capa de acceso a datos: clase Repositorio.

Encapsula todas las operaciones CRUD sobre SQLite/PostgreSQL mediante SQLAlchemy 2.x.
Implementa versionado de paquetes con hash SHA-256, paginación, logging estructurado
y registros de auditoría (exclusiones y ciclos de extracción).

Requisitos cubiertos: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.data.exceptions import DuplicateRecordError, RecordNotFoundError, RepositoryError
from src.data.models import (
    Base,
    EmbeddingMeta,
    IndicadorDestino,
    Interaccion,
    Paquete,
    PaqueteVersion,
    Resena,
    Usuario,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _paquete_a_dict(paquete: Paquete) -> dict[str, Any]:
    """
    Convierte un objeto Paquete en un diccionario serializable.

    Se utiliza para calcular el hash SHA-256 y construir el snapshot de versión.

    Args:
        paquete: Instancia del modelo Paquete a serializar.

    Returns:
        Diccionario con los campos del paquete, con valores serializables.
    """
    campos: dict[str, Any] = {}
    for columna in Paquete.__table__.columns:
        valor = getattr(paquete, columna.name)
        if isinstance(valor, datetime):
            valor = valor.isoformat()
        elif hasattr(valor, "isoformat"):
            valor = valor.isoformat()
        campos[columna.name] = valor
    return campos


def _calcular_hash(datos: dict[str, Any]) -> str:
    """
    Calcula el hash SHA-256 del diccionario serializado en JSON.

    Las claves se ordenan para garantizar determinismo en el hash.

    Args:
        datos: Diccionario a hashear.

    Returns:
        Cadena hexadecimal de 64 caracteres con el hash SHA-256.
    """
    contenido = json.dumps(datos, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------

class Repositorio:
    """
    Repositorio central de datos del Motor de Recomendación TUI.

    Proporciona operaciones CRUD para todas las entidades del sistema:
    paquetes, reseñas, indicadores, usuarios e interacciones. Implementa
    versionado automático de paquetes y logging estructurado de auditoría.

    Attributes:
        engine: Motor SQLAlchemy conectado a la base de datos.
        SessionLocal: Fábrica de sesiones configurada.
    """

    def __init__(self, database_url: str) -> None:
        """
        Inicializa el repositorio creando el engine y la session factory.

        Args:
            database_url: URL de conexión SQLAlchemy
                          (e.g. ``sqlite:///data/tui.db`` o ``postgresql://...``).
        """
        logger.info("Inicializando Repositorio con URL: %s", database_url)
        self.engine = create_engine(
            database_url,
            echo=False,
            connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
        )
        self.SessionLocal: sessionmaker[Session] = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
        )
        logger.debug("Engine y SessionLocal creados correctamente")

    def crear_tablas(self) -> None:
        """
        Crea todas las tablas definidas en los modelos si no existen.

        Equivale a ejecutar ``Base.metadata.create_all(engine)``.
        Operación idempotente: no modifica tablas ya existentes.
        """
        logger.info("Creando tablas en la base de datos...")
        Base.metadata.create_all(self.engine)
        logger.info("Tablas creadas correctamente")

    # ------------------------------------------------------------------
    # Paquetes
    # ------------------------------------------------------------------

    def upsert_paquete(self, paquete: Paquete) -> Paquete:
        """
        Inserta o actualiza un paquete en la base de datos.

        Si el paquete ya existe (mismo ``id_paquete``), actualiza todos sus
        campos y crea una nueva entrada en ``PaqueteVersion`` con el hash
        SHA-256 del JSON del registro actualizado.

        Si el paquete no existe, lo inserta y también crea la versión inicial.

        Args:
            paquete: Instancia del modelo Paquete a persistir.

        Returns:
            El paquete persistido (con posibles valores generados por la BD).

        Raises:
            RepositoryError: Si ocurre un error inesperado durante la transacción.
        """
        with self.SessionLocal() as sesion:
            try:
                existente: Paquete | None = sesion.get(Paquete, paquete.id_paquete)

                if existente is not None:
                    logger.debug(
                        "Actualizando paquete existente id=%s", paquete.id_paquete
                    )
                    # Actualizar campos del registro existente
                    for col in Paquete.__table__.columns:
                        if col.name not in ("id_paquete",):
                            setattr(existente, col.name, getattr(paquete, col.name))
                    paquete_a_versionar = existente
                else:
                    logger.debug(
                        "Insertando nuevo paquete id=%s", paquete.id_paquete
                    )
                    sesion.add(paquete)
                    paquete_a_versionar = paquete

                sesion.flush()

                # Crear versión con snapshot y hash
                datos_snapshot = _paquete_a_dict(paquete_a_versionar)
                hash_contenido = _calcular_hash(datos_snapshot)

                version = PaqueteVersion(
                    id_paquete=paquete_a_versionar.id_paquete,
                    hash_contenido=hash_contenido,
                    datos_snapshot=datos_snapshot,
                    timestamp_version=datetime.utcnow(),
                )
                sesion.add(version)
                sesion.commit()
                sesion.refresh(paquete_a_versionar)

                logger.info(
                    "Paquete id=%s persistido correctamente (hash=%s)",
                    paquete_a_versionar.id_paquete,
                    hash_contenido[:8],
                )
                return paquete_a_versionar

            except Exception as exc:
                sesion.rollback()
                logger.error(
                    "Error al persistir paquete id=%s: %s",
                    paquete.id_paquete,
                    exc,
                    exc_info=True,
                )
                raise RepositoryError(f"Error al persistir paquete: {exc}") from exc

    def upsert_paquetes(self, paquetes: list[Paquete]) -> int:
        """
        Inserta o actualiza un conjunto de paquetes en lote.

        Procesa cada paquete llamando a ``upsert_paquete`` e independiza
        los fallos individuales para no abortar el lote completo.

        Args:
            paquetes: Lista de instancias Paquete a persistir.

        Returns:
            Número de paquetes insertados o actualizados correctamente.
        """
        procesados = 0
        for paquete in paquetes:
            try:
                self.upsert_paquete(paquete)
                procesados += 1
            except RepositoryError as exc:
                logger.warning(
                    "Paquete id=%s omitido en lote por error: %s",
                    paquete.id_paquete,
                    exc,
                )

        logger.info(
            "Batch upsert completado: %d/%d paquetes procesados",
            procesados,
            len(paquetes),
        )
        return procesados

    def get_paquete(self, id_paquete: str) -> Paquete | None:
        """
        Recupera un paquete por su identificador.

        Args:
            id_paquete: UUID del paquete a recuperar.

        Returns:
            Instancia del paquete o ``None`` si no existe.
        """
        with self.SessionLocal() as sesion:
            paquete = sesion.get(Paquete, id_paquete)
            if paquete is not None:
                sesion.expunge(paquete)
            return paquete

    def list_paquetes(
        self,
        region: str | None = None,
        categoria: str | None = None,
        temporada: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[Paquete]:
        """
        Lista paquetes con filtros opcionales y paginación.

        Args:
            region: Filtrar por ``zona_geografica`` (e.g. ``"Mediterráneo"``).
            categoria: Filtrar por ``categoria`` (e.g. ``"playa"``).
            temporada: Filtrar por ``temporada`` (e.g. ``"Alta"``).
            page: Número de página (1-indexado).
            page_size: Tamaño de página. Por defecto 20.

        Returns:
            Lista de paquetes que cumplen los filtros en la página solicitada.
        """
        with self.SessionLocal() as sesion:
            consulta = select(Paquete)

            if region is not None:
                consulta = consulta.where(Paquete.zona_geografica == region)
            if categoria is not None:
                consulta = consulta.where(Paquete.categoria == categoria)
            if temporada is not None:
                consulta = consulta.where(Paquete.temporada == temporada)

            offset = (page - 1) * page_size
            consulta = consulta.offset(offset).limit(page_size)

            resultados = sesion.execute(consulta).scalars().all()
            # Expulsar de la sesión para uso fuera del contexto
            for p in resultados:
                sesion.expunge(p)

            logger.debug(
                "list_paquetes: %d resultados (region=%s, categoria=%s, temporada=%s, page=%d)",
                len(resultados),
                region,
                categoria,
                temporada,
                page,
            )
            return list(resultados)

    # ------------------------------------------------------------------
    # Reseñas
    # ------------------------------------------------------------------

    def upsert_resena(self, resena: Resena) -> Resena:
        """
        Inserta o actualiza una reseña en la base de datos.

        Args:
            resena: Instancia del modelo Resena a persistir.

        Returns:
            La reseña persistida.

        Raises:
            RepositoryError: Si ocurre un error durante la transacción.
        """
        with self.SessionLocal() as sesion:
            try:
                existente: Resena | None = sesion.get(Resena, resena.id_resena)

                if existente is not None:
                    for col in Resena.__table__.columns:
                        if col.name != "id_resena":
                            setattr(existente, col.name, getattr(resena, col.name))
                    resena_persistida = existente
                else:
                    sesion.add(resena)
                    resena_persistida = resena

                sesion.commit()
                sesion.refresh(resena_persistida)
                sesion.expunge(resena_persistida)

                logger.debug("Reseña id=%s persistida", resena_persistida.id_resena)
                return resena_persistida

            except Exception as exc:
                sesion.rollback()
                logger.error("Error al persistir reseña: %s", exc, exc_info=True)
                raise RepositoryError(f"Error al persistir reseña: {exc}") from exc

    # ------------------------------------------------------------------
    # Indicadores de destino
    # ------------------------------------------------------------------

    def upsert_indicador(self, indicador: IndicadorDestino) -> IndicadorDestino:
        """
        Inserta o actualiza un indicador de destino.

        Args:
            indicador: Instancia del modelo IndicadorDestino a persistir.

        Returns:
            El indicador persistido.

        Raises:
            RepositoryError: Si ocurre un error durante la transacción.
        """
        with self.SessionLocal() as sesion:
            try:
                existente: IndicadorDestino | None = sesion.get(
                    IndicadorDestino, indicador.id_indicador
                )

                if existente is not None:
                    for col in IndicadorDestino.__table__.columns:
                        if col.name != "id_indicador":
                            setattr(existente, col.name, getattr(indicador, col.name))
                    indicador_persistido = existente
                else:
                    sesion.add(indicador)
                    indicador_persistido = indicador

                sesion.commit()
                sesion.refresh(indicador_persistido)
                sesion.expunge(indicador_persistido)

                logger.debug(
                    "Indicador id=%s persistido", indicador_persistido.id_indicador
                )
                return indicador_persistido

            except Exception as exc:
                sesion.rollback()
                logger.error("Error al persistir indicador: %s", exc, exc_info=True)
                raise RepositoryError(f"Error al persistir indicador: {exc}") from exc

    # ------------------------------------------------------------------
    # Usuarios
    # ------------------------------------------------------------------

    def crear_usuario(self, usuario: Usuario) -> Usuario:
        """
        Crea un nuevo usuario en la base de datos.

        Args:
            usuario: Instancia del modelo Usuario a persistir.

        Returns:
            El usuario creado.

        Raises:
            DuplicateRecordError: Si ya existe un usuario con el mismo ``id_usuario``.
            RepositoryError: Si ocurre otro error durante la transacción.
        """
        with self.SessionLocal() as sesion:
            try:
                existente = sesion.get(Usuario, usuario.id_usuario)
                if existente is not None:
                    raise DuplicateRecordError("usuarios", usuario.id_usuario)

                sesion.add(usuario)
                sesion.commit()
                sesion.refresh(usuario)
                sesion.expunge(usuario)

                logger.debug("Usuario id=%s creado", usuario.id_usuario)
                return usuario

            except DuplicateRecordError:
                raise
            except Exception as exc:
                sesion.rollback()
                logger.error("Error al crear usuario: %s", exc, exc_info=True)
                raise RepositoryError(f"Error al crear usuario: {exc}") from exc

    def get_usuario(self, id_usuario: str) -> Usuario | None:
        """
        Recupera un usuario por su identificador.

        Args:
            id_usuario: UUID del usuario a recuperar.

        Returns:
            Instancia del usuario o ``None`` si no existe.
        """
        with self.SessionLocal() as sesion:
            usuario = sesion.get(Usuario, id_usuario)
            if usuario is not None:
                sesion.expunge(usuario)
            return usuario

    def list_usuarios(self, solo_sinteticos: bool = False) -> list[Usuario]:
        """
        Lista todos los usuarios registrados.

        Args:
            solo_sinteticos: Si es ``True``, devuelve únicamente usuarios
                             generados sintéticamente.

        Returns:
            Lista de usuarios que cumplen el filtro.
        """
        with self.SessionLocal() as sesion:
            consulta = select(Usuario)
            if solo_sinteticos:
                consulta = consulta.where(Usuario.es_sintetico.is_(True))

            resultados = sesion.execute(consulta).scalars().all()
            for u in resultados:
                sesion.expunge(u)

            logger.debug(
                "list_usuarios: %d resultados (solo_sinteticos=%s)",
                len(resultados),
                solo_sinteticos,
            )
            return list(resultados)

    # ------------------------------------------------------------------
    # Interacciones
    # ------------------------------------------------------------------

    def registrar_interaccion(self, interaccion: Interaccion) -> Interaccion:
        """
        Registra una nueva interacción usuario-paquete.

        Args:
            interaccion: Instancia del modelo Interaccion a persistir.

        Returns:
            La interacción registrada.

        Raises:
            RepositoryError: Si ocurre un error durante la transacción.
        """
        with self.SessionLocal() as sesion:
            try:
                sesion.add(interaccion)
                sesion.commit()
                sesion.refresh(interaccion)
                sesion.expunge(interaccion)

                logger.debug(
                    "Interacción id=%s registrada (tipo=%s)",
                    interaccion.id_interaccion,
                    interaccion.tipo,
                )
                return interaccion

            except Exception as exc:
                sesion.rollback()
                logger.error("Error al registrar interacción: %s", exc, exc_info=True)
                raise RepositoryError(f"Error al registrar interacción: {exc}") from exc

    def get_interacciones_usuario(self, id_usuario: str) -> list[Interaccion]:
        """
        Recupera todas las interacciones de un usuario.

        Args:
            id_usuario: UUID del usuario del que se quieren recuperar interacciones.

        Returns:
            Lista de interacciones del usuario, ordenadas por ``timestamp_interaccion``
            de más antigua a más reciente.
        """
        with self.SessionLocal() as sesion:
            consulta = (
                select(Interaccion)
                .where(Interaccion.id_usuario == id_usuario)
                .order_by(Interaccion.timestamp_interaccion)
            )
            resultados = sesion.execute(consulta).scalars().all()
            for i in resultados:
                sesion.expunge(i)

            logger.debug(
                "get_interacciones_usuario: %d interacciones para usuario=%s",
                len(resultados),
                id_usuario,
            )
            return list(resultados)

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    def actualizar_embedding_meta(self, meta: EmbeddingMeta) -> EmbeddingMeta:
        """
        Inserta o actualiza los metadatos del embedding de un paquete.

        Al sobrescribir, actualiza ``fecha_generacion`` al momento actual
        si no se especifica explícitamente (RF-3.5).

        Args:
            meta: Instancia del modelo EmbeddingMeta a persistir.

        Returns:
            El EmbeddingMeta persistido.

        Raises:
            RepositoryError: Si ocurre un error durante la transacción.
        """
        with self.SessionLocal() as sesion:
            try:
                existente: EmbeddingMeta | None = sesion.get(
                    EmbeddingMeta, meta.id_paquete
                )

                if existente is not None:
                    # Actualizar fecha de generación y resto de metadatos
                    existente.modelo_nombre = meta.modelo_nombre
                    existente.modelo_version = meta.modelo_version
                    existente.embedding_dim = meta.embedding_dim
                    existente.fecha_generacion = meta.fecha_generacion or datetime.utcnow()
                    existente.chroma_id = meta.chroma_id
                    meta_persistida = existente
                else:
                    if meta.fecha_generacion is None:
                        meta.fecha_generacion = datetime.utcnow()
                    sesion.add(meta)
                    meta_persistida = meta

                sesion.commit()
                sesion.refresh(meta_persistida)
                sesion.expunge(meta_persistida)

                logger.debug(
                    "EmbeddingMeta para paquete=%s actualizado (dim=%d)",
                    meta_persistida.id_paquete,
                    meta_persistida.embedding_dim,
                )
                return meta_persistida

            except Exception as exc:
                sesion.rollback()
                logger.error(
                    "Error al actualizar embedding meta: %s", exc, exc_info=True
                )
                raise RepositoryError(
                    f"Error al actualizar embedding meta: {exc}"
                ) from exc

    # ------------------------------------------------------------------
    # Auditoría y logging
    # ------------------------------------------------------------------

    def log_exclusion(self, id_paquete: str, motivo: str) -> None:
        """
        Registra en el log estructurado la exclusión de un paquete inválido.

        Implementa el requisito RF-1.8: registrar el motivo por el que un
        paquete fue excluido del conjunto de datos de entrenamiento.

        Args:
            id_paquete: UUID del paquete excluido.
            motivo: Descripción del motivo de exclusión
                    (e.g. ``"Más del 30% de atributos obligatorios vacíos"``).
        """
        logger.warning(
            "EXCLUSION | id_paquete=%s | motivo=%s",
            id_paquete,
            motivo,
        )

    def log_run(self, reporte: dict[str, Any]) -> None:
        """
        Registra en el log estructurado el reporte de un ciclo de extracción.

        Implementa el requisito NF-3.2: registrar cada ejecución del pipeline
        con fecha, versión del código y métricas obtenidas.

        Args:
            reporte: Diccionario con los datos del ciclo de extracción.
                     Se recomienda incluir al menos: ``fecha_inicio``,
                     ``version_scraper``, ``num_paquetes_insertados``,
                     ``num_paquetes_actualizados``, ``num_exclusiones``.
        """
        logger.info(
            "RUN_REPORT | %s",
            json.dumps(reporte, default=str, ensure_ascii=False),
        )
