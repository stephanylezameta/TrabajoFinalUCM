# Documento de Requisitos

## Introducción

El presente documento especifica los requisitos funcionales y no funcionales del **Motor de Recomendación Turística con IA** desarrollado para TUI como Trabajo de Fin de Máster. El sistema combina personalización del viajero, criterios de sostenibilidad y redistribución inteligente de flujos turísticos para recomendar paquetes all-inclusive (vuelo + hotel + destino) en zonas del Mediterráneo y el Caribe.

El problema que motiva este proyecto es la tendencia de los sistemas de recomendación tradicionales a concentrar la demanda en destinos ya populares, agravando el overtourism, incrementando la presión sobre infraestructuras locales y generando una distribución desigual del gasto turístico. El motor propuesto introduce el índice TDRS (Tourism Demand Redistribution Score) y un mecanismo de re-ranking dinámico para equilibrar la satisfacción del usuario con el impacto territorial.

El alcance del prototipo abarca: recolección de datos mediante scraping, procesamiento NLP y generación de embeddings, modelo recomendador híbrido, integración con un LLM para generación de lenguaje natural, y una capa de productivización con aplicación de usuario final y dashboard analítico para TUI.

---

## Glosario

- **Sistema**: El Motor de Recomendación Turística con IA desarrollado para TUI.
- **Scraper**: Módulo encargado de extraer datos de la web de TUI y fuentes públicas.
- **Limpiador**: Módulo de preprocesamiento y limpieza de datos crudos.
- **Embedder**: Módulo que transforma textos e información estructurada en vectores semánticos.
- **Repositorio**: Base de datos central que almacena usuarios, experiencias e interacciones.
- **Modelo_Afinidad**: Componente que calcula la puntuación de afinidad entre un usuario y una experiencia.
- **TDRS**: Tourism Demand Redistribution Score; índice que pondera afinidad, capacidad, accesibilidad, impacto local, temporada baja, diversificación, ocupación y sensibilidad ambiental.
- **Motor_Reranking**: Componente que combina el score base con criterios de redistribución y sostenibilidad para producir el ranking final de recomendaciones.
- **LLM_Adapter**: Componente que transforma la salida del modelo recomendador en lenguaje natural comprensible para el usuario final.
- **App_Usuario**: Interfaz de usuario final (web/app) que muestra las recomendaciones personalizadas.
- **Dashboard_TUI**: Interfaz analítica para operadores de TUI con métricas de redistribución y oportunidades de mercado.
- **Perfil_Viajero**: Conjunto de preferencias y restricciones de un usuario (cultura, gastronomía, naturaleza, playa, bienestar, aventura, presupuesto, duración, temporada preferida, accesibilidad, distancia máxima, interés en sostenibilidad).
- **Paquete**: Producto turístico all-inclusive compuesto por vuelo, hotel y destino ofertado por TUI.
- **Experiencia**: Sinónimo de Paquete en el contexto de este sistema.
- **Precision@K**: Proporción de ítems relevantes entre los K primeros recomendados.
- **NDCG@K**: Normalized Discounted Cumulative Gain a K posiciones; mide la calidad del ranking.
- **Gini_Turístico**: Coeficiente de Gini aplicado a la distribución de demanda entre destinos.
- **Saturación**: Indicador que mide el nivel de ocupación de un destino respecto a su capacidad máxima sostenible.
- **Usuario_Sintético**: Perfil de usuario generado artificialmente para entrenamiento y evaluación del modelo.

---

## Requisitos

### Requisito 1: Extracción de datos de paquetes turísticos

**User Story:** Como ingeniero de datos, quiero extraer automáticamente información de paquetes turísticos de la web de TUI y fuentes públicas, para disponer de un catálogo actualizado de experiencias del Mediterráneo y el Caribe con el que entrenar y operar el modelo.

#### Criterios de Aceptación

