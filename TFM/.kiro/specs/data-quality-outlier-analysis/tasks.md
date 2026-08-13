# Implementation Plan: Data Quality & Outlier Analysis

## Overview

Implementación del Jupyter Notebook `notebooks/Calidad_Datos_Outliers.ipynb` que analiza las 11 fuentes de datos del sistema de recomendación turística TUI. El notebook se estructura en secciones secuenciales con funciones auxiliares reutilizables, análisis de calidad (nulos, duplicados, consistencia), detección y tratamiento de outliers, y generación de un DataFrame limpio en `data/processed/dataframe_limpio.csv`.

## Tasks

- [ ] 1. Crear estructura base del notebook y funciones auxiliares
  - [ ] 1.1 Crear el notebook con celdas de título, imports y configuración inicial
    - Crear `notebooks/Calidad_Datos_Outliers.ipynb` con celda markdown de título/descripción
    - Celda de código con imports: pandas, numpy, scipy.stats, sklearn (IsolationForest, LocalOutlierFactor), matplotlib, seaborn, pathlib, sqlite3
    - Definir constantes `DATA_DIR`, `PROCESSED_DIR`, `EMBEDDINGS_DIR` y el diccionario `FUENTES_CONFIG` con las 11 rutas
    - Configurar matplotlib inline y estilo visual (seaborn style)
    - _Requirements: 1.1_

  - [ ] 1.2 Implementar funciones auxiliares de perfilado y carga
    - Implementar `cargar_fuente()` que maneja CSV, SQLite (.db con todas sus tablas) y .npy
    - Implementar `perfilar_fuente()` que retorna dict con nombre, filas, columnas, dtypes, memoria_mb
    - Manejar errores gracefully: archivo no encontrado retorna None y registra mensaje descriptivo
    - _Requirements: 1.2, 1.3, 1.4_

  - [ ] 1.3 Implementar funciones auxiliares de análisis de nulos y duplicados
    - Implementar `analisis_nulos()` con nulos_abs, nulos_pct, marca columnas críticas (>50%)
    - Implementar `indicador_completitud()` que calcula celdas no nulas / total celdas
    - Implementar `detectar_duplicados()` con conteo, pct_unicos, ejemplos y verificación de IDs
    - _Requirements: 2.1, 2.2, 2.4, 3.1, 3.3, 3.4_

  - [ ] 1.4 Implementar funciones auxiliares de detección de outliers
    - Implementar `detectar_outliers_iqr()` con umbral 1.5×IQR
    - Implementar `detectar_outliers_zscore()` con umbral |z| > 3
    - Implementar `detectar_outliers_multivariante()` con Isolation Forest y LOF
    - Implementar `estadisticos_descriptivos()` con los 9 estadísticos
    - Implementar `tabla_resumen_outliers()` para generar tabla consolidada
    - _Requirements: 6.1, 6.2, 6.5, 5.3, 6.4_

  - [ ] 1.5 Implementar funciones auxiliares de consistencia, tratamiento y correlación
    - Implementar `verificar_rango()` para detectar valores fuera de rangos lógicos
    - Implementar `cobertura_cruzada()` para comparar destinos entre fuentes
    - Implementar `aplicar_winsorizacion()` con percentiles 5-95
    - Implementar `generar_dataframe_limpio()` con estrategias y columna `_outlier_flag`
    - Implementar `seleccionar_top_cv()` para las 5 variables con mayor coeficiente de variación
    - Implementar `calcular_correlacion_significativa()` con Pearson/Spearman y p-value
    - _Requirements: 4.3, 4.1, 4.2, 8.2, 8.5, 7.4, 9.3_

  - [ ]* 1.6 Escribir property tests para funciones auxiliares de perfilado
    - **Property 1: Profiling summary completeness**
    - **Property 2: Graceful handling of missing data sources**
    - **Validates: Requirements 1.2, 1.4**

  - [ ]* 1.7 Escribir property tests para análisis de nulos
    - **Property 3: Null analysis correctness**
    - **Property 4: Critical column threshold marking**
    - **Property 5: Completitud indicator formula**
    - **Validates: Requirements 2.1, 2.2, 2.4**

  - [ ]* 1.8 Escribir property tests para detección de duplicados y consistencia
    - **Property 6: Duplicate detection and uniqueness indicator**
    - **Property 7: Cross-source destination coverage**
    - **Property 8: Range validation correctness**
    - **Validates: Requirements 3.1, 3.3, 3.4, 4.1, 4.2, 4.3**

  - [ ]* 1.9 Escribir property tests para detección de outliers
    - **Property 9: Descriptive statistics completeness**
    - **Property 11: IQR outlier detection correctness**
    - **Property 12: Z-score outlier detection correctness**
    - **Property 13: Outlier summary table structure**
    - **Validates: Requirements 5.3, 6.1, 6.2, 6.4**

  - [ ]* 1.10 Escribir property tests para tratamiento y correlación
    - **Property 15: Top coefficient of variation selection**
    - **Property 16: Winsorization bounds invariant**
    - **Property 18: Outlier flag correctness**
    - **Property 19: Significant correlation reporting threshold**
    - **Validates: Requirements 7.4, 8.2, 8.5, 9.3**

