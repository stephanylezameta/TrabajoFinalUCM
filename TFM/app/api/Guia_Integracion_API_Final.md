# Motor de Recomendación TUI — Guía de Integración Final

Backend desplegado y en funcionamiento. Expone el modelo completo (embeddings + LightGBM + TDRS + agente conversacional) por HTTP.

**URL base (Azure, ya desplegado):**
```
https://javier-tui-recomendador-api.greenbush-59ba65d9.eastus2.azurecontainerapps.io
```

**Configuración necesaria en Streamlit Cloud** → Settings → Secrets:
```
TUI_MODELO_API_BASE=https://javier-tui-recomendador-api.greenbush-59ba65d9.eastus2.azurecontainerapps.io
```

---

## Resumen: qué endpoint usa cada pantalla

| Pantalla | Endpoint | Notas |
|---|---|---|
| Buscador principal (texto libre + escenario + sliders) | `POST /recomendar` | El motor completo, con búsqueda semántica |
| Asistente conversacional (chat) | `POST /chat` | Claude interpreta lenguaje natural y llama al motor por dentro |
| Simulador TDRS (sliders puros, sin texto, sobre los 39 destinos) | `POST /tdrs_ranking` | Ya integrado en `tdrs_service.py` — no requiere cambios |
| Botón "Saber más" sobre un destino puntual | `POST /recomendar` con `incluir_descripcion_ia: true` | Ver sección 3 |

---

## 1. `POST /recomendar` — buscador principal

### Se manda

| Campo | Tipo | Notas |
|---|---|---|
| `texto_consulta` | string | **Obligatorio.** Recomendado exigir que no esté vacío (ver sección 4) |
| `session_id` | string \| null | `null` en la primera búsqueda; reenviar el recibido en turnos siguientes |
| `objetivo_popularidad` | number 0.0–1.0 | Mapeo del selector de escenario: Tradicional≈1.0, Moderado≈0.5, Aventurero≈0.0 |
| `presupuesto_max` | number | Opcional |
| `categoria` | string | Opcional |
| `excluir_destinos` | string[] | Destinos ya mostrados, para no repetir |
| `incluir_descripcion_ia` | boolean | `false` por defecto — activar solo bajo demanda (ver sección 3) |

### Devuelve

```json
{
  "rankings": {
    "tradicional": [...],
    "moderado": [...],
    "intensivo": [...],
    "personalizado": [...]
  },
  "session_id": "..."
}
```

Usar `rankings["personalizado"]` si se mandó `objetivo_popularidad`; si no, `rankings["moderado"]` como default.

Cada destino trae, **siempre, sin necesidad de IA**:

```json
{
  "id_paquete": "EXP_100550",
  "destino_nombre": "Costa del Sol",
  "precio_eur": 100.88,
  "score_final": 0.519,
  "datos_humanos": {
    "dias_soleados_pct": 50.0,
    "precipitacion_pct": 12.5,
    "horas_sol_promedio_dia": 10.7,
    "pasajeros_anuales": 2283372,
    "camas_hospital_1000hab": 2.97,
    "tasa_homicidios_100mil": 0.63,
    "sentimiento_real": 0.58,
    "n_resenas_reales": 188
  }
}
```

`datos_humanos` ya trae valores reales listos para mostrar (clima, seguridad, sentimiento de reseñas) — no requiere ningún cálculo adicional del lado de Streamlit.

### Ejemplo completo en Streamlit

```python
import requests
import streamlit as st

API_URL = st.secrets.get("TUI_MODELO_API_BASE", "http://localhost:8000")

texto = st.text_area("Cuéntanos qué buscas")
escenario = st.radio("Estilo", ["Tradicional", "Moderado", "Aventurero"])
mapeo_popularidad = {"Tradicional": 1.0, "Moderado": 0.5, "Aventurero": 0.0}

if st.button("Buscar"):
    if not texto.strip():
        st.warning("Contanos algo de lo que buscás, aunque sea una palabra 🙂")
    else:
        r = requests.post(f"{API_URL}/recomendar", json={
            "texto_consulta": texto,
            "objetivo_popularidad": mapeo_popularidad[escenario],
            "session_id": st.session_state.get("session_id"),
        })
        data = r.json()
        st.session_state["session_id"] = data["session_id"]
        st.session_state["ultima_consulta"] = texto  # se reutiliza en "Saber más"
        top3 = data["rankings"].get("personalizado", data["rankings"]["moderado"])[:3]
        st.session_state["top3"] = top3

for destino in st.session_state.get("top3", []):
    st.subheader(destino["destino_nombre"])
    st.write(f"Desde {destino['precio_eur']} €")
    dh = destino["datos_humanos"]
    col1, col2, col3 = st.columns(3)
    col1.metric("Días soleados", f"{dh.get('dias_soleados_pct', '—')}%")
    col2.metric("Satisfacción", dh.get("sentimiento_real", "—"))
    col3.metric("Reseñas reales", dh.get("n_resenas_reales", "—"))

    if st.button(f"Saber más sobre {destino['destino_nombre']}", key=destino["id_paquete"]):
        with st.spinner("Buscando más detalles..."):
            r2 = requests.post(f"{API_URL}/recomendar", json={
                "texto_consulta": st.session_state["ultima_consulta"],
                "incluir_descripcion_ia": True,
            })
        data2 = r2.json()
        top3_extendido = data2["rankings"].get("personalizado", data2["rankings"]["moderado"])
        match = next((d for d in top3_extendido if d["destino_nombre"] == destino["destino_nombre"]), None)
        if match and "descripcion_ia" in match:
            st.info(match["descripcion_ia"])
        else:
            st.caption("No se pudo generar información adicional en este momento.")
```

