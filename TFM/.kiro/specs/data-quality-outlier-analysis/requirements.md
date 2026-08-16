# Requirements Document

## Introduction

Análisis completo de calidad de datos para el sistema de recomendación turística TUI. El objetivo es evaluar las 11 fuentes de datos del proyecto (3 CSVs, 3 bases SQLite, 3 ficheros de embeddings, 2 CSVs de resultados), identificar problemas de calidad (nulos, duplicados, inconsistencias, outliers), analizar distribuciones y relaciones entre variables, y generar un DataFrame limpio con tratamiento de outliers sin alterar los datos originales. El entregable principal es un Jupyter Notebook ubicado en `notebooks/`.

## Glossary

- **Notebook_Calidad**: Jupyter Notebook principal que contiene todo el análisis de calidad de datos, ubicado en `notebooks/`
- **Fuente_Datos**: Cada una de las 11 fuentes de datos del proyecto (CSVs, bases SQLite, embeddings, resultados)
- **DataFrame_Limpio**: DataFrame resultante tras aplicar tratamiento de outliers, almacenado de forma separada sin modificar datos originales
- **Outlier**: Valor atípico que se desvía significativamente de la distribución esperada de una variable, identificado mediante métodos estadísticos (IQR, Z-score)
- **Winsorización**: Técnica de tratamiento de outliers que reemplaza valores extremos por los percentiles límite definidos
- **Indicador_Calidad**: Métrica cuantitativa que describe un aspecto de la calidad de un dataset (completitud, unicidad, consistencia)
- **Sistema_Análisis**: Conjunto de funciones y celdas del Notebook_Calidad que ejecutan el análisis
- **Datos_Originales**: Ficheros fuente en `data/` que no deben ser modificados durante el análisis

## Requirements

### Requirement 1: Carga y Perfilado de Fuentes de Datos

**User Story:** Como analista de datos, quiero cargar todas las fuentes de datos del proyecto y obtener un perfil estructural de cada una, para entender la composición y cobertura del dataset completo.

#### Acceptance Criteria

1. WHEN el Notebook_Calidad se ejecuta, THE Sistema_Análisis SHALL cargar las 11 fuentes de datos: `clima_todos_los_destinos.csv`, `seguridad_y_sanidad_banco_mundial.csv`, `conectividad_y_pasajeros_2025.csv`, tablas de `tui_recomendador.db`, tablas de `sample_tui.db`, embeddings (`hybrid_vectors.npy`, `package_embeddings.npy`, `paquete_ids.npy`), `evaluation_results.csv` y `simulation_results.csv`.
2. WHEN una Fuente_Datos se carga correctamente, THE Sistema_Análisis SHALL generar un resumen con número de filas, número de columnas, tipos de datos por columna y uso de memoria.
3. WHEN una Fuente_Datos contiene tablas múltiples (bases SQLite), THE Sistema_Análisis SHALL perfilar cada tabla de forma independiente.
4. IF una Fuente_Datos no se encuentra en la ruta esperada, THEN THE Sistema_Análisis SHALL registrar un mensaje de error descriptivo e indicar la ruta buscada sin interrumpir la ejecución del resto del análisis.

### Requirement 2: Análisis de Valores Nulos

**User Story:** Como analista de datos, quiero identificar y cuantificar valores nulos en todas las fuentes, para evaluar la completitud de los datos disponibles.

#### Acceptance Criteria

1. WHEN el perfilado de una Fuente_Datos se completa, THE Sistema_Análisis SHALL calcular el número absoluto y porcentaje de valores nulos por cada columna.
2. WHEN una columna presenta más del 50% de valores nulos, THE Sistema_Análisis SHALL marcar dicha columna como "crítica" en el informe.
3. THE Sistema_Análisis SHALL generar un mapa de calor (heatmap) de nulidad para cada Fuente_Datos tabular con más de 3 columnas.
4. THE Sistema_Análisis SHALL calcular un Indicador_Calidad de completitud global por cada Fuente_Datos como porcentaje de celdas no nulas sobre el total.

