# Propuesta de Diseño: Recomendaciones en Web TUI

## Motor de Recomendación Turística con TDRS — TFM UCM 2025

---

## Resumen Ejecutivo

Este documento presenta **7 alternativas de diseño** para integrar el output del modelo de recomendación dentro de la experiencia web de TUI. Cada propuesta traduce el score del modelo en información accionable, confiable y medible para el usuario final.

---

## Estructura de la API (JSON de respuesta)

Antes de las alternativas, definimos el contrato API que alimenta todas las variantes:

```json
{
  "request_id": "req_a1b2c3d4",
  "user_id": "usr_maria_garcia_42",
  "generated_at": "2025-08-13T10:30:00Z",
  "model_version": "tdrs_v2.1_lightfm",
  "scenario": "balanced",
  "recommendations": [
    {
      "recommendation_id": "rec_001",
      "rank": 1,
      "package_id": "pkg_mallorca_sol_marina_7n",
      "destination": "Mallorca",
      "country": "España",
      "hotel": "Hotel Sol Marina",
      "stars": 4,
      "category": "playa",
      "duration_days": 7,
      "departure_city": "Madrid",
      "price_eur": 899,
      "departure_date": "2025-11-15",
      "season": "Baja",

      "scores": {
        "overall": 0.92,
        "affinity": 0.88,
        "tdrs": 0.78,
        "sustainability": 0.85,
        "availability": 0.95
      },

      "confidence": "high",
      "priority": "top_pick",

      "explanation": {
        "summary": "Mallorca en temporada baja combina tu pasión por la playa y la gastronomía con precios excelentes y playas sin aglomeraciones.",
        "key_factors": [
          {"factor": "Afinidad playa", "weight": 0.35, "match": "alta"},
          {"factor": "Gastronomía local", "weight": 0.25, "match": "alta"},
          {"factor": "Temporada baja", "weight": 0.20, "match": "perfecta"},
          {"factor": "Sostenibilidad", "weight": 0.20, "match": "alta"}
        ],
        "user_friendly": "Porque te gusta la playa y la buena comida, y en noviembre disfrutarás sin masificación."
      },

      "expected_impact": {
        "savings_vs_high_season": "35%",
        "crowd_level": "bajo",
        "weather_score": 7.2,
        "traveler_satisfaction": 4.6
      },

      "social_proof": {
        "avg_rating": 4.6,
        "total_reviews": 342,
        "highlight_review": "Las calas en noviembre son mágicas. Cero turistas y agua cristalina.",
        "recent_bookings": 28
      },

      "badges": ["sustainable", "low_crowd", "best_value"],

      "actions": {
        "primary": {"label": "Reservar ahora", "url": "/booking/pkg_mallorca_sol_marina_7n"},
        "secondary": {"label": "Ver detalles", "url": "/package/pkg_mallorca_sol_marina_7n"},
        "tertiary": {"label": "Comparar", "action": "add_to_comparison"}
      },

      "_metadata": {
        "embedding_similarity": 0.847,
        "tdrs_raw": 0.783,
        "reranking_position_change": +2,
        "model_features_used": 384,
        "inference_time_ms": 45
      }
    }
  ],

  "user_segment": "beach_foodie_sustainable",
  "preferences_used": {
    "pref_playa": 0.35,
    "pref_gastronomia": 0.25,
    "pref_cultura": 0.15,
    "pref_naturaleza": 0.10,
    "pref_aventura": 0.10,
    "pref_bienestar": 0.05,
    "budget_max": 1500,
    "sustainability_importance": 0.7
  },

  "_debug": {
    "total_candidates_evaluated": 1247,
    "reranking_scenario": "redistribucion_moderada",
    "alpha": 0.5,
    "beta": 0.2,
    "gamma": 0.1,
    "delta": 0.1,
    "lambda_sat": 0.1
  }
}
```

### Separación de datos:

| Capa | Campos | Destino |
|------|--------|---------|
| **Usuario** | explanation.user_friendly, badges, price, destination, actions | Renderizado en UI |
| **Analítica** | scores, confidence, user_segment, rank | Dashboards internos |
| **Debug** | _metadata, _debug | Solo logs/auditoría |

---

## Alternativa 1: Recommendation Card

### Nombre del concepto
**"Tu Viaje Ideal" — Card Personalizada**

### Descripción de la experiencia
Tarjeta visual individual que presenta UN destino con toda la información necesaria para decidir: qué, por qué, cuánto y qué hacer. El usuario ve una recomendación concreta con explicación humana y CTA directo.

