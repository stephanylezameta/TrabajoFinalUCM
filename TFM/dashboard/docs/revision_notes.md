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
