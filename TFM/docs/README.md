# Documentación del TFM

Esta carpeta contiene **solo documentación**. El código de la aplicación vive en
[`TFM/dashboard/`](../dashboard/), no aquí, y el dashboard no lee nada de esta
carpeta en tiempo de ejecución.

## Contenido

| Fichero | Contenido |
| --- | --- |
| [`integraciones/api_recomendaciones.md`](integraciones/api_recomendaciones.md) | Contrato completo de la API de recomendación que consume el dashboard, verificado en vivo: vocabulario admitido, límites, respuesta y errores. |
| [`propuesta_diseno/benchmarking_competitivo.md`](propuesta_diseno/benchmarking_competitivo.md) | Posicionamiento del motor TDRS frente a competidores (Mindtrip, Nezasa, Murmuration). |
| [`propuesta_diseno/propuesta_recomendaciones_web_tui.md`](propuesta_diseno/propuesta_recomendaciones_web_tui.md) | Siete alternativas de diseño para integrar la recomendación en la web de TUI. |
| [`propuesta_diseno/propuesta_ia_redistribucion_dashboard.md`](propuesta_diseno/propuesta_ia_redistribucion_dashboard.md) | Propuesta integrada de recomendación IA, redistribución y dashboard. |
| [`Guia_Integracion_API_Recomendaciones.docx`](Guia_Integracion_API_Recomendaciones.docx) | Guía de integración de la API de recomendaciones. |

## Documentación de la aplicación

La documentación técnica del dashboard está junto a su código, en
[`TFM/dashboard/docs/`](../dashboard/docs/):

| Documento | Contenido |
| --- | --- |
| `assistant_ai_integration.md` | Contrato del asistente conversacional y su conector de IA externa. |
| `despliegue_streamlit_cloud.md` | Cómo publicar el dashboard con URL pública. |
| `image_credits.md` | Atribución y licencias de las imágenes. |
| `revision_notes.md` | Historial de rondas de feedback e iteraciones (V04–V26). |
| `feedback/` | Evidencia de las revisiones: PDFs y capturas por ronda. |

## Configuración de la API

La URL y la clave de la API de recomendaciones se configuran en
`dashboard/.streamlit/secrets.toml` (excluido por `.gitignore`), a partir de la
plantilla `secrets.toml.example`.

## Nota sobre la limpieza de esta carpeta

Se eliminaron los materiales que no eran documentación del TFM ni referencia
técnica: la captura del sitio web público de TUI (`referencia_web_tui/`, ~7,5 MB
de HTML y scripts de tracking de terceros), los HTML/PDF redundantes de las
propuestas (cuyo contenido está en los `.md`), y `API_AZURE.txt` (cuya clave vive
ahora en `secrets.toml`). Lo eliminado que estaba versionado sigue siendo
recuperable desde el historial de git.
