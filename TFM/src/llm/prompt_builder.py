"""Construye prompts personalizados para GPT-4o-mini."""
import logging
from typing import Any

logger = logging.getLogger(__name__)

class PromptBuilder:
    """Construye el prompt personalizado para cada paquete recomendado."""
    
    IDIOMAS = {"es": "español", "de": "alemán", "en": "inglés"}
    
    PREFERENCIAS_NOMBRES = {
        "pref_cultura": {"es": "cultura", "de": "Kultur", "en": "culture"},
        "pref_gastronomia": {"es": "gastronomía", "de": "Gastronomie", "en": "gastronomy"},
        "pref_naturaleza": {"es": "naturaleza", "de": "Natur", "en": "nature"},
        "pref_playa": {"es": "playa", "de": "Strand", "en": "beach"},
        "pref_bienestar": {"es": "bienestar", "de": "Wellness", "en": "wellness"},
        "pref_aventura": {"es": "aventura", "de": "Abenteuer", "en": "adventure"},
    }
    
    def build(self, paquete: dict, perfil: dict) -> str:
        """
        Construye el prompt personalizado.
        
        Args:
            paquete: Dict con datos del paquete (nombre_paquete, destino_nombre, categoria, 
                     precio_base_eur, duracion_dias, temporada, nombre_hotel, estrellas_hotel, tdrs).
            perfil: Dict con datos del perfil (pref_*, presupuesto_min/max, duracion_min/max,
                    temporada_preferida, interes_sostenibilidad, mercado).
        """
        idioma = perfil.get("mercado", "es")
        idioma_nombre = self.IDIOMAS.get(idioma, "español")
        
        # Preferencia dominante
        pref_dominante = self._preferencia_dominante(perfil)
        pref_nombre = self.PREFERENCIAS_NOMBRES.get(pref_dominante, {}).get(idioma, pref_dominante)
        
        # Bloque de sostenibilidad (solo si TDRS > 0.6)
        bloque_sostenibilidad = ""
        tdrs = paquete.get("tdrs", 0)
        if tdrs > 0.6:
            bloque_sostenibilidad = (
                f"\n- Este destino tiene un perfil de sostenibilidad destacado (TDRS={tdrs:.2f}).\n"
                f"  Menciona brevemente el beneficio de redistribución o sostenibilidad en la descripción."
            )
        
        prompt = f"""Eres un asistente especializado en turismo. Escribe una descripción personalizada de 2-3 frases
en {idioma_nombre} para un viajero con las siguientes características:
- Preferencia principal: {pref_nombre}
- Presupuesto: entre {perfil.get('presupuesto_min_eur', 500):.0f}€ y {perfil.get('presupuesto_max_eur', 2000):.0f}€
- Duración preferida: {perfil.get('duracion_min_dias', 5)}-{perfil.get('duracion_max_dias', 14)} días
- Temporada preferida: {perfil.get('temporada_preferida', 'Indiferente')}

El paquete a describir es:
- Destino: {paquete.get('destino_nombre', '')}
- Nombre: {paquete.get('nombre_paquete', '')}
- Categoría: {paquete.get('categoria', '')}
- Precio: {paquete.get('precio_base_eur', 0):.0f}€ ({paquete.get('duracion_dias', 7)} días, {paquete.get('temporada', 'Media')})
- Hotel: {paquete.get('nombre_hotel', 'Hotel')} ({paquete.get('estrellas_hotel', 4)} estrellas){bloque_sostenibilidad}

Escribe SOLO la descripción, sin encabezados ni listas. No inventes datos que no estén en la información proporcionada."""
        
        return prompt
    
    def _preferencia_dominante(self, perfil: dict) -> str:
        """Retorna la clave de la preferencia con mayor valor."""
        prefs = {
            "pref_cultura": perfil.get("pref_cultura", 0),
            "pref_gastronomia": perfil.get("pref_gastronomia", 0),
            "pref_naturaleza": perfil.get("pref_naturaleza", 0),
            "pref_playa": perfil.get("pref_playa", 0),
            "pref_bienestar": perfil.get("pref_bienestar", 0),
            "pref_aventura": perfil.get("pref_aventura", 0),
        }
        return max(prefs, key=prefs.get)
