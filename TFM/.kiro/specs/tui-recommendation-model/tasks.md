# Plan de Implementación: Motor de Recomendación Turística TUI

## Visión General

El sistema se implementa en Python 3.11+ siguiendo los seis bloques del pipeline definidos en el diseño técnico. El orden de implementación respeta las dependencias entre bloques: Bloque 1 (Scraping y Limpieza) y Bloque 2 (Embeddings) son independientes entre sí y se pueden desarrollar en paralelo; el Bloque 3 (Data Engineering) los integra; los Bloques 4, 5 y 6 se construyen sobre el Bloque 3.

El usuario ha indicado que quiere trabajar **bloque a bloque, comenzando por el Bloque 1**. Las tareas hoja del Bloque 1 no tienen dependencias previas y pueden ejecutarse inmediatamente.

---

## Tareas

- [x] 1. Bloque 1 — Scraping y Limpieza de Datos
  - [x] 1.1 Crear estructura de carpetas y configuración base del proyecto
    - Crear la estructura de directorios completa definida en design.md: `src/scraping/`, `src/embeddings/`, `src/data/`, `src/api/`, `src/recommender/`, `src/llm/`, `app/`, `tests/unit/`, `tests/pbt/`, `tests/integration/`, `scripts/`, `data/raw/`, `data/processed/`, `data/embeddings/`
    - Crear `config.yml` con todas las secciones documentadas: scraping, embeddings, modelo, tdrs, reranking, llm, bd
    - Crear `.env.example` con plantilla de variables de entorno (API keys, DATABASE_URL, API_BASE_URL)
    - Crear `requirements.txt` con versiones fijadas para todas las dependencias del backend (selenium, playwright, beautifulsoup4, praw, sqlalchemy, chromadb, fastapi, pydantic, lightfm, hypothesis, tiktoken, openai)
    - Crear `requirements-app.txt` para las dependencias Streamlit
    - Añadir `__init__.py` en todos los módulos Python
    - _Requisitos: NF-3.3_

  - [x] 1.2 Implementar los modelos de datos SQLAlchemy y la capa de base de datos
    - Crear `src/data/models.py` con los modelos SQLAlchemy para las tablas: `paquetes`, `resenas`, `indicadores_destino`, `usuarios`, `interacciones`, `embeddings_meta`, `paquetes_versiones`
    - Implementar el esquema completo de la tabla `paquetes` con todos los campos definidos en DECISIÓN-005 (identificación, trazabilidad por campo, destino, producto, precio, valoraciones, accesibilidad, sostenibilidad)
    - Implementar la tabla `paquetes_versiones` para gestión de versiones del catálogo con hash SHA-256
    - Crear `src/data/repository.py` con la clase `Repositorio` (operaciones CRUD sobre SQLite/PostgreSQL vía SQLAlchemy)
    - Implementar `src/data/retry_policy.py` con la clase `RetryPolicy` (3 reintentos, backoff exponencial 1s/2s/4s)
    - _Requisitos: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x] 1.3 Implementar el módulo `DataCleaner` (limpiador de datos)
    - Crear `src/scraping/cleaner.py` con la clase `DataCleaner`
    - Implementar `deduplicate()`: clave de unicidad `(destino_nombre, nombre_hotel, fecha_salida, fecha_vuelta, ciudad_salida)`; en caso de duplicado conservar el registro con `fecha_extraccion` más reciente
    - Implementar `normalize_minmax()`: transformación min-max sobre el conjunto completo de cada ciclo; postcondición todos los valores numéricos procesados ∈ [0, 1]
    - Implementar `validate_schema()`: verificar presencia y tipo de todos los atributos obligatorios del paquete
    - Implementar `exclude_invalid()`: si más del 30% de atributos obligatorios vacíos, marcar como inválido y registrar motivo de exclusión; lanzar `ValidationError` tipada para entradas con `nivel_ocupacion > 1` o `precio_base_eur < 0`
    - _Requisitos: 1.6, 1.7, 1.8_

  - [ ]* 1.4 Escribir tests unitarios para DataCleaner
    - Crear `tests/unit/test_cleaner.py`
    - Testear `deduplicate()`: caso con duplicados exactos, caso sin duplicados, conservación del registro más reciente
    - Testear `normalize_minmax()`: postcondición de rango [0, 1], caso de todos los valores iguales (división por cero)
    - Testear `exclude_invalid()`: registro con >30% atributos vacíos, registro válido, caso límite exactamente 30%
    - _Requisitos: 1.6, 1.7, 1.8_

  - [ ]* 1.5 Escribir property-based test PBT-7 para DataCleaner
    - Crear `tests/pbt/test_pbt_data.py`
    - **Propiedad PBT-7: Error controlado en datos de entrada inválidos**
    - Para cualquier entrada con `nivel_ocupacion > 1` o `precio_base_eur < 0`, el `DataCleaner` debe lanzar una excepción tipada y documentada sin producir resultados silenciosos ni corruptos
    - Usar `hypothesis.strategies` para generar valores fuera de rango (floats > 1, valores negativos)
    - **Valida: Requisito 1.7, 1.8**

  - [x] 1.6 Implementar los scrapers de TUI (tres mercados)
    - Crear `src/scraping/tui_spider.py` con la clase base `TUISpider` (atributos `market`, `base_url`)
    - Implementar `extract_packages(region)`: usa Selenium/Playwright para renderizado JS; extrae todos los campos del esquema ENTIDAD PAQUETE (destino, precio, duración, hotel, categoría, accesibilidad, sostenibilidad, temporada, disponibilidad)
    - Implementar `extract_package_detail(url)`: extrae descripción textual completa y atributos adicionales de la página de detalle
    - Implementar `handle_http_error(url, status_code)`: registrar URL afectada, código HTTP y marca temporal; continuar con las fuentes restantes
    - Añadir lógica de reintentos: 3 intentos con backoff exponencial (1s, 2s, 4s); respetar `robots.txt`
    - Instanciar subclases para los tres mercados: ES (`tui.es`), DE (`tui.com`), UK (`tui.co.uk`)
    - Implementar `calcular_temporada(fecha_salida)`: Alta (jun/jul/ago/dic), Baja (ene/feb/mar/nov), Media (resto)
    - _Requisitos: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 1.7 Implementar los scrapers de fuentes secundarias y terciarias
    - Crear `src/scraping/tripadvisor_scraper.py` con `TripAdvisorScraper` (BeautifulSoup): extraer reseñas de texto, puntuaciones y ranking de popularidad por destino
    - Crear `src/scraping/reddit_collector.py` con `RedditCollector` (PRAW): coleccionar posts y comentarios de r/travel, r/solotravel, r/backpacking, r/Flights, r/TravelHacks, r/vacation; credenciales desde variables de entorno
    - Crear `src/scraping/booking_scraper.py` con `BookingOccupancyScraper` (Selenium): extraer disponibilidad hotelera y nivel de ocupación estimado
    - Crear `src/scraping/statistics_client.py` con `StatisticsClient`: clientes para Eurostat (API REST), INE (API JSON), UNWTO (descarga datasets); métodos `fetch_occupancy()` y `fetch_arrivals()`
    - Añadir detección automática de idioma con `langdetect` en el campo `idioma` de las reseñas
    - _Requisitos: 1.1, 1.2, 1.4_

  - [x] 1.8 Implementar el `ScraperOrchestrator` y el script de ejecución
    - Crear `src/scraping/orchestrator.py` con la clase `ScraperOrchestrator`
    - Implementar `run_cycle(sources)`: coordina la ejecución de todos los scrapers, pasa los datos crudos al `DataCleaner` y persiste los resultados válidos en el Repositorio con metadatos de procedencia (URL fuente, fecha de extracción, versión del scraper)
    - Implementar `schedule(cron_expr)`: periodicidad configurable no superior a 7 días sin intervención manual
    - Implementar `get_last_run_status()`: devuelve estado de la última ejecución por fuente
    - Crear `scripts/run_scraping.py`: script CLI para ejecutar un ciclo de scraping completo
    - _Requisitos: 1.3, 1.4, 1.5_

