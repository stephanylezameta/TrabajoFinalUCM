# Revisión V20

- Orden del sidebar del Simulador TDRS: **Asistente IA → Pesos del modelo → Restricciones**.
- Las tarjetas del Top 3 ahora usan una búsqueda automática de imágenes en Wikipedia/Wikimedia cuando el destino no tiene fotografía curada.
- La búsqueda tiene fallback español/inglés, caché por destino, timeout y degradación segura al placeholder si no hay conexión.

# Revisión visual aplicada - ronda 6 / V05

## Simulador TDRS
- Se conserva íntegramente la V04 salvo por el cambio indicado en la captura de esta ronda.
- Se añade de nuevo el bloque **Pesos del modelo** en el sidebar, inmediatamente antes de **Restricciones**.
- El bloque contiene los cinco sliders de scoring: días soleados, baja precipitación, popularidad, capacidad sanitaria y seguridad.
- Los valores iniciales dependen del escenario superior seleccionado: **Popular**, **Equilibrado** o **Explorador**.
- Los pesos editados se envían a `compute_scores`, por lo que modifican realmente el ranking.
- Se mantienen `Precio máximo (€)` y `Máx. días hospedados` debajo del bloque de pesos.

## Conservación
- Inicio · Asistente, Control Web y Datos / modelo permanecen como en V04.
- Se mantienen fotografías, créditos, datasets, SQLite, servicios, tests, configuración y documentación previa.
- La nueva captura queda archivada en `docs/feedback/ronda_6/`.

- V06: actualización visual sin cambios funcionales. Se mantiene la V05 y se rediseñan fondo, contenedores y botones en una estética clara, iluminada y neutra.

- V07: corrección del fondo de la V06. Se preserva la estética clara, pero se evita la superposición que dejaba la app visualmente en blanco.

- V08: unificación visual del fondo del panel y la página. Se aplica un azul claro continuo con líneas negras/grises manteniendo toda la configuración y disposición previa.

- V09: sincronización visual del fondo. Se unifica el patrón decorativo en toda la app y se convierte el panel lateral en un bloque azul claro más transparente.

- V10: cambio de posición del bloque Top 3. Se mueve por encima de los KPIs, manteniendo sin cambios la lógica y el estilo de V09.

- V11: tarjetas principales TDRS simplificadas. Sin título Top 3, Posición pasa a Opción y el dato destacado es solo el precio en euros; se elimina el score visible.

- V12: precio de cada opción reubicado arriba a la derecha; se eliminan KNN y créditos visibles en las tarjetas; `Posición` pasa a `Opción` en el resto del ranking.
- V16: se simplifica la salida visible del ranking TDRS. Se ocultan Score, Cobertura, Camas/1000, Homicidios/100k y KNN de la tabla; también se retiran Cobertura/Camas/Homicidios de las tarjetas/KPIs del ranking, manteniendo esas señales internamente para el cálculo del modelo.
## V17 – Tabla de ranking
- Se elimina `Días hospedados` de la tabla visible del ranking.
- La duración máxima sigue disponible como restricción interna del simulador.


## V21 – Recomendador externo, reorganización y preparación para publicar

Primera ronda que no es solo visual: añade una fuente de recomendación nueva y
reordena el proyecto para poder desplegarlo.

### Nueva vista: Recomendador España
- Cuarta vista en la navegación, entre **Simulador TDRS** y **Control Web**.
- Consume un motor externo por API (Azure Function) que ranquea municipios
  españoles con catálogo turístico, OpenStreetMap, señales de YouTube y clima
  histórico de AEMET.
- **No sustituye al TDRS**: son dos motores con ámbitos distintos. El TDRS sigue
  calculando en local sobre SQLite.
- Muestra la explicabilidad que devuelve la API: desglose del score en cinco
  dimensiones, motivos, fortalezas, concesiones y cobertura de datos por fuente.
- Degrada sin romper. Sin endpoint configurado queda en modo informativo; ante
  error de red avisa y activa un cortacircuitos de 20 s.
- Contrato documentado en [`docs/integraciones/api_recomendaciones.md`](../../docs/integraciones/api_recomendaciones.md).

