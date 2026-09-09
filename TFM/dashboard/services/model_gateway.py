from __future__ import annotations

"""Fachada única para hablar con el modelo de recomendación.

El dashboard demuestra que existe UN modelo y que se consume de VARIAS maneras.
Para que las tres interfaces (recomendador por filtros, asistente conversacional
y panel experto de redistribución) no dependan de una API concreta, toda la
conversación con el modelo pasa por este gateway.

El gateway es una capa fina: no reimplementa red ni contratos. Reutiliza
``recommendation_api_service`` (cliente de la Function de Azure ``func-tui-demo``,
motor entrenado ``tui_hybrid_mapped``) y expone verbos de negocio:

- ``recommend_by_filters(payload)``  -> forma 1 (formulario).
- ``recommend_by_policy(policy, ...)`` -> forma 3 (panel de redistribución):
  traduce una POLÍTICA de redistribución de demanda a un payload del contrato de
  Azure y llama al mismo modelo.

GANCHO FASE 2 (backend propio ``api/app.py``)
---------------------------------------------
La variable de entorno ``TUI_MODEL_BACKEND`` selecciona el backend:

- ``"azure"`` (por defecto): consume la Function de Azure vía
  ``recommendation_api_service``. Es lo que funciona en el despliegue público
  sin depender de ningún ``localhost``.
- ``"local"``: reservado para cuando el backend propio de FastAPI
  (``api/app.py``, ``TUI_MODELO_API_BASE``) esté desplegado de forma accesible.
  El gancho está cableado en ``_policy_backend`` pero hoy degrada a ``azure``
  con un aviso, porque ese backend solo existe en ``http://localhost:8000`` y no
  sobrevive al despliegue en Streamlit Cloud.

Mantener este módulo como fachada: la lógica de red, caché y cortacircuitos
vive en ``recommendation_api_service`` y no debe duplicarse aquí.
"""

import os
from typing import Any

from services import recommendation_api_service as reco

# Backend por defecto. "azure" hace que hoy funcione en el despliegue público.
DEFAULT_BACKEND = "azure"


def active_backend() -> str:
    """Backend seleccionado por entorno. Cualquier valor no reconocido -> azure."""
    value = os.getenv("TUI_MODEL_BACKEND", DEFAULT_BACKEND).strip().lower()
    return value if value in {"azure", "local"} else DEFAULT_BACKEND


def is_configured() -> bool:
    """El modelo es consumible si el cliente de Azure tiene endpoint."""
    return reco.is_configured()


def status() -> str:
    """Estado declarativo para la interfaz: ``configured`` | ``not_configured``."""
    return reco.api_status()


# --------------------------------------------------------------------------
# Forma 1: recomendación por filtros (formulario del Recomendador España)
# --------------------------------------------------------------------------

def recommend_by_filters(payload: dict[str, Any], use_cache: bool = True) -> dict[str, Any]:
    """Delegación directa en el cliente de Azure. No transforma el payload."""
    return reco.fetch_recommendations(payload, use_cache=use_cache)


# --------------------------------------------------------------------------
# Forma 3: recomendación por POLÍTICA de redistribución (panel experto)
# --------------------------------------------------------------------------

# La tesis del TDRS (Tourism Demand Redistribution Score) es redistribuir la
# demanda. El único parámetro del contrato de Azure que expresa "cómo de
# masificado" es ``popularity_target`` (0 = destinos poco saturados, 1 =
# turismo tradicional muy visitado). El panel lo mapea directamente.
#
# El resto de la política (qué tipo de destino favorecer) se traduce a
# ``interests`` y a la preferencia climática, que el modelo ya sabe interpretar.

# Peso de política (slider de interés) -> interés del contrato de Azure.
POLICY_INTEREST_MAP: dict[str, str] = {
    "coast_beach": "coast_beach",
    "nature_mountains": "nature_mountains",
    "history_culture": "history_culture",
    "rural": "rural",
    "gastronomy_wine": "gastronomy_wine",
    "wellness": "wellness",
    "sports_outdoors": "sports_outdoors",
}

# Umbral (0-100) por encima del cual un interés se considera "activo" en la
# política y se envía al modelo. Deja margen para que el gestor mueva sliders
# sin activar todo a la vez.
INTEREST_ACTIVE_THRESHOLD = 50

