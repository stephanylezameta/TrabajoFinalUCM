# TUI Data Intelligence · Dashboard

Prototipo de dashboard de operaciones y recomendación turística para TUI,
construido en Streamlit sobre SQLite. Es una herramienta interna B2B con cuatro
funciones: simular rankings de destinos con un modelo propio, consultar un motor
de recomendación externo por API, controlar el tracking web/comercial y auditar la
calidad de los datos y sus fuentes.

Implementado a partir de `TUI_Master_Brief_Feedback_UI_V3.mb` y de las rondas de
feedback visual V04–V21, documentadas en [`docs/revision_notes.md`](docs/revision_notes.md).

## Arranque rápido

```powershell
python -m pip install -r requirements-dev.txt
python scripts\build_model.py
python -m streamlit run streamlit_app.py
```

Para que la vista **Recomendador España** funcione hace falta configurar la API:

```powershell
python scripts\setup_local_secrets.py ..\docs\propuesta_diseno\API_AZURE.txt
```

El script extrae la URL y la clave, las separa y escribe
`.streamlit/secrets.toml` (excluido por `.gitignore`) sin mostrar la clave por
pantalla. También puede hacerse a mano copiando `.streamlit/secrets.toml.example`.

Sin esa configuración la app arranca igual: la vista queda en modo informativo.

## Tests

```powershell
pytest -q
```

110 tests. No tocan `data/app.db` ni hacen llamadas de red: `conftest.py`
construye una base temporal desde los CSV de `data/raw/` y la destruye al acabar.

## Publicar con URL pública

Ver [`docs/despliegue_streamlit_cloud.md`](docs/despliegue_streamlit_cloud.md).
Entrypoint para Streamlit Community Cloud: `TFM/dashboard/streamlit_app.py`.

## Arquitectura

El brief impone el flujo `Streamlit → Services → Repositories → SQLite`, sin SQL
repartido por la interfaz.

```
streamlit_app.py        configuración de página, arranque y enrutado
config.py               rutas y DB_PATH (override con TUI_DB_PATH)
components/             presentación reutilizable
  styles.py             hoja de estilos
  assets.py             logo, iconos e imágenes de destino
  ui.py                 alertas, KPIs y encabezados
views/                  una vista por módulo
  tdrs.py  recommender.py  control_web.py  data_model.py
services/               lógica de negocio, sin dependencias de Streamlit
database/               connection · models (SCHEMA_SQL) · repositories · init_db
utils/text.py           normalize_text / slugify
scripts/                build_model.py · setup_local_secrets.py
data/                   app.db (generada) · raw/ · coordenadas · geojson
tests/                  suite pytest
docs/                   documentación e histórico de feedback
```

`services/` no importa Streamlit en ningún módulo. Eso permite usar el modelo sin
interfaz, como demuestra [`demo_modelo.ipynb`](demo_modelo.ipynb).

## Las cuatro vistas

### Simulador TDRS

Modelo propio *TDRS CSV v3.1 · KNN*. Cinco factores: días soleados, baja
precipitación, popularidad, capacidad sanitaria y seguridad.

- Selector con tres escenarios: **Popular**, **Equilibrado**, **Explorador**.
  `Personalizado` existe en el modelo pero no se expone.
- Sidebar ordenado como **Asistente IA → Pesos del modelo → Restricciones**. Los
  pesos parten del escenario y siguen siendo editables.
- Asistente conversacional que traduce lenguaje natural a los cinco pesos. Solo
  los aplica cuando el usuario pulsa **Aplicar propuesta al modelo**. Con
  `TUI_AI_ENDPOINT` usa IA externa; sin él, un intérprete local. Contrato en
  [`docs/assistant_ai_integration.md`](docs/assistant_ai_integration.md).
- Restricciones de precio máximo y días hospedados. **Solo excluyen si el dato
  existe**: un precio desconocido no descarta el destino.
- Top 3 en tarjetas con fotografía y precio destacado; resto del ranking en tabla.
- Los faltantes se estiman con **KNN k=3 sin escribir en SQLite**. Cada campo
  imputado queda marcado en `knn_imputed_fields`, y se distingue `data_coverage`
  (real) de `model_coverage` (tras imputar).