### Reorganización
- La app se movió de `docs/Streamlit_DG_P1/tui_streamlit_project/` a
  `TFM/dashboard/`. Estaba dentro de la carpeta de documentación, a cuatro
  niveles de profundidad.
- Se eliminaron cuatro copias redundantes del proyecto que convivían en `docs/`.
- `streamlit_app.py` pasa de 964 a ~150 líneas. Se reparte en:
  - `components/styles.py` — la hoja de estilos, antes embebida.
  - `components/assets.py` — logo, iconos e imágenes de destino.
  - `components/ui.py` — alertas, KPIs y encabezados compartidos.
  - `views/` — una vista por módulo.
- Se crea la carpeta `components/` que el brief autorizaba y nunca se hizo.

### Correcciones
- **Tests aislados.** Antes corrían contra `data/app.db` real. Ahora `conftest.py`
  construye una base temporal vía `TUI_DB_PATH` y la destruye al terminar.
- **Parseo de HTML robusto.** El extractor de `var DESTINOS = [...]` usaba una
  expresión regular no voraz que se rompía si un literal contenía `];`. Se
  sustituye por un escáner con emparejamiento real de delimitadores que respeta
  cadenas y escapes. Si el ancla no aparece, ahora falla de forma explícita en
  lugar de devolver cero destinos en silencio.
- **Vestigio eliminado.** `compute_scores` aceptaba `target_month` y no lo usaba:
  el clima se agrega al año completo. Se retira junto a `DEFAULT_TARGET_MONTH`.
- **Deprecación de Streamlit.** `use_container_width` está marcado para
  eliminación; se migra a `width="stretch"` en las cuatro vistas.
- **Dependencias fijadas** para que el despliegue sea reproducible, con `pytest`
  movido a `requirements-dev.txt`.

### Tests
De 12 a 110. Nuevas suites:
- `test_recommendation_api.py` — cliente de la API, sin llamadas de red.
- `test_reference_parsing.py` — el escáner de HTML/JS.
- `test_repositories.py` — persistencia, tracking y reservas.
- `test_alerts_and_analytics.py` — reglas de alerta y KPIs derivados.
- `test_app_smoke.py` — render de las cuatro vistas con `AppTest`.

## V22 – Coste de acceso a datos y omisiones silenciosas

Ronda de corrección guiada por medición, no por intuición. Se instrumentó
`sqlite3.connect` para contar conexiones y tiempo por render antes de tocar nada.

### El hallazgo

`get_system_status()`, que se pinta en el sidebar de **todas** las vistas, abría
**81 conexiones y tardaba 75 ms en cada interacción del usuario**. La causa era
una multiplicación: `get_source_health()` abría 15 conexiones (una por cada
recuento de filas y otra por cada cálculo de cobertura), y `get_alerts()` la
invocaba cuatro veces, una por regla que necesitaba las fuentes, más la que hacía
`get_system_status()` por su cuenta.

`bootstrap()` no era el problema que parecía: 9 conexiones y 8 ms.

### Medición antes y después

| Operación | Antes | Después |
| --- | --- | --- |
| `get_system_status()` | 81 conn · 75 ms | 8 conn · 9 ms |
| `get_source_health()` | 15 conn · 12 ms | 2 conn · 2 ms |
| `get_dashboard_metrics()` | 11 conn · 9 ms | 1 conn · 0,8 ms |
| `instrumentation_status()` | 11 conn · 10 ms | 1 conn · 0,8 ms |
| Render Control Web | 114 conn · 119 ms | 21 conn · 24 ms |
| Render Simulador TDRS | 91 conn · 108 ms | 18 conn · 26 ms |

### Cambios

- `get_source_health()` resuelve recuentos y coberturas sobre **una sola
  conexión**. `_row_count` y `_coverage_for_source` aceptan una conexión abierta,
  conservando su comportamiento anterior cuando no se les pasa.
- Las cuatro reglas de alerta que dependen de las fuentes aceptan recibirlas ya
  calculadas. `get_alerts(sources=...)` las obtiene una vez y las reparte, y
  `get_system_status()` reutiliza las suyas.
