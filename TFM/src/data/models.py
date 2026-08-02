"""
Modelos de datos SQLAlchemy 2.x para el Motor de Recomendación Turística TUI.

Define las tablas del esquema relacional según DECISIÓN-005:
- paquetes: catálogo de paquetes turísticos all-inclusive
- resenas: valoraciones de usuarios de fuentes externas
- indicadores_destino: estadísticas turísticas por destino
- usuarios: perfiles de viajero (reales y sintéticos)
- interacciones: registro de visualizaciones, reservas y valoraciones
- embeddings_meta: metadatos de los vectores semánticos almacenados en Chroma
- paquetes_versiones: historial de versiones del catálogo con hash SHA-256
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------------
# Base declarativa
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Clase base para todos los modelos SQLAlchemy del proyecto."""
    pass


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def _nuevo_uuid() -> str:
    """Genera un nuevo UUID v4 como cadena de texto."""
    return str(uuid.uuid4())


def _ahora_utc() -> datetime:
    """Devuelve la fecha y hora actual en UTC."""
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

class Paquete(Base):
    """
    Paquete turístico all-inclusive (vuelo + hotel + destino) ofertado por TUI.

    Corresponde a la tabla ``paquetes`` y representa la entidad principal
    del catálogo sobre la que se calculan afinidad, TDRS y re-ranking.
    """

    __tablename__ = "paquetes"

    # -- Identificación y trazabilidad
    id_paquete: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_nuevo_uuid,
        comment="UUID v4 identificador único del paquete"
    )
    mercado: Mapped[str] = mapped_column(
        String(2), nullable=False,
        comment="Mercado TUI de procedencia: es | de | uk"
    )

    # -- Destino
    destino_nombre: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="Nombre del destino turístico"
    )
    destino_pais: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="País del destino"
    )
    zona_geografica: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Zona geográfica: Mediterráneo | Caribe | otro"
    )
    categoria: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Categoría del paquete: playa | cultura | aventura | bienestar | gastronomia | naturaleza"
    )

    # -- Producto
    nombre_paquete: Mapped[str] = mapped_column(
        String(300), nullable=False,
        comment="Nombre comercial del paquete"
    )
    descripcion_texto: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Descripción completa del paquete (input para embeddings NLP)"
    )
    nombre_hotel: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="Nombre del hotel incluido en el paquete"
    )
    estrellas_hotel: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Categoría del hotel en estrellas (1-5)"
    )
    ciudad_salida: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Ciudad de salida del vuelo"
    )

    # -- Fechas y duración
    fecha_salida: Mapped[date | None] = mapped_column(
        Date, nullable=True,
        comment="Fecha de salida del vuelo"
    )
    fecha_vuelta: Mapped[date | None] = mapped_column(
        Date, nullable=True,
        comment="Fecha de vuelta del viaje"
    )
    duracion_dias: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Duración total del viaje en días"
    )

    # -- Precio
    precio_base_eur: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Precio base del paquete en euros"
    )
    moneda_original: Mapped[str | None] = mapped_column(
        String(3), nullable=True,
        comment="Código ISO 4217 de la moneda original (e.g. EUR, GBP)"
    )
    precio_original: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Precio en la moneda original del mercado"
    )

    # -- Disponibilidad y ocupación
    capacidad_plazas: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Número total de plazas del paquete"
    )
    plazas_disponibles: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Número de plazas todavía disponibles"
    )
    nivel_ocupacion: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Ratio de ocupación en [0, 1]: 0 = sin reservas, 1 = completo"
    )

    # -- Temporada y sostenibilidad
    temporada: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
        comment="Temporada calculada: Alta | Media | Baja"
    )
    accesibilidad_destino: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Nivel de accesibilidad del destino: 1 (bajo) a 3 (alto)"
    )
    indicador_sostenibilidad_tui: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True,
        comment="True si el paquete tiene certificación de sostenibilidad TUI"
    )
    sensibilidad_ambiental: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Índice de sensibilidad ambiental del destino en [0, 1]"
    )

    # -- Valoraciones
    num_valoraciones_hotel: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Número total de valoraciones disponibles para el hotel"
    )
    puntuacion_media_hotel: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Puntuación media del hotel según valoraciones (0-10)"
    )

    # -- Metadatos de procedencia
    url_fuente: Mapped[str | None] = mapped_column(
        String(1000), nullable=True,
        comment="URL de la página de origen del scraping"
    )
    fecha_extraccion: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=_ahora_utc,
        comment="Marca temporal de extracción del dato"
    )
    version_scraper: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="Versión del scraper que generó el registro"
    )

    # -- Embeddings
    embedding_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("embeddings_meta.id_paquete", ondelete="SET NULL"),
        nullable=True,
        comment="Referencia al vector en Chroma/pgvector (FK a embeddings_meta)"
    )

    # -- Relaciones
    versiones: Mapped[list["PaqueteVersion"]] = relationship(
        "PaqueteVersion",
        back_populates="paquete",
        cascade="all, delete-orphan",
    )
    resenas: Mapped[list["Resena"]] = relationship(
        "Resena",
        back_populates="paquete",
    )
    interacciones: Mapped[list["Interaccion"]] = relationship(
        "Interaccion",
        back_populates="paquete",
    )
    embedding_meta: Mapped["EmbeddingMeta | None"] = relationship(
        "EmbeddingMeta",
        foreign_keys=[embedding_id],
        primaryjoin="Paquete.embedding_id == EmbeddingMeta.id_paquete",
        uselist=False,
    )

    def __repr__(self) -> str:
        return (
            f"<Paquete id={self.id_paquete!r} destino={self.destino_nombre!r} "
            f"mercado={self.mercado!r}>"
        )


