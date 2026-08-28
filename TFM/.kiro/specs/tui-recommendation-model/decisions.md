# Registro de Decisiones — Motor de Recomendación TUI

Este documento registra las decisiones tomadas durante el desarrollo del proyecto, con fecha, justificación y estado. Sirve como trazabilidad para la memoria del TFM.

---

## Formato de cada entrada

**DECISIÓN-XXX** | Fecha | Estado: [Tomada / Pendiente / Revisada]

---

## BLOQUE 1 — Fuentes de Datos

### DECISIÓN-001 | 2026-07-29 | Estado: Tomada

**Área:** Scraping — Fuentes primarias y secundarias

**Decisión:** Usar las siguientes fuentes de datos para el sistema, organizadas por tipo:

---

#### FUENTES PRIMARIAS — Datos de paquetes TUI

| Fuente | URL | Tipo de dato | Método de acceso | Prioridad |
|--------|-----|--------------|-----------------|-----------|
| TUI España | https://www.tui.es | Paquetes, destinos, precios, fechas, hoteles, categorías | Selenium / Playwright (JS pesado) | Alta |
| TUI Alemania | https://www.tui.com | Mismos datos en mercado alemán, descripciones en alemán | Selenium / Playwright | Alta |
| TUI Reino Unido | https://www.tui.co.uk | Mismos datos en mercado anglosajón, precios en GBP | Selenium / Playwright | Media |
| TUI Noticias / Blog | https://www.tui.com/inspire | Descripciones editoriales de destinos, tendencias | BeautifulSoup | Media |

---

#### FUENTES SECUNDARIAS — Saturación, ocupación y demanda

| Fuente | URL | Tipo de dato | Método de acceso | Prioridad |
|--------|-----|--------------|-----------------|-----------|
| TripAdvisor | https://www.tripadvisor.es | Reseñas, puntuaciones, ranking de popularidad por destino | BeautifulSoup + rate limiting | Alta |
| Booking.com | https://www.booking.com | Disponibilidad hotelera, precios, ocupación estimada ("quedan X habitaciones") | Selenium | Alta |
| Eurostat Tourism | https://ec.europa.eu/eurostat/web/tourism | Pernoctaciones por destino, país, temporada — datos anuales/trimestrales | API REST pública y gratuita | Alta |
| INE — Encuesta Ocupación Hotelera | https://www.ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736177015 | Ocupación hotelera mensual por destino en España | API JSON pública | Alta |
| UNWTO / OMT | https://www.unwto.org/tourism-statistics | Llegadas internacionales, gasto turístico, ranking global de destinos | Descarga de datasets | Media |
| Google Trends | https://trends.google.com (via pytrends) | Interés de búsqueda por destino a lo largo del tiempo — proxy de demanda emergente | Librería pytrends (API no oficial) | Media |
| Skyscanner | https://www.skyscanner.es | Precios de vuelos por destino y temporada — indicador de demanda y estacionalidad | BeautifulSoup / API pública limitada | Media |
| Kayak | https://www.kayak.es | Precios combinados vuelo+hotel, tendencias de precios por destino | BeautifulSoup | Baja |
| Holidu | https://www.holidu.es | Alquiler vacacional por destino — complemento a hoteles | BeautifulSoup | Baja |

---

#### FUENTES TERCIARIAS — Texto no estructurado para NLP/Embeddings

| Fuente | URL | Tipo de dato | Método de acceso | Prioridad |
|--------|-----|--------------|-----------------|-----------|
| TripAdvisor Foros | https://www.tripadvisor.es/Tourism | Opiniones textuales de viajeros, percepción de saturación ("lleno de turistas", "temporada baja perfecta") | BeautifulSoup | Alta |
| Reddit r/travel | https://www.reddit.com/r/travel | Discusiones sobre destinos, experiencias, recomendaciones reales | API oficial PRAW | Media |
| Reddit r/solotravel / r/backpacking | https://www.reddit.com/r/solotravel | Perfil de viajero independiente — útil para segmentación | API oficial PRAW | Media |
| Lonely Planet Foros | https://www.lonelyplanet.com/thorntree | Texto de viajeros experimentados, descripciones de destinos | BeautifulSoup | Baja |
| Wikipedia — artículos de destinos | https://es.wikipedia.org | Descripción geográfica, cultural y turística de cada destino | wikipedia-api (Python) | Media |

---

#### FUENTES DE DATOS ABIERTOS — Sostenibilidad y territorio

| Fuente | URL | Tipo de dato | Método de acceso | Prioridad |
|--------|-----|--------------|-----------------|-----------|
| OpenStreetMap | https://www.openstreetmap.org | Datos geoespaciales: infraestructuras, capacidad territorial, puntos de interés | Overpass API / osmnx | Media |
| Our World in Data — Tourism | https://ourworldindata.org/tourism | Series históricas de turismo mundial, impacto ambiental | Descarga CSV | Baja |
| World Bank Open Data | https://data.worldbank.org | Indicadores de desarrollo, infraestructuras, accesibilidad por país | API REST pública | Baja |

---