# El contrato de Azure (recommendation-request-v1) admite entre 1 y 3 intereses.
MAX_INTERESTS = 3


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def policy_to_payload(policy: dict[str, Any]) -> dict[str, Any]:
    """Traduce una política de redistribución al contrato de Azure.

    ``policy`` admite:
      - ``popularity_target`` (0.0-1.0): dial tradicional<->redistribuido. Es la
        palanca central de la tesis TDRS.
      - ``interests`` (dict interés->peso 0-100): qué tipo de destino favorecer.
        Los que superan el umbral se envían como intereses del modelo.
      - ``temperature_preference`` (str del vocabulario de Azure).
      - ``month`` / ``trip_length_days`` / ``accommodation_type`` opcionales.
      - ``include_regions`` / ``exclude_regions`` opcionales.

    Devuelve un payload válido del contrato ``recommendation-request-v1``.
    """
    defaults = reco.default_request()

    popularity_target = _clamp01(policy.get("popularity_target", defaults["popularity_target"]))

    interest_weights: dict[str, float] = policy.get("interests") or {}
    interests = [
        POLICY_INTEREST_MAP[code]
        for code, weight in sorted(interest_weights.items(), key=lambda kv: -float(kv[1]))
        if code in POLICY_INTEREST_MAP and float(weight) >= INTEREST_ACTIVE_THRESHOLD
    ]
    # El contrato de Azure exige entre 1 y 3 intereses. Como están ordenados por
    # peso descendente, nos quedamos con los tres más prioritarios.
    interests = interests[:MAX_INTERESTS]
    # Si el gestor no ha priorizado ninguno por encima del umbral, se cae al
    # interés por defecto para no romper la llamada (el contrato exige al menos 1).
    if not interests:
        interests = list(defaults["interests"])[:MAX_INTERESTS]

    temperature = policy.get("temperature_preference", defaults["temperature_preference"])
    if temperature not in reco.TEMPERATURE_LABELS:
        temperature = defaults["temperature_preference"]

    accommodation = policy.get("accommodation_type", defaults["accommodation_type"])
    if accommodation not in reco.ACCOMMODATION_LABELS:
        accommodation = defaults["accommodation_type"]

    return reco.build_payload(
        month=int(policy.get("month", defaults["month"])),
        trip_length_days=int(policy.get("trip_length_days", defaults["trip_length_days"])),
        interests=interests,
        temperature_preference=temperature,
        minimum_sunny_days=policy.get("minimum_sunny_days", defaults["minimum_sunny_days"]),
        maximum_precipitation_days=policy.get(
            "maximum_precipitation_days", defaults["maximum_precipitation_days"]
        ),
        popularity_target=popularity_target,
        accommodation_type=accommodation,
        include_regions=policy.get("include_regions") or [],
        exclude_regions=policy.get("exclude_regions") or [],
    )


def recommend_by_policy(
    policy: dict[str, Any],
    max_price: float | None = None,  # noqa: ARG001 - reservado para el backend local (FASE 2)
    use_cache: bool = True,
) -> dict[str, Any]:
    """Ranquea el catálogo aplicando una POLÍTICA de redistribución.

    Traduce la política a un payload del contrato de Azure y llama al mismo
    modelo entrenado que usa el recomendador por filtros. Devuelve el ranking ya
    normalizado (mismo formato que ``recommend_by_filters``), más el payload
    efectivo enviado bajo ``policy_payload`` para que la vista pueda explicar qué
    se pidió al modelo.

    ``max_price`` se ignora en el backend ``azure`` (el contrato de la Function
    no acepta precio); queda declarado para el gancho del backend local de la
    FASE 2, que sí lo admite (``api/app.py`` ``/tdrs_ranking``).
    """
    payload = policy_to_payload(policy)
    result = _policy_backend(payload, use_cache=use_cache)
    result = dict(result)
    result["policy_payload"] = payload
    result["backend"] = active_backend()
    return result


def _policy_backend(payload: dict[str, Any], use_cache: bool = True) -> dict[str, Any]:
    """Selecciona el backend efectivo para la recomendación por política.

    Hoy siempre resuelve contra Azure. El bloque ``local`` documenta el gancho
    de la FASE 2: cuando ``api/app.py`` esté desplegado accesible, se llamaría a
    su endpoint aquí. Mientras tanto degrada a Azure sin romper.
    """
    backend = active_backend()
    if backend == "local":
        # GANCHO FASE 2: aquí iría la llamada al backend propio
        # (``TUI_MODELO_API_BASE`` + ``/tdrs_ranking``). No se activa hoy porque
        # ese servicio solo vive en localhost y no sobrevive al despliegue.
        # Se degrada a Azure de forma transparente.
        pass
    return reco.fetch_recommendations(payload, use_cache=use_cache)