- [~] 2. Checkpoint Bloque 1 — Verificar pipeline de ingestión
  - Ejecutar `scripts/run_scraping.py` con un conjunto reducido de URLs de prueba (mocks)
  - Verificar que los datos crudos se persisten en la base de datos con metadatos de procedencia completos
  - Verificar que los datos limpios superan la validación de esquema
  - Asegurarse de que todos los tests del Bloque 1 pasan. Preguntar al usuario si tiene dudas antes de continuar.

- [ ] 3. Bloque 2 — Embeddings y NLP
  - [~] 3.1 Implementar `TextEmbedder` con soporte multilingüe
    - Crear `src/embeddings/text_embedder.py` con la clase `TextEmbedder`
    - Implementar `embed_text(text)`: retorna `np.ndarray` de dimensión fija D (384 o 1024 según config.yml); la dimensión de salida es constante independientemente de la longitud del texto de entrada
    - Implementar `embed_batch(texts, batch_size=64)`: procesamiento por lotes configurable para catálogos grandes
    - Leer `model_name` y `model_version` desde `config.yml`; documentar nombre, versión y fuente del modelo en el fichero de configuración versionado
    - Soportar modelos candidatos: `paraphrase-multilingual-MiniLM-L12-v2` (dim=384) y `multilingual-e5-large` (dim=1024)
    - _Requisitos: 2.3, 3.1, 3.2, 3.3, 3.4, 3.5, NF-3.1_

  - [ ]* 3.2 Escribir tests unitarios para TextEmbedder
    - Crear `tests/unit/test_embeddings.py`
    - Testear dimensión constante de salida para textos de longitudes muy distintas (1 token vs 512 tokens)
    - Testear que `embed_batch` produce mismos resultados que llamadas individuales
    - Testear similitud coseno > 0.85 para paquetes semánticamente equivalentes (mismo destino, categoría, temporada)
    - _Requisitos: 3.3, 3.6_

  - [~] 3.3 Implementar `ReviewAggregator`, `SemanticFuser` y `HybridVectorBuilder`
    - Crear `src/embeddings/review_aggregator.py`: `ReviewAggregator.aggregate()` con mean pooling de embeddings de reseñas de un destino
    - Crear `src/embeddings/semantic_fuser.py`: `SemanticFuser.fuse()` con promedio ponderado configurable (package_weight=0.6, review_weight=0.4 desde config.yml)
    - Crear `src/embeddings/hybrid_vector_builder.py`: `HybridVectorBuilder.build()` que concatena el vector semántico con los 7 atributos numéricos ponderados (w1..w7 configurables en config.yml)
    - Pesos por defecto de DECISIÓN-008: precio_norm(1.0), duración_norm(0.5), nivel_ocupacion(1.5), accesibilidad_norm(0.8), estrellas_norm(0.7), valoraciones_norm(0.6), sostenibilidad(1.0)
    - El vector final tiene dimensión D+7; actualizar `embeddings_meta` en el Repositorio con `fecha_generacion` al sobreescribir
    - _Requisitos: 3.1, 3.2, 3.5_

  - [~] 3.4 Implementar la capa de almacenamiento vectorial (Chroma)
    - Crear `src/data/vector_store.py` con el wrapper sobre Chroma (o pgvector en escalado)
    - Implementar `add_embeddings(id_paquete, vector)`: insertar vector; latencia objetivo <100ms
    - Implementar `query_similar(user_vector, k)`: recuperar K paquetes más similares; latencia <500ms para 10K paquetes
    - Implementar `update_embedding(id_paquete, vector)`: actualizar vector y `embeddings_meta.fecha_generacion`
    - Implementar `delete_embedding(id_paquete)`: eliminar vector; latencia <50ms
    - Crear `scripts/generate_embeddings.py`: script CLI para regenerar embeddings del catálogo completo en batch
    - _Requisitos: 3.5, NF-2.3_

  - [ ]* 3.5 Escribir property-based test PBT-5 para round-trip de serialización
    - Ampliar `tests/pbt/test_pbt_data.py` o crear `tests/pbt/test_pbt_embeddings.py`
    - **Propiedad PBT-5: Round-trip de serialización del Perfil_Viajero y vectores**
    - Para cualquier vector `np.ndarray` válido generado por `HybridVectorBuilder`, serializar y deserializar (JSON y `.npy`) debe producir un array numéricamente idéntico
    - Para cualquier `PerfilViajeroRequest` válido, serializar y deserializar con el ORM/Pydantic debe producir un objeto equivalente
    - Usar `hypothesis` con estrategias de arrays NumPy y perfiles generados aleatoriamente
    - **Valida: Requisito 3.5, NF-3 (reproducibilidad)**

