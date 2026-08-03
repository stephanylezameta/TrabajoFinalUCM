"""Adaptador para la API de OpenAI (GPT-4o-mini)."""
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
    OPENAI_DISPONIBLE = True
except ImportError:
    OPENAI_DISPONIBLE = False

from src.llm.exceptions import (
    LLMTimeoutError, LLMRateLimitError, LLMUnavailableError,
    LLMEmptyResponseError, LLMError,
)

class LLMAdapter:
    """Abstracción sobre la API de OpenAI GPT-4o-mini."""
    
    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        api_key: str | None = None,
        timeout_seconds: float = 10.0,
        max_tokens_output: int = 300,
    ):
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.max_tokens_output = max_tokens_output
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._client = None
        
        if OPENAI_DISPONIBLE and self._api_key:
            self._client = OpenAI(api_key=self._api_key, timeout=timeout_seconds)
            logger.info("LLMAdapter: cliente OpenAI inicializado (modelo=%s)", model_name)
        else:
            logger.warning("LLMAdapter: OpenAI no disponible (api_key=%s, lib=%s)", 
                          bool(self._api_key), OPENAI_DISPONIBLE)
    
    def generate(self, prompt: str) -> str:
        """
        Envía prompt a OpenAI y retorna el texto generado.
        
        Raises:
            LLMTimeoutError, LLMRateLimitError, LLMUnavailableError, LLMEmptyResponseError
        """
        if not self._client:
            raise LLMUnavailableError("Cliente OpenAI no inicializado")
        
        start = time.time()
        try:
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Eres un asistente especializado en turismo."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens_output,
                temperature=0.7,
            )
            
            texto = response.choices[0].message.content
            if not texto or len(texto.strip()) < 5:
                raise LLMEmptyResponseError("Respuesta vacía del LLM")
            
            elapsed = time.time() - start
            logger.debug("LLMAdapter: respuesta en %.2fs (%d tokens)", elapsed, 
                        response.usage.total_tokens if response.usage else 0)
            
            return texto.strip()
            
        except LLMError:
            raise
        except Exception as exc:
            error_str = str(exc).lower()
            if "timeout" in error_str or "timed out" in error_str:
                raise LLMTimeoutError(f"Timeout tras {self.timeout_seconds}s") from exc
            elif "429" in error_str or "rate" in error_str:
                raise LLMRateLimitError() from exc
            elif "5" in str(getattr(exc, 'status_code', '')) or "server" in error_str:
                raise LLMUnavailableError(str(exc)) from exc
            else:
                raise LLMUnavailableError(str(exc)) from exc
    
    def is_available(self) -> bool:
        """Comprueba si la API está accesible."""
        return self._client is not None and bool(self._api_key)
    
    def get_usage_info(self, prompt: str, response_text: str) -> dict:
        """Retorna info de uso estimada."""
        from src.llm.token_counter import TokenCounter
        counter = TokenCounter(model_name=self.model_name)
        return {
            "tokens_input": counter.count_tokens(prompt),
            "tokens_output": counter.count_tokens(response_text),
            "model": self.model_name,
        }