1. WHEN el Scraper recibe una instrucción de extracción, THE Scraper SHALL obtener los atributos de cada Paquete: destino, categoría, precio base, capacidad disponible, nivel de ocupación actual, temporada óptima, indicador de accesibilidad, y sensibilidad ambiental declarada.
2. WHEN el Scraper accede a fuentes públicas de reseñas, THE Scraper SHALL extraer texto de valoraciones de usuarios e indicadores de popularidad asociados a cada destino.
3. IF una fuente web devuelve un error HTTP 4xx o 5xx durante la extracción, THEN THE Scraper SHALL registrar el error con la URL afectada, el código de respuesta y la marca temporal, y SHALL continuar con las fuentes restantes.
4. WHEN el Scraper completa un ciclo de extracción, THE Scraper SHALL almacenar los datos crudos en el Repositorio con metadatos de procedencia (URL fuente, fecha de extracción, versión del Scraper).
5. THE Scraper SHALL ejecutar ciclos de refresco de datos con una periodicidad configurable no superior a 7 días, sin requerir intervención manual.
6. WHEN el Limpiador recibe datos crudos del Scraper, THE Limpiador SHALL detectar y eliminar registros duplicados basándose en la combinación de destino, proveedor y fechas de disponibilidad.
7. WHEN el Limpiador procesa un campo numérico, THE Limpiador SHALL normalizar los valores al rango [0, 1] aplicando la transformación min-max calculada sobre el conjunto de datos completo de cada ciclo de extracción.
8. IF un registro carece de más del 30% de sus atributos obligatorios tras la limpieza, THEN THE Limpiador SHALL marcarlo como inválido y SHALL excluirlo del conjunto de datos de entrenamiento, registrando el motivo de exclusión.


### Requisito 2: Generación de perfiles de usuario

**User Story:** Como científico de datos, quiero construir perfiles de viajero a partir de datos reales (reseñas, comportamiento de reserva) y usuarios sintéticos generados, para disponer de datos suficientes con los que entrenar el modelo recomendador en un contexto de TFM.

#### Criterios de Aceptación

1. THE Sistema SHALL generar Perfiles_Viajero que contengan los siguientes atributos: preferencias temáticas (cultura, gastronomía, naturaleza, playa, bienestar, aventura) con valores en [0, 1]; rango de presupuesto en euros; duración preferida del viaje en días; temporada preferida; indicador de accesibilidad requerida; distancia máxima de vuelo en kilómetros; e interés declarado en sostenibilidad en [0, 1].
2. WHEN el Sistema genera un Usuario_Sintético, THE Sistema SHALL producir valores de atributos del Perfil_Viajero coherentes entre sí, de modo que la suma de las preferencias temáticas sea igual a 1,0 con una tolerancia de ±0,01.
3. WHEN el Sistema extrae reseñas de fuentes públicas, THE Embedder SHALL transformar el texto de cada reseña en un vector de representación semántica de dimensión fija, utilizando un modelo de embeddings preentrenado documentado en la configuración del sistema.
4. THE Sistema SHALL producir un conjunto de datos que contenga al menos 500 Perfiles_Viajero distintos antes de iniciar el entrenamiento del Modelo_Afinidad.
5. IF dos Perfiles_Viajero presentan valores idénticos en todos sus atributos, THEN THE Sistema SHALL conservar únicamente uno de ellos y SHALL registrar el número de duplicados eliminados.


### Requisito 3: Generación de embeddings y representación semántica

**User Story:** Como científico de datos, quiero convertir las descripciones textuales de paquetes y las reseñas de usuarios en representaciones vectoriales, para que el modelo pueda capturar similitudes semánticas entre experiencias y preferencias.

#### Criterios de Aceptación

1. WHEN el Embedder recibe la descripción textual de un Paquete, THE Embedder SHALL producir un vector semántico de dimensión fija D, donde D es un parámetro de configuración documentado.
2. THE Embedder SHALL combinar el vector semántico de la descripción del Paquete con los atributos estructurados normalizados del Paquete mediante concatenación, produciendo un vector de representación híbrida de dimensión D + N, siendo N el número de atributos estructurados.
3. WHEN el Embedder procesa un conjunto de descripciones de Paquetes, THE Embedder SHALL preservar la dimensión del vector de salida de forma constante independientemente de la longitud del texto de entrada.
4. THE Sistema SHALL documentar el nombre, versión y fuente del modelo de embeddings utilizado en un fichero de configuración versionado.
5. WHEN el Embedder genera embeddings para un Paquete ya almacenado, THE Embedder SHALL sobreescribir el embedding previo en el Repositorio y SHALL registrar la fecha de actualización.
6. FOR ALL pares de descripciones de Paquetes semánticamente equivalentes (mismo destino, misma categoría, misma temporada), el Sistema SHALL producir vectores de embedding cuya similitud coseno sea superior a 0,85.