class Resena(Base):
    """
    Reseña de usuario sobre un destino o paquete turístico.

    Corresponde a la tabla ``resenas``. El texto de la reseña es el input
    principal para la generación de embeddings de reputación de destinos.
    """

    __tablename__ = "resenas"

    id_resena: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_nuevo_uuid,
        comment="UUID v4 identificador único de la reseña"
    )
    id_paquete: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("paquetes.id_paquete", ondelete="SET NULL"),
        nullable=True,
        comment="FK al paquete al que hace referencia la reseña (nullable)"
    )
    destino_nombre: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="Nombre del destino al que hace referencia la reseña"
    )
    fuente: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Origen de la reseña: tripadvisor | reddit | foro"
    )
    texto_original: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Texto completo de la reseña (input para embedding de reputación)"
    )
    idioma: Mapped[str] = mapped_column(
        String(5), nullable=False,
        comment="Código de idioma detectado: es | de | en"
    )
    puntuacion: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Puntuación de la reseña en [1, 5]; None si no aplica"
    )
    fecha_publicacion: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
        comment="Fecha de publicación original de la reseña"
    )
    url_fuente: Mapped[str | None] = mapped_column(
        String(1000), nullable=True,
        comment="URL de la página de origen de la reseña"
    )
    fecha_extraccion: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=_ahora_utc,
        comment="Marca temporal de extracción"
    )

    # -- Relaciones
    paquete: Mapped["Paquete | None"] = relationship(
        "Paquete",
        back_populates="resenas",
    )

    def __repr__(self) -> str:
        return (
            f"<Resena id={self.id_resena!r} destino={self.destino_nombre!r} "
            f"fuente={self.fuente!r}>"
        )


class IndicadorDestino(Base):
    """
    Indicador estadístico turístico por destino y fuente (Eurostat, INE, UNWTO, Booking).

    Corresponde a la tabla ``indicadores_destino``. El campo ``nivel_ocupacion``
    se calcula a partir de pernoctaciones y capacidad máxima del destino.
    """

    __tablename__ = "indicadores_destino"

    id_indicador: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_nuevo_uuid,
        comment="UUID v4 identificador único del indicador"
    )
    destino_nombre: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="Nombre del destino al que pertenece el indicador"
    )
    fuente: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Fuente estadística: eurostat | ine | unwto | booking"
    )
    tipo_indicador: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Tipo de indicador (e.g. nivel_ocupacion, pernoctaciones_anuales, llegadas)"
    )
    valor: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Valor numérico del indicador"
    )
    anio: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Año al que corresponde el indicador"
    )
    mes: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Mes (1-12) al que corresponde el indicador; None si es anual"
    )
    fecha_extraccion: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=_ahora_utc,
        comment="Marca temporal de extracción del indicador"
    )

    def __repr__(self) -> str:
        return (
            f"<IndicadorDestino id={self.id_indicador!r} destino={self.destino_nombre!r} "
            f"tipo={self.tipo_indicador!r} año={self.anio}>"
        )


