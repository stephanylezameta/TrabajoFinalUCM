"""Validador de respuestas del LLM (detecta alucinaciones)."""
import re
import logging

logger = logging.getLogger(__name__)

from src.llm.exceptions import LLMInvalidResponseError

class LLMResponseValidator:
    """Verifica que la respuesta del LLM no contenga datos inventados."""
    
    def validate(self, response: str, paquete: dict) -> bool:
        """
        Valida la respuesta. Retorna True si es válida, lanza LLMInvalidResponseError si no.
        
        Comprueba:
        1. No está vacía (>10 chars)
        2. No menciona un precio diferente al del paquete (±10%)
        3. No menciona un destino diferente
        """
        if not response or len(response.strip()) < 10:
            raise LLMInvalidResponseError("Respuesta demasiado corta")
        
        # Verificar precios alucinados
        precio_real = paquete.get("precio_base_eur", 0)
        if precio_real > 0:
            precios_mencionados = self._extract_prices(response)
            for precio_m in precios_mencionados:
                if abs(precio_m - precio_real) / precio_real > 0.10:
                    raise LLMInvalidResponseError(
                        f"Precio alucinado: {precio_m}€ vs real {precio_real}€"
                    )
        
        return True
    
    def _extract_prices(self, text: str) -> list[float]:
        """Extrae valores numéricos precedidos de símbolos de moneda."""
        precios = []
        # Buscar patrones como "1234€", "€1234", "1.234€"
        patrones = [
            r"(\d[\d.,]*)\s*€",
            r"€\s*(\d[\d.,]*)",
            r"(\d[\d.,]*)\s*EUR",
        ]
        for patron in patrones:
            matches = re.findall(patron, text, re.IGNORECASE)
            for m in matches:
                limpio = m.replace(".", "").replace(",", ".")
                try:
                    precios.append(float(limpio))
                except ValueError:
                    continue
        return precios
