# MASTER BRIEF · TUI Streamlit — Propuesta 7 + Control Web + Modelo de Datos

## 1. Objetivo

Construir una aplicación en Streamlit con dos vistas principales y una capa de datos común que se genere antes de construir la interfaz.

La arquitectura general deberá seguir este flujo:

```text
Archivos de entrada
        ↓
Análisis y normalización
        ↓
Modelo de datos
        ↓
Base de datos
        ↓
Servicios / herramientas
        ↓
Streamlit
   ├── Ventana 1 — Propuesta 7
   └── Ventana 2 — Control Web
```

La interfaz no deberá depender directamente del CSV. El CSV se utilizará como fuente de importación y será transformado a un modelo persistente que pueda ser consumido por las herramientas y vistas de la aplicación.

### 1.1 Ventana 1 — Propuesta 7

Orientada al usuario final.

Debe:

- mostrar los productos/viajes disponibles,
- seleccionar los campos más relevantes para la decisión de compra,
- inspirarse en la distribución de la Propuesta 7,
- usar una identidad visual combinada con la marca TUI,
- utilizar el modelo de datos como fuente principal,
- registrar las interacciones necesarias para medir el rendimiento posterior.

### 1.2 Ventana 2 — Control Web

Orientada a negocio, operaciones y marketing.

Debe:

- medir el rendimiento cuando la página se ponga en marcha,
- calcular CTR, conversión, eficiencia, reservas, ingresos, ROAS y otras métricas turísticas cuando existan los datos necesarios,
- consumir los datos registrados por la propia aplicación,
- indicar qué tracking falta cuando una métrica todavía no pueda calcularse,
- distinguir claramente entre métricas disponibles y métricas pendientes de instrumentar.

---

## 2. Fuentes de entrada

La app debe permitir cargar:

- `CSV` del modelo,
- `HTML` de referencia/propuesta.

### 2.1 CSV

Procesar automáticamente:

- separador,
- encoding,
- tipos de columnas,
- fechas,
- campos numéricos,
- valores nulos,
- nombres de columnas,
- duplicados cuando puedan identificarse de forma segura.

El CSV no será utilizado directamente como fuente de las vistas.

Flujo esperado:

```text
CSV
 ↓
Análisis
 ↓
Mapeo de columnas
 ↓
Validación
 ↓
Normalización
 ↓
Base de datos
```

### 2.2 HTML

Extraer como mínimo:

- `<title>`,
- H1/H2/H3,
- cantidad de enlaces,
- formularios,
- inputs/selects,
- CTAs/botones relevantes.

No ejecutar scripts del HTML subido.

El HTML se utilizará como referencia estructural y visual. No deberá introducir código ejecutable dentro de la aplicación.

---

## 3. Modelo de datos y capa de persistencia

Antes de generar la página web, la aplicación deberá crear un pequeño modelo de datos que sirva como capa intermedia entre las fuentes de entrada, las herramientas de la aplicación y Streamlit.

El objetivo es evitar que las vistas trabajen directamente contra archivos y permitir que catálogo, búsquedas, eventos, reservas y métricas se consulten desde una estructura común.

### 3.1 Base de datos inicial

Para la primera versión se utilizará `SQLite`.

Motivos:

- no requiere servidor independiente,
- permite ejecutar el proyecto localmente,
- simplifica la entrega académica,
- permite persistencia real,
- puede sustituirse posteriormente por PostgreSQL u otro motor SQL.

La arquitectura deberá prepararse para que el cambio de motor no obligue a reescribir las vistas.

Estructura recomendada:

```text
database/
├── __init__.py
├── connection.py
├── models.py
├── repositories.py
└── init_db.py
```

La interfaz Streamlit no deberá contener consultas SQL repartidas por los componentes visuales.

Las consultas y operaciones deberán centralizarse mediante repositorios y/o servicios.

---

### 3.2 Entidad `products`

Representa los viajes, paquetes, hoteles u ofertas que aparecen en la Ventana 1.

Campos recomendados:

- `product_id`
- `title`
- `destination`
- `hotel`
- `price`
- `currency`
- `duration_days`
- `nights`
- `departure_date`
- `return_date`
- `rating`
- `board_basis`
- `transport`
- `airline`
- `availability`
- `discount`
- `description`
- `image_url`
- `detail_url`
- `source`
- `created_at`
- `updated_at`
- `extra_data`

`extra_data` podrá almacenar como JSON aquellas columnas del CSV que no tengan todavía un campo estándar en el modelo.

Esto permitirá trabajar con CSVs de estructuras diferentes sin perder información.

---

### 3.3 Entidad `sessions`

Representa una sesión de navegación.

Campos recomendados:

- `session_id`
- `user_id`
- `started_at`
- `ended_at`
- `source`
- `medium`
- `campaign`
- `device`
- `country`

`user_id` será opcional.

La aplicación deberá funcionar correctamente con usuarios anónimos mediante `session_id`.

---

### 3.4 Entidad `events`

Registra las interacciones realizadas dentro de la aplicación y será una de las fuentes principales de la Ventana 2 — Control Web.

Campos recomendados:

- `event_id`
- `timestamp`
- `session_id`
- `user_id`
- `page`
- `event_type`
- `element_id`
- `product_id`
- `destination`
- `source`
- `medium`
- `campaign`
- `device`
- `country`
- `response_time_ms`
- `metadata`

Tipos de eventos iniciales:

```text
page_view
search
product_impression
product_click
detail_view
filter_change
checkout_start
booking
cancellation
```

Los componentes de Streamlit deberán registrar estos eventos cuando corresponda.

Ejemplo:

```text
Usuario pulsa "Ver oferta"
        ↓
product_click
        ↓
events
        ↓
Base de datos
        ↓
Control Web
        ↓
CTR / funnel / conversión
```

---

### 3.5 Entidad `bookings`

Representa las reservas o conversiones generadas desde la aplicación.

Campos recomendados:

- `booking_id`
- `timestamp`
- `session_id`
- `user_id`
- `product_id`
- `passengers`
- `room_nights`
- `revenue_eur`
- `cost_eur`
- `margin_eur`
- `status`
- `cancelled_at`

Estados iniciales:

```text
started
confirmed
cancelled
```

Esta tabla permitirá calcular, cuando existan datos suficientes:

- reservas,
- conversión,
- ingresos,
- ticket medio,
- margen,
- pasajeros,
- noches vendidas,
- tasa de cancelación,
- ROAS cuando exista información de costes.

---

### 3.6 Relaciones básicas

Modelo conceptual:

```text
PRODUCTS
   │
   ├───────────────┐
   │               │
   ▼               ▼
EVENTS          BOOKINGS
   ▲               ▲
   │               │
   └──── SESSIONS ─┘
```

Relaciones:

```text
sessions 1 ─── N events
sessions 1 ─── N bookings
products 1 ─── N events
products 1 ─── N bookings
```

---

### 3.7 Importación automática del CSV

Cuando el usuario cargue el CSV del modelo, la aplicación deberá:

1. detectar separador y encoding,
2. detectar tipos de columnas,
3. identificar columnas relevantes,
4. mapear las columnas conocidas al modelo `products`,
5. conservar columnas adicionales dentro de `extra_data`,
6. validar registros,
7. detectar identificadores disponibles,
8. generar un `product_id` interno cuando sea necesario,
9. insertar o actualizar los productos en la base de datos.

El CSV deberá considerarse una fuente de importación, no la fuente directa utilizada por las vistas.

---

### 3.8 Conexión con las herramientas de la aplicación

Todas las funcionalidades deberán trabajar sobre la capa de datos.

#### Buscador

Consultará `products`.

Debe permitir, cuando existan esos campos:

- destino,
- hotel,
- nombre del producto,
- fechas,
- disponibilidad.

Cada búsqueda deberá poder registrar un evento `search`.

#### Filtros

Consultarán `products`.

Los cambios relevantes podrán registrarse como `filter_change`.

