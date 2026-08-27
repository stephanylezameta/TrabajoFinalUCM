# Propuesta Integrada: Recomendacion IA + Redistribucion + Dashboard

## Motor de Recomendacion Turistica TUI con TDRS
### TFM UCM 2025

---

## Resumen Ejecutivo

Esta propuesta describe como integrar un **motor de recomendacion basado en IA** con un **dashboard interactivo de redistribucion** que permite al usuario (operador turistico, DMO o gestor de destino) pasar de la recomendacion a la accion.

El sistema no solo recomienda: **ayuda a decidir, visualizar la redistribucion, evaluar el impacto y hacer seguimiento de resultados.**

---

## 1. RECOMENDACION IA

### 1.1 Que recomienda exactamente el modelo

El modelo genera un **ranking personalizado de destinos/experiencias** para cada segmento de viajero, optimizando simultaneamente:

- **Satisfaccion del viajero** (afinidad con sus preferencias)
- **Sostenibilidad del destino** (reduccion de presion turistica)
- **Viabilidad economica** (maximizar revenue sin saturar)

**Output concreto del modelo:**

Para un viajero con perfil "Cultural Explorer + Gastronomia" que normalmente visitaria Sevilla centro:

| Destino | Afinidad | TDRS | Score Final | Ocupacion actual | Precio | Accion |
|---------|----------|------|-------------|------------------|--------|--------|
| Carmona | 87% | 0.92 | 0.89 | 22% | 450 EUR | PUSH |
| Osuna | 85% | 0.90 | 0.87 | 18% | 420 EUR | PUSH |
| Sevilla centro | 90% | 0.25 | 0.52 | 88% | 680 EUR | REDUCIR |

### 1.2 Como se presenta la recomendacion al usuario

La recomendacion se muestra en **3 capas** segun el rol:

**Capa 1 - Viajero final (B2C):**
- Card con destino, explicacion en lenguaje natural, precio, CTA "Reservar"
- Ejemplo: "Carmona ofrece el mismo patrimonio cultural que Sevilla con calles vacias y gastronomia autentica, a 40 min y 34% mas barato."

**Capa 2 - Operador TUI (B2B):**
- Dashboard con tabla comparativa actual vs recomendado
- Metricas de impacto: revenue incremental, reduccion de saturacion, satisfaccion predicha
- Acciones: "Aplicar", "Simular", "Ajustar"

**Capa 3 - DMO / Destino:**
- Vision territorial: mapa de flujos redistribuidos
- Indicadores de presion ambiental pre/post
- Informe de impacto economico local

### 1.3 Variables y criterios de justificacion

El modelo TDRS utiliza **8 factores ponderados**:

```
TDRS = w1*Afinidad + w2*Capacidad + w3*Accesibilidad + 
       w4*Impacto_local + w5*Temporada_baja + 
       w6*Diversificacion + w7*Ocupacion + w8*Sensib_ambiental
```

Pesos por defecto (configurables):

| Factor | Peso | Descripcion |
|--------|------|-------------|
| w1 Afinidad | 0.20 | Similitud semantica usuario-experiencia (embeddings 384d) |
| w2 Capacidad | 0.10 | Plazas disponibles / plazas totales |
| w3 Accesibilidad | 0.10 | Tiempo de desplazamiento, conexiones aereas |
| w4 Impacto local | 0.10 | Beneficio economico para comunidad local |
| w5 Temporada baja | 0.15 | Bonus si el destino esta en temporada baja |
| w6 Diversificacion | 0.10 | Penalizacion si ya hay muchos viajeros similares |
| w7 Ocupacion | 0.15 | Penalizacion inversa a ocupacion actual |
| w8 Sensib. ambiental | 0.10 | Indice de fragilidad ecologica del destino |

### 1.4 Antes vs Despues

**Distribucion ANTES (sin TDRS):**

| Destino | % demanda | Ocupacion | Satisfaccion |
|---------|-----------|-----------|--------------|
| Sevilla centro | 45% | 88% | 3.8/5 |
| Barcelona centro | 30% | 92% | 3.6/5 |
| Cancun | 15% | 94% | 3.9/5 |
| Otros (32 destinos) | 10% | 25% media | 4.2/5 |

