# Publicar el dashboard con URL pública

El destino es [Streamlit Community Cloud](https://share.streamlit.io), que da una
URL pública gratuita del tipo `https://<nombre>.streamlit.app`.

> El despliegue requiere iniciar sesión con la cuenta de GitHub propietaria del
> repositorio y autorizar la aplicación. Ese paso es manual: no puede hacerse por
> línea de comandos ni delegarse.

## Estado de preparación

Ya está resuelto en el repositorio:

- [x] App en una ruta limpia: `TFM/dashboard/` (antes estaba enterrada en `docs/`).
- [x] `requirements.txt` con versiones fijadas, junto al entrypoint.
- [x] `pytest` fuera del runtime, en `requirements-dev.txt`.
- [x] Sin parámetros deprecados de Streamlit (`use_container_width` → `width`).
- [x] La base de datos se construye sola en el primer arranque.
- [x] Los CSV y HTML de `data/raw/` están versionados, así que el arranque tiene datos.
- [x] Secretos fuera del código y `secrets.toml` excluido por `.gitignore`.

Queda por hacer, y requiere tu cuenta:

- [ ] Subir la rama al remoto.
- [ ] Crear la app en share.streamlit.io.
- [ ] Pegar los secretos en el panel.

## Parámetros del despliegue

| Campo | Valor |
| --- | --- |
| Repository | `stephanylezameta/TrabajoFinalUCM` |
| Branch | la rama que publiques |
| Main file path | `TFM/dashboard/streamlit_app.py` |
| Python version | 3.11 o superior |

## Dos detalles del subdirectorio

La [documentación de Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/status)
avisa de algo que cambia el comportamiento cuando el entrypoint no está en la
raíz: **la app se inicializa desde la raíz del repositorio**, aunque el
entrypoint esté en un subdirectorio.

Consecuencias, y cómo están cubiertas:

1. **Dependencias.** El fichero puede estar en la raíz del repo o junto al
   entrypoint. Está junto al entrypoint (`TFM/dashboard/requirements.txt`), que
   es la opción documentada y la que mantiene el flujo de trabajo local. No hay
   que duplicarlo en la raíz; tener dos ficheros sería peor, porque Cloud usa el
   primero que encuentra.

2. **Tema visual.** Streamlit lee `.streamlit/config.toml` del directorio de
   trabajo, que en Cloud es la raíz del repo. El tema de
   `TFM/dashboard/.streamlit/config.toml` puede quedar ignorado. El impacto real
   es mínimo porque la hoja de estilos de `components/styles.py` redefine casi
   todo; lo único que gobierna el TOML es el color primario de los widgets. Si
   quieres asegurarlo, copia ese fichero a `.streamlit/config.toml` en la raíz
   del repositorio.

Las rutas a datos y recursos no se ven afectadas: todas se resuelven con
`Path(__file__)`, nunca con el directorio de trabajo.

## Pasos

### 1. Subir el código

Comprueba antes que no vas a subir secretos:

```powershell
git status --short
git check-ignore -v TFM/dashboard/.streamlit/secrets.toml TFM/docs/propuesta_diseno/API_AZURE.txt
```

El segundo comando debe listar ambos ficheros como ignorados. Si no los lista,
para y revisa el `.gitignore` antes de continuar.

```powershell
git add TFM/dashboard TFM/docs .gitignore
git commit -m "Dashboard: recomendador por API, refactor en componentes y vistas"
git push -u origin <tu-rama>
```

### 2. Crear la app

1. Entra en [share.streamlit.io](https://share.streamlit.io) con GitHub.
2. **Create app** → **Deploy a public app from GitHub**.
3. Rellena los campos de la tabla anterior.
4. En **Advanced settings**, selecciona Python 3.11+ y pega los secretos:

```toml
TUI_RECO_API_BASE = "https://<function-app>.azurewebsites.net/api/recommendations"
TUI_RECO_API_KEY = "<function-key>"
TUI_RECO_API_TIMEOUT = "30"
```

5. **Deploy**. El primer arranque instala dependencias y construye el SQLite;
   tarda un par de minutos.

### 3. Comprobar

- Las cuatro vistas cargan: Simulador TDRS, Recomendador España, Control Web,
  Datos / modelo.
- En **Datos / modelo → Fuentes**, las cinco fuentes aparecen con filas > 0.
  Si están a cero, el arranque no encontró `data/raw/`: confirma que esos ficheros
  se subieron.
- En **Recomendador España**, pide recomendaciones. Si responde con tres destinos,
  los secretos están bien. Si dice que la API no está configurada, revísalos.

## Qué esperar del entorno gratuito

- **La base de datos es efímera.** El contenedor se recicla y `data/app.db` se
  reconstruye desde `data/raw/`. Los eventos de tracking generados por el uso
  público se pierden en cada reinicio. Es aceptable para una demo; para conservar
  histórico haría falta una base gestionada.
- **La app se suspende por inactividad** y tarda unos segundos en despertar.
- **La primera llamada a la API puede tardar** por el arranque en frío de la
  Function. El cliente lo avisa en lugar de fallar en silencio.

## Aviso de seguridad

El dashboard se publica **sin autenticación**: cualquiera con la URL verá los
datos y podrá usar el formulario del recomendador, lo que consume cuota de tu
Azure Function. Para este TFM es razonable, porque los datos son públicos o
sintéticos, pero conviene tenerlo presente:

- La clave de la Function no se expone en el navegador. Vive en el servidor de
  Streamlit y viaja en una cabecera servidor-a-servidor.
- Si quieres restringir el acceso, Community Cloud permite limitar la app por
  lista de correos en **Settings → Sharing**, a cambio de que deje de ser pública.
- Si la clave se filtrara, se rota desde el portal de Azure (Function App → App
  keys) y se actualiza el secreto en el panel de Streamlit.

## Alternativas

| Opción | Cuándo interesa |
| --- | --- |
| Streamlit Community Cloud | Demo pública gratuita. Es la recomendada aquí. |
| Hugging Face Spaces | Alternativa gratuita; requiere un `Dockerfile` o adaptar la estructura. |
| Azure App Service | Coherente con la Function ya desplegada, y permite persistir la base. Tiene coste. |