#### Tarjetas de producto

Obtendrán sus datos de `products`.

Podrán registrar:

```text
product_impression
product_click
detail_view
```

#### Checkout / reserva

Utilizará:

```text
sessions
products
events
bookings
```

El inicio del proceso registrará `checkout_start`.

La confirmación deberá generar una reserva y registrar el evento correspondiente.

#### Control Web

Obtendrá sus métricas principalmente de:

```text
sessions
events
bookings
products
```

Las métricas no deberán introducirse manualmente cuando puedan calcularse a partir de datos registrados.

---

### 3.9 Capa de servicios

La aplicación deberá disponer de funciones reutilizables.

Ejemplos:

```python
get_products()
search_products()
filter_products()
get_product()
import_products_from_csv()
create_session()
register_event()
create_booking()
cancel_booking()
get_dashboard_metrics()
get_funnel_metrics()
get_destination_metrics()
```

Arquitectura:

```text
Streamlit UI
     ↓
Services
     ↓
Repositories
     ↓
Database
     ↓
SQLite
```

Estructura recomendada:

```text
services/
├── __init__.py
├── catalog_service.py
├── import_service.py
├── tracking_service.py
├── booking_service.py
└── analytics_service.py
```

---

### 3.10 Inicialización automática

Al arrancar la aplicación:

```bash
streamlit run streamlit_app.py
```

el sistema deberá comprobar si la base de datos existe.

Si no existe:

1. crear la base de datos,
2. crear las tablas,
3. inicializar la estructura,
4. dejarla preparada para importar el CSV.

No será necesario que el usuario cree manualmente tablas o ejecute scripts SQL.

---

### 3.11 Reglas de calidad del modelo

- No eliminar columnas desconocidas del CSV.
- Conservarlas mediante `extra_data` cuando sea necesario.
- No inventar valores que no existan en los datos originales.
- Utilizar identificadores internos estables.
- Evitar lógica SQL dentro de la interfaz.
- Centralizar el acceso a datos.
- Preparar el modelo para una futura migración a PostgreSQL.
- Mantener separadas la lógica de datos, la lógica de negocio y la presentación.
- Registrar automáticamente los eventos necesarios para calcular los KPIs disponibles.
- Cuando un KPI necesite información que todavía no se registra, mostrar `pendiente de instrumentar`.

---

## 4. Selección de columnas para usuario final

La selección de columnas deberá realizarse durante la importación y normalización del CSV.

### Prioridad alta

- nombre/título del viaje o paquete,
- destino,
- hotel/alojamiento,
- precio,
- moneda,
- duración/días/noches,
- fecha de salida,
- fecha de regreso,
- valoración,
- régimen,
- transporte/aerolínea,
- disponibilidad,
- descuento/oferta,
- descripción,
- imagen,
- URL de detalle.

### Penalizar

- ids técnicos,
- uuid/hash,
- índices,
- embeddings/vectores,
- columnas raw/debug,
- probabilidades internas,
- campos con demasiados nulos.

La app debe generar una tabla con:

- columna,
- rol detectado,
- score de utilidad para usuario,
- motivo,
- tipo,
- % nulos,
- número de valores únicos,
- campo del modelo al que fue mapeada,
- estado de importación.

---

## 5. Ventana 1 — Propuesta 7

Distribución funcional propuesta:

- Cabecera TUI.
- Hero principal.
- Buscador.
- Filtros por destino, precio, rating y, cuando exista, disponibilidad/fecha.
- KPIs rápidos del catálogo.
- Rejilla de tarjetas de producto/viaje.
- Tabla con los campos seleccionados.
- Panel opcional con el análisis del HTML.

La estructura debe poder reajustarse cuando se disponga del HTML real de la Propuesta 7.

### 5.1 Fuente de datos

La Ventana 1 deberá obtener los productos mediante la capa de servicios.

No deberá leer el CSV directamente para pintar los componentes principales.

### 5.2 Tracking mínimo

La vista deberá poder registrar:

