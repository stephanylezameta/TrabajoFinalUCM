"""Motor de plantillas predefinidas (fallback cuando el LLM no está disponible)."""
import logging

logger = logging.getLogger(__name__)

class FallbackTemplateEngine:
    """Genera texto desde plantillas trilingües cuando el LLM no está disponible."""
    
    TEMPLATES = {
        "es": "{nombre_paquete} en {destino_nombre}: una experiencia de {categoria} durante {duracion_dias} días desde {precio_base_eur:.0f}€. {frase_preferencia} {frase_sostenibilidad}",
        "de": "{nombre_paquete} in {destino_nombre}: ein {categoria}-Erlebnis für {duracion_dias} Tage ab {precio_base_eur:.0f}€. {frase_preferencia} {frase_sostenibilidad}",
        "en": "{nombre_paquete} in {destino_nombre}: a {categoria} experience for {duracion_dias} days from {precio_base_eur:.0f}€. {frase_preferencia} {frase_sostenibilidad}",
    }
    
    FRASES_PREFERENCIA = {
        "es": "Ideal para amantes de {preferencia}.",
        "de": "Ideal für {preferencia}-Liebhaber.",
        "en": "Perfect for {preferencia} lovers.",
    }
    
    FRASES_SOSTENIBILIDAD = {
        "es": "Destino comprometido con el turismo sostenible.",
        "de": "Nachhaltiges Reiseziel.",
        "en": "A destination committed to sustainable tourism.",
    }
    
    def generate(self, paquete: dict, perfil: dict) -> str:
        """
        Genera descripción desde plantilla. Nunca retorna vacío ni None.
        Siempre contiene destino_nombre y categoria como substrings.
        """
        idioma = perfil.get("mercado", "es")
        template = self.TEMPLATES.get(idioma, self.TEMPLATES["es"])
        
        # Preferencia dominante
        prefs = {
            "pref_cultura": perfil.get("pref_cultura", 0),
            "pref_gastronomia": perfil.get("pref_gastronomia", 0),
            "pref_naturaleza": perfil.get("pref_naturaleza", 0),
            "pref_playa": perfil.get("pref_playa", 0),
            "pref_bienestar": perfil.get("pref_bienestar", 0),
            "pref_aventura": perfil.get("pref_aventura", 0),
        }
        pref_dominante = max(prefs, key=prefs.get).replace("pref_", "")
        
        frase_pref = self.FRASES_PREFERENCIA.get(idioma, self.FRASES_PREFERENCIA["es"]).format(preferencia=pref_dominante)
        
        # Sostenibilidad solo si TDRS > 0.6
        frase_sost = ""
        if paquete.get("tdrs", 0) > 0.6:
            frase_sost = self.FRASES_SOSTENIBILIDAD.get(idioma, self.FRASES_SOSTENIBILIDAD["es"])
        
        resultado = template.format(
            nombre_paquete=paquete.get("nombre_paquete", "Paquete"),
            destino_nombre=paquete.get("destino_nombre", "Destino"),
            categoria=paquete.get("categoria", "turismo"),
            duracion_dias=paquete.get("duracion_dias", 7),
            precio_base_eur=paquete.get("precio_base_eur", 0),
            frase_preferencia=frase_pref,
            frase_sostenibilidad=frase_sost,
        )
        
        return resultado.strip()
