"""API REST del Motor de Recomendación TUI."""
import logging
import time
import numpy as np
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.schemas import (
    RecomendacionRequest, PaqueteRecomendado, ExplicacionFactores,
    OportunidadMercado, MetricasModelo, HealthStatus, ModuloStatus,
    PerfilViajeroRequest,
)
from src.data.repository import Repositorio

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Motor de Recomendación TUI",
    description="API REST para recomendaciones turísticas con redistribución inteligente",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Estado global
_repo: Repositorio | None = None
_embeddings: np.ndarray | None = None
_paquete_ids: np.ndarray | None = None

def _get_repo() -> Repositorio:
    global _repo
    if _repo is None:
        _repo = Repositorio("sqlite:///data/sample_tui.db")
    return _repo

def _get_embeddings():
    global _embeddings, _paquete_ids
    if _embeddings is None:
        emb_path = Path("data/embeddings/hybrid_vectors.npy")
        ids_path = Path("data/embeddings/paquete_ids.npy")
        if emb_path.exists() and ids_path.exists():
            _embeddings = np.load(emb_path)
            _paquete_ids = np.load(ids_path, allow_pickle=True)
    return _embeddings, _paquete_ids

@app.post("/recomendaciones", response_model=list[PaqueteRecomendado])
async def get_recomendaciones(request: RecomendacionRequest):
    """Genera recomendaciones para un perfil de viajero."""
    start = time.time()
    repo = _get_repo()
    embeddings, paquete_ids = _get_embeddings()
    
    if embeddings is None:
        raise HTTPException(status_code=503, detail="Embeddings no disponibles")
    
    # Construir vector de usuario desde preferencias
    perfil = request.perfil
    user_prefs = np.array([
        perfil.pref_cultura, perfil.pref_gastronomia, perfil.pref_naturaleza,
        perfil.pref_playa, perfil.pref_bienestar, perfil.pref_aventura,
    ], dtype=np.float32)
    
    # Vector de usuario simplificado: repetir preferencias para llenar dim
    # En producción se usaría el promedio ponderado de paquetes interaccionados
    dim = embeddings.shape[1]
    user_vector = np.zeros(dim, dtype=np.float32)
    # Llenar la parte semántica con preferencias expandidas
    user_vector[:6] = user_prefs
    # Llenar atributos estructurados
    precio_norm = (perfil.presupuesto_min_eur + perfil.presupuesto_max_eur) / 2 / 3000.0
    user_vector[-7] = min(1.0, precio_norm)
    user_vector[-6] = perfil.duracion_min_dias / 14.0
    user_vector[-5] = 0.5  # ocupacion neutra
    user_vector[-3] = 0.5  # estrellas neutro
    user_vector[-1] = perfil.interes_sostenibilidad
    
    # Calcular afinidad por coseno
    norms_emb = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8
    norm_user = np.linalg.norm(user_vector) + 1e-8
    scores = (embeddings @ user_vector) / (norms_emb.flatten() * norm_user)
    scores = (scores + 1) / 2  # Normalizar a [0,1]
    
    # Top-K
    top_indices = np.argsort(scores)[::-1][:request.top_k]
    
    # Construir respuesta
    resultados = []
    paquetes_cache = {}
    for idx in top_indices:
        pkg_id = str(paquete_ids[idx])
        if pkg_id not in paquetes_cache:
            paq = repo.get_paquete(pkg_id)
            if paq:
                paquetes_cache[pkg_id] = paq
        
        paq = paquetes_cache.get(pkg_id)
        if not paq:
            continue
        
        afinidad = float(scores[idx])
        ocupacion = paq.nivel_ocupacion or 0.5
        tdrs = afinidad * 0.7 - ocupacion * 0.3  # TDRS simplificado
        score_final = afinidad  # Se refinará en Bloque 4
        
        resultados.append(PaqueteRecomendado(
            id_paquete=pkg_id,
            nombre_paquete=paq.nombre_paquete or "",
            destino_nombre=paq.destino_nombre or "",
            precio_base_eur=paq.precio_base_eur or 0,
            categoria=paq.categoria or "",
            duracion_dias=paq.duracion_dias or 7,
            temporada=paq.temporada or "Media",
            score_afinidad=round(afinidad, 4),
            tdrs=round(tdrs, 4),
            score_final=round(score_final, 4),
            descripcion_llm=paq.descripcion_texto,
            explicacion=ExplicacionFactores(
                afinidad=round(afinidad, 4),
                tdrs=round(tdrs, 4),
                saturacion=round(ocupacion, 4),
            ),
        ))
    
    elapsed = time.time() - start
    logger.info("Recomendaciones generadas en %.2fs para escenario '%s'", elapsed, request.escenario)
    return resultados

@app.get("/paquetes")
async def list_paquetes(
    region: str | None = None,
    categoria: str | None = None,
    temporada: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    """Listado paginado de paquetes con filtros."""
    repo = _get_repo()
    paquetes = repo.list_paquetes(region=region, categoria=categoria, temporada=temporada, page=page, page_size=page_size)
    return [{"id_paquete": p.id_paquete, "nombre_paquete": p.nombre_paquete, 
             "destino_nombre": p.destino_nombre, "precio_base_eur": p.precio_base_eur,
             "categoria": p.categoria, "temporada": p.temporada} for p in paquetes]

@app.get("/oportunidades", response_model=list[OportunidadMercado])
async def get_oportunidades(zona: str | None = None, temporada: str | None = None, umbral: float = 0.20):
    """Destinos con oportunidad de mercado."""
    # Placeholder — se implementará completo en Bloque 4
    return []

@app.get("/metricas", response_model=MetricasModelo)
async def get_metricas():
    """Métricas del modelo actual."""
    return MetricasModelo()

@app.get("/health", response_model=HealthStatus)
async def health_check():
    """Estado de los módulos del sistema."""
    repo_status = "ok"
    try:
        repo = _get_repo()
        repo.list_paquetes(page_size=1)
    except Exception:
        repo_status = "unavailable"
    
    emb_status = "ok" if Path("data/embeddings/hybrid_vectors.npy").exists() else "unavailable"
    
    return HealthStatus(
        scraper=ModuloStatus(status="ok", latency_ms=None),
        repositorio=ModuloStatus(status=repo_status, latency_ms=None),
        modelo_afinidad=ModuloStatus(status=emb_status, latency_ms=None),
        llm_adapter=ModuloStatus(status="ok", latency_ms=None),
    )
