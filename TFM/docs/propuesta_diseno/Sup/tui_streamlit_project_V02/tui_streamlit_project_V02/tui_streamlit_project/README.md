# TUI Data Intelligence · Feedback UI/UX V05

Versión Streamlit implementada a partir de `TUI_Master_Brief_Feedback_UI_V3.mb` y ajustada con la última ronda de feedback visual.

## Ajuste V05
- Se mantiene íntegramente la V04 y se recupera **Pesos del modelo** en el sidebar del Simulador TDRS, justo encima de **Restricciones**.
- Los cinco sliders parten de los valores del escenario Popular / Equilibrado / Explorador y pueden editarse para recalcular el ranking.
- La captura de esta ronda se conserva en `docs/feedback/ronda_6/`.

## Ajustes V04
- Marca lateral: se elimina la palabra **Luxury**, quedando `Madrid UI · Operations`.
- Simulador TDRS: se retira el bloque lateral de **Filtros / pesos del modelo**; los pesos se aplican automáticamente según Popular, Equilibrado o Explorador.
- Top 3: se añaden fotografías de Algarve, Mallorca y Split con atribución visible.
- Control Web y Datos / modelo: se eliminan sus títulos principales del contenido; ambas vistas arrancan directamente en el bloque de alertas.
- Los PDFs de esta ronda se conservan en `docs/feedback/ronda_5/`.
- Créditos de las fotografías en `docs/image_credits.md`.

## Vistas

### Inicio · Asistente
- Chat operativo a ancho completo.
- KPIs fuera del chat y debajo de la conversación.
- El sistema de alertas se concentra en las vistas **Control Web** y **Datos / modelo**.

### Simulador TDRS
- TDRS CSV v3.1.
- Selector superior con tres escenarios: **Popular**, **Equilibrado** y **Explorador**.
- El escenario **Personalizado** no se muestra en la interfaz.
- Factores: días soleados, baja precipitación, popularidad, capacidad sanitaria y seguridad.
- Los pesos parten del escenario seleccionado y vuelven a ser editables desde el bloque lateral **Pesos del modelo**; las restricciones permanecen debajo.
- Restricciones: precio máximo y máximo de días hospedados (hasta 365).
- Top 3 diferenciado con fotografías de destino y resto del ranking en tabla.
- Faltantes del scoring estimados con **KNN k=3** sin sobrescribir SQLite. La cobertura original y los campos imputados se mantienen visibles en el ranking.

### Control Web
- Sistema de alertas operativas al comienzo de la vista.
- KPIs: Sesiones, Clics, Reservas, Ingresos, Cancelaciones y ROI.
- Mapa geoespacial con tres botones grandes: **Clics / Reservas / Ingresos**.
- El mapa combina métricas reales de `events` + `bookings` con `data/destination_coordinates.csv`.
- Se mantienen Estado de instrumentación y Rendimiento por destino.

### Datos / modelo
- Sistema de alertas de datos en la parte superior.
- KPIs técnicos compactos.
- Tabs: Fuentes, Historial de actualizaciones, Bases y tablas, Configuración.

## Fuentes

La app mantiene los datasets suministrados en `data/raw/` y SQLite en `data/app.db`.

El fichero `data/destination_coordinates.csv` contiene coordenadas de referencia del prototipo. Antes de producción debe sustituirse o verificarse mediante un geocoder/API corporativo fiable.

## Instalación

```powershell
python -m pip install -r requirements.txt
python scripts\build_model.py
python -m streamlit run streamlit_app.py
```

## Tests

```powershell
pytest -q
```

La versión incluye tests de esquema, TDRS/KNN y geolocalización.


## V06

La V06 mantiene la lógica de la V05 y aplica únicamente una actualización visual: fondo blanco iluminado con líneas negras/grises, tarjetas más luminosas y botones con estilo premium en escala neutra.


## V07

La V07 corrige un problema de superposición visual detectado en la V06. Se mantiene el lenguaje visual claro con fondo blanco y líneas negras/grises, pero se elimina la capa que podía ocultar los contenidos de la interfaz.


## V08

La V08 mantiene la configuración de la V07 y ajusta únicamente el fondo visual para lograr un panel lateral y un lienzo principal más continuos, con base azul claro y líneas negras/grises integradas.


## V09

La V09 ajusta la continuidad visual del fondo: las líneas decorativas quedan sincronizadas entre sidebar y contenido principal, y el panel lateral adopta un azul claro más translúcido sin cambiar la configuración funcional.


## V10

La V10 mantiene íntegramente la V09 y cambia únicamente el orden visual del simulador: el Top 3 aparece antes de los KPIs.


## V11

La V11 mantiene la V10 y simplifica las tres tarjetas principales del TDRS: se elimina el título Top 3, se cambia Posición por Opción y el valor principal pasa a ser únicamente el precio en euros, sin mostrar el score.


## V12

La V12 conserva la lógica de la V11 y refina las tarjetas de las tres opciones: precio alineado arriba a la derecha, sin texto KNN ni créditos visibles, y la tabla del resto del ranking usa `Opción` en lugar de `Posición`.