**Distribucion DESPUES (con TDRS moderada):**

| Destino | % demanda | Ocupacion | Satisfaccion |
|---------|-----------|-----------|--------------|
| Sevilla centro | 22% (-23pp) | 65% | 4.1/5 |
| Carmona / Osuna | 12% (+12pp) | 38% | 4.5/5 |
| Barcelona centro | 15% (-15pp) | 72% | 4.0/5 |
| Split / Algarve | 18% (+14pp) | 42% | 4.4/5 |
| Otros | 33% (+23pp) | 35% media | 4.3/5 |

---

## 2. REDISTRIBUCION

### 2.1 Como se realiza la redistribucion

La redistribucion NO es una asignacion forzada. Es un **re-ranking inteligente** que:

1. **Modifica la visibilidad** de destinos en la web TUI (que aparece primero)
2. **Ajusta pricing dinamico** (ofertas para destinos infrautilizados)
3. **Personaliza las explicaciones** (por que este destino para ti)
4. **Controla el inventario mostrado** (limita plazas visibles en destinos saturados)

### 2.2 Tabla de redistribucion: Actual vs Recomendado vs Diferencia

| Destino | Asignacion actual | Recomendacion IA | Diferencia | Estado |
|---------|:-----------------:|:----------------:|:----------:|:------:|
| Sevilla centro | 4,500 viajeros/mes | 2,200 | -2,300 | Descongestionar |
| Carmona | 180 viajeros/mes | 1,200 | +1,020 | Potenciar |
| Osuna | 120 viajeros/mes | 900 | +780 | Potenciar |
| Barcelona centro | 3,000 viajeros/mes | 1,500 | -1,500 | Descongestionar |
| Split | 400 viajeros/mes | 1,200 | +800 | Potenciar |
| Algarve | 350 viajeros/mes | 1,100 | +750 | Potenciar |
| Mallorca (nov) | 600 viajeros/mes | 1,400 | +800 | Potenciar |

### 2.3 Restricciones de la redistribucion

La redistribucion respeta las siguientes **restricciones duras**:

| Restriccion | Descripcion | Valor |
|-------------|-------------|-------|
| Presupuesto total | Inversion marketing no puede exceder | 500K EUR/mes |
| Capacidad maxima | Ningun destino puede superar 90% ocupacion | umbral configurable |
| Capacidad minima | No reducir a 0 ningun destino con demanda organica | min 10% de actual |
| Accesibilidad | No recomendar destinos sin conexion aerea directa para vuelos > 4h | regla de negocio |
| Satisfaccion minima | Score de afinidad debe ser > 0.70 para cualquier recomendacion | umbral calidad |
| Viabilidad hotel | Solo recomendar destinos con al menos 1 hotel partner TUI | inventario real |
| Estacionalidad | No forzar destinos con clima adverso en el periodo | datos Open-Meteo |
| Revenue minimo | Revenue esperado por recomendacion > coste de adquisicion | ROI > 1.0 |

**Restricciones blandas** (penalizan pero no bloquean):

- Preferencia por destinos con certificacion sostenible TUI
- Preferencia por destinos con impacto economico local alto
- Preferencia por rutas con menor huella de carbono

### 2.4 Escenarios de redistribucion

El usuario puede elegir entre 3 modos:

**A) Recomendacion automatica:**
- El modelo aplica la estrategia seleccionada (Moderada por defecto)
- Genera ranking optimizado y redistribuye automaticamente la visibilidad
- Sin intervencion humana

**B) Ajuste manual:**
- El operador ve la recomendacion y puede:
  - Fijar un destino en una posicion (pin)
  - Excluir un destino del ranking
  - Modificar pesos w1-w8
  - Forzar un minimo/maximo de asignacion
- El modelo recalcula respetando los ajustes

