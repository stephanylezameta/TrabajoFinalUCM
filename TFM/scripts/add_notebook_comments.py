"""
Añade comentarios explicativos en español a cada celda de código del notebook EDA_completo.ipynb.
Los comentarios son conversacionales, como si se lo explicaras a un tutor que no sabe programar.
"""
import json
from pathlib import Path

NOTEBOOK_PATH = Path("notebooks/EDA_completo.ipynb")

# Comentarios para cada celda de código (en orden)
# Cada comentario son 2-3 líneas explicando el POR QUÉ de lo que hace esa celda
COMENTARIOS = [
    # Cell 1 (index 1): import sqlite3 + setup
    (
        "# Aquí preparamos todas las herramientas necesarias para el análisis:\n"
        "# conectamos con la base de datos donde guardamos las reseñas y verificamos\n"
        "# que todo esté en orden antes de empezar a explorar los datos.\n"
    ),
    # Cell 2 (index 3): print inventario
    (
        "# Hacemos un inventario rápido de cuánta información tenemos almacenada.\n"
        "# Esto nos permite saber de un vistazo si nuestro scraping ha funcionado\n"
        "# y cuántos datos reales hemos conseguido de cada fuente.\n"
    ),
    # Cell 3 (index 6): df = query("SELECT * FROM resenas")
    (
        "# Cargamos todas las reseñas de la base de datos y calculamos estadísticas\n"
        "# básicas: cuántos destinos tenemos, de qué fuentes vienen, en qué idiomas\n"
        "# están escritas y qué tan largos son los textos de los viajeros.\n"
    ),
    # Cell 4 (index 7): fig bar chart top destinos
    (
        "# Este gráfico de barras nos muestra qué destinos tienen más reseñas.\n"
        "# Los que están arriba son los más comentados por viajeros — esto nos dice\n"
        "# dónde tenemos más información para hacer buenas recomendaciones.\n"
    ),
    # Cell 5 (index 8): fig axes fuentes
    (
        "# Aquí vemos de dónde vienen nuestras reseñas (TripAdvisor, Reddit, etc.)\n"
        "# y en qué idiomas están escritas. Nos interesa tener variedad de fuentes\n"
        "# para que las recomendaciones no dependan de una sola plataforma.\n"
    ),
    # Cell 6 (index 9): distribución longitud texto
    (
        "# Analizamos qué tan largos son los textos de las reseñas. Los textos más\n"
        "# largos suelen tener información más útil para nuestro sistema. Si la mayoría\n"
        "# son muy cortos, puede que necesitemos filtrar o buscar fuentes mejores.\n"
    ),
    # Cell 7 (index 10): otra distribución
    (
        "# Estudiamos la distribución temporal de las reseñas — cuándo fueron escritas.\n"
        "# Las reseñas más recientes reflejan mejor la realidad actual de cada destino,\n"
        "# así que nos interesa que la mayoría sean de los últimos 2-3 años.\n"
    ),
    # Cell 8 (index 11): heatmap fuente x destino
    (
        "# Este mapa de calor nos muestra qué fuentes cubren qué destinos.\n"
        "# El color intenso significa buena cobertura; los huecos en blanco nos dicen\n"
        "# dónde nos falta información — ahí es donde debemos hacer más scraping.\n"
    ),
    # Cell 9 (index 13): df_clima
    (
        "# Cargamos los datos climáticos históricos de cada destino (2022-2025).\n"
        "# El clima es uno de los factores más importantes para recomendar destinos:\n"
        "# nadie quiere ir a la playa en época de lluvias.\n"
    ),
    # Cell 10 (index 14): pivot_temp heatmap temperatura
    (
        "# Creamos un mapa de calor con la temperatura media de cada destino por mes.\n"
        "# Esto nos permite ver de un vistazo cuándo hace buen tiempo en cada sitio\n"
        "# y detectar los mejores meses para recomendar cada destino.\n"
    ),
    # Cell 11 (index 15): precipitación y sol
    (
        "# Comparamos la precipitación (lluvia) y las horas de sol entre destinos.\n"
        "# Un destino puede ser cálido pero muy lluvioso — estos datos nos ayudan\n"
        "# a hacer recomendaciones más precisas según las preferencias del viajero.\n"
    ),
    # Cell 12 (index 17): df_ind indicadores
    (
        "# Cargamos los indicadores turísticos: llegadas de turistas, pernoctaciones,\n"
        "# ingresos por turismo, etc. Estos datos vienen del INE, Eurostat y World Bank\n"
        "# y nos ayudan a entender la popularidad real y la estacionalidad de cada destino.\n"
    ),
    # Cell 13 (index 18): gráficos indicadores
    (
        "# Visualizamos los indicadores turísticos para comparar destinos entre sí.\n"
        "# Podemos ver cuáles son los más populares internacionalmente y cómo varía\n"
        "# su demanda a lo largo del año — clave para evitar masificación.\n"
    ),
    # Cell 14 (index 19): Google Trends
    (
        "# Analizamos las tendencias de búsqueda en Google para cada destino.\n"
        "# Si un destino está de moda (muchas búsquedas recientes), puede indicar\n"
        "# que será muy demandado pronto — útil para anticiparse a la demanda.\n"
    ),
    # Cell 15 (index 21): df_dest destinos_caracteristicas
    (
        "# Cargamos las características de los 39 destinos: si tienen playa, si son isla,\n"
        "# si tienen patrimonio UNESCO, su clima predominante, etc. Estas etiquetas son\n"
        "# las que usa el motor de recomendación para encontrar destinos similares.\n"
    ),
    # Cell 16 (index 23): DESTINOS_39 completitud
    (
        "# Verificamos la completitud de datos para los 39 destinos del sistema.\n"
        "# Creamos una matriz que muestra qué información tenemos de cada destino.\n"
        "# Los huecos nos indican dónde necesitamos completar datos para que el modelo funcione bien.\n"
    ),
    # Cell 17 (index 24): fig completitud visual
    (
        "# Este gráfico visual resume la cobertura de datos por destino.\n"
        "# Verde significa que tenemos datos completos; rojo indica que falta información.\n"
        "# Nuestro objetivo es que todos los 39 destinos estén en verde.\n"
    ),
    # Cell 18 (index 26): conectividad destinos
    (
        "# Analizamos la conectividad aérea de cada destino — cuántos vuelos y pasajeros\n"
        "# reciben. Un destino muy bien conectado es más fácil de recomendar porque\n"
        "# el viajero tendrá más opciones de vuelo y mejores precios.\n"
    ),
    # Cell 19 (index 28): seguridad destinos
    (
        "# Revisamos los datos de seguridad de cada destino. La seguridad es un factor\n"
        "# crítico para los viajeros — el sistema debe poder filtrar destinos según\n"
        "# el nivel de riesgo que cada persona está dispuesta a aceptar.\n"
    ),
    # Cell 20 (index 30): clima agua
    (
        "# Finalmente, exploramos la temperatura del agua de mar por destino y mes.\n"
        "# Para viajeros que buscan destinos de playa, saber si el agua está a 18°C\n"
        "# o a 28°C puede marcar la diferencia en su decisión final.\n"
    ),
]