### Requisito 4: Almacenamiento y gestión de datos (Data Engineering)

**User Story:** Como ingeniero de datos, quiero centralizar todos los datos del sistema en una base de datos estructurada, para garantizar consistencia, trazabilidad y eficiencia en el acceso durante el entrenamiento y la inferencia.

#### Criterios de Aceptación

1. THE Repositorio SHALL almacenar entidades de tipo Usuario, Experiencia e Interacción en tablas o colecciones separadas con esquemas documentados.
2. THE Repositorio SHALL registrar para cada Interacción: el identificador de usuario, el identificador de experiencia, el tipo de interacción (visualización, reserva, valoración), el valor numérico asociado (cuando aplique) y la marca temporal.
3. WHEN el Repositorio recibe una operación de escritura, THE Repositorio SHALL completar la transacción en menos de 500 ms para registros individuales bajo condiciones de carga normal (menos de 100 escrituras concurrentes).
4. WHEN el Repositorio recibe una consulta de recuperación de los K Paquetes más afines a un Perfil_Viajero, THE Repositorio SHALL devolver los resultados en menos de 2 segundos para catálogos de hasta 10.000 Paquetes.
5. THE Repositorio SHALL mantener un registro de versiones (timestamps y hash de contenido) para cada actualización de los datos de Paquetes, de modo que sea posible reconstruir el estado del catálogo en cualquier fecha anterior.
6. IF la conexión con el Repositorio falla durante una operación de escritura, THEN THE Sistema SHALL reintentar la operación un máximo de 3 veces con intervalos exponenciales de 1, 2 y 4 segundos, y SHALL registrar el fallo definitivo si los 3 reintentos fallan.


### Requisito 5: Modelo de Afinidad Usuario-Experiencia

**User Story:** Como científico de datos, quiero calcular una puntuación de afinidad entre cada viajero y cada paquete turístico, para disponer de una señal base de relevancia personalizada sobre la que aplicar el TDRS.

#### Criterios de Aceptación

1. THE Modelo_Afinidad SHALL calcular una puntuación Afinidad(u, e) en el rango [0, 1] para cada par (usuario u, experiencia e) del catálogo.
2. WHEN el Modelo_Afinidad recibe el Perfil_Viajero de un usuario y el vector de representación de una Experiencia, THE Modelo_Afinidad SHALL producir la puntuación Afinidad(u, e) en menos de 100 ms por par.
3. THE Sistema SHALL entrenar al menos dos variantes del Modelo_Afinidad: una baseline basada en similitud del coseno o KNN, y una avanzada basada en al menos uno de los siguientes enfoques: LightFM, XGBoost o arquitectura Two-Tower.
4. WHEN el Modelo_Afinidad es evaluado sobre el conjunto de test, THE Modelo_Afinidad SHALL alcanzar un valor de Precision@10 igual o superior a 0,30 y un NDCG@10 igual o superior a 0,35 en la variante avanzada.
5. THE Sistema SHALL documentar los hiperparámetros utilizados en el entrenamiento de cada variante del Modelo_Afinidad en un fichero de configuración versionado.
6. WHEN el Modelo_Afinidad genera recomendaciones para un usuario, THE Modelo_Afinidad SHALL incluir al menos un Paquete de temporada baja entre los 10 primeros resultados si existen Paquetes de temporada baja con Afinidad(u, e) superior a 0,40.
7. FOR ALL usuarios con Perfiles_Viajero idénticos, THE Modelo_Afinidad SHALL producir rankings de Afinidad idénticos (propiedad determinista).


### Requisito 6: Cálculo del Tourism Demand Redistribution Score (TDRS)

