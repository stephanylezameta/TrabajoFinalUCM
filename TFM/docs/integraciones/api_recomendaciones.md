# API de recomendaciones de destinos de España

Motor de recomendación externo desplegado como Azure Function. Lo consume la
vista **Recomendador España** del dashboard, a través de
[`services/recommendation_api_service.py`](../../dashboard/services/recommendation_api_service.py).

Este contrato se verificó llamando a la API real. Los límites y el vocabulario
que aquí se documentan están replicados en el cliente para validar en local y no
gastar una llamada de red en un error evitable.

## Relación con el TDRS

Son **dos motores independientes**, no uno que sustituya al otro:

| | Simulador TDRS | Recomendador España |
| --- | --- | --- |
| Ámbito | Catálogo internacional de TUI (Algarve, Mallorca, Split, Maldivas…) | Municipios españoles (Níjar, Sevilla, Mijas…) |
| Cálculo | Local, sobre SQLite | Remoto, en la Function |
| Fuentes | CSV de clima, conectividad aérea e indicadores del Banco Mundial | Catálogo turístico, OpenStreetMap, señales de YouTube y clima histórico de AEMET |
| Salida | Ranking completo del catálogo | Siempre 3 destinos |

## Configuración

Ninguna clave va en el código. El servicio lee variables de entorno, y
`streamlit_app.py` publica en el entorno lo que encuentre en `st.secrets`.

| Variable | Uso |
| --- | --- |
| `TUI_RECO_API_BASE` | URL del endpoint **sin** el parámetro `code`. Opción recomendada. |
| `TUI_RECO_API_KEY` | Clave de función. Se envía en la cabecera `x-functions-key`, no en el querystring, así no queda en logs de proxies ni en el historial del navegador. |
| `TUI_RECO_API_URL` | Alternativa: URL completa con `?code=` incluido. |
| `TUI_RECO_API_TIMEOUT` | Segundos de espera. 30 por defecto, porque la Function tiene arranque en frío. |

Si no hay endpoint configurado, la vista no falla: queda en modo informativo
mostrando el formulario y el contrato.

## Petición

`POST` con `Content-Type: application/json`.

```json
{
  "contract_version": "recommendation-request-v1",
  "travel": { "month": 7, "trip_length_days": 7 },
  "preferences": {
    "interests": ["coast_beach", "nature_mountains"],
    "climate": {
      "temperature_preference": "warm_sunny",
      "minimum_sunny_days": 25,
      "maximum_precipitation_days": 2
    },
    "popularity_target": 0.8,
    "accommodation_type": "apartment"
  },
  "filters": {
    "include_regions": [],
    "exclude_regions": ["Comunidad de Madrid"],
    "exclude_destinations": []
  },
  "locale": "es-ES"
}
```

`contract_version` es opcional: la API acepta la petición sin él.

### Vocabulario admitido

Cualquier valor fuera de estas listas devuelve `400`.

- **`interests`** (7): `coast_beach`, `nature_mountains`, `sports_outdoors`,
  `gastronomy_wine`, `history_culture`, `rural`, `wellness`.
- **`temperature_preference`** (4): `warm_sunny`, `mild`, `cool`, `any`.
- **`accommodation_type`** (3): `hotel`, `apartment`, `any`.

### Límites

| Campo | Rango |
| --- | --- |
| `travel.month` | 1–12 |
| `travel.trip_length_days` | 1–30 |
| `preferences.popularity_target` | 0–1 |

`popularity_target` es un objetivo de **proximidad**, no un máximo: el motor
busca destinos cuyo índice se acerque al valor pedido.

### Filtros

`include_regions` y `exclude_regions` aceptan nombres de comunidad autónoma
(`"Andalucía"`, `"Illes Balears"`…).

Dos comportamientos verificados que conviene tener presentes:

- Si los filtros dejan menos de tres destinos disponibles, la API responde `422`
  en lugar de devolver una lista corta.