### Requirement 3: Detección de Duplicados

**User Story:** Como analista de datos, quiero identificar registros duplicados exactos y quasi-duplicados, para evaluar la unicidad de los datos.

#### Acceptance Criteria

1. WHEN el análisis de duplicados se ejecuta sobre una Fuente_Datos, THE Sistema_Análisis SHALL contar el número de filas completamente duplicadas.
2. WHEN se identifican filas duplicadas, THE Sistema_Análisis SHALL mostrar ejemplos de las primeras 5 filas duplicadas con todas sus columnas.
3. WHEN una tabla contiene campos de identificador (ID), THE Sistema_Análisis SHALL verificar la unicidad de dichos identificadores y reportar los valores repetidos.
4. THE Sistema_Análisis SHALL calcular un Indicador_Calidad de unicidad por cada Fuente_Datos como porcentaje de filas únicas sobre el total.

### Requirement 4: Análisis de Consistencia e Integridad

**User Story:** Como analista de datos, quiero detectar inconsistencias entre fuentes y problemas de integridad referencial, para identificar datos contradictorios.

#### Acceptance Criteria

1. WHEN el análisis de consistencia se ejecuta, THE Sistema_Análisis SHALL verificar que los nombres de destinos sean consistentes entre las distintas fuentes de datos (misma grafía y formato).
2. WHEN se detectan destinos presentes en una fuente pero ausentes en otra, THE Sistema_Análisis SHALL generar un informe de cobertura cruzada indicando la fuente y los destinos faltantes.
3. WHEN una columna numérica contiene valores fuera de rangos lógicos (precios negativos, ratings fuera de 1-5, porcentajes fuera de 0-100), THE Sistema_Análisis SHALL listar las filas con valores inválidos.
4. WHEN existen relaciones de clave foránea entre tablas SQLite, THE Sistema_Análisis SHALL verificar la integridad referencial y reportar las referencias huérfanas.

### Requirement 5: Análisis de Distribuciones

**User Story:** Como analista de datos, quiero visualizar y analizar las distribuciones de todas las variables numéricas y categóricas relevantes, para entender los patrones subyacentes.

#### Acceptance Criteria

1. WHEN el análisis de distribuciones se ejecuta sobre variables numéricas, THE Sistema_Análisis SHALL generar histogramas con estimación de densidad (KDE) para cada variable numérica.
2. WHEN el análisis de distribuciones se ejecuta sobre variables categóricas, THE Sistema_Análisis SHALL generar gráficos de barras con frecuencias absolutas y relativas para cada variable con menos de 30 categorías únicas.
3. THE Sistema_Análisis SHALL calcular estadísticos descriptivos (media, mediana, desviación estándar, asimetría, curtosis, mínimo, máximo, Q1, Q3) para cada variable numérica.
4. WHEN una variable numérica presenta asimetría absoluta mayor a 2, THE Sistema_Análisis SHALL indicar que la distribución es significativamente sesgada y sugerir transformación logarítmica o Box-Cox.

### Requirement 6: Detección de Outliers

**User Story:** Como analista de datos, quiero identificar valores atípicos en variables numéricas mediante métodos estadísticos, para evaluar su impacto en el análisis posterior.

#### Acceptance Criteria

1. THE Sistema_Análisis SHALL aplicar el método IQR (rango intercuartil, umbral 1.5×IQR) para detectar outliers en cada variable numérica.
2. THE Sistema_Análisis SHALL aplicar el método Z-score (umbral |z| > 3) para detectar outliers en cada variable numérica.
3. WHEN se detectan outliers en una variable, THE Sistema_Análisis SHALL generar un boxplot anotando el número de outliers detectados por cada método.
4. THE Sistema_Análisis SHALL generar una tabla resumen con el número de outliers por variable, método de detección utilizado y porcentaje sobre el total de registros.
5. WHEN se detectan outliers multivariantes, THE Sistema_Análisis SHALL aplicar Isolation Forest o LOF (Local Outlier Factor) para identificar registros anómalos considerando múltiples variables simultáneamente.

