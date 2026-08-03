"""Modelos Pydantic para la API REST (FastAPI)."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional

class PerfilViajeroRequest(BaseModel):
    pref_cultura: float = Field(ge=0.0, le=1.0)
    pref_gastronomia: float = Field(ge=0.0, le=1.0)
    pref_naturaleza: float = Field(ge=0.0, le=1.0)
    pref_playa: float = Field(ge=0.0, le=1.0)
    pref_bienestar: float = Field(ge=0.0, le=1.0)
    pref_aventura: float = Field(ge=0.0, le=1.0)
    presupuesto_min_eur: float = Field(gt=0)
    presupuesto_max_eur: float = Field(gt=0)
    duracion_min_dias: int = Field(ge=1)
    duracion_max_dias: int = Field(ge=1)
    temporada_preferida: Optional[str] = None
    requiere_accesibilidad: bool = False
    distancia_max_km: Optional[float] = None
    interes_sostenibilidad: float = Field(ge=0.0, le=1.0, default=0.5)
    mercado: str = Field(default="es", pattern="^(es|de|en)$")
    
    @field_validator('pref_aventura')
    @classmethod
    def preferencias_suman_uno(cls, v, info):
        """Verifica que la suma de preferencias ≈ 1.0."""
        valores = info.data
        suma = (valores.get('pref_cultura', 0) + valores.get('pref_gastronomia', 0) +
                valores.get('pref_naturaleza', 0) + valores.get('pref_playa', 0) +
                valores.get('pref_bienestar', 0) + v)
        if abs(suma - 1.0) > 0.05:
            raise ValueError(f"La suma de preferencias debe ser ~1.0, es {suma:.3f}")
        return v

class RecomendacionRequest(BaseModel):
    perfil: PerfilViajeroRequest
    escenario: str = Field(default="moderado", pattern="^(tradicional|moderado|intensivo)$")
    top_k: int = Field(default=10, ge=1, le=50)

class ExplicacionFactores(BaseModel):
    afinidad: float
    tdrs: float
    saturacion: float
    posicion_ranking_tradicional: Optional[int] = None
    posicion_ranking_redistributivo: Optional[int] = None
    motivo_cambio_posicion: Optional[str] = None

class PaqueteRecomendado(BaseModel):
    id_paquete: str
    nombre_paquete: str
    destino_nombre: str
    precio_base_eur: float
    categoria: str
    duracion_dias: int
    temporada: str
    score_afinidad: float
    tdrs: float
    score_final: float
    descripcion_llm: Optional[str] = None
    explicacion: ExplicacionFactores

class OportunidadMercado(BaseModel):
    destino_nombre: str
    zona_geografica: str
    temporada: str
    afinidad_media: float
    nivel_ocupacion: float
    indicador_oportunidad: float
    perfil_usuario_afin: Optional[str] = None

class MetricasModelo(BaseModel):
    precision_at_5: float = 0.0
    precision_at_10: float = 0.0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    ndcg_at_5: float = 0.0
    ndcg_at_10: float = 0.0
    map_at_5: float = 0.0
    map_at_10: float = 0.0
    gini_tradicional: float = 0.0
    gini_moderado: float = 0.0
    gini_intensivo: float = 0.0
    cr5_tradicional: float = 0.0
    cr5_moderado: float = 0.0
    cr5_intensivo: float = 0.0
    intra_list_diversity: float = 0.0
    cobertura_catalogo: float = 0.0
    novedad_media: float = 0.0
    distribucion_categoria: Optional[dict[str, float]] = None

class ModuloStatus(BaseModel):
    status: str  # "ok" | "degraded" | "unavailable"
    latency_ms: Optional[float] = None

class HealthStatus(BaseModel):
    scraper: ModuloStatus
    repositorio: ModuloStatus
    modelo_afinidad: ModuloStatus
    llm_adapter: ModuloStatus
