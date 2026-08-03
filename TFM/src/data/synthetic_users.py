"""
Generador de usuarios sintéticos para entrenamiento del modelo.

Genera perfiles de viajero coherentes usando distribuciones estadísticas:
- Preferencias temáticas: Dirichlet(alpha=[1,1,1,1,1,1]) → suma = 1.0
- Presupuesto: lognormal(mu=7.0, sigma=0.5) → rango [300, 5000] EUR
- Duración: randint(3, 21) días
- Accesibilidad: Bernoulli(0.15)
- Interés sostenibilidad: Beta(2, 5)
"""
import logging
import numpy as np
from datetime import datetime
from src.data.models import Usuario

logger = logging.getLogger(__name__)

class SyntheticUserGenerator:
    """Genera perfiles de viajero sintéticos para entrenamiento."""
    
    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed
        self.rng = np.random.default_rng(random_seed)
    
    def generate_batch(self, n: int = 500) -> list[Usuario]:
        """Genera N perfiles coherentes."""
        usuarios = []
        for i in range(n):
            usuario = self._generar_usuario(i)
            if self.validate_coherence(usuario):
                usuarios.append(usuario)
        
        # Deduplicar (RF-2.5)
        usuarios_unicos = self._deduplicar(usuarios)
        logger.info("SyntheticUserGenerator: %d usuarios generados (%d tras deduplicar)", n, len(usuarios_unicos))
        return usuarios_unicos
    
    def _generar_usuario(self, index: int) -> Usuario:
        """Genera un usuario individual."""
        import uuid
        
        # Preferencias temáticas via Dirichlet → suma = 1.0
        prefs = self.rng.dirichlet(alpha=[1, 1, 1, 1, 1, 1])
        
        # Presupuesto: lognormal
        presupuesto_centro = float(np.exp(self.rng.normal(7.0, 0.5)))
        presupuesto_centro = max(300, min(5000, presupuesto_centro))
        presupuesto_min = max(300, presupuesto_centro * self.rng.uniform(0.6, 0.8))
        presupuesto_max = min(5000, presupuesto_centro * self.rng.uniform(1.2, 1.5))
        
        # Duración
        duracion_centro = int(self.rng.integers(3, 21))
        duracion_min = max(1, duracion_centro - int(self.rng.integers(1, 4)))
        duracion_max = min(30, duracion_centro + int(self.rng.integers(1, 4)))
        
        # Temporada preferida
        temporada = self.rng.choice(["Alta", "Media", "Baja", None], p=[0.3, 0.3, 0.2, 0.2])
        
        # Accesibilidad: Bernoulli(0.15)
        requiere_accesibilidad = bool(self.rng.random() < 0.15)
        
        # Interés en sostenibilidad: Beta(2, 5) → sesgado hacia valores bajos/medios
        interes_sostenibilidad = float(self.rng.beta(2, 5))
        
        # Mercado
        mercado = str(self.rng.choice(["es", "de", "en"]))
        
        return Usuario(
            id_usuario=str(uuid.uuid4()),
            es_sintetico=True,
            pref_cultura=float(prefs[0]),
            pref_gastronomia=float(prefs[1]),
            pref_naturaleza=float(prefs[2]),
            pref_playa=float(prefs[3]),
            pref_bienestar=float(prefs[4]),
            pref_aventura=float(prefs[5]),
            presupuesto_min_eur=round(presupuesto_min, 2),
            presupuesto_max_eur=round(presupuesto_max, 2),
            duracion_min_dias=duracion_min,
            duracion_max_dias=duracion_max,
            temporada_preferida=temporada if temporada else None,
            requiere_accesibilidad=requiere_accesibilidad,
            distancia_max_km=float(self.rng.uniform(1000, 8000)) if self.rng.random() > 0.5 else None,
            interes_sostenibilidad=round(interes_sostenibilidad, 3),
            mercado=mercado,
            fecha_creacion=datetime.utcnow(),
            seed_generacion=self.random_seed,
        )
    
    def validate_coherence(self, usuario: Usuario) -> bool:
        """Verifica que la suma de preferencias ∈ [0.99, 1.01]."""
        suma = (usuario.pref_cultura + usuario.pref_gastronomia + 
                usuario.pref_naturaleza + usuario.pref_playa + 
                usuario.pref_bienestar + usuario.pref_aventura)
        return abs(suma - 1.0) <= 0.01
    
    def _deduplicar(self, usuarios: list[Usuario]) -> list[Usuario]:
        """Elimina usuarios con atributos idénticos."""
        vistos = set()
        unicos = []
        for u in usuarios:
            clave = (
                round(u.pref_cultura, 4), round(u.pref_gastronomia, 4),
                round(u.pref_naturaleza, 4), round(u.pref_playa, 4),
                round(u.pref_bienestar, 4), round(u.pref_aventura, 4),
                round(u.presupuesto_min_eur, 0), round(u.presupuesto_max_eur, 0),
                u.duracion_min_dias, u.duracion_max_dias,
                u.temporada_preferida, u.requiere_accesibilidad,
            )
            if clave not in vistos:
                vistos.add(clave)
                unicos.append(u)
        eliminados = len(usuarios) - len(unicos)
        if eliminados > 0:
            logger.info("SyntheticUserGenerator: %d duplicados eliminados", eliminados)
        return unicos