**C) Simulacion what-if:**
- "Que pasaria si subo sostenibilidad a 30%?"
- "Que pasaria si excluyo Cancun del catalogo?"
- "Que pasaria si hay un evento en Mallorca que sube demanda 40%?"
- El modelo genera el nuevo ranking y muestra impacto sin aplicar cambios

---

## 3. DASHBOARD

### 3.1 Arquitectura del dashboard

```
+------------------------------------------------------------------+
|  HEADER: TUI - Simulador de Redistribucion Turistica             |
+------------------------------------------------------------------+
|  SIDEBAR         |  CONTENIDO PRINCIPAL                          |
|                  |                                                |
|  - Filtros       |  Tab 1: Estado actual                         |
|  - Estrategia    |  Tab 2: Recomendacion IA                      |
|  - Pesos TDRS    |  Tab 3: Redistribucion propuesta              |
|  - Restricciones |  Tab 4: Impacto esperado                      |
|                  |  Tab 5: Simulador what-if                      |
|                  |  Tab 6: Seguimiento post-aplicacion            |
|                  |                                                |
+------------------------------------------------------------------+
|  FOOTER: Metadata modelo, version, timestamp, confianza          |
+------------------------------------------------------------------+
```

### 3.2 Tab 1: Estado actual

Muestra la situacion HOY sin intervencion:
- 8 KPIs principales (CTR, conversion, diversidad, concentracion, distribucion geografica, satisfaccion, ocupacion fuera temporada, equilibrio territorial)
- Mapa de calor: ocupacion por destino
- Tabla: destinos ordenados por saturacion
- Alerta: destinos por encima del 85% de ocupacion

### 3.3 Tab 2: Recomendacion IA

Muestra QUE propone el modelo:
- Ranking TDRS con scores desglosados
- Explicacion por destino (XAI)
- Factores con mayor peso para cada recomendacion
- Nivel de confianza del modelo (alto/medio/bajo)
- Insight generado: el ejemplo Sevilla -> Carmona/Osuna

### 3.4 Tab 3: Redistribucion propuesta

Muestra COMO reasignar:
- Tabla: Actual | Recomendado | Diferencia | Accion
- Grafico de flujos (sankey): de donde a donde se mueve la demanda
- Restricciones activas (cuales limitan la redistribucion)
- Presupuesto de marketing necesario para ejecutar

### 3.5 Tab 4: Impacto esperado

Muestra QUE PASA SI se aplica:
- Comparativa before/after en las 8 metricas
- Revenue incremental estimado
- Reduccion de huella CO2
- Cambio en satisfaccion por segmento
- ROI proyectado de la redistribucion

### 3.6 Tab 5: Simulador what-if

Permite EXPLORAR alternativas:
- Sliders para ajustar pesos w1-w8
- Toggle para activar/desactivar restricciones
- Selector de eventos externos (festival, clima adverso, etc.)
- Comparativa instantanea con escenario base
- Boton "Aplicar este escenario"

### 3.7 Tab 6: Seguimiento post-aplicacion

Muestra SI FUNCIONO (despues de aplicar):
- Metricas reales vs predichas (A/B testing)
- Evolucion temporal de los KPIs
- Destinos que respondieron mejor/peor de lo esperado
- Alertas de desviacion
- Aprendizajes para recalibrar el modelo

---

## 4. EXPLICABILIDAD (XAI)

### 4.1 Por que la IA propone esa redistribucion

Cada recomendacion incluye una **explicacion multinivel**:

**Nivel 1 - Resumen natural (para viajero/operador):**
"Recomendamos Carmona porque ofrece un 87% de afinidad con el perfil Cultural+Gastronomia, esta a 40 min de Sevilla, tiene solo 22% de ocupacion y un alto impacto economico local."

**Nivel 2 - Factores desglosados (para analista):**

| Factor | Valor | Peso | Contribucion al score |
|--------|-------|------|-----------------------|
| Afinidad semantica | 0.87 | 0.20 | 0.174 |
| Capacidad disponible | 0.78 | 0.10 | 0.078 |
| Accesibilidad (40 min) | 0.92 | 0.10 | 0.092 |
| Impacto economico local | 0.95 | 0.10 | 0.095 |
| Temporada baja | 0.85 | 0.15 | 0.128 |
| Diversificacion | 0.90 | 0.10 | 0.090 |
| Baja ocupacion | 0.78 | 0.15 | 0.117 |
| Sensibilidad ambiental | 0.88 | 0.10 | 0.088 |
| **TOTAL TDRS** | | | **0.862** |

