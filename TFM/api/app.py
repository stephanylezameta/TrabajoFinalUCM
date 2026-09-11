"""
API backend real, para reemplazar el placeholder que hoy usa el dashboard
("La API no respondio en el ultimo intento"). Carga el modelo UNA sola vez
al arrancar (no en cada request), y expone:

  GET  /health              -- para que Streamlit muestre "modelo conectado"
  POST /recomendar          -- llama a recomendar() directo
  POST /feedback            -- llama a registrar_feedback()
  POST /chat                -- el agente conversacional (Claude + tool use)
  POST /tdrs_ranking        -- ranking de los 39 destinos por sliders

Uso local:
    cd TFM
    pip install fastapi uvicorn anthropic
    uvicorn api.app:app --reload --port 8000
"""
import json
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from pydantic import BaseModel
import anthropic

from scripts.recommendation.run_recommendation import (
    recomendar,
    registrar_feedback,
    precargar_recursos,
    cargar_metadata_experiencias,
    cargar_clima_por_destino,
    cargar_accesibilidad_por_destino,
    cargar_capacidad_sanitaria_por_destino,
    cargar_seguridad_criminalidad_por_destino,
    cargar_sentimiento_por_destino,
    cargar_impacto_local_por_destino,
    cargar_diversificacion_por_destino,
    cargar_temporada_baja_por_destino,
    cargar_datos_humanos_por_destino,
)

app = FastAPI(title="TUI Recomendador API")

DB_PATH = os.environ.get("DB_PATH", "data/tui_recomendador.db")
client_anthropic = anthropic.Anthropic()  # lee ANTHROPIC_API_KEY del entorno
MODELO_AGENTE = "claude-sonnet-4-6"


# --------------------------------------------------------------------------
# Arranque del servicio: carga el modelo de embeddings (~2 GB), el catalogo
# vectorial y las señales de la BD UNA sola vez, cuando el contenedor arranca.
# Antes esto ocurria en cada peticion a /recomendar, lo que agotaba la memoria
# del contenedor y devolvia 503. Con la precarga en el startup, la primera
# consulta real ya encuentra todo en memoria.
# --------------------------------------------------------------------------
@app.on_event("startup")
def _precargar_modelo() -> None:
    try:
        precargar_recursos(DB_PATH)
        print("Recursos del recomendador precargados en el arranque.")
    except Exception as e:  # noqa: BLE001
        # No se bloquea el arranque: si la precarga falla, la primera peticion
        # intentara cargar bajo demanda y el error se vera alli con contexto.
        print(f"Aviso: no se pudieron precargar los recursos en el arranque: {e}")


# --------------------------------------------------------------------------
# /health -- para que el dashboard sepa si el backend esta arriba
# --------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "modelo": "conectado"}


# --------------------------------------------------------------------------
# /recomendar -- llamada directa, para el formulario de filtros manuales
# --------------------------------------------------------------------------
class RecomendarRequest(BaseModel):
    texto_consulta: str
    session_id: str | None = None
    presupuesto_max: float | None = None
    categoria: str | None = None
    destino: str | None = None
    objetivo_popularidad: float | None = None
    excluir_ids: list[str] | None = None
    excluir_destinos: list[str] | None = None
    incluir_descripcion_ia: bool = False