- carga de página,
- impresiones de productos,
- búsquedas,
- uso de filtros,
- clics en productos,
- vistas de detalle,
- inicio de checkout,
- reserva.

---

## 6. Ventana 2 — Control Web

### 6.1 Métricas esenciales

- Impresiones.
- Clics.
- CTR = clics / impresiones.
- Sesiones.
- Usuarios.
- Búsquedas.
- Vistas de detalle.
- Inicio de checkout.
- Reservas.
- Conversión = reservas / sesiones.
- Click-to-booking = reservas / clics.
- Cancelaciones.
- Tasa de cancelación.
- Ingresos.
- Coste.
- ROAS = ingresos / coste.
- Ticket medio = ingresos / reservas.
- Ingreso por sesión.
- Margen.
- Pasajeros.
- Noches vendidas.
- Tiempo de respuesta/latencia.

### 6.2 Embudo recomendado

```text
Sesiones
   ↓
Búsquedas
   ↓
Vistas de detalle
   ↓
Checkout
   ↓
Reservas
```

### 6.3 KPIs específicos de turismo

- Search-to-detail.
- Detail-to-checkout.
- Checkout-to-booking.
- Ticket medio.
- Ingreso por sesión.
- Margen por reserva.
- Pasajeros por reserva.
- Noches por reserva.
- Booking lead time.
- Tasa de cancelación.
- Disponibilidad.
- Rendimiento por destino.
- Rendimiento por campaña/canal/dispositivo.
- Latencia web/API.

### 6.4 Principio de cálculo

La Ventana 2 deberá calcular los KPIs a partir de las tablas y eventos disponibles.

Ejemplo:

```text
events + sessions + bookings
            ↓
analytics_service
            ↓
KPIs / funnel / tablas / gráficos
```

No inventar resultados.

Cuando falten los datos necesarios, indicar:

```text
Pendiente de instrumentar
```

y explicar qué evento o campo necesita registrarse.

---

## 7. Esquema de tracking recomendado

El tracking deberá estar integrado con el modelo de datos.

### 7.1 Campos de evento

- `timestamp`
- `session_id`
- `user_id`
- `page`
- `event_type`
- `element_id`
- `product_id`
- `destination`
- `source`
- `medium`
- `campaign`
- `device`
- `country`
- `response_time_ms`
- `metadata`

### 7.2 Campos de negocio asociados

Cuando corresponda, los datos de negocio se almacenarán principalmente en `bookings`:

- `bookings`
- `cancellations`
- `revenue_eur`
- `cost_eur`
- `margin_eur`
- `passengers`
- `room_nights`

### 7.3 Métricas derivadas

Los siguientes valores deberán calcularse a partir de eventos y tablas siempre que sea posible:

- `impressions`
- `clicks`
- `sessions`
- `searches`
- `detail_views`
- `checkout_starts`
- `bookings`
- `cancellations`

No es obligatorio almacenar un contador agregado por cada interacción si puede obtenerse de manera fiable mediante consultas.

### 7.4 Plantilla CSV de tracking

La aplicación deberá poder generar una plantilla CSV de tracking para:

- inspección,
- pruebas,
- carga manual de datos históricos,
- demostración del esquema esperado.

---

## 8. Diseño visual TUI

### Paleta

- TUI Red: `#D40E14`
- TUI Blue: `#70CBF4`
- TUI Dark Blue: `#092A5E`
- TUI Digital Blue: `#176599`
- TUI Blue 50%: `#C2E6FA`
- TUI Blue 25%: `#E2F3FE`
- White: `#FFFFFF`

### Principios

- azul oscuro para cabeceras y texto principal,
- rojo TUI para CTA/precio/acento,
- azul claro para fondos y pills,
- tarjetas blancas con bordes suaves,
- diseño claro, de viaje y orientado a conversión.

---

## 9. Reglas de calidad

