"""
Genera 500 usuarios sintéticos y los persiste en la BD.

Uso:
    cd /d D:\Master\TrabajoFinalUCM\TFM
    python scripts/generate_synthetic_users.py
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.repository import Repositorio
from src.data.synthetic_users import SyntheticUserGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

def main():
    database_url = "sqlite:///data/sample_tui.db"
    
    print("Generando usuarios sintéticos...")
    generator = SyntheticUserGenerator(random_seed=42)
    usuarios = generator.generate_batch(n=1000)
    
    print(f"  -> {len(usuarios)} usuarios generados (coherentes y únicos)")
    
    # Recopilar estadísticas ANTES de persistir (evita DetachedInstanceError)
    import numpy as np
    prefs = [(u.pref_cultura, u.pref_gastronomia, u.pref_naturaleza, 
              u.pref_playa, u.pref_bienestar, u.pref_aventura) for u in usuarios]
    prefs_arr = np.array(prefs)
    presupuestos_min = [u.presupuesto_min_eur for u in usuarios]
    presupuestos_max = [u.presupuesto_max_eur for u in usuarios]
    accesibilidad_count = sum(1 for u in usuarios if u.requiere_accesibilidad)
    sostenibilidad_vals = [u.interes_sostenibilidad for u in usuarios]
    total_usuarios = len(usuarios)
    
    # Persistir
    repo = Repositorio(database_url)
    repo.crear_tablas()
    
    insertados = 0
    with repo.SessionLocal() as sesion:
        for usuario in usuarios:
            try:
                sesion.add(usuario)
                insertados += 1
            except Exception as e:
                print(f"  [WARN] Error: {e}")
        sesion.commit()
    
    print(f"  -> {insertados} usuarios persistidos en {database_url}")
    
    # Mostrar estadísticas (usando datos pre-calculados)
    print(f"\n{'='*50}")
    print(f"  USUARIOS SINTÉTICOS GENERADOS")
    print(f"{'='*50}")
    print(f"  Total: {insertados}")
    print(f"  Pref. dominante media: {['cultura','gastro','natura','playa','bienestar','aventura'][prefs_arr.mean(axis=0).argmax()]}")
    print(f"  Presupuesto medio: {np.mean(presupuestos_min):.0f}-{np.mean(presupuestos_max):.0f}€")
    print(f"  % requiere accesibilidad: {accesibilidad_count/total_usuarios*100:.1f}%")
    print(f"  Interés sostenibilidad medio: {np.mean(sostenibilidad_vals):.3f}")
    print(f"{'='*50}\n")

if __name__ == "__main__":
    main()