**Justificación:** La combinación de fuentes primarias (TUI directamente), secundarias (Eurostat, INE, Booking) y terciarias (foros, Reddit) permite construir tanto el catálogo de paquetes como los indicadores de saturación y el corpus textual para embeddings. Las fuentes de datos abiertos aportan la dimensión de sostenibilidad territorial.

**Consideraciones legales:** El scraping de TUI y Booking debe respetar sus `robots.txt` y términos de servicio. Para el contexto académico del TFM, se usará con fines de investigación y sin distribución comercial. Las fuentes gubernamentales (Eurostat, INE, UNWTO) son de uso libre.

**Frecuencia de refresco:** Diaria para fuentes primarias (TUI) y secundarias de ocupación (Booking). Mensual para fuentes estadísticas (Eurostat, INE). Puntual/semanal para fuentes de texto (Reddit, foros).

---

## BLOQUE 1 — Preguntas Resueltas

### PENDIENTE-001 → DECISIÓN-002 | 2026-07-29 | Estado: Tomada

**Pregunta resuelta:** ¿Con qué frecuencia refrescar los datos de TUI?
**Decisión:** Refresco **diario** para fuentes primarias (TUI) y secundarias de ocupación (Booking.com). Mensual para fuentes estadísticas (Eurostat, INE, UNWTO). Puntual para corpus textual (Reddit, foros).
**Justificación:** Los precios y disponibilidad de TUI cambian diariamente. Los datos estadísticos oficiales se publican con periodicidad mensual o trimestral, por lo que un refresco más frecuente no aporta valor.

---

### PENDIENTE-002 → DECISIÓN-003 | 2026-07-29 | Estado: Tomada

**Pregunta resuelta:** ¿Qué mercados de TUI cubrir?
**Decisión:** Cubrir los **tres mercados**: España (tui.es), Alemania (tui.com) y Reino Unido (tui.co.uk).
**Impacto en NLP:** El sistema deberá gestionar textos en tres idiomas — español, alemán e inglés. Se usará un modelo de embeddings multilingüe (paraphrase-multilingual-MiniLM o similar).
**Impacto en datos:** Aumenta el volumen del catálogo y la diversidad de precios (EUR y GBP).

---

### PENDIENTE-003 → DECISIÓN-004 | 2026-07-29 | Estado: Tomada

**Pregunta resuelta:** ¿Reddit vía API oficial (PRAW) o scraping directo?
**Decisión:** **API oficial de Reddit con PRAW**.
**Justificación:**
- Gratuita. Solo requiere crear una app en reddit.com/prefs/apps (5 minutos).
- Datos estructurados en JSON: título, texto, puntuación, fecha, subreddit, comentarios.
- Estable ante cambios de HTML en la web de Reddit.
- Académicamente correcta — citarla como fuente de datos estructurada en la memoria del TFM.
- Límite de 100 peticiones/minuto, suficiente para el volumen del proyecto.
- Scraping directo fue descartado por fragilidad y restricciones de Reddit desde 2023.
**Subreddits objetivo:** r/travel, r/solotravel, r/backpacking, r/Flights, r/TravelHacks, r/vacation.

---

## BLOQUE 2 — Embeddings y NLP

### DECISIÓN-006 | 2026-07-29 | Estado: Parcialmente tomada

**Área:** Modelo de embeddings

**Decisión:** Comparar `paraphrase-multilingual-MiniLM-L12-v2` (Sentence-BERT) vs `multilingual-e5-large` (Microsoft) antes de comprometerse con uno.

**Metodología de comparación:**
1. Scrapeamos un conjunto piloto de ~50-100 paquetes de TUI con sus descripciones
2. Generamos embeddings con ambos modelos
3. Medimos similitud coseno entre paquetes del mismo destino — el modelo que produzca clusters más coherentes gana
4. El experimento se documenta en la memoria del TFM como criterio de selección de modelo

**Características comparadas:**

| Característica | MiniLM-L12-v2 | multilingual-e5-large |
|----------------|--------------|----------------------|
| Dimensión del vector | 384 | 1024 |
| Idiomas soportados | 50+ | 100+ |
| Coste | Gratuito, local | Gratuito, local |
| Velocidad | Rápido | Más lento |
| RAM requerida | ~500 MB | ~2.5 GB |
| Calidad semántica | Buena | Muy buena |
| Recomendado para TFM | Sí (prototipo) | Sí (si hay GPU/RAM) |

**Estado:** Pendiente de experimento de comparación. Se registrará como DECISIÓN-006b cuando se elija el modelo final.

---

### DECISIÓN-007 | 2026-07-29 | Estado: Tomada

**Área:** Contenido del embedding — qué texto se embedda

**Decisión:** Embedding híbrido de dos componentes:

1. **Embedding del paquete** — concatenación de: `nombre_paquete` + `descripcion_texto` + `categoria` + `destino_nombre` (texto de TUI). Captura lo que TUI dice del producto.

2. **Embedding de reputación del destino** — promedio de los embeddings de las reseñas de TripAdvisor y Reddit asociadas al destino. Captura la percepción real del viajero (saturación, calidad de experiencia, temporadas, etc.).

**Vector semántico final del paquete** = promedio ponderado de (1) y (2), con peso configurable.