- No inventar KPIs si faltan columnas o eventos.
- Mostrar `pendiente de instrumentar` cuando una métrica no pueda calcularse.
- Evitar ejecutar código/scripts del HTML.
- Mantener separada la vista de cliente de la vista de negocio.
- Usar nombres de métricas claros y fórmulas visibles.
- La página debe ser usable con CSVs de estructura variable.
- El código debe ser modular y fácilmente ampliable.
- No acoplar Streamlit directamente a SQLite.
- Centralizar el acceso a datos.
- Mantener separadas UI, servicios y persistencia.
- Mantener trazabilidad entre producto importado y registro original.
- No eliminar información del CSV que no pueda mapearse.
- Evitar duplicar reservas o eventos por re-renderizados de Streamlit.
- Utilizar caché solo cuando no rompa la consistencia del tracking.
- Gestionar errores de importación sin bloquear toda la aplicación.
- Mostrar al usuario los registros rechazados o problemáticos cuando sea útil.

---

## 10. Entregables

La solución deberá incluir como mínimo:

```text
streamlit_app.py

database/
├── __init__.py
├── connection.py
├── models.py
├── repositories.py
└── init_db.py

services/
├── __init__.py
├── catalog_service.py
├── import_service.py
├── tracking_service.py
├── booking_service.py
└── analytics_service.py

data/
└── app.db

requirements.txt
plantilla_tracking.csv
Master Brief
```

También podrá incluirse:

```text
pages/
components/
utils/
tests/
```

si mejora la modularidad del proyecto.

---

## 11. Orden obligatorio de implementación

La implementación deberá seguir este orden:

```text
1. Analizar archivos de entrada
        ↓
2. Detectar y mapear columnas
        ↓
3. Crear modelo de datos
        ↓
4. Crear/inicializar base de datos
        ↓
5. Importar y normalizar CSV
        ↓
6. Crear repositorios
        ↓
7. Crear capa de servicios
        ↓
8. Implementar sesiones y tracking
        ↓
9. Crear Ventana 1 — Propuesta 7
        ↓
10. Conectar herramientas con el modelo
        ↓
11. Crear Ventana 2 — Control Web
        ↓
12. Conectar KPIs con datos reales
        ↓
13. Validar flujo completo
```

La interfaz no deberá construirse como una capa independiente de los datos.

Desde el inicio deberá quedar conectada al modelo generado.

---

## 12. Ejecución

Instalar dependencias:

```bash
pip install -r requirements.txt
```

Ejecutar:

```bash
streamlit run streamlit_app.py
```

En el arranque:

1. comprobar base de datos,
2. crearla si no existe,
3. crear tablas si no existen,
4. inicializar sesión,
5. cargar la aplicación.

---

## 13. Pendiente imprescindible para versión final

Para una versión final 1:1 se deberán disponer de:

- el CSV real del modelo,
- el HTML real, especialmente si representa la Propuesta 7.

Al recibirlos:

1. revisar todas las columnas reales,
2. ajustar el scoring,
3. mapear los nombres reales a campos del modelo,
4. validar la importación a `products`,
5. revisar tipos y nulos,
6. reproducir la distribución de Propuesta 7 con fidelidad,
7. adaptar los KPIs al tracking realmente implementado,
8. comprobar qué eventos pueden capturarse automáticamente,
9. validar la conexión completa entre base de datos, herramientas y vistas.

---

## 14. Criterio de aceptación final

La aplicación se considerará correctamente implementada cuando sea posible demostrar el siguiente flujo completo:

```text
CSV real
   ↓
Importación
   ↓
products
   ↓
Buscador / filtros / tarjetas
   ↓
Interacción del usuario
   ↓
sessions + events
   ↓
Reserva
   ↓
bookings
   ↓
analytics_service
   ↓
Control Web
```

La demostración deberá confirmar que:

- los productos mostrados proceden de la base de datos,
- las herramientas utilizan la capa de servicios,
- las interacciones relevantes generan tracking,
- las reservas se persisten,
- los KPIs se calculan con datos reales disponibles,
- los KPIs no disponibles se identifican como pendientes de instrumentar,
- la aplicación puede reiniciarse sin perder los datos persistidos en SQLite.
