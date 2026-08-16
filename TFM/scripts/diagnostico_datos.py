"""
Script de diagnóstico completo de las bases de datos del proyecto TUI Recomendador.

Ejecutar con:
    cd /d D:\\Master\\TrabajoFinalUCM\\TFM && python scripts/diagnostico_datos.py

Revisa TODAS las tablas de data/tui_recomendador.db y data/sample_tui.db
e imprime un informe completo de estructura, contenido y cobertura de destinos.
"""

import sqlite3
import sys
import os
from pathlib import Path

# Asegurar salida UTF-8 (necesario en Windows al redirigir)
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PRINCIPAL = BASE_DIR / "data" / "tui_recomendador.db"
DB_SAMPLE = BASE_DIR / "data" / "sample_tui.db"

DESTINOS_ESPERADOS = [
    "Mallorca", "Tenerife", "Ibiza", "Costa del Sol", "Barcelona",
    "Madrid", "Málaga", "Sevilla", "Valencia", "Gran Canaria",
    "Alicante", "Bilbao", "San Sebastián", "Córdoba", "Granada",
    "Cádiz", "Fuerteventura", "Lanzarote", "Menorca", "Antalya",
    "Rodas", "Santorini", "Hurghada", "Punta Cana", "Cancún",
    "Riviera Maya", "Dubái", "Maldivas", "Bali", "Phuket",
    "Marrakech", "Cabo Verde", "Split", "Creta", "Sicilia",
    "Cerdeña", "Costa Amalfitana", "Algarve", "Túnez"
]

# Campos que pueden contener nombre de destino
CAMPOS_DESTINO = ["destino_nombre", "destination", "destino", "nombre"]


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def separador(titulo, char="=", ancho=80):
    print(f"\n{char * ancho}")
    print(f"  {titulo}")
    print(f"{char * ancho}")


def sub_separador(titulo, char="-", ancho=60):
    print(f"\n  {char * ancho}")
    print(f"  {titulo}")
    print(f"  {char * ancho}")