- `get_dashboard_metrics()` agrupa sus doce agregaciones en una conexión.
- `instrumentation_status(metrics)` y `get_funnel_metrics(metrics)` aceptan
  métricas ya calculadas; Control Web las calcula una vez y las comparte.
- `bootstrap()` pasa a `@st.cache_resource`: es una operación de arranque, no de
  render.

### Omisión silenciosa en el mapa

`get_geospatial_metrics()` descartaba con un `continue` cualquier destino sin
coordenada. No inventaba una posición, que es correcto, pero lo hacía **sin
dejar rastro**, en contra de la regla de trazabilidad del proyecto.

- Nuevas `get_unmapped_destinations()` y `coordinate_coverage()`.
- Control Web declara bajo el mapa qué destinos con interacción quedan fuera y
  por qué.

### Coordenadas

Se verificaron las 16 coordenadas de `data/destination_coordinates.csv` contra
valores conocidos: todas correctas. El aviso del README sobre sustituirlas por un
geocoder sigue vigente por procedencia, no por exactitud. Se añaden tests que
detectan los errores gruesos típicos de un fichero curado a mano: latitud y
longitud intercambiadas, signo invertido, duplicados y procedencia sin declarar.

### Tests

De 110 a 120, incluidas dos regresiones que fijan la mejora contando cuántas
veces se llama a `get_source_health()`.

## V23 – Sexto factor: satisfacción real de viajeros

El dashboard vivía sobre `app.db` (16 destinos, 3 ofertas) mientras el pipeline
del TFM tenía en `tui_recomendador.db` 289.344 filas, entre ellas 37.956 reseñas
ya clasificadas por un transformer multilingüe. Esa señal no se usaba en ninguna
parte. Ahora es el sexto factor del TDRS.

### Por qué esta señal y no otra

Es la única del modelo que mide **experiencia vivida** en lugar de condiciones
objetivas del destino. Las cinco anteriores (sol, precipitación, popularidad,
camas de hospital, homicidios) describen cómo *es* un destino; esta describe cómo
*salieron* quienes fueron.

Y produce un resultado que el modelo antes no podía expresar: **Dubrovnik es el
peor valorado de los 16 destinos** (0,45 de sentimiento medio, 34,6 % de reseñas
negativas sobre 101 analizadas) siendo uno de los que el dashboard destacaba con
fotografía. La tensión entre popularidad y satisfacción se puede ver, no solo
enunciar.

### Cómo llega el dato sin arrastrar 64 MB

`tui_recomendador.db` está excluida por `.gitignore` y no puede viajar al
despliegue. `scripts/export_sentiment.py` agrega sus reseñas a una fila por
destino y las escribe en `data/raw/sentimiento_por_destino.csv`, que sí se
versiona. El ETL existente lo importa como una fuente más, con su estado y su
cadencia en el panel Datos/modelo.

Se exportan los recuentos además de las medias: una media sin su `n` no es
auditable. Umbral de 25 reseñas por destino, que no cuesta cobertura y descarta
medias sin fundamento. Resultado: 392 destinos, 36.063 reseñas.

### Cobertura y trazabilidad

De los 16 destinos del catálogo, **11 tienen sentimiento real** (69 %). Los 5
restantes (Carmona, Osuna, Ronda, Sevilla, Zadar) no tienen reseñas en el
pipeline, así que el KNN los estima y quedan marcados en `knn_imputed_fields`.

En la tabla del ranking se muestra el **valor real, no el imputado**: un destino
sin reseñas aparece como `—` aunque internamente tenga una estimación con la que
calcular el score. Es la regla de dato ausente ≠ dato estimado aplicada a la capa
visible. El KPI «Satisfacción Top 5» va acompañado de «Con reseñas reales n/5»
para que la media no se lea como si fuese toda observada.

### Pesos por escenario

| Escenario | Peso | Motivo |
| --- | --- | --- |
| Popular | 40 | Prioriza volumen; es donde se ve el conflicto con destinos saturados |
| Equilibrado | 70 | En línea con el resto de señales |
| Explorador | 95 | Busca calidad frente a masificación: es su señal más pertinente |

