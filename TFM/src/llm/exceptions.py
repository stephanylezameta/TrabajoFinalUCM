"""Jerarquía de excepciones del Bloque 5 (LLM)."""

class LLMError(Exception):
    """Error base para el módulo LLM."""
    pass

class LLMTimeoutError(LLMError):
    """La API no respondió dentro del timeout."""
    pass

class LLMRateLimitError(LLMError):
    """HTTP 429 - Rate limit de OpenAI."""
    def __init__(self, retry_after_seconds: float = 60.0):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limit. Retry after {retry_after_seconds}s")

class LLMUnavailableError(LLMError):
    """HTTP 5xx o error de red."""
    pass

class LLMEmptyResponseError(LLMError):
    """La respuesta del LLM llegó vacía."""
    pass

class LLMInvalidResponseError(LLMError):
    """La respuesta del LLM contiene datos inventados/alucinados."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Respuesta inválida: {reason}")

class BudgetExceededError(LLMError):
    """Se superó el presupuesto de tokens configurado."""
    def __init__(self, tokens_consumed: int, budget_limit: int):
        self.tokens_consumed = tokens_consumed
        self.budget_limit = budget_limit
        super().__init__(f"Budget excedido: {tokens_consumed}/{budget_limit} tokens")