### Requirement 7: Visualización de Outliers y Patrones

**User Story:** Como analista de datos, quiero visualizaciones específicas para los outliers y sus relaciones con otras variables, para comprender su naturaleza y decidir su tratamiento.

#### Acceptance Criteria

1. WHEN se detectan outliers en una variable, THE Sistema_Análisis SHALL generar scatter plots con los outliers resaltados en color diferente respecto a los datos normales.
2. THE Sistema_Análisis SHALL generar una matriz de correlación (heatmap) entre todas las variables numéricas con coeficientes de Pearson y Spearman.
3. WHEN dos variables numéricas presentan correlación absoluta mayor a 0.7, THE Sistema_Análisis SHALL generar un scatter plot específico con línea de regresión y los outliers señalados.
4. THE Sistema_Análisis SHALL generar pair plots para las 5 variables numéricas con mayor variabilidad relativa (coeficiente de variación).

### Requirement 8: Tratamiento de Outliers y Generación de DataFrame Limpio

**User Story:** Como analista de datos, quiero aplicar tratamientos propuestos para outliers y generar un DataFrame limpio, para disponer de datos preparados para modelización sin alterar los originales.

#### Acceptance Criteria

1. THE Sistema_Análisis SHALL proponer para cada variable con outliers una de las siguientes estrategias: winsorización (percentiles 5-95), eliminación de registros, o imputación por mediana.
2. WHEN se aplica winsorización, THE Sistema_Análisis SHALL reemplazar valores por debajo del percentil 5 con el valor del percentil 5, y valores por encima del percentil 95 con el valor del percentil 95.
3. THE Sistema_Análisis SHALL generar el DataFrame_Limpio aplicando las estrategias propuestas y almacenarlo en `data/processed/` en formato CSV.
4. THE Sistema_Análisis SHALL mantener los Datos_Originales sin modificación alguna en sus rutas originales dentro de `data/`.
5. WHEN el DataFrame_Limpio se genera, THE Sistema_Análisis SHALL incluir una columna adicional `_outlier_flag` indicando con valor booleano si el registro original contenía al menos un outlier tratado.
6. THE Sistema_Análisis SHALL generar un resumen comparativo mostrando las distribuciones antes y después del tratamiento de outliers (histogramas superpuestos o side-by-side).

### Requirement 9: Análisis de Relaciones entre Variables

**User Story:** Como analista de datos, quiero identificar relaciones significativas entre variables de distintas fuentes, para descubrir patrones útiles para el sistema de recomendación.

#### Acceptance Criteria

1. THE Sistema_Análisis SHALL calcular correlaciones entre variables climáticas (temperatura, precipitación) y métricas de demanda (bookings, valoraciones) por destino.
2. THE Sistema_Análisis SHALL analizar la relación entre indicadores de seguridad/sanidad y ratings de reseñas por destino.
3. WHEN se identifica una correlación estadísticamente significativa (p-value < 0.05), THE Sistema_Análisis SHALL reportar el coeficiente, p-value e interpretación textual.
4. THE Sistema_Análisis SHALL generar al menos 3 visualizaciones que crucen información de fuentes distintas para revelar patrones inter-dataset.

### Requirement 10: Informe de Conclusiones y Recomendaciones

**User Story:** Como analista de datos, quiero un resumen ejecutivo con conclusiones y recomendaciones, para tomar decisiones informadas sobre el preprocesamiento final.

#### Acceptance Criteria

1. THE Sistema_Análisis SHALL generar una celda markdown de conclusiones al final del Notebook_Calidad con un resumen de hallazgos principales.
2. THE Sistema_Análisis SHALL incluir una tabla resumen con Indicadores_Calidad globales: completitud, unicidad, consistencia y porcentaje de outliers por cada Fuente_Datos.
3. THE Sistema_Análisis SHALL listar recomendaciones priorizadas para el tratamiento de datos previo a la modelización del sistema de recomendación.
4. THE Sistema_Análisis SHALL documentar las decisiones tomadas para el tratamiento de cada tipo de outlier con su justificación.