**Nivel 3 - Debug tecnico (para data scientist):**
- Embedding similarity: 0.847 (cosine, 384d)
- Model version: tdrs_v2.1_lightfm
- Inference time: 45ms
- Training data: 149,941 bookings
- Features used: 384 (embeddings) + 8 (numericos) = 392

### 4.2 Que factores tienen mayor peso

Visualizacion SHAP-style mostrando contribucion de cada factor:

```
Afinidad semantica    ████████████████████  0.174 (mayor contribucion)
Temporada baja        █████████████         0.128
Baja ocupacion        ████████████          0.117
Impacto local         ██████████            0.095
Accesibilidad         █████████             0.092
Diversificacion       █████████             0.090
Sensib. ambiental     █████████             0.088
Capacidad disponible  ████████              0.078
```

### 4.3 Impacto esperado de cada cambio

| Si el operador... | Impacto en revenue | Impacto en satisfaccion | Impacto en sostenibilidad |
|-------------------|:------------------:|:-----------------------:|:-------------------------:|
| Aplica recomendacion completa | +12% | +0.4 pts | -45% CO2 |
| Solo redistribuye 50% | +7% | +0.2 pts | -22% CO2 |
| Mantiene status quo | 0% | 0 pts | 0% |
| Redistribucion intensiva | +8% | +0.3 pts | -62% CO2 |

### 4.4 Nivel de confianza

Cada recomendacion tiene un **indicador de confianza**:

- **Alta** (score > 0.85): "Fuerte evidencia de que el viajero aceptara esta alternativa. Basado en 500+ viajeros similares que reservaron destinos equivalentes."
- **Media** (0.70-0.85): "Evidencia moderada. El perfil del viajero encaja pero hay incertidumbre sobre la temporada o el precio."
- **Baja** (< 0.70): "Recomendacion exploratoria. Pocos datos historicos para este perfil en este destino. Usar con precaucion."

### 4.5 Alertas y riesgos

El sistema genera alertas automaticas cuando:

- La redistribucion podria saturar un destino alternativo (>70% post-cambio)
- El precio recomendado esta por debajo del break-even
- El destino tiene restricciones operativas (obras, cierre temporal)
- La confianza del modelo es baja para un segmento critico
- La redistribucion viola una restriccion blanda de forma significativa

---

## 5. ESTRUCTURA API

El dashboard consume datos de un unico endpoint:

```
POST /api/v1/redistribution
```

**Request:**
```json
{
  "user_segment": "cultural_foodie",
  "origin_city": "Madrid",
  "travel_dates": {"from": "2025-11-15", "to": "2025-11-22"},
  "strategy": "moderada",
  "weights": {"w1": 0.20, "w2": 0.10, "w3": 0.10, "w4": 0.10, "w5": 0.15, "w6": 0.10, "w7": 0.15, "w8": 0.10},
  "constraints": {"max_occupancy": 0.85, "min_affinity": 0.70, "budget_eur": 500000},
  "excluded_destinations": [],
  "pinned_destinations": []
}
```

