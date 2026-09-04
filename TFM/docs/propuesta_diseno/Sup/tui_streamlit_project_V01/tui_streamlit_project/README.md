# TUI Data Intelligence · Feedback UI/UX V3

Versión Streamlit implementada a partir de `TUI_Master_Brief_Feedback_UI_V3.mb`.

## Vistas

### Inicio · Asistente
- Alertas y estado en la parte superior.
- Chat operativo a ancho completo.
- KPIs fuera del chat y debajo de la conversación.

### Simulador TDRS
- TDRS CSV v3.1.
- Factores: días soleados, baja precipitación, popularidad, capacidad sanitaria y seguridad.
- Selector de escenarios con icono y descripción.
- Restricciones: precio máximo y máximo de días hospedados (hasta 365).
- Top 3 diferenciado y resto del ranking en tabla.
- Faltantes del scoring estimados con **KNN k=3** sin sobrescribir SQLite. La cobertura original y los campos imputados se mantienen visibles.

### Control Web
- KPIs: Sesiones, Clics, Reservas, Ingresos, Cancelaciones y ROI.
- El embudo se sustituye por un mapa geoespacial.
- Selector del mapa: Clics / Reservas / Ingresos.
- El mapa combina métricas reales de `events` + `bookings` con `data/destination_coordinates.csv`.
- Si no existe tracking por destino, el mapa muestra los puntos de referencia con intensidad 0 y lo indica explícitamente.
- Se mantienen Estado de instrumentación y Rendimiento por destino.

### Datos / modelo
- Alertas de datos en la parte superior.
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