def generar_descripciones_ia(destinos_top: list[dict]) -> dict[str, str]:
    """Genera una descripcion cualitativa breve por destino, basandose
    UNICAMENTE en los datos reales ya calculados (datos_humanos, precio) --
    nunca inventa informacion sobre el destino que no venga de estos datos.
    Una sola llamada a Claude para todo el lote, no una por destino (mas
    barato y rapido que N llamadas separadas)."""
    if not destinos_top:
        return {}

    contexto = []
    for d in destinos_top:
        dh = d.get("datos_humanos", {})
        contexto.append({
            "destino": d["destino_nombre"],
            "precio_desde_eur": d.get("precio_eur"),
            "dias_soleados_pct": dh.get("dias_soleados_pct"),
            "sentimiento_real": dh.get("sentimiento_real"),
            "n_resenas_reales": dh.get("n_resenas_reales"),
        })

    prompt = f"""Tienes estos datos REALES de {len(contexto)} destinos turisticos:

{contexto}

Para cada destino, escribe una descripcion breve (1-2 frases, español de España)
que ayude a un viajero a decidir. Basate UNICAMENTE en los datos dados -- si un
dato es null, no lo menciones, no inventes nada que no este en la lista.

Responde EXCLUSIVAMENTE con un JSON valido, sin texto adicional, con esta forma:
{{"NombreDestino1": "descripcion...", "NombreDestino2": "descripcion..."}}"""

    try:
        respuesta = client_anthropic.messages.create(
            model=MODELO_AGENTE, max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        texto = respuesta.content[0].text.strip()
        if texto.startswith("```"):
            texto = texto.split("```")[1].replace("json", "", 1).strip()
        return json.loads(texto)
    except Exception:
        return {}  # no bloqueante: si falla, se devuelve sin descripciones


@app.post("/recomendar")
def endpoint_recomendar(req: RecomendarRequest):
    filtros = {}
    if req.presupuesto_max is not None:
        filtros["presupuesto_max"] = req.presupuesto_max
    if req.categoria is not None:
        filtros["categoria"] = req.categoria
    if req.destino is not None:
        filtros["destino"] = req.destino

    rankings, session_id = recomendar(
        texto_consulta=req.texto_consulta,
        db_path=DB_PATH,
        session_id=req.session_id,
        filtros=filtros or None,
        objetivo_popularidad=req.objetivo_popularidad,
        excluir_ids=req.excluir_ids,
        excluir_destinos=req.excluir_destinos,
    )

    if req.incluir_descripcion_ia:
        escenario_principal = "personalizado" if "personalizado" in rankings else "moderado"
        top = rankings[escenario_principal][:3]
        descripciones = generar_descripciones_ia(top)
        for escenario in rankings.values():
            for item in escenario:
                if item["destino_nombre"] in descripciones:
                    item["descripcion_ia"] = descripciones[item["destino_nombre"]]

    return {"rankings": rankings, "session_id": session_id}


# --------------------------------------------------------------------------
# /feedback -- para registrar rechazos/intereses del usuario
# --------------------------------------------------------------------------
class FeedbackRequest(BaseModel):
    session_id: str
    id_paquete: str
    senal: str  # 'rechazado' | 'interesado' | 'reservado'
    log_id: str | None = None


@app.post("/feedback")
def endpoint_feedback(req: FeedbackRequest):
    registrar_feedback(
        db_path=DB_PATH, session_id=req.session_id,
        id_paquete=req.id_paquete, senal=req.senal, log_id=req.log_id,
    )
    return {"ok": True}


# --------------------------------------------------------------------------
# /chat -- el agente conversacional completo (Claude decide cuando llamar
# a recomendar()). El historial de la conversacion lo manda el cliente
# (Streamlit) en cada request, junto con lo que el usuario acaba de escribir.
# --------------------------------------------------------------------------
TOOL_RECOMENDAR = {
    "name": "recomendar_destinos",
    "description": (
        "Busca destinos turisticos reales segun lo que pide el usuario. "
        "Usar cada vez que el usuario describa que tipo de viaje busca, "
        "incluso si ya se llamo antes y ahora pide algo distinto."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "texto_consulta": {"type": "string", "description": "Resumen en español de lo que busca el usuario."},
            "presupuesto_max": {"type": "number", "description": "Precio maximo en euros, si lo menciono."},
            "objetivo_popularidad": {
                "type": "number",
                "description": "0.0-1.0. 1.0=muy popular, 0.0=poco visitado. Default 0.5 si no hay indicio.",
            },
            "excluir_destinos": {
                "type": "array", "items": {"type": "string"},
                "description": "Destinos ya rechazados en esta conversacion.",
            },
        },
        "required": ["texto_consulta"],
    },
}

