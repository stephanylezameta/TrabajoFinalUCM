"""Logger de uso del LLM."""
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class UsageLogger:
    """Registra uso de tokens y costes en log JSON."""
    
    def __init__(self, log_file: str = "data/llm_usage.jsonl"):
        self.log_file = log_file
    
    def log_llm_call(
        self,
        id_paquete: str,
        id_usuario: str = "",
        tokens_input: int = 0,
        tokens_output: int = 0,
        latency_ms: float = 0,
        model: str = "gpt-4o-mini",
        used_fallback: bool = False,
        fallback_reason: str | None = None,
    ) -> None:
        """Emite entrada de log con todos los campos."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "id_paquete": id_paquete,
            "id_usuario": id_usuario,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "latency_ms": round(latency_ms, 1),
            "model": model,
            "used_fallback": used_fallback,
            "fallback_reason": fallback_reason,
        }
        
        logger.info("LLM_USAGE | %s", json.dumps(entry, ensure_ascii=False))
        
        # También escribir en fichero
        try:
            from pathlib import Path
            Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.debug("UsageLogger: no se pudo escribir en fichero: %s", exc)
