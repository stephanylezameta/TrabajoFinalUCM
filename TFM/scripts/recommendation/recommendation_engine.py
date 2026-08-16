"""
Módulo del Motor de Recomendación (Paso 2).
-------------------------------------------------------------------------
Este script carga los vectores híbridos generados previamente y expone 
una clase optimizada para realizar búsquedas por similitud de coseno en 
memoria.
"""

import numpy as np
from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity
import sys

# Asegurar la ruta raíz del proyecto de forma compatible con Notebooks y Scripts
try:
    project_root = Path(__file__).resolve().parent.parent
except NameError:
    project_root = Path.cwd()
    if project_root.name == "scripts":
        project_root = project_root.parent

sys.path.insert(0, str(project_root))

class TuiRecommender:
    """
    Clase principal encargada de gestionar el catálogo vectorial y 
    calcular las recomendaciones turísticas más afines a una consulta.
    """
    
    def __init__(self, embeddings_dir="data/embeddings"):
        """
        Inicializa el recomendador cargando los arrays de vectores e IDs en RAM.
        
        Args:
            embeddings_dir (str): Ruta al directorio donde se guardaron los .npy
        """
        self.embeddings_dir = Path(embeddings_dir)
        self.hybrid_matrix = None
        self.paquete_ids = None
        self.load_data()

    def load_data(self):
        """
        Carga los vectores híbridos y los identificadores de paquetes desde disco.
        Lanza un error descriptivo si los archivos no existen.
        """
        vector_path = self.embeddings_dir / "hybrid_vectors.npy"
        ids_path = self.embeddings_dir / "paquete_ids.npy"
        
        if not vector_path.exists() or not ids_path.exists():
            raise FileNotFoundError(
                f"⚠️ No se encontraron los archivos en {self.embeddings_dir}. "
                "Asegúrate de haber ejecutado el proceso de generación de embeddings."
            )
            
        self.hybrid_matrix = np.load(vector_path)
        self.paquete_ids = np.load(ids_path, allow_pickle=True)
        print(f"✅ Motor de recomendación cargado: {len(self.paquete_ids)} paquetes disponibles en memoria.")

    def search(self, query_vector: np.ndarray, top_k: int = 5):
        """
        Realiza una búsqueda por similitud de coseno contra el catálogo completo.
        
        Args:
            query_vector (np.ndarray): Vector híbrido de consulta (dimensiones texto + atributos).
            top_k (int): Número de recomendaciones principales a devolver.
            
        Returns:
            list[dict]: Lista con los IDs de los paquetes y su respectivo score de similitud.
        """
        if self.hybrid_matrix is None:
            raise ValueError("La matriz de búsqueda no está inicializada en memoria.")
            
        # Asegurar formato de matriz bidimensional (1, N) para scikit-learn
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)
            
        # Calcular similitudes de coseno frente a todos los paquetes del catálogo
        similarities = cosine_similarity(query_vector, self.hybrid_matrix)[0]
        
        # Obtener los índices ordenados de mayor a menor similitud
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        # Construir la estructura de resultados ordenada
        results = [
            {
                "id_paquete": int(self.paquete_ids[i]),
                "score_similitud": float(similarities[i])
            }
            for i in top_indices
        ]
        
        return results

# Bloque de prueba unitaria del motor
if __name__ == "__main__":
    try:
        recommender = TuiRecommender()
        
        print("\n Ejecutando prueba de búsqueda con vector sintético...")
        # Simulamos una consulta con 391 dimensiones aleatorias
        dummy_query = np.random.rand(391).astype(np.float32)
        
        resultados = recommender.search(dummy_query, top_k=3)
        
        print("Mejores recomendaciones de prueba:")
        for r in resultados:
            print(f"  - Paquete ID: {r['id_paquete']} | Score: {r['score_similitud']:.4f}")
            
    except Exception as e:
        print(f"Error al probar el motor: {e}")