### Cómo se visualizaría

### Información de la API
- `explanation.user_friendly` → Texto en la card
- `scores.overall` → Barra de match
- `social_proof` → Rating y reviews
- `badges` → Iconos superiores
- `actions` → Botones

### CTA
**"Reservar ahora"** (primario) + "Ver detalles" + "Comparar"

### Ventajas
- Formato familiar para el usuario (estilo Booking/Airbnb)
- Alta densidad de información sin abrumar
- La explicación genera confianza inmediata
- CTR alto por ser directo y visual

### Riesgos
- Si solo se muestra 1 card, el usuario puede sentir limitación
- La explicación LLM puede no ser siempre precisa
- Requiere buenas imágenes por destino

### Escenario ideal
- **Homepage personalizada**: primera impresión al entrar a TUI
- **Email marketing**: recomendación destacada del mes
- **Push notifications**: "Hemos encontrado algo para ti"

### Métricas de Growth
- **CTR** sobre la card (click en cualquier elemento)
- **Bookmark rate** (guardados para después)
- **Time-to-action** (segundos hasta click)
- **Conversion rate** (reserva completada / card vista)

---

## Alternativa 2: Top Recommendation / Best Action

### Nombre del concepto
**"Nuestra Mejor Recomendación para Ti" — Hero Recommendation**

### Descripción de la experiencia
UNA sola recomendación destacada al máximo, presentada como "la mejor opción" según el modelo. Full-width, con impacto visual máximo y urgencia implícita. El sistema elige POR el usuario.

### Cómo se visualizaría


### Información de la API
- `recommendations[0]` (solo el top-1)
- `explanation.key_factors` → Lista de checkmarks
- `expected_impact.savings_vs_high_season` → Ahorro
- `social_proof.recent_bookings` → Urgencia social

### CTA
**"Reservar este viaje"** — Único y prominente

### Ventajas
- Elimina parálisis de elección (paradoja de la elección)
- Máximo impacto visual y emocional
- Transmite autoridad del sistema ("sabemos qué necesitas")
- Conversion rate más alto por simplicidad

### Riesgos
- Si la recomendación no resuena, el usuario rebota sin alternativas
- Requiere altísima confianza en el modelo (score > 0.85)
- Puede percibirse como agresivo/invasivo

### Escenario ideal
- **Usuarios recurrentes** con perfil bien definido
- **Modelo con confianza > 0.90** para el top-1
- **Campañas de retargeting**: "Sabemos qué buscas"

### Métricas de Growth
- **Direct conversion rate** (reserva sin ver alternativas)
- **Bounce rate** (si no convence, se va)
- **Revenue per recommendation** (ingreso directo)
- **Trust score** (encuesta post-compra: "¿Confió en la recomendación?")

---

## Alternativa 3: Ranking de Recomendaciones

### Nombre del concepto
**"Tus Top 10 Destinos" — Ranking Personalizado**

### Descripción de la experiencia
Lista ordenada de 10 destinos con score visible, permitiendo al usuario explorar opciones de mayor a menor afinidad. Incluye filtros y opción de reordenar por criterio (precio, sostenibilidad, etc.).

### Cómo se visualizaría


### Información de la API
- `recommendations[]` completo (10 items)
- `scores.overall` → Barra y posición
- `explanation.user_friendly` → Subtítulo
- `badges` → Iconos laterales
- Filtros activan re-request con `scenario` diferente

### CTA
**"Ver" + "Reservar"** por cada item del ranking

### Ventajas
- El usuario mantiene control y autonomía
- Permite descubrimiento ("ah, no había pensado en Creta")
- Los filtros aumentan engagement y tiempo en página
- El ranking ordinal transmite jerarquía clara

### Riesgos
- Parálisis de elección si hay demasiadas opciones
- El usuario puede ignorar items debajo del #3
- El score numérico puede confundir usuarios no técnicos

### Escenario ideal
- **Fase de exploración**: usuario que aún no sabe qué quiere
- **Usuarios analíticos** que disfrutan comparar
- **SEO/Content**: landing pages "Top destinos para ti"

### Métricas de Growth
- **Scroll depth** (hasta qué posición llega)
- **CTR por posición** (decae con el ranking)
- **Filter usage rate** (engagement con los filtros)
- **Comparison starts** (cuántos añade a comparar)
- **Average items viewed** before booking