- [~] 4. Checkpoint Bloque 2 — Verificar generación de embeddings
  - Ejecutar `scripts/generate_embeddings.py` sobre un subset de 20 paquetes de prueba
  - Verificar que los vectores se almacenan en Chroma con la dimensión correcta
  - Verificar que la búsqueda de similitud devuelve resultados coherentes
  - Asegurarse de que todos los tests del Bloque 2 pasan. Preguntar al usuario si tiene dudas antes de continuar.

- [ ] 5. Bloque 3 — Data Engineering (API y usuarios sintéticos)
  - [~] 5.1 Implementar el generador de usuarios sintéticos
    - Crear `src/data/synthetic_users.py` con la clase `SyntheticUserGenerator`
    - Implementar `generate_batch(n=500)`: generar N perfiles con atributos coherentes entre sí usando distribuciones estadísticas definidas en design.md (Dirichlet para preferencias, lognormal para presupuesto, Beta para interés en sostenibilidad)
    - Garantizar que la suma de preferencias temáticas ∈ [0.99, 1.01] (validado por `validate_coherence()`)
    - Fijar semilla aleatoria desde `config.yml` (NF-3.1); documentar el valor de semilla
    - Implementar deduplicación: si dos perfiles tienen valores idénticos en todos los atributos, conservar solo uno y registrar duplicados eliminados
    - Producir al menos 500 perfiles distintos antes de iniciar el entrenamiento
    - Crear `scripts/generate_synthetic_users.py`: script CLI para generar y persistir el batch de usuarios
    - _Requisitos: 2.1, 2.2, 2.4, 2.5, NF-3.1_

  - [~] 5.2 Implementar los modelos Pydantic y la app FastAPI
    - Crear `src/api/schemas.py` con todos los modelos Pydantic: `PerfilViajeroRequest` (con validador cross-field de suma de preferencias), `RecomendacionRequest`, `PaqueteRecomendado`, `ExplicacionFactores`, `OportunidadMercado`, `MetricasModelo`, `HealthStatus`
    - Crear `src/api/main.py` con la app FastAPI y los routers
    - Crear `src/api/dependencies.py` con la inyección de dependencias (repositorio, vector store, modelos)
    - Implementar los endpoints: `POST /recomendaciones` (<3s e2e), `GET /paquetes` (<500ms, paginado), `GET /oportunidades`, `GET /metricas`, `GET /health`
    - El endpoint `/health` devuelve estado de Scraper, Repositorio, Modelo_Afinidad, LLM_Adapter en JSON (NF-4.4)
    - _Requisitos: 4.3, 4.4, 9.1, 9.2, 10.4, 12.1, 12.2, 12.3, 13.4, NF-4.4_

  - [ ]* 5.3 Escribir tests de integración para los endpoints FastAPI
    - Crear `tests/integration/test_api_endpoints.py`
    - Testear `POST /recomendaciones` con perfil válido e inválido (suma preferencias ≠ 1)
    - Testear `GET /health` devuelve estructura JSON con los cuatro módulos
    - Testear `GET /oportunidades` con y sin filtros de zona/temporada
    - Testear latencias: `/recomendaciones` <3s, `/paquetes` <500ms
    - _Requisitos: 4.3, 4.4, NF-1.1, NF-4.4_