**User Story:** Como investigador de sostenibilidad turística, quiero calcular el TDRS de cada experiencia candidata para un usuario, para evaluar si la recomendación es adecuada desde la perspectiva de redistribución territorial y sostenibilidad.

#### Criterios de Aceptación

1. THE Sistema SHALL calcular el TDRS para cada par (usuario, experiencia) según la fórmula:
   TDRS = w₁·Afinidad + w₂·Capacidad + w₃·Accesibilidad + w₄·Impacto_Local + w₅·Temporada_Baja + w₆·Diversificación − w₇·Ocupación − w₈·Sensibilidad_Ambiental,
   donde todos los términos están normalizados en [0, 1] y la suma de pesos absolutos es igual a 1,0.
2. THE Sistema SHALL exponer los pesos w₁..w₈ como parámetros configurables en un fichero de configuración, con valores predeterminados documentados.
3. WHEN el Sistema calcula el TDRS para un conjunto de Experiencias, THE Sistema SHALL producir valores de TDRS en el rango [−1, 1].
4. WHEN el nivel de Ocupación de un destino supera el 85% de su capacidad máxima declarada, THE Sistema SHALL asignar un valor de Ocupación igual a 1,0 en el cálculo del TDRS de ese destino, incrementando su penalización máxima.
5. WHEN el Sistema actualiza los datos de ocupación o capacidad de un destino, THE Sistema SHALL recalcular el TDRS de todos los Paquetes asociados a ese destino en el siguiente ciclo de refresco.
6. FOR ALL configuraciones de pesos en las que w₁ > 0 y w₇ > 0, el TDRS de un Paquete con Afinidad máxima (1,0) y Ocupación máxima (1,0) SHALL ser menor que el TDRS del mismo Paquete con Afinidad máxima y Ocupación mínima (0,0), manteniendo constantes el resto de variables.


### Requisito 7: Re-ranking dinámico y generación del ranking final

**User Story:** Como product manager de TUI, quiero que el sistema produzca un ranking final de recomendaciones que equilibre la relevancia para el usuario con los objetivos de redistribución y sostenibilidad, para poder comparar distintas estrategias de recomendación.

#### Criterios de Aceptación

1. THE Motor_Reranking SHALL calcular el Score_Final de cada Experiencia candidata según la fórmula:
   Score_Final = α·Score_Base + β·Redistribución + γ·Sostenibilidad + δ·Capacidad − λ·Saturación,
   donde α + β + γ + δ + λ = 1,0 y todos los coeficientes son no negativos.
2. THE Motor_Reranking SHALL producir tres rankings diferenciados para cada solicitud de recomendación: (a) tradicional (α = 1,0, resto = 0), (b) redistribución moderada (parámetros predeterminados documentados), y (c) redistribución intensiva (parámetros predeterminados documentados).
3. WHEN el Motor_Reranking genera el ranking de redistribución intensiva, THE Motor_Reranking SHALL asegurar que al menos el 30% de los K Paquetes recomendados correspondan a destinos distintos al destino más recomendado en el ranking tradicional.
4. WHEN el Motor_Reranking genera cualquier ranking, THE Motor_Reranking SHALL completar el cálculo para K = 10 recomendaciones en menos de 500 ms por usuario.
5. THE Motor_Reranking SHALL exponer los coeficientes α, β, γ, δ y λ como parámetros configurables en tiempo de ejecución sin necesidad de reentrenamiento del modelo.
6. FOR ALL solicitudes de recomendación con el mismo Perfil_Viajero y el mismo estado del catálogo, THE Motor_Reranking SHALL producir rankings idénticos (propiedad determinista).
7. WHEN el Score_Final de dos Experiencias difiere en menos de 0,001, THE Motor_Reranking SHALL resolver el empate por orden alfabético del identificador de Experiencia para garantizar resultados reproducibles.


### Requisito 8: Integración con LLM para generación de lenguaje natural

**User Story:** Como viajero, quiero recibir una explicación en lenguaje natural de por qué se me recomienda cada paquete, para entender el razonamiento del sistema y sentir que la recomendación está personalizada para mí.

#### Criterios de Aceptación