---

## Alternativa 4: Before → After / Impacto Esperado

### Nombre del concepto
**"Tu Viaje en Números" — Impacto Comparativo**

### Descripción de la experiencia
Muestra al usuario QUÉ GANA eligiendo la recomendación vs. la alternativa popular/genérica. Formato before-after que visualiza el impacto tangible de seguir la recomendación del modelo.

### Cómo se visualizaría


### Información de la API
- `expected_impact` → Métricas del comparativo
- Requiere campo adicional: `comparison_baseline` con datos del destino popular
- `explanation.key_factors` → Puntos de resumen

### CTA
**"Elegir la recomendación inteligente"**

### Ventajas
- El impacto tangible (€ ahorrados, menos CO2) es poderosamente persuasivo
- Apela a la racionalidad del decisor
- El formato vs. es universalmente comprensible
- Refuerza el valor del motor de recomendación

### Riesgos
- Puede percibirse como manipulativo si el "baseline" es artificialmente malo
- Requiere datos del baseline que no siempre existen
- No funciona si el usuario YA quiere el destino popular

### Escenario ideal
- **Redistribución de demanda**: convencer de destinos alternativos
- **Usuarios price-sensitive**: el ahorro es el argumento principal
- **Campañas de sostenibilidad**: "Viaja mejor, no más lejos"

### Métricas de Growth
- **Persuasion rate** (% que cambia de opción popular a recomendada)
- **Net savings realized** (ahorro real post-booking)
- **Sustainability adoption** (% que elige opción sostenible)
- **Virality** (compartidos: "mira cuánto ahorro")

---

## Alternativa 5: AI Assistant / Conversational Recommendation

### Nombre del concepto
**"TUI Travel Advisor" — Chat Conversacional**

### Descripción de la experiencia
Interfaz de chat donde el usuario interactúa con un asistente IA que va refinando recomendaciones en tiempo real según la conversación. El modelo se invoca iterativamente con cada respuesta del usuario.


### Información de la API
- Endpoint conversacional: `POST /api/chat`
- Input: historial de mensajes + user_id
- Output: recomendaciones actualizadas + texto explicativo
- Usa LLM (GPT-4o-mini) para generar respuesta natural
- Modelo de recomendación se re-ejecuta con cada cambio de restricciones

### CTA
**"Reservar" inline** en cada mini-card dentro del chat

### Ventajas
- Experiencia natural y personalizada
- El usuario siente que "elige" (no que le imponen)
- Permite refinamiento iterativo sin frustración
- Máximo engagement (conversación es adictiva)
- Captura preferencias no explícitas del usuario

### Riesgos
- Alto costo computacional (LLM + modelo por cada mensaje)
- Latencia perceptible puede frustrar
- Si el LLM alucina, pierde confianza inmediatamente
- Usuarios mayores pueden preferir interfaz tradicional
- Difícil de medir con métricas estándar

### Escenario ideal
- **Usuarios indecisos** que necesitan guía
- **Primera visita**: no hay historial de preferencias
- **Viajes complejos** (grupos, restricciones múltiples)
- **Mobile-first**: el chat es nativo en móvil

### Métricas de Growth
- **Conversation completion rate** (% que llega a booking)
- **Messages per session** (engagement)
- **Recommendation acceptance rate** (click en "Reservar" dentro del chat)
- **NPS post-interacción** (¿recomendarías este asistente?)
- **Return rate** (% que vuelve a usar el chat)

---

## Alternativa 6: Social Discovery Wall

### Nombre del concepto
**"Viajeros Como Tú" — Descubrimiento Social**

### Descripción de la experiencia
Muestra recomendaciones contextualizadas con experiencias reales de viajeros similares. Combina el output del modelo con social proof de las reseñas scrapeadas, creando una experiencia tipo "feed" social.


### Información de la API
- `social_proof.highlight_review` → Cita del viajero
- `user_segment` → Matching de perfil similar
- Requiere campo adicional: `similar_traveler` con datos anónimos

### CTA
**"Quiero lo mismo →"** (apela al deseo de imitación social)

### Ventajas
- Social proof es el persuasor más potente (Cialdini)
- Las historias reales generan conexión emocional
- Reduce percepción de "algoritmo frío"
- Alto scroll engagement (formato feed infinito)
- Las reseñas vienen del scraping propio (diferenciador)