- [ ] 6. Bloque 4 — Modelo Recomendador (Afinidad, TDRS, Re-ranking)
  - [~] 6.1 Implementar el modelo baseline de afinidad por similitud de coseno
    - Crear `src/recommender/affinity/cosine_model.py` con la clase `CosineAffinityModel`
    - Implementar `score(user_vector, package_vector)`: similitud del coseno normalizada a [0,1] mediante `(cos+1)/2`; postcondición: resultado ∈ [0,1] (PBT-1)
    - Implementar `top_k(user_vector, catalog_vectors, k)`: retorna índices de los K paquetes más afines; latencia <100ms para 10K paquetes (RF-5.2)
    - Construir el vector de usuario como promedio ponderado de vectores de paquetes interaccionados (pesos: valoracion=1.0, reserva=0.8, visualizacion=0.3); para usuarios sin historial, construir desde preferencias temáticas del perfil
    - _Requisitos: 5.1, 5.2, 5.3_

  - [~] 6.2 Implementar el modelo avanzado de afinidad con LightFM
    - Crear `src/recommender/affinity/lightfm_model.py` con la clase `LightFMAffinityModel`
    - Implementar `train(interactions, item_features, user_features, epochs=30, num_threads=4, random_state=42)`: usar pérdida WARP para implicit feedback; documentar hiperparámetros en config.yml (NF-3.2)
    - Implementar `score(user_id, item_id)`: puntuación normalizada [0,1] (PBT-1)
    - Implementar `top_k(user_id, k)`: latencia <100ms por usuario (RF-5.2)
    - Crear partición train/test con al menos 20% de interacciones en test; verificar ausencia de data leakage (RF-14.5)
    - Crear `scripts/train_model.py`: script CLI para entrenar ambas variantes y registrar hiperparámetros
    - _Requisitos: 5.3, 5.4, 5.5, 14.1, 14.5, NF-3.1_

  - [ ]* 6.3 Escribir tests unitarios y property-based tests para los modelos de afinidad
    - Añadir a `tests/unit/test_embeddings.py` o crear `tests/unit/test_affinity.py`
    - Testear que `CosineAffinityModel.score()` retorna valores ∈ [0,1] para vectores aleatorios
    - Testear determinismo: mismo input → mismo output (PBT-2)
    - **Propiedad PBT-1: Invariante del rango de puntuaciones** — en `tests/pbt/test_pbt_afinidad.py`
    - Para cualquier par (usuario, paquete) válido, `Afinidad(u,e) ∈ [0,1]`
    - **Propiedad PBT-2: Determinismo** — misma entrada produce ranking idéntico en dos invocaciones
    - Para usuarios con perfiles idénticos, el ranking de afinidad debe ser idéntico (RF-5.7)
    - **Valida: Requisitos 5.1, 5.7**

  - [~] 6.4 Implementar el `TDRSCalculator`
    - Crear `src/recommender/tdrs_calculator.py` con la clase `TDRSCalculator`
    - Implementar `calculate(afinidad, capacidad, accesibilidad, impacto_local, temporada_baja, diversificacion, ocupacion, sensibilidad_ambiental)` con la fórmula de 8 componentes ponderados; postcondición: TDRS ∈ [-1, 1] (PBT-1, RF-6.3)
    - Exponer pesos w1..w8 como parámetros configurables en `config.yml` con valores predeterminados documentados (RF-6.2); Σ|wᵢ| = 1.0
    - Implementar regla RF-6.4: si `ocupacion > 0.85`, forzar `ocupacion = 1.0`
    - Implementar `recalculate_for_destination(destino_id)`: recalcular TDRS de todos los paquetes de un destino tras actualización de datos (RF-6.5)
    - _Requisitos: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 6.5 Escribir tests unitarios y property-based tests para TDRSCalculator
    - Crear `tests/unit/test_tdrs.py` con tests unitarios
    - Testear rango de salida ∈ [-1, 1] para combinaciones extremas de inputs
    - Testear regla de ocupación: `ocupacion=0.86` → forzado a 1.0; verificar que reduce el TDRS
    - **Propiedad PBT-1 (TDRS): Invariante de rango** — `TDRS(u,e) ∈ [-1,1]` para cualquier input válido
    - **Propiedad PBT-3: Monotonía del TDRS respecto a la Ocupación** — en `tests/pbt/test_pbt_afinidad.py`
    - Para cualquier paquete con los demás factores constantes, mayor `ocupacion` ⟹ TDRS menor o igual
    - **Valida: Requisitos 6.1, 6.3, 6.4**

  - [~] 6.6 Implementar el `ReRankingEngine` y `ExplainabilityBuilder`
    - Crear `src/recommender/reranking_engine.py` con `ReRankingEngine`
    - Implementar `score_final(score_base, redistribucion, sostenibilidad, capacidad, saturacion, escenario)` con los tres escenarios (α+β+γ+δ+λ=1.0); postcondición determinista (PBT-2, RF-7.6)
    - Implementar `rank(candidates, escenario, k=10)`: ordenar por Score_Final desc; desempate por orden alfabético de `id_paquete` (RF-7.7); latencia <500ms para K=10 (RF-7.4)
    - Implementar `rank_all_scenarios(candidates, k=10)`: retorna los tres rankings en una sola llamada (RF-7.2)
    - Incluir la regla RF-7.3 en el escenario intensivo: al menos 30% de los K paquetes deben corresponder a destinos distintos al más recomendado en el ranking tradicional
    - Exponer coeficientes α, β, γ, δ, λ como configurables en runtime sin reentrenamiento (RF-7.5)
    - Crear `src/recommender/explainability.py` con `ExplainabilityBuilder.build()`: desglose de afinidad, TDRS, saturación; indicar cambio de posición entre rankings y motivo (RF-9.1, RF-9.3); latencia <200ms adicionales (RF-9.4)
    - _Requisitos: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 9.1, 9.2, 9.3, 9.4_

  - [ ]* 6.7 Escribir tests unitarios y property-based tests para ReRankingEngine
    - Crear `tests/unit/test_reranking.py`
    - Testear que los tres escenarios suman coeficientes = 1.0
    - Testear determinismo: mismo input → mismo ranking (PBT-2)
    - Testear desempate por id_paquete alfabético (RF-7.7)
    - **Propiedad PBT-4: Cobertura mínima del ranking redistributivo**
    - Para escenario intensivo con al menos 20 candidatos de al menos 5 destinos distintos, el top-10 debe contener al menos 3 destinos distintos
    - **Propiedad PBT-6: Invariante de ordenación del ranking** — en `tests/pbt/test_pbt_afinidad.py`
    - Para cualquier par e1, e2 en el ranking, `posicion(e1) < posicion(e2)` implica `Score_Final(e1) >= Score_Final(e2)`
    - **Valida: Requisitos 7.1, 7.3, 7.6, 7.7**

  - [~] 6.8 Implementar `MarketOpportunityDetector` y `TerritorialImpactSimulator`
    - Crear `src/recommender/opportunity_detector.py` con `MarketOpportunityDetector`
    - Implementar `calculate_opportunity_score(afinidad_media, nivel_ocupacion)`: `indicador = afinidad_media - nivel_ocupacion`; destino con oportunidad si indicador > umbral configurable (default 0.20)
    - Implementar `detect_opportunities(destinos)`: agregar por zona geográfica y temporada; asociar perfil de usuario más frecuentemente afín (RF-10.5)
    - Crear `src/recommender/territorial_simulator.py` con `TerritorialImpactSimulator`
    - Implementar `simulate(users, escenarios)`: simular distribución de demanda para los tres escenarios sobre ≥500 usuarios; latencia <60s en entorno con 4 núcleos (RF-11.5)
    - Implementar `calcular_gini(demand_distribution)`, `calcular_cr5(demand_distribution)`, `export_csv(results, path)`
    - Registrar alerta en log si Gini_moderado ≥ Gini_tradicional (RF-11.4)
    - Crear `scripts/run_simulation.py`: script CLI para ejecutar la simulación de impacto territorial
    - _Requisitos: 10.1, 10.2, 10.3, 10.4, 10.5, 11.1, 11.2, 11.3, 11.4, 11.5_

  - [~] 6.9 Implementar la evaluación y comparación de modelos
    - Añadir a `scripts/train_model.py` la evaluación de todas las variantes del Modelo_Afinidad sobre el conjunto de test (≥20% de interacciones)
    - Calcular y registrar todas las métricas: Precision@K, Recall@K, NDCG@K, MAP@K (K∈{5,10}), intra-list diversity, cobertura, novedad, Gini_Turístico, CR5
    - Almacenar resultados en fichero JSON/CSV estructurado con: nombre de variante, fecha, todos los valores de métricas (RF-14.3)
    - Incluir comparación tabular de variantes ordenadas por NDCG@10 desc (RF-14.4)
    - Verificar ausencia de data leakage: el test no debe contener usuarios ni interacciones del train (RF-14.5)
    - Verificar que la variante avanzada alcanza Precision@10 ≥ 0.30 y NDCG@10 ≥ 0.35 (RF-5.4)
    - _Requisitos: 5.4, 5.5, 14.1, 14.2, 14.3, 14.4, 14.5_

