from __future__ import annotations

"""Asistente conversacional para personalizar los pesos del TDRS.

El módulo funciona en dos modos:
1. IA externa: si ``TUI_AI_ENDPOINT`` está configurado, envía la conversación a
   ese endpoint y espera una respuesta estructurada.
2. Fallback local: interpreta frases sencillas para que la interfaz siga siendo
   demostrable aunque todavía no exista una IA conectada.

La IA no calcula el ranking. Su función es conversar, recoger preferencias del
usuario y traducirlas a los cinco pesos que ya consume el modelo TDRS.
"""

import json
import os
import re
import unicodedata
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MODEL_FIELDS = (
    "sunny_days_pct",
    "low_precipitation_pct",
    "popularity",
    "hospital_beds",
    "safety",
)

PREFERENCE_FIELDS = ("popularity", "climate", "safety", "health")

FIELD_LABELS = {
    "popularity": "popularidad",
    "climate": "buen tiempo",
    "safety": "seguridad",
    "health": "capacidad sanitaria",
}

SYSTEM_PROMPT = """Eres el asistente del Simulador TDRS de TUI.
Tu objetivo es conversar de forma breve y natural para entender qué valora el
usuario en un destino y convertir esas preferencias en pesos de 0 a 100.

Solo puedes ajustar estas señales del modelo:
- sunny_days_pct: importancia de días soleados.
- low_precipitation_pct: importancia de poca precipitación.
- popularity: importancia de destinos visitados/conocidos.
- hospital_beds: importancia de capacidad sanitaria.
- safety: importancia de seguridad.

Pregunta una sola cosa cada vez cuando falte información. No inventes datos del
usuario. Explica de forma simple qué has entendido. La IA no debe alterar el
ranking directamente: únicamente propone pesos y el usuario decide si los
aplica.

Si tu integración devuelve JSON, usa este contrato:
{
  "reply": "respuesta conversacional",
  "preferences": {
    "popularity": 0-100 o null,
    "climate": 0-100 o null,
    "safety": 0-100 o null,
    "health": 0-100 o null
  },
  "weights": {
    "sunny_days_pct": 0-100,
    "low_precipitation_pct": 0-100,
    "popularity": 0-100,
    "hospital_beds": 0-100,
    "safety": 0-100
  }
}
"""


def initial_message() -> str:
    return (
        "Hola. Cuéntame cómo sería tu viaje ideal y yo iré traduciendo lo que me "
        "digas a los pesos del modelo. Por ejemplo: *quiero buen tiempo, mucha "
        "seguridad y prefiero lugares menos masificados*."
    )


