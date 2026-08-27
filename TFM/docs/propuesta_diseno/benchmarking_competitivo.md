# Benchmarking Competitivo: Posicionamiento del Motor TDRS

## TFM UCM 2025 — Motor de Recomendación Turística TUI

---

## Mapa Competitivo: IA en Turismo 2024-2025

| Capacidad | **TUI + TDRS (Nuestro)** | Mindtrip | Nezasa TripBuilder | Murmuration |
|-----------|:------------------------:|:--------:|:------------------:|:-----------:|
| Recomendaciones personalizadas | ✅ | ✅ | ⚠️ Parcial | ❌ |
| Chat conversacional IA | ✅ GPT-4o-mini | ✅ OpenAI | ⚠️ Copilot B2B | ❌ |
| Redistribución de demanda (TDRS) | ✅ | ❌ | ❌ | ⚠️ Solo métricas |
| Scoring de sostenibilidad | ✅ 8 factores | ❌ | ❌ | ✅ Satelital |
| Paquetes completos (vuelo+hotel) | ✅ | ❌ Solo inspiración | ✅ | ❌ |
| Booking integrado | ✅ via API TUI | ⚠️ Vuelos solo | ✅ | ❌ |
| Itinerarios día a día | ⚠️ Potencial | ✅ | ✅ | ❌ |
| Datos de presión ambiental | ✅ Eurostat/INE | ❌ | ❌ | ✅ Satélite |
| Explicabilidad (XAI) | ✅ Factores visibles | ⚠️ Chat natural | ❌ | ❌ |
| B2B para operadores/DMOs | ✅ Dashboard | ❌ Solo B2C | ✅ | ✅ |
| Multi-escenario re-ranking | ✅ 3 estrategias | ❌ | ❌ | ❌ |
| Open-source / académico | ✅ | ❌ Propietary | ❌ Propietary | ❌ Propietary |

---

## Análisis Individual

### 1. Mindtrip (mindtrip.ai)

**Qué es:** Plataforma B2C de planificación de viajes con IA conversacional.

**Modelo de negocio:** B2B2C — Se asocia con DMOs (Destination Marketing Organizations) y oficinas de turismo para ofrecer experiencia de descubrimiento personalizada.

**Stack tecnológico:** OpenAI + datos de TripAdvisor, Viator, Priceline, Agoda, Google, HotelBeds.

**Fortalezas:**
- Chat natural excepcional (OpenAI bajo el capó)
- Itinerarios completos con mapas interactivos, distancias y secuenciación inteligente
- Booking de vuelos integrado (Sabre + PayPal)
- Expansión Europa 2026 (Madeira, Norwegian Travel Cluster)
- $19M levantados

**Debilidades:**
- NO redistribuye demanda — refuerza destinos populares
- Sin scoring de sostenibilidad
- Sin métricas de ocupación/saturación
- Solo inspiración, no paquetes completos (vuelo+hotel juntos)

**Qué incorporamos de Mindtrip:**
- Chat conversacional con refinamiento iterativo (Propuesta 5)
- Itinerario día a día generado por LLM
- Mapas con distancias y secuenciación

---

### 2. Nezasa TripBuilder (nezasa.com)

**Qué es:** Plataforma B2B de comercio turístico con IA para operadores y aerolíneas.

**Dato clave: TUI ya es cliente de Nezasa** — Usaron TripBuilder para redefinir sus tours ofrecidos.

**Modelo de negocio:** SaaS B2B — Licencia a touroperadores, aerolíneas y agencias.

**Stack tecnológico:** AI Copilot para agentes, API-native, integración con GDS (Sabre, Amadeus).

**Fortalezas:**
- Genera itinerarios completos desde un prompt de texto
- Conecta inventario real (vuelos, hoteles, actividades)
- Operaciones post-booking automatizadas
- Video-to-Itinerary (lee un video de viaje y genera paquete)
- Probado en producción con TUI a escala

**Debilidades:**
- Sin personalización basada en perfil de viajero individual
- Sin redistribución de demanda
- Sin sostenibilidad como criterio
- Orientado a agentes, no a viajero final
- No tiene explicabilidad (XAI)

**Qué incorporamos de Nezasa:**
- Concepto de "un prompt genera un paquete completo" (Propuesta 2)
- Conexión con inventario real de TUI
- Automatización del packaging

---

### 3. Murmuration (murmuration-sas.com)