1. WHEN el LLM_Adapter recibe el ranking final de un usuario junto con los atributos del Perfil_Viajero, THE LLM_Adapter SHALL generar una descripción en lenguaje natural para cada uno de los 3 primeros Paquetes recomendados.
2. THE LLM_Adapter SHALL incluir en cada descripción generada al menos uno de los siguientes elementos de personalización: referencia explícita a una preferencia temática del usuario, mención al rango de presupuesto, o indicación de la temporada recomendada.
3. WHEN el TDRS de un Paquete recomendado supera 0,6, THE LLM_Adapter SHALL incluir en la descripción una mención al beneficio de sostenibilidad o redistribución asociado a ese destino.
4. WHEN el LLM_Adapter genera una descripción, THE LLM_Adapter SHALL producir el texto en menos de 5 segundos por Paquete bajo condiciones de carga normal.
5. IF el LLM externo no está disponible, THEN THE LLM_Adapter SHALL recurrir a plantillas de texto predefinidas para generar la descripción, y SHALL registrar la indisponibilidad del servicio LLM.
6. THE LLM_Adapter SHALL aceptar como parámetro configurable el nombre y versión del modelo LLM a utilizar, sin requerir modificación del código fuente.


### Requisito 9: Explicabilidad de las recomendaciones

**User Story:** Como viajero, quiero conocer los factores concretos que determinan cada recomendación, para poder evaluar si se ajusta a mis preferencias y confiar en el sistema.

#### Criterios de Aceptación

1. WHEN el Sistema genera una recomendación, THE Sistema SHALL proporcionar junto a cada Paquete recomendado un desglose de los factores que contribuyen a su Score_Final, incluyendo al menos: puntuación de Afinidad, valor de TDRS y componente de Saturación.
2. THE Sistema SHALL presentar el desglose de factores de forma comprensible para un usuario no técnico, expresando cada componente como un valor normalizado en [0, 1] acompañado de una etiqueta descriptiva.
3. WHEN el Paquete recomendado ocupa una posición diferente en el ranking tradicional respecto al ranking redistributivo, THE Sistema SHALL indicar explícitamente la diferencia de posición y el motivo principal del ascenso o descenso.
4. THE Sistema SHALL generar la explicación de cada recomendación en menos de 200 ms adicionales al tiempo de generación del ranking.


### Requisito 10: Detección de oportunidades de mercado para TUI

**User Story:** Como analista de TUI, quiero identificar destinos infrautilizados con potencial de demanda latente, para orientar estrategias comerciales hacia productos y zonas con mayor capacidad de absorción de visitantes.

#### Criterios de Aceptación

1. WHEN el Sistema completa un ciclo de refresco de datos, THE Sistema SHALL calcular para cada destino del catálogo un indicador de oportunidad de mercado definido como la diferencia entre la afinidad media de los usuarios hacia el destino y su nivel de ocupación actual.
2. THE Sistema SHALL identificar como "destino con oportunidad" todo Paquete cuyo indicador de oportunidad de mercado supere un umbral configurable (valor predeterminado: 0,20).
3. THE Sistema SHALL agregar los destinos con oportunidad por zona geográfica (Mediterráneo / Caribe) y por temporada, y SHALL almacenar el resultado en el Repositorio con la marca temporal del ciclo de refresco.
4. WHEN el Dashboard_TUI solicita el listado de oportunidades de mercado, THE Sistema SHALL devolver los resultados ordenados por indicador de oportunidad de mayor a menor en menos de 3 segundos.
5. THE Sistema SHALL asociar a cada destino con oportunidad el perfil de usuario más frecuentemente afín a ese destino, para facilitar la segmentación en campañas comerciales.


### Requisito 11: Simulación de impacto territorial

**User Story:** Como investigador, quiero comparar la distribución de la demanda turística bajo distintas estrategias de recomendación, para cuantificar el impacto del motor redistributivo frente a un sistema tradicional.

#### Criterios de Aceptación