El asistente conversacional entiende la nueva dimensión («destinos bien
valorados», «las reseñas me dan igual») y la traduce al sexto peso, con la misma
precaución que en popularidad: las expresiones negativas se comprueban antes que
las positivas.

### Cambios

- Nueva tabla `destination_sentiment` y fuente `sentiment` en el panel de datos.
- `import_sentiment_csv` en `import_service`.
- `tdrs_service`: `CSV_FACTORS`, `PRESETS` y `RAW_FIELDS` pasan a seis señales;
  el modelo se etiqueta como `TDRS CSV v3.2 · 6 señales · KNN`.
- `scenario_metrics` reporta `avg_top5_sentiment` y `top5_sentiment_real`.
- Nuevos `scripts/export_sentiment.py` e `scripts/inspect_db.py`.

### Tests

De 121 a 130. Entre ellos, uno que comprueba que el factor **influye de verdad**:
con peso 0 y con peso 100 el orden del ranking difiere.

## V24 – Diseño del recomendador y filtro de imágenes

Consolidación: sin datos nuevos, solo el acabado de la vista que consume la API.

### Fotografía en el recomendador

La vista no tenía ninguna imagen, mientras el simulador sí las usaba en su Top 3.
Era la incoherencia visual más evidente.

- El bloque destacado lleva la fotografía **como fondo con degradado encima**, de
  modo que da contexto sin competir con el texto ni desplazar información.
- Las tarjetas de alternativas llevan fotografía superior, como el podio del
  simulador.
- Atribución visible en ambos casos.
- El score se acompaña de una lectura cualitativa («afinidad muy alta», «alta»…):
  un 0,86 a secas no dice nada a quien lo lee.
- Se retiran los KPIs técnicos que había bajo el bloque destacado («Destinos
  propuestos», «Score máximo», «Con cobertura completa»): repetían lo que el
  propio bloque ya comunica.

### El filtro que hizo falta

Al verificar las fotos de los municipios que devuelve la API apareció un problema
que habría empeorado el diseño en lugar de mejorarlo: **Wikipedia usa la bandera o
el escudo del infobox como miniatura principal** de los artículos de municipios
españoles. Níjar devolvía `Bandera_de_Nijar.svg`, Sevilla `Flag_of_Seville.svg`,
Madrid su escudo. Una bandera municipal a pantalla completa como fondo destacado
queda mal.

`destination_image_service` ahora descarta esas miniaturas por dos vías
independientes:

1. **Nombre del fichero**: bandera, flag, escudo, coat_of_arms, mapa, location,
   locator, logo y variantes.
2. **Proporción**: un escudo o una bandera es vertical o cuadrada; una fotografía
   de paisaje es panorámica. Se exige una relación de aspecto mínima de 1,15.

Y se amplían los candidatos de búsqueda de 5 a 12, porque al descartar símbolos a
menudo no quedaba ninguno.

Efecto medido sobre 13 municipios reales de la API: la cobertura baja de 8/13 a
5/13, pero **las que pasan son fotografías de verdad**. Níjar devuelve el Arrecife
de las Sirenas, Mijas una vista aérea, Sevilla la ciudad. Se prefiere el fondo
sólido a ilustrar un destino con su escudo.

### Otros

- Se recorta el docstring de `streamlit_app.py`, que describía la estructura de
  carpetas y se quedaba obsoleto en cada refactor. Esa información vive en el
  README.

### Tests

De 130 a 135, con seis casos nuevos que fijan el filtro: banderas, escudos,
mapas, imágenes verticales, y la preferencia por la fotografía cuando conviven
con un símbolo en el mismo conjunto de resultados.

## V25 – Escenarios que se notan, imágenes locales y limpieza del podio

Tres ajustes pedidos tras usar la app.

### El selector de escenario no cambiaba el podio

Se midió: con los presets anteriores, el **Top 3 era idéntico** en Popular,
Equilibrado y Explorador (Algarve, Menorca, Mallorca). No era un fallo de la
lógica de pesos, sino de datos: con 16 destinos y unos pocos fuertes en todas las
señales, ningún reajuste tibio los desbancaba.