**Qué es:** Startup francesa que usa datos satelitales para medir presión turística y ambiental.

**Modelo de negocio:** B2B/B2G — Vende indicadores a DMOs, gobiernos y ONGs.

**Filosofía:** "Crear ecosistema de actores turísticos para cuantificar presión ambiental y limitar impactos en contexto de cambio climático."

**Stack tecnológico:** Imágenes satelitales de alta resolución + datos locales + series temporales.

**Fortalezas:**
- Indicadores de presión ambiental objetivos y transparentes (datos satelitales)
- Visión temporal: puede retroceder en el tiempo, identificar problemas y prever evoluciones
- Enfoque holístico: turistas + profesionales + autoridades + ONGs
- Case study: Bali (presión turística medida por satélite)
- Datos factuales e invaluables

**Debilidades:**
- NO genera recomendaciones personalizadas
- Sin interacción con el viajero final
- Solo mide, no actúa (no redistribuye activamente)
- Sin booking ni experiencia de usuario
- Solo indicadores, sin motor de decisión

**Qué incorporamos de Murmuration:**
- Filosofía de redistribución = TDRS
- Indicadores de presión ambiental (sensibilidad_ambiental en nuestro score)
- Datos objetivos de ocupación como input del modelo
- Enfoque multi-stakeholder (viajero + destino + operador)

---

## Posicionamiento Diferencial: Nuestra Propuesta

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│         NUESTRO MOTOR TUI + TDRS                                │
│         ════════════════════════                                 │
│                                                                 │
│    ┌──────────┐   ┌──────────────┐   ┌──────────────────┐      │
│    │ Mindtrip │ + │   Nezasa     │ + │   Murmuration    │      │
│    │          │   │              │   │                  │      │
│    │ Chat IA  │   │ Paquetes     │   │ Presión          │      │
│    │ Personal.│   │ Completos    │   │ Ambiental        │      │
│    │ Itinerar.│   │ Booking real │   │ Redistribución   │      │
│    └──────────┘   └──────────────┘   └──────────────────┘      │
│                          │                                      │
│                          ▼                                      │
│    ┌─────────────────────────────────────────────────┐          │
│    │     TOURISM DEMAND REDISTRIBUTION SCORE         │          │
│    │                                                 │          │
│    │  TDRS = w₁·Afinidad + w₂·Capacidad +           │          │
│    │         w₃·Accesibilidad + w₄·Impacto local +  │          │
│    │         w₅·Temporada baja + w₆·Diversificación +│          │
│    │         w₇·Ocupación + w₈·Sensib. ambiental     │          │
│    │                                                 │          │
│    │  → Maximiza satisfacción del viajero            │          │
│    │  → Minimiza presión sobre hotspots              │          │
│    │  → Impulsa economías locales                    │          │
│    └─────────────────────────────────────────────────┘          │
│                                                                 │
│    RESULTADO: Recomendaciones que el viajero ACEPTA             │
│    porque son altamente relevantes, Y que redistribuyen         │
│    demanda hacia destinos infrautilizados.                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Valor Estratégico Diferencial

| Dimensión | Competidores | Nuestro Motor |
|-----------|:------------:|:-------------:|
| Optimiza para... | Conversión | Conversión + Sostenibilidad |
| Visión del destino | Recurso infinito | Recurso con capacidad limitada |
| Dato de presión | No usa | Input central del TDRS |
| Efecto sobre overtourism | Lo agrava | Lo mitiga activamente |
| Quién se beneficia | Solo viajero | Viajero + Destino + Comunidad |
| Transparencia | Caja negra | XAI: factores visibles |
| Multi-escenario | No | 3 estrategias seleccionables |

---

## Conclusión para el TFM

Nuestro sistema es el **primero en combinar las tres capas** en una sola plataforma integrada:

1. **Personalización nivel Mindtrip** → Chat IA + explicaciones + itinerarios
2. **Operatividad nivel Nezasa** → Paquetes reales TUI con booking
3. **Sostenibilidad nivel Murmuration** → TDRS con 8 factores de redistribución

El resultado es un motor que genera recomendaciones **igualmente atractivas para el viajero** pero que redistribuyen demanda hacia destinos con capacidad disponible, reduciendo overtourism y beneficiando a comunidades locales.

---

*TFM UCM 2025 — Motor de Recomendación Turística con Redistribución de Demanda*