- [~] 7. Checkpoint Bloque 4 — Verificar núcleo algorítmico
  - Ejecutar `scripts/train_model.py` sobre datos sintéticos generados en el Bloque 3
  - Verificar que el reporte de evaluación se genera con todas las métricas requeridas
  - Asegurarse de que todos los tests del Bloque 4 pasan. Preguntar al usuario si tiene dudas antes de continuar.

- [ ] 8. Bloque 5 — Integración con LLM
  - [~] 8.1 Implementar `LLMAdapter` con gestión de errores y fallback
    - Crear `src/llm/llm_adapter.py` con la clase `LLMAdapter`
    - Leer `model_name` desde `config.yml`; API key desde variable de entorno `OPENAI_API_KEY` (RF-8.6)
    - Implementar `generate(prompt)`: llamada a la API OpenAI con timeout configurable; tiempo objetivo <5s (RF-8.4)
    - Definir jerarquía de excepciones: `LLMError`, `LLMTimeoutError`, `LLMRateLimitError` (con `retry_after_seconds`), `LLMUnavailableError`, `LLMEmptyResponseError`, `LLMInvalidResponseError`, `BudgetExceededError`
    - Implementar `is_available()`: health check ligero de la API
    - Si el LLM no está disponible, activar automáticamente el fallback y registrar la indisponibilidad (RF-8.5)
    - _Requisitos: 8.1, 8.4, 8.5, 8.6_

  - [~] 8.2 Implementar `PromptBuilder` y `FallbackTemplateEngine`
    - Crear `src/llm/prompt_builder.py` con `PromptBuilder.build(paquete, perfil)`: construir prompt personalizado inyectando preferencia dominante, presupuesto, temporada preferida e idioma (es/de/en)
    - Inyectar bloque de sostenibilidad si `paquete.tdrs > 0.6` (RF-8.3)
    - Garantizar que el prompt contiene al menos uno de: preferencia temática dominante, rango de presupuesto, temporada preferida (RF-8.2)
    - Crear `src/llm/fallback_templates.py` con `FallbackTemplateEngine` multilingüe (es/de/en): plantillas predefinidas que producen texto nunca vacío, siempre con `destino_nombre` y `categoria` como substrings
    - _Requisitos: 8.1, 8.2, 8.3, 8.5_

  - [~] 8.3 Implementar `LLMResponseValidator`, `TokenCounter` y `UsageLogger`
    - Crear `src/llm/response_validator.py` con `LLMResponseValidator.validate(response, paquete)`: verificar longitud >10 chars, detectar precios alucinados (diferencia >10% del `precio_base_eur`), detectar hotel o destino incorrecto
    - Crear `src/llm/token_counter.py` con `TokenCounter`: estimación de tokens con `tiktoken` (cl100k_base); `check_budget(prompt)` verifica límite configurable; `register_usage()` acumula uso real; activar fallback si se supera el presupuesto (BudgetExceededError)
    - Crear `src/llm/usage_logger.py` con `UsageLogger.log_llm_call()`: registrar por línea en JSON: id_paquete, id_usuario, tokens, latencia, modelo, used_fallback, fallback_reason
    - _Requisitos: 8.4, 8.5_

  - [ ]* 8.4 Escribir tests unitarios y property-based tests para el Bloque 5
    - Crear `tests/unit/test_llm_adapter.py` y `tests/unit/test_fallback_templates.py`
    - Testear que `FallbackTemplateEngine.generate()` nunca retorna vacío ni None para cualquier combinación válida de paquete y perfil
    - Testear que `LLMResponseValidator` detecta precios con diferencia >10%
    - Crear `tests/pbt/test_pbt_llm.py`
    - **Propiedad B5-1:** Prompt siempre contiene al menos un elemento de personalización del perfil
    - **Propiedad B5-2:** Prompt incluye mención de sostenibilidad cuando TDRS > 0.6
    - **Propiedad B5-3:** Fallback nunca produce texto vacío ante cualquier tipo de error LLM
    - **Propiedad B5-4:** Descripción de fallback contiene `destino_nombre` y `categoria` como substrings
    - **Propiedad B5-5:** `TokenCounter.count_tokens(t) > 0` para cualquier texto no vacío; monotonía débil
    - **Propiedad B5-6:** Validador detecta precios alucinados (diferencia >10%)
    - **Valida: Requisitos 8.2, 8.3, 8.5**