- `exclude_destinations` con un **nombre** de municipio no surte efecto: al
  excluir `"Níjar"` el destino seguía apareciendo en el ranking. Probablemente
  espera un `place_id`. Sin confirmar con el equipo de la API.

## Respuesta

`contract_version` = `recommendation-response-v1`.

Campos de primer nivel: `recommendation_id`, `generated_at`, `engine`,
`normalized_input`, `ranking`, `global_warnings`.

`engine` declara el tipo de motor y si se usó un modelo entrenado. En la versión
verificada: `deterministic_heuristic`, `heuristic-v1`,
`trained_model_used: false`.

**El ranking contiene siempre 3 elementos.** Los parámetros `top_n`, `limit`,
`max_results` y `options.top_n` se aceptan pero se ignoran.

Cada elemento del ranking incluye:

| Campo | Contenido |
| --- | --- |
| `rank` | Posición, 1–3. |
| `destination` | `place_id`, `ine_code`, `name`, `province`, `autonomous_community`, `primary_typology`. |
| `recommendation_score` | Puntuación global 0–1. |
| `confidence` | `score` y `level` (`high` / `medium` / `low`). |
| `headline` | Resumen en una frase. |
| `reason_codes` | Motivos en forma de código, p. ej. `INTEREST_MATCH`, `PRECIPITATION_MATCH`. |
| `preference_match` | Por cada preferencia pedida: valor solicitado, valor histórico y `matched` booleano. |
| `score_breakdown` | Cinco dimensiones: `interest_match`, `climate_fit`, `popularity_fit`, `tourism_offer`, `accommodation_fit`. |
| `what_it_offers` | Recuento de puntos de interés, categorías principales, hoteles y apartamentos. |
| `climate_profile` | Clima histórico del mes: temperaturas, días de sol, precipitación, horas de sol. |
| `popularity_profile` | `index`, `basis` y número de vídeos de la señal de YouTube. |
| `strengths` / `tradeoffs` | Justificación en lenguaje natural, incluidas las concesiones. |
| `data_coverage` | Cuatro banderas: `catalog`, `osm`, `youtube`, `aemet`. |
| `data_warnings` | Avisos específicos del destino. |

La respuesta es autoexplicativa por diseño: `score_breakdown`,
`preference_match`, `tradeoffs` y `data_coverage` permiten justificar cada
recomendación y saber con qué fuentes se construyó. La vista los expone tal cual,
sin reinterpretarlos.

## Errores

| Código | Significado | Tratamiento en el cliente |
| --- | --- | --- |
| `400` | Validación: `{"error": "..."}`. Para `temperature_preference` y `accommodation_type` el mensaje enumera los valores válidos; para `interests` no. | `error_kind = "validation"`, se muestra como aviso. |
| `422` | Los filtros dejan menos de tres destinos. | `error_kind = "validation"`. |
| `5xx` | Error del servidor. | Activa el cortacircuitos. |
| Sin red / timeout | La Function puede estar arrancando en frío. | `error_kind = "network"`, se sugiere reintentar. |

El cliente nunca lanza excepciones hacia la interfaz: siempre devuelve un
diccionario con `ok` y, si procede, un `error` legible.

Tras un fallo de red o `5xx` se activa un **cortacircuitos** de 20 segundos para
que la interfaz no acumule esperas en reruns sucesivos, y hay una **caché en
proceso** (32 entradas) que evita repetir la misma consulta en cada rerun de
Streamlit.

## Cómo se descubrió el vocabulario

La API no expone esquema ni endpoint de descubrimiento. El vocabulario se obtuvo
por sondeo: enviando valores candidatos de uno en uno y registrando cuáles
devolvían `200`. Los mensajes de error de `temperature_preference` y
`accommodation_type` enumeran los valores válidos, lo que permitió cerrar esas
dos listas con certeza. La de `interests` se cerró probando 90 candidatos.

Si el equipo de la API añade intereses, habrá que ampliar `INTEREST_LABELS` en
`services/recommendation_api_service.py` y el test
`test_vocabulary_matches_documented_contract`, que fija el contrato.