- [ ] 2. Implementar secciones de carga, perfilado y análisis de nulos/duplicados
  - [ ] 2.1 Implementar sección §1 — Carga y perfilado de fuentes
    - Celda markdown con título de sección
    - Código que itera sobre FUENTES_CONFIG, llama a `cargar_fuente()` y almacena resultados
    - Llamar `perfilar_fuente()` para cada DataFrame cargado
    - Mostrar tabla resumen con perfiles de las 11 fuentes
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ] 2.2 Implementar sección §2 — Análisis de valores nulos
    - Celda markdown con título de sección
    - Aplicar `analisis_nulos()` a cada DataFrame tabular
    - Generar heatmaps de nulidad para fuentes con >3 columnas usando `heatmap_nulidad()`
    - Calcular indicador de completitud global por fuente
    - Marcar y listar columnas críticas (>50% nulos)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ] 2.3 Implementar sección §3 — Detección de duplicados
    - Celda markdown con título de sección
    - Aplicar `detectar_duplicados()` a cada fuente tabular con sus columnas ID correspondientes
    - Mostrar ejemplos de primeras 5 filas duplicadas por fuente
    - Calcular indicador de unicidad por fuente
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ] 3. Checkpoint - Verificar ejecución parcial
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implementar secciones de consistencia, distribuciones y detección de outliers
  - [ ] 4.1 Implementar sección §4 — Consistencia e integridad
    - Celda markdown con título de sección
    - Extraer sets de nombres de destinos por fuente y aplicar `cobertura_cruzada()`
    - Verificar rangos lógicos: precios ≥ 0, ratings en [1, 5], porcentajes en [0, 100]
    - Verificar integridad referencial entre tablas SQLite (claves foráneas)
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [ ] 4.2 Implementar sección §5 — Distribuciones
    - Celda markdown con título de sección
    - Generar histogramas con KDE para cada variable numérica usando `histograma_kde()`
    - Generar gráficos de barras para variables categóricas con <30 categorías
    - Calcular `estadisticos_descriptivos()` por variable y mostrar en tabla
    - Detectar y señalar variables con asimetría > 2, sugerir transformaciones
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ] 4.3 Implementar sección §6 — Detección de outliers
    - Celda markdown con título de sección
    - Aplicar `detectar_outliers_iqr()` y `detectar_outliers_zscore()` a todas las variables numéricas
    - Generar boxplots anotados con `boxplot_outliers()` para cada variable con outliers
    - Aplicar `detectar_outliers_multivariante()` (Isolation Forest) a combinaciones de variables
    - Generar tabla resumen con `tabla_resumen_outliers()`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 5. Implementar secciones de visualización, tratamiento y relaciones
  - [ ] 5.1 Implementar sección §7 — Visualización de outliers y patrones
    - Celda markdown con título de sección
    - Generar scatter plots con outliers resaltados usando `scatter_outliers()`
    - Calcular y visualizar matriz de correlación (Pearson y Spearman) como heatmap
    - Generar scatter plots con regresión para pares con |r| > 0.7
    - Generar pair plots para las 5 variables con mayor CV usando `seleccionar_top_cv()`
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ] 5.2 Implementar sección §8 — Tratamiento de outliers y DataFrame limpio
    - Celda markdown con título de sección
    - Definir diccionario de estrategias por variable (winsorización, eliminación, mediana)
    - Aplicar `generar_dataframe_limpio()` con las estrategias definidas
    - Guardar resultado en `data/processed/dataframe_limpio.csv`
    - Generar comparaciones antes/después con `comparar_distribuciones()`
    - Verificar que datos originales no fueron modificados
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ] 5.3 Implementar sección §9 — Relaciones entre variables
    - Celda markdown con título de sección
    - Calcular correlaciones clima (temperatura, precipitación) vs demanda (bookings, valoraciones)
    - Analizar relación seguridad/sanidad vs ratings de reseñas
    - Reportar correlaciones significativas con `calcular_correlacion_significativa()`
    - Generar al menos 3 visualizaciones cruzando fuentes distintas
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [ ]* 5.4 Escribir property tests para correlación y calidad global
    - **Property 14: Correlation matrix mathematical properties**
    - **Property 20: Quality indicators summary completeness**
    - **Validates: Requirements 7.2, 10.2**

- [ ] 6. Implementar conclusiones y validación final
  - [ ] 6.1 Implementar sección §10 — Conclusiones y recomendaciones
    - Celda markdown con resumen ejecutivo de hallazgos principales
    - Generar tabla resumen con indicadores de calidad globales por fuente (completitud, unicidad, consistencia, pct_outliers)
    - Listar recomendaciones priorizadas para preprocesamiento
    - Documentar decisiones de tratamiento de outliers con justificación
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ]* 6.2 Escribir property tests para inmutabilidad y flag
    - **Property 17: Original data immutability**
    - **Property 10: Skewness threshold flagging**
    - **Validates: Requirements 8.4, 5.4**

- [ ] 7. Final checkpoint - Validación completa
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- El notebook final debe ejecutarse de forma secuencial sin errores
- Los datos originales en `data/` nunca se modifican; solo se escribe en `data/processed/`
- Las funciones auxiliares se definen en celdas tempranas para reutilización posterior

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4", "1.5"] },
    { "id": 2, "tasks": ["1.6", "1.7", "1.8", "1.9", "1.10"] },
    { "id": 3, "tasks": ["2.1"] },
    { "id": 4, "tasks": ["2.2", "2.3"] },
    { "id": 5, "tasks": ["4.1", "4.2", "4.3"] },
    { "id": 6, "tasks": ["5.1", "5.2", "5.3", "5.4"] },
    { "id": 7, "tasks": ["6.1", "6.2"] }
  ]
}
```