**Response:**
```json
{
  "request_id": "req_abc123",
  "model_version": "tdrs_v2.1",
  "confidence": "high",
  "generated_at": "2025-08-13T14:30:00Z",
  "current_state": {
    "total_demand": 10000,
    "concentration_top5": 0.68,
    "avg_satisfaction": 3.8,
    "saturated_destinations": 8
  },
  "recommended_state": {
    "total_demand": 10000,
    "concentration_top5": 0.42,
    "avg_satisfaction": 4.3,
    "saturated_destinations": 2
  },
  "redistribution": [
    {
      "destination": "Carmona",
      "current_allocation": 180,
      "recommended_allocation": 1200,
      "change": "+1020",
      "action": "PUSH",
      "score_tdrs": 0.92,
      "explanation": "87% afinidad, 40 min de Sevilla, 22% ocupacion, alto impacto local",
      "confidence": "high",
      "key_factors": [
        {"factor": "Afinidad semantica", "value": 0.87, "contribution": 0.174},
        {"factor": "Temporada baja", "value": 0.85, "contribution": 0.128}
      ]
    },
    {
      "destination": "Sevilla centro",
      "current_allocation": 4500,
      "recommended_allocation": 2200,
      "change": "-2300",
      "action": "REDUCE",
      "score_tdrs": 0.25,
      "explanation": "88% ocupacion, saturacion turistica critica, experiencia degradada",
      "confidence": "high",
      "key_factors": [
        {"factor": "Alta ocupacion", "value": 0.88, "contribution": -0.132},
        {"factor": "Baja sostenibilidad", "value": 0.40, "contribution": -0.040}
      ]
    }
  ],
  "expected_impact": {
    "revenue_change_pct": 12.4,
    "satisfaction_change": 0.4,
    "co2_reduction_pct": 45,
    "roi_projected": 3.2
  },
  "alerts": [
    {"type": "info", "message": "Carmona necesitara 2 hoteles partner adicionales para absorber demanda."},
    {"type": "warning", "message": "Osuna tiene accesibilidad limitada (sin conexion ferroviaria directa)."}
  ]
}
```

---

## 6. EJEMPLO VISUAL DEL DASHBOARD

### KPIs principales (fila superior):

```
+----------+  +----------+  +----------+  +----------+
| CTR      |  | Convers. |  | Diversid.|  | Reduccion|
| 12.7%    |  | 4.8%     |  | 78%      |  | -34%     |
| +2.1%    |  | +1.2%    |  | +23%     |  | concentr.|
+----------+  +----------+  +----------+  +----------+

+----------+  +----------+  +----------+  +----------+
| Distrib. |  | Satisf.  |  | Ocup.off |  | Equilib. |
| 6 zonas  |  | 4.5/5    |  | +18%     |  | 0.72     |
| geograf. |  | +0.3     |  | temp.baja|  | territ.  |
+----------+  +----------+  +----------+  +----------+
```

### Tabla "Actual vs Recomendado":

```
+---------------+--------+----------+--------+--------+
| Destino       | Actual | Recomend.| Difer. | Accion |
+===============+========+==========+========+========+
| Sevilla       | 4,500  | 2,200    | -2,300 | REDUCIR|
| Barcelona     | 3,000  | 1,500    | -1,500 | REDUCIR|
| Carmona       |   180  | 1,200    | +1,020 | PUSH   |
| Osuna         |   120  |   900    |  +780  | PUSH   |
| Split         |   400  | 1,200    |  +800  | PUSH   |
| Mallorca (nov)|   600  | 1,400    |  +800  | PUSH   |
| Algarve       |   350  | 1,100    |  +750  | PUSH   |
+---------------+--------+----------+--------+--------+
```

### Grafico de redistribucion (barras apiladas):

```
Sevilla    [======ACTUAL======][===RECOM===]        -51%
Barcelona  [=====ACTUAL=====][==RECOM==]            -50%
Carmona    [A][========RECOMENDADO========]         +567%
Osuna      [A][=======RECOMENDADO=======]           +650%
Split      [==A==][=====RECOMENDADO=====]           +200%
Mallorca   [===A===][======RECOMENDADO======]       +133%
Algarve    [==A==][=====RECOMENDADO=====]           +214%
```

### Impacto esperado (cards):

```
+---------------------+  +---------------------+  +---------------------+
| Revenue incremental |  | Huella CO2          |  | Satisfaccion        |
| +47,200 EUR/mes     |  | -45% emision        |  | 3.8 -> 4.3 (+0.5)  |
| ROI: 3.2x           |  | -2.1 ton/mes        |  | Todos los segmentos |
+---------------------+  +---------------------+  +---------------------+
```

### Explicacion de la recomendacion:

```
+-------------------------------------------------------------------+
| POR QUE ESTA REDISTRIBUCION                                       |
| Confianza: ALTA                                                   |
+-------------------------------------------------------------------+
| Factor principal: Sevilla supera umbral de saturacion (88% > 85%) |
| Accion: Redistribuir 51% de su demanda hacia destinos con:       |
|   - Afinidad > 85% con el mismo segmento                         |
|   - Ocupacion < 40%                                               |
|   - Tiempo desplazamiento < 1h (Carmona, Osuna)                  |
|   - Impacto economico local > 90% (beneficio directo a PYMES)    |
+-------------------------------------------------------------------+
```

### Acciones disponibles:

```
[Simular otro escenario]  [Ajustar pesos]  [Aplicar recomendacion]  [Ver impacto historico]
```

---

## 7. VALOR ANADIDO

### Solo IA (sin dashboard):

- Genera recomendaciones pero nadie las entiende
- No hay forma de validar antes de aplicar
- No se puede simular alternativas
- No se mide si funciono
- Caja negra: el operador no confia

### Solo dashboard (sin IA):

- Muestra datos pero no propone acciones
- El operador debe decidir solo (sesgo humano)
- No hay optimizacion multiobjetivo
- Reactivo: muestra el pasado, no predice el futuro
- No escala: cada decision es manual

### IA + Dashboard integrado (nuestra propuesta):

- **Recomienda Y explica** por que
- **Visualiza el impacto** antes de aplicar
- **Permite simular** escenarios alternativos
- **Respeta restricciones** de negocio automaticamente
- **Mide resultados** y aprende de ellos
- **Escala**: funciona para 39 destinos o 3,900
- **Genera confianza**: explicabilidad total (XAI)
- **Diferenciador competitivo**: ni Mindtrip, ni Nezasa, ni Murmuration ofrecen esto

### Comparativa final:

| Capacidad | Solo IA | Solo Dashboard | IA + Dashboard (nuestro) |
|-----------|:-------:|:--------------:|:------------------------:|
| Recomendar destinos | Si | No | Si |
| Explicar por que | Parcial | No | Completo (XAI) |
| Visualizar impacto | No | Si (pasado) | Si (prediccion) |
| Simular escenarios | No | Limitado | Completo (what-if) |
| Respetar restricciones | Parcial | Manual | Automatico |
| Medir resultados | No | Si | Si + feedback loop |
| Redistribuir activamente | Si (ciega) | No | Si (informada) |
| Confianza del usuario | Baja | Media | Alta |
| Escalabilidad | Alta | Baja | Alta |
| Time-to-decision | Rapido | Lento | Rapido + informado |

---

## 8. IMPLEMENTACION TECNICA

### Stack:

| Componente | Tecnologia |
|------------|-----------|
| Modelo recomendacion | LightFM + embeddings (sentence-transformers) |
| Score TDRS | Funcion custom Python con pesos configurables |
| API | FastAPI (endpoint /api/v1/redistribution) |
| Dashboard | Streamlit (prototipo) / React (produccion) |
| Explicabilidad | SHAP values + LLM para narrativa natural |
| Base de datos | SQLite (prototipo) / PostgreSQL (produccion) |
| Embeddings | ChromaDB / pgvector |
| LLM explicaciones | GPT-4o-mini via API |
| Monitoreo | MLflow + metricas custom |

### Flujo de datos:

```
[Datos: reservas, clima, ocupacion, resenas, comportamiento]
                        |
                        v
[Modelo: LightFM + Embeddings + TDRS scoring]
                        |
                        v
[API: /api/v1/redistribution (FastAPI)]
                        |
                        v
[Dashboard: Streamlit / HTML interactivo]
                        |
                        v
[Usuario: Valida -> Simula -> Aplica -> Mide]
                        |
                        v
[Feedback loop: Resultados reales -> Recalibrar modelo]
```

---

*TFM UCM 2025 - Motor de Recomendacion Turistica con Redistribucion de Demanda (TDRS)*
*Combinando: Mindtrip (personalizacion) + Nezasa (paquetes) + Murmuration (redistribucion)*