SYSTEM_PROMPT = """Eres el asistente de recomendaciones de viaje de TUI España.

IDIOMA Y TONO: responde siempre en español de España (castellano peninsular),
usando "tú" no "vos" ni "usted". Tono profesional pero cercano.

REGLA ABSOLUTA: nunca menciones "el sistema", "la herramienta", "el modelo" ni
ningun mecanismo interno. Si las opciones no encajan bien, nunca lo expliques
como una limitacion tecnica -- haz una pregunta genuina que abra el criterio.

GUIAR AL USUARIO: construye un perfil util con preguntas naturales y concretas
(presupuesto, tipo de actividad, con quien viaja) cuando la conversacion este
vaga o el usuario rechace varias opciones seguidas.

MANEJO DE RECHAZOS: agrega el destino rechazado a excluir_destinos y ajusta
la busqueda segun lo que el usuario haya dicho -- no repitas variaciones
superficiales de lo mismo.

CATALOGO CERRADO (regla inviolable): SOLO puedes recomendar destinos que
aparezcan EXACTAMENTE en la lista devuelta por la herramienta
recomendar_destinos en este turno. Tienes TERMINANTEMENTE PROHIBIDO nombrar,
sugerir o describir cualquier destino que no este en esa lista, aunque lo
conozcas o encaje mejor con lo que pide el usuario. No inventes rutas,
excursiones ni lugares que no figuren en los datos recibidos.

CUANDO EL CATALOGO NO ENCAJA: si ninguno de los destinos devueltos responde
bien a lo que pide el usuario (por ejemplo pide un tipo de viaje o una region
que no esta cubierta), NO inventes una alternativa fuera de la lista. Dilo con
naturalidad, sin excusas tecnicas, y reorienta con una pregunta que abra el
criterio hacia lo que si esta disponible. Presenta como mucho los destinos de
la lista que mas se acerquen, dejando claro en que difieren.

Presenta 2-3 destinos con razones concretas basadas en los datos reales que te
da la herramienta (categoria, precio, afinidad). Se breve."""


class ChatRequest(BaseModel):
    mensaje: str
    historial: list[dict] = []
    session_id: str | None = None


@app.post("/chat")
def endpoint_chat(req: ChatRequest):
    historial = req.historial + [{"role": "user", "content": req.mensaje}]
    session_id = req.session_id

    respuesta = client_anthropic.messages.create(
        model=MODELO_AGENTE, max_tokens=1024, system=SYSTEM_PROMPT,
        tools=[TOOL_RECOMENDAR], messages=historial,
    )

    # Se guarda el ranking estructurado de la ULTIMA llamada a la herramienta
    # para que el cliente pueda mostrar en la tarjeta destacada exactamente los
    # destinos que el chat recomienda (misma estructura que /recomendar).
    ultimo_rankings: dict | None = None
    ultimo_objetivo_popularidad: float | None = None

    bloques_tool = [b for b in respuesta.content if b.type == "tool_use"]
    if bloques_tool:
        historial.append({"role": "assistant", "content": respuesta.content})
        for bloque in bloques_tool:
            filtros = {}
            if "presupuesto_max" in bloque.input:
                filtros["presupuesto_max"] = bloque.input["presupuesto_max"]
            rankings, session_id = recomendar(
                texto_consulta=bloque.input["texto_consulta"],
                db_path=DB_PATH,
                session_id=session_id,
                filtros=filtros or None,
                objetivo_popularidad=bloque.input.get("objetivo_popularidad"),
                excluir_destinos=bloque.input.get("excluir_destinos"),
            )
            ultimo_rankings = rankings
            ultimo_objetivo_popularidad = bloque.input.get("objetivo_popularidad")
            escenario = "personalizado" if "personalizado" in rankings else "moderado"
            resultado = [
                {
                    "destino": r["destino_nombre"],
                    "precio_eur": r.get("precio_eur"),
                    "categoria": r.get("category"),
                    "afinidad": round(r["afinidad"], 3) if r.get("afinidad") is not None else None,
                    "tdrs": round(r["tdrs"], 3) if r.get("tdrs") is not None else None,
                }
                for r in rankings[escenario][:5]
            ]
            historial.append({
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": bloque.id, "content": str(resultado)}],
            })
        respuesta_final = client_anthropic.messages.create(
            model=MODELO_AGENTE, max_tokens=1024, system=SYSTEM_PROMPT,
            tools=[TOOL_RECOMENDAR], messages=historial,
        )
        texto = respuesta_final.content[0].text
        historial.append({"role": "assistant", "content": respuesta_final.content})
    else:
        texto = respuesta.content[0].text
        historial.append({"role": "assistant", "content": respuesta.content})

    return {
        "respuesta": texto,
        "historial": historial,
        "session_id": session_id,
        # Ranking estructurado de la recomendacion citada por el chat (mismo
        # formato que /recomendar). None si el agente no llamo a la herramienta
        # en este turno (p. ej. una pregunta de perfilado).
        "rankings": ultimo_rankings,
        "objetivo_popularidad": ultimo_objetivo_popularidad,
    }