1. THE Sistema SHALL simular la distribución de demanda para los tres escenarios definidos en el Requisito 7 (tradicional, redistribución moderada, redistribución intensiva) sobre un conjunto de al menos 500 Perfiles_Viajero.
2. WHEN el Sistema ejecuta la simulación, THE Sistema SHALL calcular las siguientes métricas de distribución para cada escenario: coeficiente Gini_Turístico, índice de concentración de los 5 destinos más demandados (CR5), y porcentaje de demanda dirigida a destinos con Saturación inferior a 0,50.
3. THE Sistema SHALL exportar los resultados de simulación en formato CSV y en formato compatible con la herramienta de visualización del Dashboard_TUI.
4. WHEN el coeficiente Gini_Turístico del escenario de redistribución moderada es mayor o igual que el del escenario tradicional, THE Sistema SHALL registrar una alerta en el log indicando que los parámetros de redistribución no están logrando el efecto esperado.
5. THE Sistema SHALL completar la simulación sobre 500 usuarios en menos de 60 segundos en un entorno de ejecución con al menos 4 núcleos de CPU.


### Requisito 12: Aplicación de usuario final (App_Usuario)

**User Story:** Como viajero, quiero acceder a una aplicación web donde introducir mis preferencias y recibir recomendaciones de paquetes turísticos personalizadas, para decidir mi próximo viaje con TUI de forma sencilla.

#### Criterios de Aceptación

1. THE App_Usuario SHALL permitir al usuario introducir o actualizar su Perfil_Viajero mediante un formulario que cubra todos los atributos definidos en el Glosario para Perfil_Viajero.
2. WHEN el usuario envía su Perfil_Viajero, THE App_Usuario SHALL mostrar los 10 Paquetes recomendados según el ranking de redistribución moderada, incluyendo para cada uno: nombre del destino, precio, categoría, puntuación de Afinidad, valor de TDRS y la descripción en lenguaje natural generada por el LLM_Adapter.
3. THE App_Usuario SHALL ofrecer al usuario la opción de cambiar entre los tres escenarios de recomendación (tradicional, moderado, intensivo) sin necesidad de reintroducir el Perfil_Viajero.
4. WHEN el usuario selecciona un Paquete, THE App_Usuario SHALL mostrar el desglose de factores de explicabilidad definido en el Requisito 9.
5. THE App_Usuario SHALL responder a las acciones del usuario (envío de formulario, cambio de escenario, selección de paquete) en menos de 3 segundos bajo condiciones de uso normal.
6. IF el backend no está disponible, THEN THE App_Usuario SHALL mostrar un mensaje de error comprensible al usuario y SHALL registrar el fallo en el log de la aplicación.


### Requisito 13: Dashboard analítico para TUI (Dashboard_TUI)

**User Story:** Como analista de TUI, quiero acceder a un dashboard con métricas de redistribución, diversidad y oportunidades de mercado, para monitorizar el comportamiento del motor y orientar decisiones estratégicas.

#### Criterios de Aceptación

1. THE Dashboard_TUI SHALL mostrar para el ciclo de datos más reciente las métricas de recomendación: Precision@K, Recall@K, NDCG@K y MAP@K para K ∈ {5, 10}.
2. THE Dashboard_TUI SHALL mostrar las métricas de diversidad: intra-list diversity media, cobertura del catálogo (porcentaje de Paquetes recomendados al menos una vez) y novedad media.
3. THE Dashboard_TUI SHALL mostrar las métricas de redistribución: Gini_Turístico, CR5, reducción de saturación media respecto al escenario tradicional, y porcentaje de demanda dirigida a destinos con Saturación inferior a 0,50.
4. THE Dashboard_TUI SHALL mostrar el listado de destinos con oportunidad de mercado calculado según el Requisito 10, con posibilidad de filtrar por zona geográfica y temporada.
5. WHEN el administrador de TUI actualiza los datos del Repositorio, THE Dashboard_TUI SHALL reflejar los nuevos valores en las métricas en menos de 10 segundos tras la actualización.
6. THE Dashboard_TUI SHALL permitir exportar todas las métricas mostradas en formato CSV con un único clic.


### Requisito 14: Evaluación y comparación de modelos

**User Story:** Como científico de datos, quiero evaluar y comparar sistemáticamente las variantes del modelo recomendador, para seleccionar la configuración que mejor equilibra relevancia, diversidad y redistribución.

