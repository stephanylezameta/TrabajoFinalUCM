# Documentación del TFM

Esta carpeta contiene **solo documentación**. El código de la aplicación vive en
[`TFM/dashboard/`](../dashboard/), no aquí.

## Estructura

| Carpeta | Contenido |
| --- | --- |
| [`propuesta_diseno/`](propuesta_diseno/) | Entregables de diseño y análisis: benchmarking competitivo, propuestas de recomendación y de dashboard B2B, y los HTML/PDF de las propuestas presentadas. |
| [`integraciones/`](integraciones/) | Contratos de las APIs externas que consume el proyecto. |
| [`referencia_web_tui/`](referencia_web_tui/) | Captura del sitio público de TUI (`TUI.html` + `TUI_files/`) usada como referencia visual. Material de terceros, no lo consume ningún código. |

## Documentación de la aplicación

La documentación técnica del dashboard está junto a su código, en
[`TFM/dashboard/docs/`](../dashboard/docs/):

| Documento | Contenido |
| --- | --- |
| [`assistant_ai_integration.md`](../dashboard/docs/assistant_ai_integration.md) | Contrato del asistente conversacional y su conector de IA externa. |
| [`despliegue_streamlit_cloud.md`](../dashboard/docs/despliegue_streamlit_cloud.md) | Cómo publicar el dashboard con URL pública. |
| [`image_credits.md`](../dashboard/docs/image_credits.md) | Atribución y licencias de las imágenes. |
| [`revision_notes.md`](../dashboard/docs/revision_notes.md) | Historial de rondas de feedback visual. |
| [`feedback/`](../dashboard/docs/feedback/) | Evidencia de las revisiones: PDFs y capturas por ronda. |

## Nota sobre credenciales

`propuesta_diseno/API_AZURE.txt` contiene la clave de función de la API de
recomendaciones dentro del querystring. Está excluido por `.gitignore` y **no
debe subirse al repositorio**. Para configurar la aplicación, usa
`dashboard/.streamlit/secrets.toml` a partir de la plantilla
`secrets.toml.example`, o ejecuta:

```powershell
python scripts\setup_local_secrets.py ..\docs\propuesta_diseno\API_AZURE.txt
```

## Historial de reorganización

La carpeta contenía cinco copias del proyecto Streamlit (`Streamlit_DG_P1`,
`propuesta_diseno/Streamlit_DG_final` y tres instantáneas bajo
`propuesta_diseno/Sup/`). Se comprobó que `Streamlit_DG_final` era byte a byte
idéntica a `Streamlit_DG_P1` una vez normalizado el fin de línea, y que ninguna
copia contenía ficheros ausentes en ella. La copia viva se movió a
`TFM/dashboard/` y las redundantes se eliminaron; siguen recuperables desde el
historial de git.