- [ ] 9. Bloque 6 — Productivización (Streamlit)
  - [~] 9.1 Implementar `APIClient` y configuración de la app Streamlit
    - Crear `app/api/client.py` con `APIClient`: wrapper sobre todos los endpoints FastAPI; gestionar `ConnectionError`, `Timeout` y `HTTPError` mostrando mensajes de error comprensibles al usuario (RF-12.6)
    - Implementar `get_recomendaciones_todos_escenarios()`: tres llamadas en paralelo con `ThreadPoolExecutor` (RF-12.5); latencia <3s total
    - Crear `app/config.py`: leer `API_BASE_URL`, `API_TIMEOUT`, `CACHE_TTL_METRICAS`, `CACHE_TTL_HEALTH`, `DEFAULT_IDIOMA`, `TOP_K_RECOMENDACIONES` desde variables de entorno con valores por defecto
    - Crear la estructura de directorios de la app: `app/Home.py`, `app/pages/`, `app/components/`
    - Implementar `inicializar_session_state()` con todas las claves definidas en design.md
    - _Requisitos: 12.5, 12.6, NF-1.1_

  - [~] 9.2 Implementar el formulario de perfil y la comparativa de escenarios (`App_Usuario`)
    - Crear `app/components/perfil_form.py` con `render_perfil_form()`: 6 sliders de preferencias temáticas (paso 0.05), indicador de suma con color rojo/verde, sliders de presupuesto y duración, selectbox de temporada, checkbox de accesibilidad, slider de interés en sostenibilidad
    - Validar que la suma de preferencias ∈ [0.99, 1.01] antes de llamar a la API; retornar `None` si no es válida (B6-1)
    - Crear `app/components/ranking_card.py` con `render_ranking_card()`: tarjeta con posición, nombre, destino, precio, categoría, barra de Score_Final, descripcion_llm y expander de explicabilidad
    - Crear `app/components/explicabilidad_panel.py` con `render_explicabilidad_panel()`: métricas de afinidad, TDRS normalizado [-1,1]→[0,1], saturación con color rojo si >0.7, motivo de cambio de posición
    - Crear `app/pages/1_App_Usuario.py`: formulario + llamada a los tres escenarios + comparativa en tres columnas (B6-2); persistir perfil en session_state entre cambios de escenario (B6-5)
    - _Requisitos: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

  - [~] 9.3 Implementar el `Dashboard_TUI`
    - Crear `app/components/metricas_redistribucion.py` con `render_metricas_redistribucion()`: métricas Gini y CR5 para los tres escenarios con deltas; alerta si Gini_moderado ≥ Gini_tradicional (RF-11.4)
    - Implementar `render_mapa_saturacion(destinos)`: mapa de calor geográfico con Altair; color según nivel de saturación [0,1] con escala redyellowgreen invertida
    - Implementar `render_tabla_oportunidades(oportunidades)`: tabla con filtros por zona y temporada; columna `indicador_oportunidad` como ProgressColumn; ordenada descendente (RF-10.4)
    - Implementar `render_diversidad_catalogo(metricas)`: intra-list diversity, cobertura, novedad; gráfico de barras por categoría
    - Implementar `render_export_button(metricas)`: botón de descarga CSV con todas las métricas en un clic (RF-13.6)
    - Implementar `render_health_status(health)`: estado de los cuatro módulos con iconos de color (NF-4.4)
    - Crear `app/components/health_status.py` y `app/pages/2_Dashboard_TUI.py` con refresco automático de métricas cada 60s (RF-13.5)
    - _Requisitos: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

  - [ ]* 9.4 Escribir property-based tests para la capa UI (Bloque 6)
    - Crear `tests/pbt/test_pbt_ui.py`
    - **Propiedad B6-1:** Con sliders cuya suma difiere de 1.0 en >0.01, `render_perfil_form()` retorna `None` y no llama a la API
    - **Propiedad B6-2:** `render_comparativa_escenarios()` siempre renderiza exactamente 3 escenarios
    - **Propiedad B6-3:** `safe_api_call()` nunca propaga excepciones de red; siempre retorna `None` ante errores de conexión
    - **Propiedad B6-4:** Todas las claves de `session_state` existen tras cualquier flujo de navegación
    - **Propiedad B6-5:** El `perfil_actual` persiste en session_state entre cambios de escenario
    - **Valida: Requisito 12** (robustez de la interfaz de usuario)

  - [ ]* 9.5 Escribir test de integración end-to-end del pipeline
    - Crear `tests/integration/test_pipeline_e2e.py`
    - Testear flujo completo: perfil → recomendaciones → descripciones LLM (o fallback) → explicabilidad
    - Verificar tiempo de respuesta e2e <3s para un usuario (NF-1.1)
    - Verificar que los tres escenarios producen rankings distintos cuando los parámetros difieren
    - _Requisitos: NF-1.1, 12.2, 12.3_