---

## 2. `POST /chat` — asistente conversacional

### Se manda

```json
{
  "mensaje": "quiero playa con buen clima y poco masificada",
  "historial": [],
  "session_id": null
}
```

### Devuelve

```json
{
  "respuesta": "texto ya redactado por el agente, listo para mostrar",
  "historial": [...guardar y reenviar en el siguiente turno...],
  "session_id": "..."
}
```

El agente **ya incluye descripciones cualitativas de los destinos dentro de su respuesta narrativa** — no necesita (ni debe usar) `incluir_descripcion_ia`, esa opción es exclusiva de `/recomendar`.

### Ejemplo en Streamlit

```python
if "historial_chat" not in st.session_state:
    st.session_state.historial_chat = []
if "session_id_chat" not in st.session_state:
    st.session_state.session_id_chat = None

mensaje = st.chat_input("Cuéntame cómo sería tu viaje ideal")
if mensaje:
    st.chat_message("user").write(mensaje)
    r = requests.post(f"{API_URL}/chat", json={
        "mensaje": mensaje,
        "historial": st.session_state.historial_chat,
        "session_id": st.session_state.session_id_chat,
    })
    data = r.json()
    st.session_state.historial_chat = data["historial"]
    st.session_state.session_id_chat = data["session_id"]
    st.chat_message("assistant").write(data["respuesta"])
```

---

## 3. Descripciones cualitativas bajo demanda (`incluir_descripcion_ia`)

**Por qué es opcional y no automático**: cada activación implica una llamada adicional a Claude (uno o dos segundos extra, costo mínimo pero no nulo). Se decidió que solo tenga sentido en el buscador principal, activada por un botón explícito ("Saber más"), nunca en cada búsqueda automática — así el flujo principal se mantiene rápido.

**Por qué no se implementa en el chat**: el agente conversacional ya redacta descripciones cualitativas como parte natural de su respuesta — agregar el mismo mecanismo ahí sería duplicar una función que ya cumple.

**Garantía de contenido**: las descripciones generadas se basan exclusivamente en los datos reales ya calculados (clima, sentimiento, precio) — nunca se inventa información sobre un destino que no provenga de esos datos.

---

## 4. Recomendación de UX: exigir texto no vacío en el buscador

Para evitar ambigüedad entre "el usuario no escribió nada" y "el usuario realmente quiere ver todo sin filtrar" (que es lo que ya cubre el Simulador TDRS), se recomienda no permitir una búsqueda con el campo de texto vacío. Para que esto no se sienta como una traba, se sugieren botones de acceso rápido que completan el campo con un clic:

```python
col1, col2, col3, col4 = st.columns(4)
if col1.button("🏖️ Playa"):
    st.session_state["texto_prellenado"] = "playa relajante"
if col2.button("🏛️ Cultura"):
    st.session_state["texto_prellenado"] = "turismo cultural e histórico"
if col3.button("🏔️ Naturaleza"):
    st.session_state["texto_prellenado"] = "naturaleza y aire libre"
if col4.button("🎉 Aventura"):
    st.session_state["texto_prellenado"] = "aventura y deportes"
```

---

## 5. Notas operativas

- El servicio está configurado con `min-replicas: 1` (siempre encendido) — no debería haber demora de "arranque en frío".
- La clave de Anthropic ya está configurada como variable de entorno segura en el servidor de Azure — no es necesario ni posible verla desde el dashboard.
- Cualquier error de conexión debe mostrarse de forma genérica al usuario ("no se pudo completar la búsqueda, intenta de nuevo"), sin exponer detalles técnicos internos.
- El motor no tiene acceso a información sobre fechas de vuelo, disponibilidad en tiempo real ni paquetes específicos con transporte — tanto el agente como el buscador manual deberían, ante ese tipo de pedido, remitir a los canales oficiales de contacto de TUI.
