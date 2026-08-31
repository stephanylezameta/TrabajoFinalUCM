"""
Módulo del Pipeline de Consultas (Paso 3).
-------------------------------------------------------------------------
Este script se encarga de transformar una consulta en texto natural 
realizada por un usuario en un vector híbrido listo para ser utilizado 
por el motor de recomendaciones del Paso 2.
"""

import numpy as np
from pathlib import Path
import sys

# Asegurar la ruta raíz del proyecto de forma compatible con Notebooks y Scripts
try:
    # El archivo está en scripts/recommendation/, dos niveles de profundidad
    # bajo TFM/ -> hacen falta 3 .parent, no 2, para llegar a la raíz.
    project_root = Path(__file__).resolve().parent.parent.parent
except NameError:
    project_root = Path.cwd()
    if project_root.name == "scripts":
        project_root = project_root.parent

sys.path.insert(0, str(project_root))

from src.embeddings.text_embedder import TextEmbedder
from src.embeddings.semantic_fuser import SemanticFuser
from src.embeddings.hybrid_vector_builder import HybridVectorBuilder

class QueryPipeline:
    """
    Pipeline encargado de procesar la consulta del usuario, generar su embedding 
    textual, fusionarlo y construir el vector híbrido final de búsqueda.
    """
    
    def __init__(self):
        """Inicializa los modelos de embedding y fusión necesarios para la consulta."""
        print(" Inicializando componentes del pipeline de consultas...")
        # Debe coincidir con el modelo usado para generar el catálogo
        # (ver DECISION-021: e5-large, no MiniLM). Un desajuste aquí
        # produce vectores de dimensión distinta a la del catálogo y
        # rompe la búsqueda por similitud.
        self.embedder = TextEmbedder(model_name="intfloat/multilingual-e5-large")
        self.fuser = SemanticFuser(package_weight=0.6, review_weight=0.4)
        self.builder = HybridVectorBuilder()
        
    def process_query(self, text_query: str, target_attributes: dict = None) -> np.ndarray:
        """
        Convierte una consulta de texto y atributos opcionales en un vector híbrido de 391 dimensiones.
        
        Args:
            text_query (str): Texto introducido por el usuario (ej. "Hotel de lujo en la playa con spa").
            target_attributes (dict, optional): Atributos normalizados. Si no se especifican, 
                                                se asignan valores neutros por defecto.
                                                
        Returns:
            np.ndarray: Vector híbrido de la consulta listo para el recomendador.
        """
        # 1. Generar el embedding del texto de la consulta del usuario
        # e5-large requiere el prefijo "query: " en el texto de busqueda
        # (asimetrico respecto al catalogo, que usa "passage: " -- ver
        # generate_embeddings.py). Sin este prefijo, el espacio vectorial
        # de la consulta no queda alineado con el del catalogo.
        text_emb = self.embedder.embed_text(f"query: {text_query}")
        
        # 2. Fusionar el texto con un contexto base (reutilizamos el embedding de texto 
        # o un contexto neutro para mantener la simetría con los vectores de los paquetes)
        fused_emb = self.fuser.fuse(text_emb, text_emb)
        
        # 3. Definir atributos estructurados por defecto (valores neutros o medios)
        if target_attributes is None:
            # Valores neutros/medios por defecto, todos en rango [0,1]
            # (antes nivel_ocupacion=1.5, fuera de rango, rompía el TDRS).
            target_attributes = {
                "precio_base_eur_norm": 0.5,
                "duracion_dias_norm": 0.5,
                "nivel_ocupacion": 0.5,
                "accesibilidad_destino_norm": 0.5,
                "estrellas_hotel_norm": 0.5,
                "num_valoraciones_hotel_norm": 0.5,
                "indicador_sostenibilidad_tui": 0.5,
            }
            
        # 4. Construir el vector híbrido final combinando semántica y atributos
        query_vector = self.builder.build(fused_emb, target_attributes)
        
        return query_vector

# Bloque de prueba unitaria del pipeline
if __name__ == "__main__":
    try:
        pipeline = QueryPipeline()
        
        consulta_usuario = "Busco unas vacaciones relajantes en la playa con buen clima y hotel de 4 estrellas"
        print(f"\n Procesando consulta de prueba: '{consulta_usuario}'")
        
        vector_generado = pipeline.process_query(consulta_usuario)
        
        print(f"✅ Vector de consulta generado con éxito.")
        print(f"   - Forma del vector (Dimensiones): {vector_generado.shape}")
        
    except Exception as e:
        print(f"❌ Error en el pipeline de consulta: {e}")