- [~] 10. Checkpoint Final — Verificar sistema completo
  - Ejecutar la suite completa de tests (`pytest tests/`) y verificar cobertura >70% en módulos Limpiador, Embedder, Modelo_Afinidad, TDRS y Motor_Reranking (NF-3.4)
  - Ejecutar `scripts/run_simulation.py` sobre 500 usuarios sintéticos y verificar que genera el CSV de métricas
  - Verificar que el endpoint `/health` devuelve estado operativo de todos los módulos
  - Asegurarse de que todos los tests pasan. Preguntar al usuario si tiene dudas antes de continuar.

---

## Notas

- Las tareas marcadas con `*` son opcionales (tests) y pueden saltarse para una iteración MVP más rápida. Sin embargo, se recomienda su implementación para alcanzar la cobertura de código >70% exigida por NF-3.4.
- Cada tarea referencia los requisitos específicos del documento `requirements.md` para trazabilidad completa.
- Los checkpoints garantizan validación incremental bloque a bloque.
- Las propiedades PBT (Hypothesis) verifican invariantes matemáticos del sistema que los tests unitarios no pueden cubrir exhaustivamente.
- El Bloque 1 (tareas 1.1–1.8) no tiene dependencias previas y puede ejecutarse inmediatamente.
- Los Bloques 1 y 2 pueden desarrollarse en paralelo; el Bloque 3 los integra.
- La semilla aleatoria global debe fijarse al valor documentado en `config.yml` en todos los módulos con aleatoriedad (NF-3.1).
- El stack tecnológico está fijado: Python 3.11+, SQLite→PostgreSQL, Chroma→pgvector, FastAPI, Streamlit, LightFM, Hypothesis.

