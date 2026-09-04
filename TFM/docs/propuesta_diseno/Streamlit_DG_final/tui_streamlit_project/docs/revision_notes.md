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