# --------------------------------------------------------------------------
# /tdrs_ranking -- para la pestaña "Simulador TDRS", donde el usuario mueve
# sliders de peso y rankea el catalogo COMPLETO de 39 destinos, sin ninguna
# consulta de texto.
# --------------------------------------------------------------------------
SENALES_TDRS_RANKING = [
    "sunny_days_pct", "dry_months_pct", "popularity", "hospital_beds",
    "safety", "satisfaction", "impacto_local", "diversificacion", "temporada_baja",
]


def _cargar_todas_las_senales(db_path: str) -> dict[str, dict]:
    temp_confort, dias_secos, horas_sol = cargar_clima_por_destino(db_path)
    return {
        "sunny_days_pct": temp_confort,
        "dry_months_pct": dias_secos,
        "popularity": cargar_accesibilidad_por_destino(db_path),
        "hospital_beds": cargar_capacidad_sanitaria_por_destino(db_path),
        "safety": cargar_seguridad_criminalidad_por_destino(db_path),
        "satisfaction": cargar_sentimiento_por_destino(db_path),
        "impacto_local": cargar_impacto_local_por_destino(db_path),
        "diversificacion": cargar_diversificacion_por_destino(db_path),
        "temporada_baja": cargar_temporada_baja_por_destino(db_path),
    }


class TdrsRankingRequest(BaseModel):
    weights: dict[str, float]
    max_price: float | None = None
    max_stay_days: int | None = None


@app.post("/tdrs_ranking")
def endpoint_tdrs_ranking(req: TdrsRankingRequest):
    senales = _cargar_todas_las_senales(DB_PATH)
    metadata = cargar_metadata_experiencias(DB_PATH)
    datos_humanos = cargar_datos_humanos_por_destino(DB_PATH)

    precio_por_destino: dict[str, float] = {}
    for meta in metadata.values():
        destino = meta["destino_nombre"]
        precio = meta.get("price_eur")
        if precio is not None:
            actual = precio_por_destino.get(destino)
            if actual is None or precio < actual:
                precio_por_destino[destino] = precio

    destinos = sorted({m["destino_nombre"] for m in metadata.values()})
    total_peso = sum(max(0.0, v) for v in req.weights.values()) or 1.0

    ranked, excluded = [], []
    for destino in destinos:
        precio_ref = precio_por_destino.get(destino)

        if req.max_price is not None and precio_ref is not None and precio_ref > req.max_price:
            excluded.append({"destino_nombre": destino, "excluded_by": ["precio"]})
            continue

        score = 0.0
        contribuciones = []
        for nombre_senial, peso in req.weights.items():
            peso = max(0.0, peso)
            valor = senales.get(nombre_senial, {}).get(destino)
            contribucion = (peso / total_peso) * valor if valor is not None else 0.0
            score += contribucion
            contribuciones.append({
                "factor": nombre_senial, "peso": peso, "valor": valor, "contribucion": contribucion,
            })
        contribuciones.sort(key=lambda c: -c["contribucion"])

        ranked.append({
            "destino_nombre": destino,
            "score": round(score, 4),
            "precio_referencia_eur": precio_ref,
            "datos_humanos": datos_humanos.get(destino, {}),
            "contribuciones": contribuciones,
        })

    ranked.sort(key=lambda r: -r["score"])
    return {
        "ranked": ranked,
        "excluded": excluded,
        "señales_disponibles": SENALES_TDRS_RANKING,
        "fuente": "Datos reales del modelo TDRS (Eurostat/INE, AENA, Open-Meteo, sentimiento XLM-RoBERTa)",
    }