---

## Task Dependency Graph

```json
{
  "waves": [
    {
      "id": 0,
      "tasks": ["1.1"]
    },
    {
      "id": 1,
      "tasks": ["1.2", "1.3", "3.1"]
    },
    {
      "id": 2,
      "tasks": ["1.4", "1.5", "1.6", "3.2", "3.3"]
    },
    {
      "id": 3,
      "tasks": ["1.7", "3.4", "3.5"]
    },
    {
      "id": 4,
      "tasks": ["1.8"]
    },
    {
      "id": 5,
      "tasks": ["5.1", "5.2"]
    },
    {
      "id": 6,
      "tasks": ["5.3", "6.1"]
    },
    {
      "id": 7,
      "tasks": ["6.2"]
    },
    {
      "id": 8,
      "tasks": ["6.3", "6.4"]
    },
    {
      "id": 9,
      "tasks": ["6.5", "6.6"]
    },
    {
      "id": 10,
      "tasks": ["6.7", "6.8"]
    },
    {
      "id": 11,
      "tasks": ["6.9"]
    },
    {
      "id": 12,
      "tasks": ["8.1"]
    },
    {
      "id": 13,
      "tasks": ["8.2", "8.3"]
    },
    {
      "id": 14,
      "tasks": ["8.4"]
    },
    {
      "id": 15,
      "tasks": ["9.1"]
    },
    {
      "id": 16,
      "tasks": ["9.2", "9.3"]
    },
    {
      "id": 17,
      "tasks": ["9.4", "9.5"]
    }
  ]
}
```
