"""Control de presupuesto de tokens."""
import logging

logger = logging.getLogger(__name__)

try:
    import tiktoken
    TIKTOKEN_DISPONIBLE = True
except ImportError:
    TIKTOKEN_DISPONIBLE = False

class TokenCounter:
    """Estima y controla el consumo de tokens."""
    
    def __init__(self, model_name: str = "gpt-4o-mini", max_budget_tokens: int = 5_000_000):
        self.model_name = model_name
        self.max_budget_tokens = max_budget_tokens
        self._tokens_consumed = 0
        self._encoding = None
        
        if TIKTOKEN_DISPONIBLE:
            try:
                self._encoding = tiktoken.encoding_for_model(model_name)
            except Exception:
                self._encoding = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str) -> int:
        """Cuenta tokens de un texto."""
        if not text:
            return 0
        if self._encoding:
            return len(self._encoding.encode(text))
        # Estimación fallback: ~4 chars por token
        return max(1, len(text) // 4)
    
    def check_budget(self, prompt: str) -> bool:
        """Retorna True si hay presupuesto disponible para esta llamada."""
        estimated = self.count_tokens(prompt) + 200  # margen para respuesta
        return (self._tokens_consumed + estimated) <= self.max_budget_tokens
    
    def register_usage(self, tokens_input: int, tokens_output: int) -> None:
        """Acumula uso real."""
        self._tokens_consumed += tokens_input + tokens_output
        logger.debug("TokenCounter: uso acumulado = %d tokens", self._tokens_consumed)
    
    def estimated_cost_eur(self) -> float:
        """Coste estimado en EUR."""
        # GPT-4o-mini: $0.15/1M input, $0.60/1M output (estimamos 50/50)
        cost_usd = self._tokens_consumed * 0.000000375  # promedio
        return cost_usd * 0.92  # USD to EUR aprox
    
    @property
    def tokens_remaining(self) -> int:
        return max(0, self.max_budget_tokens - self._tokens_consumed)