### Riesgos
- Requiere curación cuidadosa de reseñas (evitar negativas)
- Puede percibirse como fabricado si los perfiles no son creíbles
- Menos efectivo para destinos con pocas reseñas
- Problemas de privacidad si se usan datos reales

### Escenario ideal
- **Usuarios emocionales** que compran por inspiración
- **Mobile browsing**: scroll infinito es natural
- **Redes sociales**: formatos compartibles
- **Destinos nuevos**: las historias reducen incertidumbre

### Métricas de Growth
- **Scroll depth** y dwell time
- **Story engagement** (tiempo leyendo cada testimonio)
- **Social share rate** (compartidos a redes)
- **"Quiero lo mismo" CTR**
- **Discovery rate** (% que reserva destino que no buscaba inicialmente)

---

## Alternativa 7: Escenarios Interactivos (Diferenciador TDRS)

### Nombre del concepto
**"Elige Tu Estilo de Viaje" — Escenarios de Re-ranking**

### Descripción de la experiencia
Presenta los mismos destinos pero reordenados según 3 filosofías de viaje. El usuario elige su "modo" y el sistema muestra el ranking correspondiente. Es la forma de comunicar el valor del TDRS al usuario final.

### Cómo se visualizaría

### Información de la API
- Tres llamadas con `scenario`: "tradicional", "redistribucion_moderada", "redistribucion_intensiva"
- O una sola llamada que devuelve los 3 rankings simultáneamente
- `expected_impact` comparativo entre escenarios

### CTA
**"Explorar este modo"** → Despliega el ranking completo del escenario elegido

### Ventajas
- **Diferenciador único** vs. competencia (ningún OTA ofrece esto)
- Educa al usuario sobre turismo sostenible sin sermón
- El usuario siente control y autonomía ("yo elijo")
- Perfecto para el TFM: demuestra el valor del TDRS visualmente
- Gamificación implícita ("modo explorador" suena emocionante)

### Riesgos
- Concepto nuevo que puede confundir
- Requiere 3x computación (3 rankings)
- Si el modo "explorador" no convence, perjudica confianza
- Puede fragmentar la conversión

### Escenario ideal
- **Landing page principal de TUI**: experiencia diferenciadora
- **Campañas de marca** sobre sostenibilidad
- **Presentación del TFM**: demuestra el TDRS en acción
- **Usuarios eco-conscientes**: segmento creciente

### Métricas de Growth
- **Mode selection distribution** (qué % elige cada modo)
- **Conversion by mode** (cuál convierte mejor)
- **Sustainability adoption rate** (% que NO elige "popular")
- **Revenue per mode** (ingresos por escenario)
- **Brand perception shift** (encuesta pre/post sobre TUI y sostenibilidad)

---

## Resumen Comparativo

| Alternativa | Complejidad técnica | CTR esperado | Confianza generada | Mejor para |
|------------|--------------------:|:-------------|:-------------------|:-----------|
| 1. Recommendation Card | Baja | Alto | Media-Alta | Homepage, emails |
| 2. Top / Best Action | Baja | Muy alto | Alta (si acierta) | Retargeting, power users |
| 3. Ranking | Media | Medio | Alta | Exploración, comparación |
| 4. Before → After | Media | Alto | Muy alta | Redistribución, price-sensitive |
| 5. AI Chat | Alta | Variable | Muy alta | Indecisos, mobile |
| 6. Social Discovery | Media | Alto | Alta | Inspiración, emocional |
| 7. Escenarios TDRS | Alta | Medio-Alto | Alta | TFM demo, eco-conscious |

---

## Recomendación Final para el TFM

Para la **demo del TFM**, recomiendo implementar una combinación de:

1. **Alternativa 7** (Escenarios) como landing principal → demuestra el valor académico del TDRS
2. **Alternativa 1** (Cards) como formato de cada resultado → formato familiar y efectivo
3. **Alternativa 5** (Chat) como feature "wow" → demuestra integración LLM

Esta combinación cubre los 6 objetivos del brief:
- ✅ Entiende qué recomienda → Cards claras
- ✅ Comprende por qué → Explicación LLM en cada card
- ✅ Confía → Social proof + transparencia de escenarios
- ✅ Percibe beneficio → Badges de sostenibilidad e impacto
- ✅ Ejecuta acción → CTA directo "Reservar"
- ✅ Medible → Cada interacción genera eventos analíticos

---

## Archivo Complementario

- `mockup_web.html` — Prototipo visual interactivo (abrir en navegador)