def main():
    # Leer notebook
    with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
        nb = json.load(f)

    cells = nb['cells']
    code_cell_indices = [i for i, c in enumerate(cells) if c['cell_type'] == 'code']

    print(f"Total cells: {len(cells)}")
    print(f"Code cells: {len(code_cell_indices)}")
    print(f"Comentarios preparados: {len(COMENTARIOS)}")

    if len(code_cell_indices) != len(COMENTARIOS):
        print(f"WARNING: Mismatch! {len(code_cell_indices)} code cells vs {len(COMENTARIOS)} comments")
        # Use min to avoid index errors
        n = min(len(code_cell_indices), len(COMENTARIOS))
    else:
        n = len(code_cell_indices)

    modified = 0
    for idx in range(n):
        cell_index = code_cell_indices[idx]
        cell = cells[cell_index]
        comment = COMENTARIOS[idx]

        # Check if comment already exists (avoid duplicates)
        source = cell.get('source', [])
        if source and source[0].startswith("# Aquí") or (source and source[0].startswith("# Hac")):
            print(f"  Cell {idx+1}: ya tiene comentario, saltando")
            continue

        # Add comment at the beginning of source
        # source in ipynb is a list of strings (each line is an element)
        comment_lines = [line + "\n" for line in comment.strip().split("\n")]
        comment_lines.append("\n")  # Empty line after comment

        cell['source'] = comment_lines + source
        modified += 1
        print(f"  Cell {idx+1} (index {cell_index}): comentario añadido")

    # Save notebook
    with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)

    print(f"\n{'='*50}")
    print(f"Notebook actualizado: {modified} celdas con nuevos comentarios")
    print(f"Archivo: {NOTEBOOK_PATH}")


if __name__ == "__main__":
    main()