Los pesos de cada escenario se han **contrastado** para que la señal dominante de
cada uno mande de verdad: Popular pone popularidad 100 y baja el resto; Explorador
pone popularidad 10 y satisfacción 100. Medido después: el Top 3 ya difiere entre
escenarios y el resto del ranking se mueve claramente. Este efecto crecerá cuando
se amplíe el catálogo a 39 destinos.

### Iconos de mineral fuera del podio

Se retiran los iconos oro/plata/bronce de Icons8 del podio del simulador. Eran
imágenes remotas que a veces no cargaban y dejaban un cuadro de color junto a
«opción N». Ahora solo queda el texto «opción 1/2/3».

### Fotografías servidas desde local

`scripts/download_destination_images.py` descarga una foto por destino del
catálogo a `assets/destinations/` y el dashboard las sirve desde ahí, sin llamar a
Wikipedia en cada carga. Se obtienen vía la API de MediaWiki (no por URL directa
de Commons, que responde 429 ante descargas en ráfaga), se reescalan a 1280 px y
se recomprimen.

Resultado: **10 de 16** destinos con foto local curada (~2,3 MB en total). Los 6
restantes son municipios cuyo artículo solo ofrece bandera o escudo como
miniatura, que el filtro descarta; esos caen en el fallback a Wikipedia en vivo o
en su fondo sólido. `components/assets.py` gana `get_local_destination_image`, que
las vistas del simulador y del recomendador consultan antes que la red.

### Tests

De 135 a 141. Nuevos: que los escenarios no produzcan el mismo ranking, que
Popular y Explorador difieran, y la carga de imágenes locales por slug
normalizado.

## V26 – Catálogo de 39 destinos y tracking de impresiones

### El problema de fondo: Algarve ganaba siempre

Medido: con el catálogo de 16 destinos, Algarve salía 1º en los tres escenarios
porque puntuaba alto en las seis señales a la vez (1.00 en sol, precipitación y
satisfacción; 0.95 en popularidad). No había combinación de pesos que lo bajara,
y no debía haberla: era un dato real. La causa no era el modelo sino el catálogo
corto con un ganador claro.

### La solución: ampliar a los 39 destinos del pipeline

`scripts/export_catalog.py` exporta de `tui_recomendador.db` a CSV versionables:

- `destinos_pipeline.csv` — 39 destinos con características (playa, UNESCO, isla,
  accesibilidad, saturación) y precio de referencia derivado de la mediana de sus
  experiencias reales.
- `clima_pipeline.csv` — 1638 observaciones mensuales.
- `conectividad_pipeline.csv` — 39 destinos.
- `seguridad_pipeline.csv` — 16 países.

La fuente `destinations_tdrs` deja de leer el mock `propuesta_7.html` y pasa a
importar el CSV, con `import_destinations_csv`. Clima, conectividad y seguridad
apuntan también a los CSV del pipeline.

Resultado, medido tras el cambio:

| Escenario | Top 3 |
| --- | --- |
| Popular | Alicante, Gran Canaria, Barcelona |
| Equilibrado | Córdoba, Alicante, Barcelona |
| Explorador | Córdoba, Alicante, Fuerteventura |

Algarve ya no aparece en el Top 6: tiene competencia real. Los tres escenarios
dan rankings distintos y el selector se nota de verdad.

### Tracking de impresiones

Los KPIs de clics y el mapa de Control Web estaban a cero porque la app nunca
generaba eventos con destino: solo registraba `page_view`. Ahora el Simulador
TDRS registra un `product_impression` por cada destino del podio al calcularse el
ranking, con `dedupe_key` por escenario. Es interacción real y trazable (el
usuario ve esos destinos recomendados) y alimenta el mapa y los KPIs, que antes
quedaban vacíos.

### Tests

141 (se mantiene el número; se sustituyen los que asumían 16 destinos concretos).
Se corrige un test del servicio de imágenes que heredaba el cortacircuitos de red
de otro test: `conftest.py` gana un fixture que resetea los cortacircuitos entre
tests.