#### Criterios de Aceptación

1. THE Sistema SHALL evaluar todas las variantes del Modelo_Afinidad sobre un conjunto de test reservado que represente al menos el 20% de las interacciones totales disponibles.
2. THE Sistema SHALL calcular y registrar las métricas de evaluación definidas (Precision@K, Recall@K, NDCG@K, MAP@K, intra-list diversity, cobertura, novedad, Gini_Turístico, CR5) para cada variante evaluada.
3. WHEN el Sistema finaliza la evaluación de una variante, THE Sistema SHALL almacenar los resultados en un fichero de reporte estructurado (JSON o CSV) con el nombre de la variante, la fecha de evaluación y todos los valores de métricas.
4. THE Sistema SHALL incluir en el reporte de evaluación una comparación tabular de todas las variantes evaluadas, ordenadas por NDCG@10 de mayor a menor.
5. THE Sistema SHALL garantizar que el conjunto de test no contiene usuarios ni interacciones presentes en el conjunto de entrenamiento (ausencia de data leakage).


---

## Requisitos No Funcionales

### Requisito NF-1: Rendimiento

**User Story:** Como usuario del sistema, quiero que las recomendaciones se generen con rapidez, para no experimentar esperas perceptibles durante el uso de la aplicación.

#### Criterios de Aceptación

1. THE Sistema SHALL generar el ranking final de 10 recomendaciones para un usuario, incluyendo el cálculo de Afinidad, TDRS y Score_Final, en menos de 3 segundos de extremo a extremo bajo condiciones de carga normal (menos de 10 usuarios concurrentes).
2. WHEN el pipeline completo de entrenamiento (embeddings + modelo + evaluación) es ejecutado sobre el conjunto de datos completo, THE Sistema SHALL completar el proceso en menos de 4 horas en un entorno con al menos 8 GB de RAM y 4 núcleos de CPU.
3. THE Sistema SHALL soportar al menos 10 solicitudes de recomendación concurrentes sin degradar el tiempo de respuesta por encima del 50% respecto a la línea base de una solicitud aislada.


### Requisito NF-2: Escalabilidad

**User Story:** Como investigador, quiero que el sistema pueda escalar el catálogo de paquetes y el número de usuarios sin rediseño arquitectural, para que el prototipo sea extrapolable a un entorno de mayor escala.

#### Criterios de Aceptación

1. THE Sistema SHALL manejar catálogos de hasta 10.000 Paquetes y hasta 10.000 Perfiles_Viajero sin cambios en la arquitectura de datos ni en los módulos de inferencia.
2. WHEN el tamaño del catálogo de Paquetes se incrementa en un factor de 10 respecto al tamaño de entrenamiento, THE Sistema SHALL producir recomendaciones sin errores de memoria ni de tiempo de espera superior a 10 segundos por solicitud.
3. THE Sistema SHALL utilizar procesamiento por lotes (batch processing) para operaciones de generación masiva de embeddings y cálculo masivo de puntuaciones, con un tamaño de lote configurable.

### Requisito NF-3: Mantenibilidad y reproducibilidad

**User Story:** Como investigador, quiero que el sistema sea reproducible y mantenible, para que los experimentos puedan ser replicados y el código sea auditable en el contexto del TFM.

#### Criterios de Aceptación

1. THE Sistema SHALL fijar la semilla aleatoria (random seed) en todos los componentes que utilicen aleatoriedad (generación de usuarios sintéticos, partición train/test, inicialización de modelos), y SHALL documentar el valor de semilla utilizado.
2. THE Sistema SHALL registrar en un fichero de log cada ejecución del pipeline con: fecha y hora de inicio, versión del código, parámetros de configuración activos, y métricas de evaluación obtenidas.
3. THE Sistema SHALL gestionar sus dependencias Python mediante un fichero de requisitos versionado (requirements.txt o pyproject.toml) con versiones de paquetes fijadas.
4. THE Sistema SHALL incluir tests unitarios para los módulos Limpiador, Embedder, Modelo_Afinidad, TDRS y Motor_Reranking, con una cobertura de código superior al 70%.