**Justificación:** Las reseñas capturan información que TUI no declara explícitamente — "masificado en verano", "tranquilo en temporada baja", "ideal para familias con niños". Este contexto enriquece la representación semántica y mejora la calidad de las recomendaciones.

**Wikipedia descartada** en esta fase: añadiría complejidad sin impacto crítico para el prototipo. Se deja como mejora futura.

---

### DECISIÓN-008 | 2026-07-29 | Estado: Tomada

**Área:** Fusión de embedding textual con atributos numéricos

**Decisión:** **Concatenación ponderada (weighted fusion)**

**Fórmula del vector final de cada paquete:**

```
vector_final = [embedding_semántico | w₁·precio_norm | w₂·duracion_norm | w₃·ocupacion_norm | w₄·accesibilidad_norm | w₅·estrellas_norm | w₆·num_valoraciones_norm | w₇·sostenibilidad_norm]
```

Donde `w₁...w₇` son pesos configurables que escalan cada atributo antes de concatenar.

**Atributos numéricos incluidos en el vector:**

| Atributo | Normalización | Peso inicial |
|----------|--------------|-------------|
| `precio_base_eur` | Min-max global | w₁ = 1.0 |
| `duracion_dias` | Min-max global | w₂ = 0.5 |
| `nivel_ocupacion` | Ya en [0,1] | w₃ = 1.5 (mayor peso — clave para TDRS) |
| `accesibilidad_destino` | Escala 1-3 → [0,1] | w₄ = 0.8 |
| `estrellas_hotel` | Escala 3-5 → [0,1] | w₅ = 0.7 |
| `num_valoraciones_hotel` | Log-normalización | w₆ = 0.6 |
| `indicador_sostenibilidad_tui` | Booleano → 0/1 | w₇ = 1.0 |

**Justificación de ponderación vs concatenación simple:** Los pesos permiten controlar la importancia relativa de cada atributo en el vector final. Por ejemplo, dar más peso a `nivel_ocupacion` hace que el modelo distinga mejor entre destinos saturados y libres — clave para el TDRS. Los pesos se documentan y justifican en la memoria como decisión de diseño.

**Los pesos son hiperparámetros** — se calibrarán durante el entrenamiento del modelo y se versionarán en el fichero de configuración.

---

## BLOQUE 3 — Data Engineering

### DECISIÓN-009 | 2026-07-29 | Estado: Tomada

**Área:** Base de datos principal — almacenamiento estructurado

**Decisión:** Estrategia en dos fases:
- **Fase 1 (prototipo TFM):** SQLite — sin instalación, fichero local, desarrollo ágil
- **Fase 2 (escalado):** PostgreSQL — robusto, gratuito, soporta JSON, concurrencia y extensión pgvector

**Justificación:** SQLite permite arrancar en horas sin configurar servidores. La migración a PostgreSQL es directa con SQLAlchemy (mismo ORM, cambio de connection string). Azure SQL / Cosmos DB descartado para el TFM por complejidad de credenciales y coste, aunque sería la opción natural en un entorno productivo TUI.

**Tablas principales:**

| Tabla | Contenido | Fase |
|-------|-----------|------|
| `paquetes` | Entidad PAQUETE completa (30+ campos) | SQLite → PostgreSQL |
| `resenas` | Entidad RESEÑA (10 campos) | SQLite → PostgreSQL |
| `indicadores_destino` | Entidad INDICADOR DE DESTINO (12 campos) | SQLite → PostgreSQL |
| `usuarios` | Perfiles de viajero (sintéticos + reales) | SQLite → PostgreSQL |
| `interacciones` | Historial usuario-paquete | SQLite → PostgreSQL |
| `embeddings_meta` | Metadatos de embeddings (id, modelo, fecha) | SQLite → PostgreSQL |

**ORM:** SQLAlchemy — abstrae la base de datos y facilita la migración SQLite → PostgreSQL sin cambiar el código de acceso a datos.

---

### DECISIÓN-010 | 2026-07-29 | Estado: Tomada

**Área:** Almacenamiento y búsqueda vectorial (embeddings)

**Decisión:** Estrategia en dos fases:
- **Fase 1 (prototipo TFM):** Chroma — base de datos vectorial embebida en Python, corre en memoria o persiste en disco, sin infraestructura adicional
- **Fase 2 (escalado):** pgvector — extensión de PostgreSQL, integrada en la misma BD relacional, cero overhead de servicio extra

**Justificación:** Chroma se instala con `pip install chromadb` y funciona directamente en Python sin levantar ningún servicio. Cuando migremos a PostgreSQL, pgvector añade índices HNSW para búsqueda KNN aproximada con latencia <10ms. Qdrant descartado para el prototipo por requerir un servicio separado.

**Operaciones vectoriales principales:**

| Operación | Descripción | Latencia objetivo |
|-----------|-------------|------------------|
| `add_embeddings` | Insertar vector de paquete | <100ms |
| `query_similar` | Encontrar K paquetes más similares a perfil usuario | <500ms para 10K paquetes |
| `update_embedding` | Actualizar vector cuando cambian datos del paquete | <100ms |
| `delete_embedding` | Eliminar vector si paquete se da de baja | <50ms |