def _plain(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text).lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _clamp(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return None


def normalize_preferences(data: dict[str, Any] | None) -> dict[str, int | None]:
    data = data or {}
    return {field: _clamp(data.get(field)) for field in PREFERENCE_FIELDS}


def normalize_weights(data: dict[str, Any] | None) -> dict[str, int] | None:
    if not isinstance(data, dict):
        return None
    result: dict[str, int] = {}
    for field in MODEL_FIELDS:
        value = _clamp(data.get(field))
        if value is None:
            return None
        result[field] = value
    return result


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _explicit_score(text: str, labels: tuple[str, ...]) -> int | None:
    for label in labels:
        match = re.search(rf"\b{re.escape(label)}\b\s*(?:=|:|en)?\s*(100|[0-9]{{1,2}})\b", text)
        if match:
            return _clamp(match.group(1))
    return None


def _priority_word(text: str) -> int | None:
    compact = text.strip(" .,!¿?¡")
    if compact in {"muy alta", "maxima", "máxima", "muchisima", "muchísima"}:
        return 100
    if compact in {"alta", "importante", "mucho", "mucha"}:
        return 80
    if compact in {"media", "normal", "moderada", "moderado"}:
        return 60
    if compact in {"baja", "poca", "poco"}:
        return 35
    if compact in {"ninguna", "nada", "me da igual", "indiferente"}:
        return 20
    return None


def extract_preferences(
    prompt: str,
    current: dict[str, Any] | None = None,
    focus_field: str | None = None,
) -> dict[str, int | None]:
    """Extrae señales básicas del lenguaje natural sin depender de una IA."""
    prefs = normalize_preferences(current)
    text = _plain(prompt)

    # Una respuesta corta como "alta" se aplica a la pregunta que el asistente
    # acaba de formular.
    priority = _priority_word(text)
    if priority is not None and focus_field in PREFERENCE_FIELDS:
        prefs[focus_field] = priority

    explicit = {
        "popularity": _explicit_score(text, ("popularidad", "popular")),
        "climate": _explicit_score(text, ("clima", "buen tiempo", "sol")),
        "safety": _explicit_score(text, ("seguridad", "seguro")),
        "health": _explicit_score(text, ("sanidad", "salud", "hospitales", "capacidad sanitaria")),
    }
    for field, value in explicit.items():
        if value is not None:
            prefs[field] = value

    # Popularidad: se detectan primero las expresiones negativas para evitar que
    # "poco turístico" se interprete como alta popularidad.
    if _contains_any(text, (
        "menos masificado", "poco masificado", "sin masas", "sin mucha gente",
        "poco turistico", "poco turisticos", "menos turistico", "menos turisticos", "lugares tranquilos", "sitios tranquilos",
        "destinos tranquilos", "autentico", "autentica", "descubrir", "explorar",
        "fuera de lo tipico", "menos conocido", "poco conocido",
    )):
        prefs["popularity"] = 25
    elif _contains_any(text, (
        "muy popular", "muy conocido", "muy famosa", "muy famoso", "iconico", "iconica",
        "lugares conocidos", "destinos conocidos", "turistico", "turistica", "animado",
        "vida nocturna", "mucho ambiente",
    )):
        prefs["popularity"] = 90
    elif "equilibr" in text and prefs["popularity"] is None:
        prefs["popularity"] = 65

    # Clima.
    if _contains_any(text, (
        "buen tiempo", "mucho sol", "soleado", "soleada", "playa", "calor",
        "poca lluvia", "sin lluvia", "clima agradable", "tiempo estable", "seco", "seca",
    )) or re.search(r"\bsol\b", text):
        prefs["climate"] = 90
    elif _contains_any(text, (
        "clima me da igual", "me da igual el clima", "no me importa el clima",
        "el tiempo me da igual", "no priorizo el clima",
    )):
        prefs["climate"] = 30

    # Seguridad.
    if _contains_any(text, (
        "muy seguro", "mucha seguridad", "seguridad alta", "priorizo seguridad",
        "seguridad es importante", "seguro", "segura", "tranquilidad",
    )):
        prefs["safety"] = 95
    elif _contains_any(text, (
        "seguridad me da igual", "me da igual la seguridad", "no priorizo seguridad",
    )):
        prefs["safety"] = 35

    # Sanidad/capacidad sanitaria.
    if _contains_any(text, (
        "buena sanidad", "capacidad sanitaria", "hospital", "hospitales", "atencion medica",
        "servicios medicos", "sanidad importante", "salud importante",
    )):
        prefs["health"] = 90
    elif _contains_any(text, (
        "sanidad me da igual", "me da igual la sanidad", "no priorizo sanidad",
        "no me importa la sanidad",
    )):
        prefs["health"] = 35

    return prefs


def build_weights(
    preferences: dict[str, Any] | None,
    scenario_defaults: dict[str, Any],
) -> dict[str, int]:
    """Traduce preferencias a los cinco pesos que consume el TDRS.

    Los campos todavía no conversados conservan el valor del escenario activo;
    así el asistente solo cambia aquello que realmente ha aprendido del usuario.
    """
    prefs = normalize_preferences(preferences)
    result = {field: _clamp(scenario_defaults.get(field)) or 0 for field in MODEL_FIELDS}

    if prefs["climate"] is not None:
        result["sunny_days_pct"] = prefs["climate"]
        result["low_precipitation_pct"] = prefs["climate"]
    if prefs["popularity"] is not None:
        result["popularity"] = prefs["popularity"]
    if prefs["health"] is not None:
        result["hospital_beds"] = prefs["health"]
    if prefs["safety"] is not None:
        result["safety"] = prefs["safety"]
    return result


def missing_preferences(preferences: dict[str, Any] | None) -> list[str]:
    prefs = normalize_preferences(preferences)
    return [field for field in PREFERENCE_FIELDS if prefs[field] is None]


def _summary_fragment(preferences: dict[str, Any]) -> str:
    prefs = normalize_preferences(preferences)
    chunks: list[str] = []
    if prefs["popularity"] is not None:
        if prefs["popularity"] <= 40:
            chunks.append("menos masificación")
        elif prefs["popularity"] >= 80:
            chunks.append("destinos conocidos")
        else:
            chunks.append("popularidad equilibrada")
    if prefs["climate"] is not None:
        chunks.append("buen tiempo" if prefs["climate"] >= 70 else "clima secundario")
    if prefs["safety"] is not None:
        chunks.append("seguridad alta" if prefs["safety"] >= 70 else "seguridad flexible")
    if prefs["health"] is not None:
        chunks.append("buena capacidad sanitaria" if prefs["health"] >= 70 else "sanidad con menor peso")
    return ", ".join(chunks)


def _question_for(field: str) -> str:
    questions = {
        "popularity": "¿Prefieres destinos muy conocidos o lugares menos masificados y por descubrir?",
        "climate": "¿Qué importancia tiene para ti encontrar buen tiempo y poca lluvia: baja, media, alta o muy alta?",
        "safety": "¿Qué importancia tiene la seguridad del destino: baja, media, alta o muy alta?",
        "health": "¿Y la capacidad sanitaria del destino: baja, media, alta o muy alta?",
    }
    return questions[field]


def _local_reply(preferences: dict[str, Any]) -> tuple[str, str | None]:
    missing = missing_preferences(preferences)
    understood = _summary_fragment(preferences)
    lead = f"Entendido. De momento recojo **{understood}**. " if understood else "Entendido. "
    if missing:
        next_field = missing[0]
        return lead + _question_for(next_field), next_field
    return (
        lead
        + "Ya tengo suficiente información para proponerte una configuración. "
          "Puedes aplicarla al modelo y seguir conversando si quieres afinarla.",
        None,
    )


def ai_connection_status() -> str:
    return "connected" if os.getenv("TUI_AI_ENDPOINT", "").strip() else "local"


def _call_external_ai(
    prompt: str,
    messages: list[dict[str, str]],
    preferences: dict[str, Any],
    scenario: str,
    scenario_defaults: dict[str, Any],
    focus_field: str | None,
) -> dict[str, Any] | None:
    endpoint = os.getenv("TUI_AI_ENDPOINT", "").strip()
    if not endpoint:
        return None

    payload = {
        "system_prompt": SYSTEM_PROMPT,
        "message": prompt,
        "conversation": messages[-12:],
        "context": {
            "scenario": scenario,
            "current_preferences": normalize_preferences(preferences),
            "scenario_default_weights": scenario_defaults,
            "focus_field": focus_field,
        },
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    api_key = os.getenv("TUI_AI_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    timeout = float(os.getenv("TUI_AI_TIMEOUT", "20"))
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return None


def converse(
    prompt: str,
    messages: list[dict[str, str]],
    preferences: dict[str, Any] | None,
    scenario: str,
    scenario_defaults: dict[str, Any],
    focus_field: str | None = None,
) -> dict[str, Any]:
    """Procesa un turno conversacional y devuelve respuesta + propuesta de pesos."""
    local_preferences = extract_preferences(prompt, preferences, focus_field=focus_field)
    external = _call_external_ai(
        prompt,
        messages,
        local_preferences,
        scenario,
        scenario_defaults,
        focus_field,
    )

    if external:
        external_prefs = normalize_preferences(external.get("preferences"))
        merged = dict(local_preferences)
        for field, value in external_prefs.items():
            if value is not None:
                merged[field] = value

        weights = normalize_weights(external.get("weights")) or build_weights(merged, scenario_defaults)
        reply = str(external.get("reply") or external.get("message") or "").strip()
        local_reply, next_field = _local_reply(merged)
        if not reply:
            reply = local_reply
        # Si la IA no declara el siguiente foco, seguimos preguntando por el
        # primer criterio pendiente para soportar respuestas cortas posteriores.
        declared_focus = external.get("focus_field")
        if declared_focus not in PREFERENCE_FIELDS:
            declared_focus = next_field
        return {
            "reply": reply,
            "preferences": merged,
            "weights": weights,
            "missing": missing_preferences(merged),
            "focus_field": declared_focus,
            "source": "ai",
        }

    reply, next_field = _local_reply(local_preferences)
    return {
        "reply": reply,
        "preferences": local_preferences,
        "weights": build_weights(local_preferences, scenario_defaults),
        "missing": missing_preferences(local_preferences),
        "focus_field": next_field,
        "source": "local",
    }
