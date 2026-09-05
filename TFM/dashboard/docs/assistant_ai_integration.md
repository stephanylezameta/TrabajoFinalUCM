# Integración del Asistente TDRS con IA

## Objetivo

La IA actúa como capa conversacional. Su responsabilidad es entender qué busca el usuario y traducir esa conversación a preferencias/pesos del modelo TDRS. La IA **no calcula el ranking** y **no cambia pesos sin confirmación** del usuario.

## Variables de entorno

```text
TUI_AI_ENDPOINT=https://tu-backend-ia/tdrs-assistant
TUI_AI_API_KEY=tu_token_opcional
TUI_AI_TIMEOUT=20
```

`TUI_AI_API_KEY` es opcional. Si existe, la app envía `Authorization: Bearer <token>`.

Si `TUI_AI_ENDPOINT` no está configurado, el asistente usa un intérprete local de demostración para mantener el flujo conversacional operativo.

## Request enviado al endpoint

La aplicación hace un `POST` JSON con una estructura equivalente a:

```json
{
  "system_prompt": "...",
  "message": "Quiero buen tiempo y lugares tranquilos",
  "conversation": [
    {"role": "assistant", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "context": {
    "scenario": "Equilibrado",
    "current_preferences": {
      "popularity": 25,
      "climate": 90,
      "safety": null,
      "health": null
    },
    "scenario_default_weights": {
      "sunny_days_pct": 70,
      "low_precipitation_pct": 60,
      "popularity": 75,
      "hospital_beds": 65,
      "safety": 80
    },
    "focus_field": "safety"
  }
}
```

## Response recomendada

```json
{
  "reply": "Entendido. Priorizas buen tiempo y destinos menos masificados. ¿Qué importancia tiene para ti la seguridad?",
  "preferences": {
    "popularity": 25,
    "climate": 90,
    "safety": null,
    "health": null
  },
  "weights": {
    "sunny_days_pct": 90,
    "low_precipitation_pct": 90,
    "popularity": 25,
    "hospital_beds": 65,
    "safety": 80
  },
  "focus_field": "safety"
}
```

Los valores se normalizan a `0–100`. Si la IA no devuelve `weights`, la app los construye a partir de `preferences` y mantiene los valores del escenario activo para los criterios todavía no conversados.

## Criterios del modelo

- `sunny_days_pct`: importancia de días soleados.
- `low_precipitation_pct`: importancia de poca precipitación.
- `popularity`: importancia de destinos visitados/conocidos.
- `hospital_beds`: importancia de capacidad sanitaria.
- `safety`: importancia de seguridad.

## Flujo de seguridad funcional

1. El usuario conversa con el asistente.
2. La IA propone preferencias/pesos.
3. La interfaz muestra `Propuesta actual`.
4. Solo al pulsar `Aplicar propuesta al modelo` se actualizan los sliders del TDRS.
5. `compute_scores` continúa siendo la única lógica que calcula el ranking.