### Recomendador España

Motor externo consumido por API. Ranquea municipios españoles combinando catálogo
turístico, OpenStreetMap, señales de YouTube y clima histórico de AEMET.

Es **independiente del TDRS**, no lo sustituye: el TDRS cubre el catálogo
internacional de TUI y calcula en local. Devuelve siempre tres destinos con su
explicabilidad: desglose del score en cinco dimensiones, motivos, fortalezas,
concesiones y cobertura por fuente.

Contrato completo en
[`docs/integraciones/api_recomendaciones.md`](../docs/integraciones/api_recomendaciones.md).

### Control Web

Alertas operativas, seis KPIs comerciales (sesiones, clics, reservas, ingresos,
cancelaciones, ROI), mapa geoespacial con selector Clics/Reservas/Ingresos,
estado de instrumentación y rendimiento por destino.

El mapa se dibuja con matplotlib sobre un GeoJSON local, sin pydeck ni geopandas.

La app se instrumenta a sí misma: cada vista visitada y cada interacción del
asistente se registran en la tabla `events`, y esos mismos eventos alimentan
estos KPIs.

### Datos / modelo

Alertas de datos, KPIs técnicos y cuatro pestañas: Fuentes, Historial de
actualizaciones, Bases y tablas, Configuración. La pestaña de configuración
escribe en SQLite los intervalos objetivo y permite relanzar fuentes.

## Reglas de datos

Del brief, y visibles en el código:

- **Dato ausente ≠ dato estimado.** Si falta una variable se muestra `—`, nunca se
  inventa. La única excepción autorizada es la imputación KNN del scoring, que
  vive solo en memoria y queda trazada.
- **Trazabilidad.** Toda métrica debe poder rastrearse hasta un CSV, la base, un
  evento o una reserva.
- **Degradación en cascada.** Sin IA externa hay intérprete local; sin foto curada
  se busca en Wikipedia; sin red, placeholder; sin tracking, el mapa se pinta a
  intensidad cero; sin `cost_eur`, el ROI queda «Pendiente». La app no rompe por
  la falta de un recurso externo.

## Fuentes de datos

`data/raw/` contiene los datasets originales: clima mensual por destino,
conectividad aérea y pasajeros, e indicadores de seguridad y sanidad del Banco
Mundial (con celdas vacías, que es lo que justifica el KNN). Dos HTML aportan el
listado de destinos y el catálogo de ofertas.

`data/app.db` se genera; no está versionada. `scripts/build_model.py` la
reconstruye y es idempotente.

`data/destination_coordinates.csv` son centroides curados a mano para el
prototipo. **Antes de producción deben sustituirse por un geocoder corporativo.**

## Variables de entorno

| Variable | Uso |
| --- | --- |
| `TUI_DB_PATH` | Ruta alternativa del SQLite. La usan los tests. |
| `TUI_RECO_API_BASE` / `TUI_RECO_API_KEY` | API de recomendaciones. La clave viaja en cabecera. |
| `TUI_RECO_API_URL` | Alternativa con la clave en el querystring. |
| `TUI_RECO_API_TIMEOUT` | Espera en segundos. 30 por defecto. |
| `TUI_AI_ENDPOINT` / `TUI_AI_API_KEY` / `TUI_AI_TIMEOUT` | Asistente conversacional. |
| `TUI_IMAGE_USER_AGENT` / `TUI_IMAGE_TIMEOUT_SECONDS` | Búsqueda de imágenes en Wikipedia. |

Los servicios leen `os.getenv`, para poder usarse sin Streamlit.
`streamlit_app.py` publica en el entorno lo que encuentre en `st.secrets`, de modo
que la misma configuración sirve en local y en Streamlit Cloud.

## Limitaciones conocidas

- `data/destination_coordinates.csv` no está verificado contra un geocoder.
- `exclude_destinations` de la API externa no filtra por nombre de municipio.
- El motor externo devuelve siempre tres destinos: no admite paginación.
- En Streamlit Community Cloud el SQLite es efímero, así que el tracking generado
  por el uso público se pierde en cada reinicio del contenedor.