**Dimensión de vectores:** 384 (MiniLM) o 1024 (e5-large) — se configura al inicializar la colección.

---

### DECISIÓN-011 | 2026-07-29 | Estado: Tomada

**Área:** Capa de servicio de datos — API

**Decisión:** **FastAPI** como capa REST entre la base de datos, el modelo recomendador y las interfaces.

**Endpoints principales planificados:**

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/paquetes` | GET | Listar paquetes con filtros (región, categoría, temporada) |
| `/paquetes/{id}` | GET | Detalle de un paquete |
| `/recomendaciones` | POST | Obtener top-K recomendaciones dado un perfil de usuario |
| `/destinos/{id}/indicadores` | GET | Indicadores de saturación y demanda de un destino |
| `/oportunidades` | GET | Listado de destinos con oportunidad de mercado |
| `/metricas` | GET | Métricas del modelo (Precision@K, NDCG@K, Gini...) |
| `/health` | GET | Estado operativo de cada módulo del sistema |

**Justificación:** FastAPI genera documentación automática (Swagger/OpenAPI), es asíncrono, tiene validación de esquemas con Pydantic y es el estándar para APIs Python modernas. La documentación automática es especialmente útil para el TFM — los endpoints quedan documentados sin esfuerzo adicional.

**GraphQL descartado:** Mayor curva de aprendizaje sin beneficio claro para el volumen de consultas del TFM.
**Acceso directo a BD descartado:** Acopla el modelo a la BD y dificulta el testing y la mantenibilidad.

---

## Decisiones de Arquitectura

*(Se irán añadiendo conforme avancemos en el diseño técnico)*

---

## Decisiones de Modelo

*(Se irán añadiendo en el Bloque 4)*

---

## Decisiones de Productivización

*(Se irán añadiendo en el Bloque 6)*

---

---

### DECISIÓN-005 | 2026-07-29 | Estado: Tomada

**Área:** Esquema de datos — campos a extraer y almacenar

**Decisión:** Definir el esquema completo de las tres entidades principales del sistema.

---

#### ENTIDAD: PAQUETE (fuente principal: TUI)

**Identificación y trazabilidad**

| Campo | Tipo | Descripción | Fuente |
|-------|------|-------------|--------|
| `id_paquete` | string | Identificador único generado | Sistema |
| `fuente` | string | tui.es / tui.com / tui.co.uk | Scraper |
| `url_origen` | string | URL exacta de extracción | Scraper |
| `fecha_extraccion` | datetime | Timestamp del scraping | Scraper |

**Trazabilidad de procedencia por campo**

| Campo | Tipo | Descripción | Fuente |
|-------|------|-------------|--------|
| `origen_datos_producto` | string | Fuente de los datos del producto (nombre_paquete, descripcion, categoria, etc.) — ej: "tui.es", "tui.com", "tui.co.uk" | Scraper |
| `origen_datos_precio` | string | Fuente del precio y disponibilidad — ej: "tui.es", "tui.co.uk" | Scraper |
| `origen_datos_valoraciones` | string | Fuente de las valoraciones — ej: "booking.com", "tripadvisor.es", "tripadvisor.com" | Scraper secundario |
| `origen_datos_ocupacion` | string | Fuente del nivel de ocupación — ej: "booking.com", "ine.es", "eurostat" | Scraper / API |
| `origen_datos_accesibilidad` | string | Fuente de los campos de accesibilidad — ej: "tui.es", "booking.com", "openstreetmap" | Scraper / API |
| `origen_datos_sostenibilidad` | string | Fuente del indicador de sostenibilidad — ej: "tui.es", "calculado" | TUI / Calculado |
| `fecha_ultima_actualizacion` | datetime | Timestamp de la última actualización de cualquier campo del registro | Sistema |

**Destino**

| Campo | Tipo | Descripción | Fuente |
|-------|------|-------------|--------|
| `destino_nombre` | string | Nombre del destino (ej: "Mallorca") | TUI |
| `pais` | string | País del destino | TUI |
| `region` | string | Mediterráneo / Caribe / Otro | TUI / calculado |
| `ciudad_salida` | string | Ciudad de origen del vuelo | TUI |
| `aeropuerto_salida` | string | Código IATA origen (MAD, BCN, LHR...) | TUI |
| `aeropuerto_llegada` | string | Código IATA destino | TUI |

**Producto**

| Campo | Tipo | Descripción | Fuente |
|-------|------|-------------|--------|
| `nombre_paquete` | string | Título del paquete en TUI | TUI |
| `descripcion_texto` | string | Descripción completa (para embeddings NLP) | TUI |
| `categoria` | string | Sol y playa / Cultural / Aventura / Bienestar / Familiar / Lujo | TUI |
| `tipo_alojamiento` | string | Hotel / Resort / Apartamento | TUI |
| `nombre_hotel` | string | Nombre del hotel | TUI |
| `estrellas_hotel` | int | 3 / 4 / 5 | TUI |
| `regimen` | string | Todo incluido / Media pensión / Solo alojamiento | TUI |
| `duracion_dias` | int | Duración del paquete en días | TUI |
| `incluye_vuelo` | bool | True / False | TUI |

**Precio y disponibilidad**

| Campo | Tipo | Descripción | Fuente |
|-------|------|-------------|--------|
| `precio_base_eur` | float | Precio en euros (convertido si viene en GBP) | TUI |
| `precio_original` | float | Precio en moneda original | TUI |
| `moneda_original` | string | EUR / GBP | TUI |
| `disponibilidad` | int | Plazas disponibles o estimación | TUI |
| `fecha_salida` | date | Fecha de salida | TUI |
| `fecha_vuelta` | date | Fecha de regreso | TUI |
| `temporada` | string | Alta / Media / Baja (calculado desde fechas) | Calculado |

**Valoraciones**

| Campo | Tipo | Descripción | Fuente |
|-------|------|-------------|--------|
| `puntuacion_media_hotel` | float | Puntuación media del hotel (escala 1-10) | Booking / TripAdvisor |
| `num_valoraciones_hotel` | int | Número total de reseñas del hotel | Booking / TripAdvisor |
| `puntuacion_destino` | float | Valoración media del destino (escala 1-10) | TripAdvisor |
| `num_valoraciones_destino` | int | Número de reseñas del destino | TripAdvisor |

**Accesibilidad**

| Campo | Tipo | Descripción | Fuente |
|-------|------|-------------|--------|
| `accesibilidad_hotel` | bool | El hotel declara instalaciones adaptadas para movilidad reducida | TUI / Booking |
| `accesibilidad_destino` | int | Escala 1-3: Baja / Media / Alta (basada en infraestructura) | Calculado / OpenStreetMap |
| `distancia_aeropuerto_km` | float | Distancia en km del hotel al aeropuerto de llegada | OpenStreetMap |

**Sostenibilidad y saturación**

| Campo | Tipo | Descripción | Fuente |
|-------|------|-------------|--------|
| `indicador_sostenibilidad_tui` | bool | TUI lo etiqueta como producto sostenible | TUI |
| `nivel_ocupacion` | float | % de ocupación del destino (0-1) | Booking / INE |
| `nivel_saturacion` | string | Alto / Medio / Bajo (calculado) | Calculado |
| `sensibilidad_ambiental` | int | Escala 1-5 (calculada o declarada por TUI) | TUI / Calculado |

---

#### ENTIDAD: RESEÑA (fuentes: TripAdvisor, Reddit, foros)

| Campo | Tipo | Descripción | Fuente |
|-------|------|-------------|--------|
| `id_resena` | string | Identificador único | Sistema |
| `id_destino_referencia` | string | FK al destino al que hace referencia | Sistema |
| `fuente` | string | TripAdvisor / Reddit / LonelyPlanet | Scraper |
| `texto_original` | string | Texto completo de la reseña (para embeddings) | Scraper |
| `idioma` | string | es / de / en | Detectado automáticamente |
| `puntuacion` | float | 1 a 5 si aplica (null si no tiene puntuación) | Scraper |
| `fecha_publicacion` | date | Fecha de publicación de la reseña | Scraper |
| `url_origen` | string | URL de la reseña | Scraper |
| `origen_dato` | string | Nombre exacto de la fuente — ej: "tripadvisor.es", "reddit/r/travel", "lonelyplanet.com/thorntree" | Scraper |
| `fecha_extraccion` | datetime | Timestamp de cuando se extrajo esta reseña | Scraper |

---

#### ENTIDAD: INDICADOR DE DESTINO (fuentes: Eurostat, INE, UNWTO)

| Campo | Tipo | Descripción | Fuente |
|-------|------|-------------|--------|
| `id_destino` | string | Identificador único | Sistema |
| `destino_nombre` | string | Nombre del destino | Eurostat / INE |
| `pais` | string | País | Eurostat |
| `region` | string | Mediterráneo / Caribe | Calculado |
| `pernoctaciones_anuales` | int | Total de pernoctaciones anuales | Eurostat / INE |
| `llegadas_internacionales` | int | Llegadas turísticas internacionales | UNWTO |
| `variacion_interanual_pct` | float | Variación % respecto al año anterior | Calculado |
| `mes_referencia` | string | Mes al que corresponden los datos (YYYY-MM) | Fuente |
| `indice_gini_local` | float | Gini de distribución mensual de demanda (0-1) | Calculado |
| `origen_dato` | string | Nombre exacto de la fuente — ej: "eurostat.ec.europa.eu", "ine.es", "unwto.org", "ourworldindata.org" | Sistema |
| `url_origen` | string | URL exacta del dataset o endpoint consultado | Sistema |
| `fecha_extraccion` | datetime | Timestamp de cuando se descargó o consultó este indicador | Sistema |

---

**Decisión adicional — Imágenes:** Solo texto. No se capturan imágenes de los paquetes. Los embeddings se generarán únicamente a partir de texto (descripción del paquete, nombre del hotel, destino, categoría). Esto simplifica el pipeline y es suficiente para el alcance del TFM.

**Justificación del número de valoraciones:** Un hotel con 4.5/5 basado en 12 reseñas es diferente a uno con 4.5/5 basado en 3.200. El volumen de valoraciones es proxy de popularidad y sirve como señal para el TDRS — destinos con pocas valoraciones pueden ser candidatos a "emergentes".

**Justificación de accesibilidad:** El target premium de TUI incluye viajeros mayores y con movilidad reducida. La accesibilidad es también un criterio de redistribución: destinos accesibles pero poco conocidos son oportunidades directas para el motor.

---

*Última actualización: 2026-07-29 — Bloque 3 Data Engineering documentado (DECISIONES-009, 010, 011)*
*Próxima revisión: Al completar el diseño técnico del Bloque 1*

---

## BLOQUE 7 — Datos Reales Externos

### DECISIÓN-016 | 2026-08-02 | Estado: Tomada, pendiente de autorización académica

**Área:** Fuentes de datos — sustitución de datos sintéticos por datasets académicos reales

**Decisión:** Incorporar los datasets del repositorio NTIC UCM 2025 como **fuente primaria** de catálogo, reseñas e interacciones. Los datos sintéticos (`data/sample_tui.db`: 10.000 paquetes, 1.000 usuarios) quedan relegados a relleno para escenarios de cold-start, identificados con `es_sintetico = TRUE`.

**Datasets incorporados:**

| Dataset | Aportación | Volumen |
|---------|-----------|---------|
| `Destinia/Customer Bookings/` | Interacciones y perfiles reales | ~150.000 reservas |
| `Destinia/experiences_catalog_v1.csv` | Catálogo real de experiencias | ~6.000 experiencias |
| `Destinia/Review Dataset/` | Reseñas con `Sentiment Score` | ~50.000 reseñas |
| `Smart Touring/Movement Distribution Data/` | Movilidad real (Meta Data-for-Good, GADM, España 2023-2025) | 33 CSV |
| `Smart Touring/interes_turistico_mensual_por_ciudad.csv` | Estacionalidad real | 8 ciudades, 2021-2025 |
| `REDESCUBRIENDO ESPAÑA/Ciudades_Nivel_Turismo.csv` | Ground truth `Exc_turismo` | Ciudades etiquetadas |
| `REDESCUBRIENDO ESPAÑA/Reviews_Data_Final.csv` | Etiqueta `Molestia` | Reseñas con molestia percibida |
| `SmartCity Tour/Data.csv` | `CATEGORIA_TUI`, `ACCESIBILIDAD_SILLA_RUEDAS` (Google Places) | Puntos de interés |

**Justificación:** 150.000 reservas reales y ~50.000 reseñas con sentimiento aportan una validez que el generador sintético no puede replicar. Los perfiles sintéticos generados con Dirichlet producen preferencias uniformes que no reflejan el comportamiento real de reserva, y la demanda simulada distorsiona las métricas de redistribución. El usuario ha manifestado explícitamente que no quiere usar datos sintéticos.

**Alternativa descartada:** Continuar con el generador sintético calibrando sus distribuciones a partir de las reseñas scrapeadas. Descartada porque mantiene la circularidad (el sistema se evalúa contra datos que él mismo genera) y no resuelve la ausencia de interacciones reales.

**Riesgo abierto:** Requiere confirmación del tutor sobre la autorización de uso y la forma de citación de datasets procedentes de otros TFM del repositorio académico. Ningún dataset externo se incluye en la memoria del TFM antes de esa confirmación.

---

### DECISIÓN-017 | 2026-08-02 | Estado: Tomada

**Área:** Fuente de la ocupación real — Meta Movement Distribution (Data-for-Good) frente a INE/Eurostat

**Decisión:** Calcular `nivel_ocupacion` a partir de `Smart Touring/Movement Distribution Data/` (Meta Data-for-Good), normalizando el volumen de movilidad observada al rango [0, 1] por zona GADM y mes. INE y Eurostat se conservan como fuente de **contraste de validación**, no como fuente primaria.

**Justificación:** Meta Data-for-Good ofrece granularidad por zona GADM y por mes con cobertura 2023-2025, mientras que INE y Eurostat agregan por provincia y publican con retardo. Para un índice como el TDRS, que penaliza la saturación a nivel de destino, la resolución territorial y temporal es determinante.

**Alternativa descartada:** INE/Eurostat como fuente primaria — agregación provincial demasiado gruesa y retardo de publicación incompatible con el ciclo de refresco del sistema.

**Limitación documentada:** La cobertura de Meta Data-for-Good en este dataset es **solo España**. Los destinos de Caribe y de Mediterráneo no español mantienen ocupación estimada y se marcan con `origen_datos_ocupacion = "estimado"` (RF-17.5), quedando diferenciados en el reporte.

---

### DECISIÓN-018 | 2026-08-02 | Estado: Tomada

**Área:** Embeddings — ampliación del vector híbrido de D+7 a D+9

**Decisión:** Ampliar el vector híbrido definido en DECISIÓN-008 con dos atributos numéricos nuevos:

| Atributo nuevo | Origen | Peso |
|----------------|--------|------|
| `sentiment_score_medio_destino` | `Sentiment Score` de `Destinia/Review Dataset/`, promediado por destino | `w8 = 0.9` |
| `ratio_molestia_destino` | etiqueta `Molestia` de `Reviews_Data_Final.csv`, proporción por destino | `w9 = 1.2` |

Dimensión resultante: **D + 9** — 400 dimensiones con MiniLM-384 (antes 391).

**Justificación:** El sentimiento agregado y la molestia percibida por los residentes son señales directas de saturación que ningún atributo actual del vector captura. `ratio_molestia_destino` recibe el peso más alto después de `nivel_ocupacion` (w3 = 1.5) porque mide impacto social directo sobre la población local, que es precisamente el fenómeno que el TDRS pretende mitigar.

**Alternativa descartada:** Introducir ambas señales únicamente como filtros post-ranking. Descartada porque perdería su contribución en el espacio de similitud: dos paquetes idénticos en el resto de atributos pero con molestia percibida muy distinta seguirían siendo vecinos en el espacio vectorial.

**Consecuencia operativa:** Obliga a regenerar todos los embeddings del catálogo y a versionar `embeddings_meta` con `embedding_dim = 400`. Los vectores D+7 y D+9 no son comparables, por lo que el almacén vectorial se recrea completo.

---

### DECISIÓN-019 | 2026-08-02 | Estado: Tomada

**Área:** Evaluación — validación externa del TDRS contra `Exc_turismo`

**Decisión:** Validar el `nivel_saturacion` calculado por el sistema contra el campo `Exc_turismo` de `REDESCUBRIENDO ESPAÑA/Ciudades_Nivel_Turismo.csv` como etiqueta de referencia independiente, reportando AUC-ROC, precisión, exhaustividad y matriz de confusión. **Umbral objetivo: AUC-ROC ≥ 0,70.** Se añade la correlación de Spearman frente a la etiqueta `Molestia` como validación complementaria.

**Justificación:** El TDRS es una construcción propia de este TFM. Sin validación contra una etiqueta externa e independiente no es defendible en la memoria: solo se podría afirmar que el sistema hace lo que se le ha programado hacer. Contrastarlo con una clasificación de exceso de turismo elaborada por terceros convierte el TDRS en un indicador validado empíricamente.

**Alternativa descartada:** Validar únicamente con la reducción del Gini entre escenarios. Descartada por circular: mide el propio mecanismo de redistribución del sistema, no su correspondencia con la saturación real del territorio.

**Transparencia:** Si el AUC-ROC no alcanza 0,70, el resultado se registra tal cual y se documentan las hipótesis de desviación (cobertura territorial parcial, desalineación entre destinos TUI y ciudades españolas etiquetadas). No se oculta ni se recalibra la métrica para superar el umbral.

---

### DECISIÓN-020 | 2026-08-02 | Estado: Tomada

**Área:** Scraping — migración del scraper de ocupación a Playwright

**Decisión:** Migrar `BookingOccupancyScraper` de Selenium a **Playwright**, siguiendo el patrón de `scraper_booking_final.py` del repositorio académico. El resto de scrapers (TripAdvisor, Google Maps, YouTube con Selenium; Reddit vía Arctic Shift) se mantienen sin cambios.

**Justificación:** El patrón de `scraper_booking_final.py` resiste mejor la detección anti-bot de Booking.com que el Selenium actual (gestión de contexto de navegador, interceptación de red, esperas basadas en eventos en lugar de esperas fijas). El resto de scrapers ya funciona de forma estable, por lo que migrarlos añadiría riesgo sin beneficio.

**Saturación del scraping documentada:** El corpus de scraping está saturado en **18.502 reseñas**. En la última ronda de 60 minutos, de 804 reseñas extraídas 789 fueron duplicados (98,1%). El crecimiento del corpus proviene por tanto de los datasets externos del Bloque 7, no de más rondas de scraping. El scraping se conserva como fuente complementaria de refresco de precios y ocupación.

---

### DECISIÓN-021 | 2026-08-25 | Estado: Tomada

**Área:** Embeddings — selección final de modelo y arquitectura del vector híbrido (actualiza DECISIÓN-006/018)

**Contexto:** Las DECISIONES-016 a 020 (sesión 2026-08-02) quedan como guía inicial no vinculante. Tras verificación del equipo, se confirma que los datos sintéticos de `experiencias`, `customer_bookings` y `reviews_dataset` proceden del dataset compartido por TUI, no de datasets externos de otros proyectos académicos. Se retira por tanto el riesgo de autorización señalado en DECISIÓN-016, y se mantiene la arquitectura D+7 original (DECISIÓN-008), no la ampliación a D+9 de DECISIÓN-018.

**Decisión:**
1. **Modelo de embeddings**: `intfloat/multilingual-e5-large` (1024 dim), seleccionado sobre `paraphrase-multilingual-MiniLM-L12-v2` (384 dim) mediante el experimento de coherencia de clusters definido en DECISIÓN-006, sobre un corpus piloto de 100 experiencias. Resultado: e5-large = 0.9478, MiniLM = 0.8250 de similitud coseno intra-cluster (mismo destino+categoría). Costo: ~2.2h para regenerar el catálogo completo (5850 experiencias), asumible dentro del cronograma.
2. **Sentimiento**: se mantiene D+7. El atributo `estrellas_hotel_norm` se calcula como mezcla 50/50 entre el rating sintético de `experiencias` y el sentimiento real agregado por destino, calculado con XLM-RoBERTa multilingüe (`cardiffnlp/twitter-xlm-roberta-base-sentiment`) sobre las 37.956 reseñas reales scrapeadas por el equipo (cobertura: 38/39 destinos del catálogo). No se usa el `Sentiment Score` de fuentes externas propuesto en DECISIÓN-018.
3. **Ocupación**: `nivel_ocupacion` se calcula desde `indicadores_destino` (Eurostat/INE, ya poblado con 3342 registros), no desde Meta Movement Distribution (fuente propuesta en DECISIÓN-017, no verificada/disponible para el equipo).

**Justificación:** Se prioriza usar fuentes de datos generadas y verificadas directamente por el equipo (scraping propio + análisis de sentimiento propio) sobre fuentes externas de procedencia no confirmada, manteniendo la arquitectura D+7 ya documentada y validada en el resto del pipeline (`HybridVectorBuilder`, `recommendation_engine.py`).

**Archivos generados:** `data/embeddings/hybrid_vectors.npy`, `paquete_ids.npy`, `package_embeddings.npy` (versión oficial, e5-large). Se conservan además `hybrid_vectors_e5large.npy` y análogos como copia explícita de la versión ganadora, y puede regenerarse la versión MiniLM con `--modelo paraphrase-multilingual-MiniLM-L12-v2` si se necesita comparar de nuevo.

**Pendiente de equipo:** Confirmar con Steph la procedencia exacta de `customer_bookings`/`reviews_dataset` para dejarlo documentado sin ambigüedad en la memoria final (citación correcta si en algún punto se usó material de otros TFM).

---
## Historial de Conversaciones

Esta sección referencia los temas discutidos en cada sesión de trabajo para trazabilidad del TFM.

### Sesión 2026-07-29
- Definición del alcance general del proyecto y los 6 bloques del pipeline
- Creación del documento vision.md
- Exportación de vision.md a PDF (vision_TUI.pdf)
- Identificación y clasificación de fuentes de datos (primarias, secundarias, terciarias, datos abiertos)
- Resolución de pendientes: frecuencia de refresco (diaria), mercados (ES/DE/UK), acceso a Reddit (PRAW)
- Definición del esquema completo de datos: entidades PAQUETE, RESEÑA e INDICADOR DE DESTINO con todos sus campos
- Decisiones: número de valoraciones (sí), accesibilidad (sí), imágenes (no — solo texto)
- Campo `origen_dato` / `origen_datos_*` añadido a las tres entidades para trazabilidad completa de procedencia
- Bloque 2 NLP/Embeddings: modelo a comparar (MiniLM vs e5-large), texto a embeddir (paquete + reseñas), fusión ponderada con pesos configurables (DECISIONES-006, 007, 008)
- Bloque 3 Data Engineering: SQLite→PostgreSQL, Chroma→pgvector, FastAPI REST (DECISIONES-009, 010, 011)

### Sesión 2026-08-02
- Lectura y exploración del repositorio académico `Datos NTIC UCM 2025`: Destinia (reservas, catálogo de experiencias, reseñas con `Sentiment Score`), Smart Touring (movilidad Meta Data-for-Good, estacionalidad mensual por ciudad, Google Places), REDESCUBRIENDO ESPAÑA (`Exc_turismo`, `Molestia`), Discoverxo y el resto de proyectos
- Diagnóstico del estado actual: scraping saturado en 18.502 reseñas (789 duplicados de 804 extracciones en la última ronda de 60 min); catálogo y usuarios sintéticos; Gini tradicional inflado por los pesos desiguales de destinos de `generate_sample_data.py` (0,5923) y Gini moderado poco realista (0,1559); RF-5.4 no alcanzado (Precision@10 = 0,0937; NDCG@10 = 0,3078)
- Identificación de mejoras aplicables al proyecto en cuatro frentes: scraping (Playwright), datos (sustitución de sintéticos por reales), embeddings (sentimiento y molestia percibida) y modelo (interacciones reales, indicadores territoriales reales, validación externa)
- Definición del **Bloque 7 — Integración de Datos Reales Externos** como bloque transversal de ingesta conectado al Bloque 1 (limpieza) y al Bloque 3 (persistencia), con regeneración forzada de los Bloques 2 y 4
- Nuevos requisitos 15 a 18: ingesta de datasets externos reales, interacciones reales y reducción de la dependencia de usuarios sintéticos, indicadores territoriales reales de saturación y estacionalidad, y validación externa del TDRS contra ground truth de overtourism
- Nuevas propiedades PBT-8 (idempotencia de la carga externa) y PBT-9 (suma de preferencias en perfiles derivados de reservas reales)
- Decisiones: sustitución de datos sintéticos por datasets académicos reales (016), Meta Data-for-Good como fuente de ocupación real (017), ampliación del vector híbrido de D+7 a D+9 (018), validación externa del TDRS contra `Exc_turismo` (019), migración del scraper de ocupación a Playwright (020)
- Riesgo abierto registrado: la incorporación de los datasets externos queda pendiente de confirmación del tutor sobre autorización de uso y forma de citación