class Usuario(Base):
    """
    Perfil de viajero (real o sintético) del sistema de recomendación.

    Corresponde a la tabla ``usuarios``. Las preferencias temáticas deben
    sumar 1.0 ± 0.01 (validado en la capa de generación de usuarios sintéticos).
    """

    __tablename__ = "usuarios"

    id_usuario: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_nuevo_uuid,
        comment="UUID v4 identificador único del usuario"
    )
    es_sintetico: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="True si el perfil fue generado sintéticamente para entrenamiento"
    )

    # -- Preferencias temáticas (deben sumar 1.0 ± 0.01)
    pref_cultura: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="Interés en cultura en [0, 1]"
    )
    pref_gastronomia: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="Interés en gastronomía en [0, 1]"
    )
    pref_naturaleza: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="Interés en naturaleza en [0, 1]"
    )
    pref_playa: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="Interés en playa en [0, 1]"
    )
    pref_bienestar: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="Interés en bienestar en [0, 1]"
    )
    pref_aventura: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="Interés en aventura en [0, 1]"
    )

    # -- Restricciones de viaje
    presupuesto_min_eur: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Presupuesto mínimo en euros"
    )
    presupuesto_max_eur: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Presupuesto máximo en euros"
    )
    duracion_min_dias: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Duración mínima preferida del viaje en días"
    )
    duracion_max_dias: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Duración máxima preferida del viaje en días"
    )
    temporada_preferida: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
        comment="Temporada preferida: Alta | Media | Baja"
    )
    requiere_accesibilidad: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="True si el usuario requiere destinos con accesibilidad mejorada"
    )
    distancia_max_km: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Distancia máxima de vuelo tolerada en kilómetros"
    )
    interes_sostenibilidad: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="Interés declarado en sostenibilidad en [0, 1]"
    )

    # -- Metadatos
    mercado: Mapped[str | None] = mapped_column(
        String(2), nullable=True,
        comment="Mercado de procedencia del usuario: es | de | en"
    )
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_ahora_utc,
        comment="Fecha y hora de creación del perfil"
    )
    seed_generacion: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Semilla aleatoria usada para generar el perfil sintético"
    )

    # -- Relaciones
    interacciones: Mapped[list["Interaccion"]] = relationship(
        "Interaccion",
        back_populates="usuario",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        tipo = "sintético" if self.es_sintetico else "real"
        return f"<Usuario id={self.id_usuario!r} tipo={tipo} mercado={self.mercado!r}>"


class Interaccion(Base):
    """
    Registro de interacción de un usuario con un paquete turístico.

    Corresponde a la tabla ``interacciones``. Almacena visualizaciones,
    reservas y valoraciones con su valor numérico y marca temporal.
    """

    __tablename__ = "interacciones"

    id_interaccion: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_nuevo_uuid,
        comment="UUID v4 identificador único de la interacción"
    )
    id_usuario: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("usuarios.id_usuario", ondelete="CASCADE"),
        nullable=False,
        comment="FK al usuario que realizó la interacción"
    )
    id_paquete: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("paquetes.id_paquete", ondelete="CASCADE"),
        nullable=False,
        comment="FK al paquete con el que se interaccionó"
    )
    tipo: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Tipo de interacción: visualizacion | reserva | valoracion"
    )
    valor: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Valor numérico de la interacción (e.g. puntuación 1-5 en valoración)"
    )
    timestamp_interaccion: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_ahora_utc,
        comment="Marca temporal del momento de la interacción"
    )

    # -- Relaciones
    usuario: Mapped["Usuario"] = relationship(
        "Usuario",
        back_populates="interacciones",
    )
    paquete: Mapped["Paquete"] = relationship(
        "Paquete",
        back_populates="interacciones",
    )

    def __repr__(self) -> str:
        return (
            f"<Interaccion id={self.id_interaccion!r} tipo={self.tipo!r} "
            f"usuario={self.id_usuario!r} paquete={self.id_paquete!r}>"
        )


class EmbeddingMeta(Base):
    """
    Metadatos del vector semántico de un paquete almacenado en Chroma/pgvector.

    Corresponde a la tabla ``embeddings_meta``. Se actualiza cada vez que el
    Embedder regenera el vector de un paquete (RF-3.5).
    """

    __tablename__ = "embeddings_meta"

    id_paquete: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("paquetes.id_paquete", ondelete="CASCADE"),
        primary_key=True,
        comment="FK al paquete propietario del embedding (clave primaria)"
    )
    modelo_nombre: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="Nombre del modelo de embeddings utilizado"
    )
    modelo_version: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Versión del modelo de embeddings"
    )
    embedding_dim: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Dimensión del vector de embedding generado"
    )
    fecha_generacion: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_ahora_utc,
        comment="Fecha y hora de generación o actualización del embedding"
    )
    chroma_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
        comment="Identificador interno en la colección Chroma/pgvector"
    )

    def __repr__(self) -> str:
        return (
            f"<EmbeddingMeta paquete={self.id_paquete!r} "
            f"modelo={self.modelo_nombre!r} dim={self.embedding_dim}>"
        )


class PaqueteVersion(Base):
    """
    Versión histórica de un paquete turístico (snapshot inmutable).

    Corresponde a la tabla ``paquetes_versiones``. Permite reconstruir el
    estado del catálogo en cualquier fecha anterior (RF-4.5).
    El hash SHA-256 del JSON del registro se calcula al crear la versión.
    """

    __tablename__ = "paquetes_versiones"

    id_version: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_nuevo_uuid,
        comment="UUID v4 identificador único de la versión"
    )
    id_paquete: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("paquetes.id_paquete", ondelete="CASCADE"),
        nullable=False,
        comment="FK al paquete del que es versión"
    )
    timestamp_version: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_ahora_utc,
        comment="Marca temporal del momento de creación de la versión"
    )
    hash_contenido: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="Hash SHA-256 del JSON serializado del registro (64 caracteres hex)"
    )
    datos_snapshot: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="Copia completa del registro en formato JSON para reconstrucción"
    )
    campo_modificado: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="Nombre del campo que motivó la nueva versión (None para inserciones)"
    )

    # -- Relaciones
    paquete: Mapped["Paquete"] = relationship(
        "Paquete",
        back_populates="versiones",
    )

    def __repr__(self) -> str:
        return (
            f"<PaqueteVersion id={self.id_version!r} paquete={self.id_paquete!r} "
            f"ts={self.timestamp_version!r}>"
        )