### Requisito NF-4: Observabilidad

**User Story:** Como ingeniero, quiero que el sistema registre información suficiente sobre su comportamiento interno, para poder diagnosticar errores y evaluar la calidad de las recomendaciones en producción.

#### Criterios de Aceptación

1. THE Sistema SHALL registrar en log cada solicitud de recomendación con: identificador de usuario, timestamp, escenario seleccionado, top-3 de Paquetes recomendados (solo identificadores) y tiempo de procesamiento total.
2. WHEN el Sistema detecta que el tiempo de procesamiento de una solicitud supera el doble del percentil 95 histórico, THE Sistema SHALL registrar una entrada de alerta en el log con nivel WARNING.
3. THE Sistema SHALL registrar con nivel ERROR toda excepción no controlada en cualquier módulo, incluyendo el stack trace completo y los parámetros de entrada que provocaron el error.
4. THE Sistema SHALL exponer un endpoint de salud (health check) que devuelva el estado operativo de cada módulo (Scraper, Repositorio, Modelo_Afinidad, LLM_Adapter) en formato JSON.


---

## Propiedades de Corrección para Property-Based Testing (PBT)

Las siguientes propiedades deben verificarse mediante tests basados en propiedades (e.g., Hypothesis en Python). Se aplican sobre la lógica propia del sistema, no sobre servicios externos.

### PBT-1: Invariante del rango de puntuaciones

**Módulos:** Modelo_Afinidad, TDRS, Motor_Reranking

Para cualquier Perfil_Viajero válido y cualquier Paquete válido del catálogo:
- Afinidad(u, e) ∈ [0, 1]
- TDRS(u, e) ∈ [−1, 1]
- Score_Final(u, e) ∈ [−1, 1] (o en [0, 1] si los coeficientes son todos positivos y los inputs están en [0, 1])

### PBT-2: Propiedad determinista (idempotencia de la inferencia)

**Módulos:** Modelo_Afinidad, Motor_Reranking

Dado el mismo Perfil_Viajero y el mismo estado del catálogo, ejecutar la inferencia dos veces SHALL producir rankings idénticos:
`rank(u, catálogo) = rank(u, catálogo)` — sin variabilidad estocástica en inferencia.

### PBT-3: Monotonía del TDRS respecto a la Ocupación

**Módulo:** TDRS

Para cualquier Paquete e con todos los demás factores constantes, incrementar el valor de Ocupación SHALL reducir o mantener el TDRS:
`Ocupación(e₁) > Ocupación(e₂) ⟹ TDRS(u, e₁) ≤ TDRS(u, e₂)`

### PBT-4: Propiedad de cobertura mínima del ranking redistributivo

**Módulo:** Motor_Reranking

Para el escenario de redistribución intensiva y cualquier conjunto de al menos 20 Paquetes candidatos con al menos 5 destinos distintos, el top-10 del ranking SHALL contener al menos 3 destinos distintos:
`|{destino(e) : e ∈ top10_intensivo}| ≥ 3`

### PBT-5: Round-trip de serialización del Perfil_Viajero

**Módulo:** Repositorio / capa de serialización

Para cualquier Perfil_Viajero válido p, serializar y deserializar SHALL producir un perfil equivalente:
`deserializar(serializar(p)) == p`

Esta propiedad es crítica para garantizar que los perfiles no se corrompen al persistirlos y recuperarlos.

### PBT-6: Invariante de ordenación del ranking

**Módulo:** Motor_Reranking

Para cualquier par de Paquetes e₁, e₂ en el ranking final, si e₁ aparece antes que e₂ entonces su Score_Final es mayor o igual:
`posición(e₁) < posición(e₂) ⟹ Score_Final(e₁) ≥ Score_Final(e₂)`

### PBT-7: Propiedad de error controlado en datos de entrada inválidos

**Módulos:** Limpiador, Modelo_Afinidad

Para cualquier entrada con atributos fuera de rango (e.g., Ocupación > 1, presupuesto negativo), el módulo correspondiente SHALL lanzar una excepción tipada y documentada, sin producir resultados silenciosos ni corruptos.

