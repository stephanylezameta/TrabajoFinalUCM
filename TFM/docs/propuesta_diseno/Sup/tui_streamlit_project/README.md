# TUI Streamlit · TDRS

Proyecto ejecutable basado en el Master Brief y en los HTML/CSV suministrados.

## Qué genera el modelo

`python scripts/build_model.py` crea `data/app.db` con:

- `products`: ofertas/paquetes.
- `sessions`, `events`, `bookings`: tracking y conversión.
- `destinations`: factores base del simulador TDRS de Propuesta 7.
- `climate_observations`: clima mensual.
- `connectivity_stats`: conectividad aérea y pasajeros.
- `country_indicators`: seguridad/sanidad por país.
- `imports`: trazabilidad de cargas.

Los CSV no son leídos directamente por la UI: se importan a SQLite y la app consume servicios/repositorios.

## Ejecutar

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python scripts/build_model.py
streamlit run streamlit_app.py
```

## Fuentes incluidas

Los ficheros originales se copian en `data/raw/`. El HTML se analiza/parsea pero **no se ejecutan scripts**.

## Notas de modelado

Los CSV entregados son señales de destino (clima, conectividad y país), no un catálogo completo de productos. Por eso están normalizados en tablas propias. `products` se inicializa con las tres tarjetas visibles de `tui_experiencia_final.html` y queda preparado para importar un CSV de productos real cuando exista.

El TDRS base conserva los factores del HTML de Propuesta 7: afinidad, demanda, capacidad (inversa de ocupación), impacto local, temporada/clima, accesibilidad y sostenibilidad. Los indicadores CSV se muestran como contexto y no sustituyen silenciosamente los factores base.