def get_tablas(cursor):
    """Obtiene la lista de tablas en la BD."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [row[0] for row in cursor.fetchall()]


def get_columnas(cursor, tabla):
    """Obtiene la lista de columnas de una tabla."""
    cursor.execute(f"PRAGMA table_info('{tabla}')")
    return [row[1] for row in cursor.fetchall()]


def get_total_registros(cursor, tabla):
    """Obtiene el total de registros de una tabla."""
    cursor.execute(f"SELECT COUNT(*) FROM '{tabla}'")
    return cursor.fetchone()[0]


def get_nulls_por_columna(cursor, tabla, columnas):
    """Obtiene la cantidad de NULLs por columna."""
    nulls = {}
    for col in columnas:
        cursor.execute(f"SELECT COUNT(*) FROM '{tabla}' WHERE \"{col}\" IS NULL")
        nulls[col] = cursor.fetchone()[0]
    return nulls


def encontrar_campo_destino(columnas):
    """Busca cuál campo de destino existe en la lista de columnas."""
    for campo in CAMPOS_DESTINO:
        if campo in columnas:
            return campo
    return None


def analizar_cobertura_destinos(cursor, tabla, campo_destino):
    """Analiza qué destinos esperados tienen datos."""
    cursor.execute(f"SELECT DISTINCT \"{campo_destino}\" FROM '{tabla}'")
    destinos_en_bd = set(row[0] for row in cursor.fetchall() if row[0])
    
    presentes = []
    ausentes = []
    for d in DESTINOS_ESPERADOS:
        if d in destinos_en_bd:
            presentes.append(d)
        else:
            ausentes.append(d)
    
    return presentes, ausentes, destinos_en_bd


def print_tabla_destinos(presentes, ausentes):
    """Imprime la cobertura de destinos formateada."""
    print(f"\n    Destinos CON datos ({len(presentes)}/{len(DESTINOS_ESPERADOS)}):")
    for i in range(0, len(presentes), 4):
        grupo = presentes[i:i+4]
        print(f"      ✓ {', '.join(grupo)}")
    
    if ausentes:
        print(f"\n    Destinos SIN datos ({len(ausentes)}/{len(DESTINOS_ESPERADOS)}):")
        for i in range(0, len(ausentes), 4):
            grupo = ausentes[i:i+4]
            print(f"      ✗ {', '.join(grupo)}")


def registros_por_campo(cursor, tabla, campo):
    """Cuenta registros agrupados por un campo."""
    cursor.execute(f"SELECT \"{campo}\", COUNT(*) FROM '{tabla}' GROUP BY \"{campo}\" ORDER BY COUNT(*) DESC")
    return cursor.fetchall()


# ============================================================
# ANÁLISIS ESPECÍFICOS POR TABLA
# ============================================================

def analizar_resenas(cursor, tabla="resenas"):
    """Análisis específico: reseñas por destino."""
    sub_separador("4. Tabla 'resenas': registros por destino")
    columnas = get_columnas(cursor, tabla)
    campo = encontrar_campo_destino(columnas)
    if not campo:
        print("    ⚠ No se encontró campo de destino en la tabla 'resenas'")
        print(f"    Columnas disponibles: {columnas}")
        return
    
    datos = registros_por_campo(cursor, tabla, campo)
    print(f"    Campo de destino: '{campo}'")
    print(f"    {'Destino':<25} {'Registros':>10}")
    print(f"    {'─'*25} {'─'*10}")
    for destino, count in datos:
        print(f"    {str(destino):<25} {count:>10}")


def analizar_indicadores_destino(cursor, tabla="indicadores_destino"):
    """Análisis específico: indicadores por destino y tipo."""
    sub_separador("5. Tabla 'indicadores_destino': registros por destino y tipo_indicador")
    columnas = get_columnas(cursor, tabla)
    campo = encontrar_campo_destino(columnas)
    if not campo:
        print("    ⚠ No se encontró campo de destino en 'indicadores_destino'")
        print(f"    Columnas disponibles: {columnas}")
        return
    
    # Por destino
    datos_destino = registros_por_campo(cursor, tabla, campo)
    print(f"\n    Por destino (campo: '{campo}'):")
    print(f"    {'Destino':<25} {'Registros':>10}")
    print(f"    {'─'*25} {'─'*10}")
    for destino, count in datos_destino:
        print(f"    {str(destino):<25} {count:>10}")
    
    # Por tipo_indicador
    if "tipo_indicador" in columnas:
        datos_tipo = registros_por_campo(cursor, tabla, "tipo_indicador")
        print(f"\n    Por tipo_indicador:")
        print(f"    {'Tipo':<35} {'Registros':>10}")
        print(f"    {'─'*35} {'─'*10}")
        for tipo, count in datos_tipo:
            print(f"    {str(tipo):<35} {count:>10}")
    else:
        print("    ⚠ No existe columna 'tipo_indicador'")
        print(f"    Columnas disponibles: {columnas}")


def analizar_clima_destinos(cursor, tabla="clima_destinos"):
    """Análisis específico: clima por destino."""
    sub_separador("6. Tabla 'clima_destinos': registros por destino")
    columnas = get_columnas(cursor, tabla)
    campo = encontrar_campo_destino(columnas)
    if not campo:
        print("    ⚠ No se encontró campo de destino en 'clima_destinos'")
        print(f"    Columnas disponibles: {columnas}")
        return
    
    datos = registros_por_campo(cursor, tabla, campo)
    print(f"    Campo de destino: '{campo}'")
    print(f"    {'Destino':<25} {'Registros':>10}")
    print(f"    {'─'*25} {'─'*10}")
    for destino, count in datos:
        print(f"    {str(destino):<25} {count:>10}")


def analizar_experiencias(cursor, tabla="experiencias"):
    """Análisis específico: experiencias por destino (campo destination)."""
    sub_separador("7. Tabla 'experiencias': registros por destino (destination)")
    columnas = get_columnas(cursor, tabla)
    campo = encontrar_campo_destino(columnas)
    if not campo:
        print("    ⚠ No se encontró campo de destino en 'experiencias'")
        print(f"    Columnas disponibles: {columnas}")
        return
    
    datos = registros_por_campo(cursor, tabla, campo)
    print(f"    Campo de destino: '{campo}'")
    print(f"    {'Destino':<25} {'Registros':>10}")
    print(f"    {'─'*25} {'─'*10}")
    for destino, count in datos:
        print(f"    {str(destino):<25} {count:>10}")


def analizar_customer_bookings(cursor, tabla="customer_bookings"):
    """Análisis específico: bookings totales y top 10 experience_id."""
    sub_separador("8. Tabla 'customer_bookings': total y top 10 experience_id")
    columnas = get_columnas(cursor, tabla)
    total = get_total_registros(cursor, tabla)
    print(f"    Total registros: {total:,}")
    
    if "experience_id" in columnas:
        cursor.execute(f"SELECT \"experience_id\", COUNT(*) FROM '{tabla}' GROUP BY \"experience_id\" ORDER BY COUNT(*) DESC LIMIT 10")
        datos = cursor.fetchall()
        print(f"\n    Top 10 experience_id:")
        print(f"    {'experience_id':<20} {'Registros':>10} {'%':>8}")
        print(f"    {'─'*20} {'─'*10} {'─'*8}")
        for exp_id, count in datos:
            pct = (count / total * 100) if total > 0 else 0
            print(f"    {str(exp_id):<20} {count:>10} {pct:>7.1f}%")
    else:
        print("    ⚠ No existe columna 'experience_id'")
        print(f"    Columnas disponibles: {columnas}")


def analizar_reviews_dataset(cursor, tabla="reviews_dataset"):
    """Análisis específico: reviews totales y distribución por rating."""
    sub_separador("9. Tabla 'reviews_dataset': total y distribución por rating")
    columnas = get_columnas(cursor, tabla)
    total = get_total_registros(cursor, tabla)
    print(f"    Total registros: {total:,}")
    
    if "rating" in columnas:
        datos = registros_por_campo(cursor, tabla, "rating")
        print(f"\n    Distribución por rating:")
        print(f"    {'Rating':<10} {'Registros':>10} {'%':>8}")
        print(f"    {'─'*10} {'─'*10} {'─'*8}")
        for rating, count in sorted(datos, key=lambda x: x[0] if x[0] else 0):
            pct = (count / total * 100) if total > 0 else 0
            print(f"    {str(rating):<10} {count:>10} {pct:>7.1f}%")
    else:
        print("    ⚠ No existe columna 'rating'")
        print(f"    Columnas disponibles: {columnas}")


def analizar_destinos_caracteristicas(cursor, tabla="destinos_caracteristicas"):
    """Análisis específico: cobertura de los 39 destinos esperados."""
    sub_separador("10. Tabla 'destinos_caracteristicas': cobertura de 39 destinos")
    columnas = get_columnas(cursor, tabla)
    campo = encontrar_campo_destino(columnas)
    if not campo:
        print("    ⚠ No se encontró campo de destino en 'destinos_caracteristicas'")
        print(f"    Columnas disponibles: {columnas}")
        return
    
    presentes, ausentes, _ = analizar_cobertura_destinos(cursor, tabla, campo)
    print(f"    Campo de destino: '{campo}'")
    print_tabla_destinos(presentes, ausentes)


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

def diagnosticar_bd(db_path, nombre_bd):
    """Ejecuta diagnóstico completo sobre una base de datos."""
    separador(f"BASE DE DATOS: {nombre_bd}", "█", 80)
    print(f"  Ruta: {db_path}")
    
    if not db_path.exists():
        print(f"  ✗ ERROR: El archivo no existe!")
        return {}
    
    file_size = db_path.stat().st_size
    print(f"  Tamaño: {file_size / (1024*1024):.2f} MB")
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # 1. Tablas existentes
    tablas = get_tablas(cursor)
    sub_separador(f"1. Tablas encontradas ({len(tablas)})")
    for i, tabla in enumerate(tablas, 1):
        total = get_total_registros(cursor, tabla)
        print(f"    {i:>2}. {tabla:<35} ({total:,} registros)")
    
    # 2. Detalle por tabla
    sub_separador("2. Detalle por tabla: columnas y NULLs")
    resumen_tablas = {}
    
    for tabla in tablas:
        columnas = get_columnas(cursor, tabla)
        total = get_total_registros(cursor, tabla)
        nulls = get_nulls_por_columna(cursor, tabla, columnas)
        
        resumen_tablas[tabla] = {
            "total": total,
            "columnas": columnas,
            "nulls": nulls
        }
        
        print(f"\n    ┌─ Tabla: {tabla} ({total:,} registros, {len(columnas)} columnas)")
        print(f"    │  {'Columna':<30} {'NULLs':>8} {'% NULL':>8}")
        print(f"    │  {'─'*30} {'─'*8} {'─'*8}")
        for col in columnas:
            n = nulls[col]
            pct = (n / total * 100) if total > 0 else 0
            indicador = "⚠" if pct > 50 else " "
            print(f"    │  {col:<30} {n:>8} {pct:>7.1f}% {indicador}")
        print(f"    └{'─'*60}")
    
    # 3. Cobertura de destinos en tablas con campo destino
    sub_separador("3. Cobertura de destinos (39 esperados) en tablas con campo destino")
    for tabla in tablas:
        columnas = resumen_tablas[tabla]["columnas"]
        campo = encontrar_campo_destino(columnas)
        if campo:
            print(f"\n    Tabla: {tabla} (campo: '{campo}')")
            presentes, ausentes, _ = analizar_cobertura_destinos(cursor, tabla, campo)
            print_tabla_destinos(presentes, ausentes)
    
    # 4-10. Análisis específicos (solo si la tabla existe)
    if "resenas" in tablas:
        analizar_resenas(cursor)
    else:
        sub_separador("4. Tabla 'resenas': NO EXISTE en esta BD")
    
    if "indicadores_destino" in tablas:
        analizar_indicadores_destino(cursor)
    else:
        sub_separador("5. Tabla 'indicadores_destino': NO EXISTE en esta BD")
    
    if "clima_destinos" in tablas:
        analizar_clima_destinos(cursor)
    else:
        sub_separador("6. Tabla 'clima_destinos': NO EXISTE en esta BD")
    
    if "experiencias" in tablas:
        analizar_experiencias(cursor)
    else:
        sub_separador("7. Tabla 'experiencias': NO EXISTE en esta BD")
    
    if "customer_bookings" in tablas:
        analizar_customer_bookings(cursor)
    else:
        sub_separador("8. Tabla 'customer_bookings': NO EXISTE en esta BD")
    
    if "reviews_dataset" in tablas:
        analizar_reviews_dataset(cursor)
    else:
        sub_separador("9. Tabla 'reviews_dataset': NO EXISTE en esta BD")
    
    if "destinos_caracteristicas" in tablas:
        analizar_destinos_caracteristicas(cursor)
    else:
        sub_separador("10. Tabla 'destinos_caracteristicas': NO EXISTE en esta BD")
    
    conn.close()
    return resumen_tablas


def imprimir_resumen_final(resumen_principal, resumen_sample):
    """Imprime el resumen final con indicadores de estado."""
    separador("RESUMEN FINAL", "★", 80)
    
    print("\n  Leyenda:")
    print("    ✓  = Tabla con datos completos (>0 registros, sin NULLs críticos)")
    print("    ⚠  = Tabla con datos parciales (tiene registros pero con NULLs >50% en alguna columna)")
    print("    ✗  = Tabla vacía o inexistente")
    print()
    
    todas_tablas = set()
    if resumen_principal:
        todas_tablas.update(resumen_principal.keys())
    if resumen_sample:
        todas_tablas.update(resumen_sample.keys())
    
    def estado_tabla(resumen, tabla):
        if not resumen or tabla not in resumen:
            return "✗", "No existe"
        info = resumen[tabla]
        if info["total"] == 0:
            return "✗", "Vacía"
        # Chequear si alguna columna tiene >50% NULLs
        tiene_nulls_criticos = False
        for col, n in info["nulls"].items():
            if info["total"] > 0 and (n / info["total"]) > 0.5:
                tiene_nulls_criticos = True
                break
        if tiene_nulls_criticos:
            return "⚠", f"{info['total']:,} reg. (NULLs >50%)"
        return "✓", f"{info['total']:,} registros"
    
    print(f"  {'Tabla':<30} {'tui_recomendador.db':<30} {'sample_tui.db':<30}")
    print(f"  {'─'*30} {'─'*30} {'─'*30}")
    
    for tabla in sorted(todas_tablas):
        est1, desc1 = estado_tabla(resumen_principal, tabla)
        est2, desc2 = estado_tabla(resumen_sample, tabla)
        print(f"  {tabla:<30} {est1} {desc1:<27} {est2} {desc2:<27}")


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════════════════════════════════╗")
    print("║         DIAGNÓSTICO COMPLETO DE BASES DE DATOS - TUI RECOMENDADOR           ║")
    print("╠══════════════════════════════════════════════════════════════════════════════╣")
    print(f"║  Directorio base: {str(BASE_DIR):<57} ║")
    print(f"║  BD Principal:    {str(DB_PRINCIPAL.name):<57} ║")
    print(f"║  BD Sample:       {str(DB_SAMPLE.name):<57} ║")
    print(f"║  Destinos esperados: {len(DESTINOS_ESPERADOS):<54} ║")
    print("╚══════════════════════════════════════════════════════════════════════════════╝")
    
    # Diagnosticar BD principal
    resumen_principal = diagnosticar_bd(DB_PRINCIPAL, "tui_recomendador.db")
    
    # Diagnosticar BD sample
    resumen_sample = diagnosticar_bd(DB_SAMPLE, "sample_tui.db")
    
    # Resumen final
    imprimir_resumen_final(resumen_principal, resumen_sample)
    
    print("\n" + "═" * 80)
    print("  FIN DEL DIAGNÓSTICO")
    print("═" * 80 + "\n")
