"""
Analiza y unifica las bases de datos tui_recomendador.db y tui_recomendador-javier.db.

Uso:
    cd /d D:\Master\TrabajoFinalUCM\TFM
    python scripts/merge_databases.py
"""
import sys
import sqlite3
import hashlib
import uuid
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DB1_PATH = "data/tui_recomendador.db"
DB2_PATH = "data/tui_recomendador-javier.db"


def analizar_db(path: str) -> dict:
    """Analiza una BD y retorna estadísticas."""
    conn = sqlite3.connect(path)
    
    total = conn.execute("SELECT COUNT(*) FROM resenas").fetchone()[0]
    fuentes = conn.execute("SELECT fuente, COUNT(*) FROM resenas GROUP BY fuente ORDER BY COUNT(*) DESC").fetchall()
    destinos = conn.execute("SELECT destino_nombre, COUNT(*) FROM resenas GROUP BY destino_nombre ORDER BY COUNT(*) DESC LIMIT 15").fetchall()
    idiomas = conn.execute("SELECT idioma, COUNT(*) FROM resenas GROUP BY idioma ORDER BY COUNT(*) DESC LIMIT 10").fetchall()
    
    textos = conn.execute("SELECT texto_original FROM resenas WHERE texto_original IS NOT NULL").fetchall()
    hashes = set()
    for (t,) in textos:
        if t and len(t.strip()) > 10:
            hashes.add(hashlib.md5(t.strip().lower().encode()).hexdigest())
    
    conn.close()
    return {
        "total": total,
        "fuentes": fuentes,
        "destinos": destinos,
        "idiomas": idiomas,
        "hashes": hashes,
        "textos_unicos": len(hashes),
    }


def unificar_databases(db1_path: str, db2_path: str):
    """Copia reseñas únicas de db2 a db1 (sin duplicados)."""
    conn1 = sqlite3.connect(db1_path)
    conn2 = sqlite3.connect(db2_path)
    
    # Cargar hashes de DB1
    textos1 = conn1.execute("SELECT texto_original FROM resenas WHERE texto_original IS NOT NULL").fetchall()
    hashes1 = set()
    for (t,) in textos1:
        if t and len(t.strip()) > 10:
            hashes1.add(hashlib.md5(t.strip().lower().encode()).hexdigest())
    
    # Leer todas las reseñas de DB2
    resenas2 = conn2.execute("""
        SELECT destino_nombre, fuente, texto_original, idioma, puntuacion, 
               fecha_publicacion, url_fuente, fecha_extraccion 
        FROM resenas WHERE texto_original IS NOT NULL
    """).fetchall()
    
    # Insertar solo las que no existen en DB1
    insertadas = 0
    for row in resenas2:
        destino, fuente, texto, idioma, puntuacion, fecha_pub, url, fecha_ext = row
        if not texto or len(texto.strip()) <= 10:
            continue
        h = hashlib.md5(texto.strip().lower().encode()).hexdigest()
        if h in hashes1:
            continue
        hashes1.add(h)
        
        try:
            conn1.execute(
                """INSERT INTO resenas (id_resena, destino_nombre, fuente, texto_original,
                   idioma, puntuacion, fecha_publicacion, url_fuente, fecha_extraccion)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), destino, fuente, texto, idioma, puntuacion, fecha_pub, url, fecha_ext)
            )
            insertadas += 1
        except Exception:
            pass
    
    conn1.commit()
    conn1.close()
    conn2.close()
    return insertadas


def main():
    print(f"\n{'='*70}")
    print(f"  ANÁLISIS Y COMPARACIÓN DE BASES DE DATOS")
    print(f"{'='*70}")
    
    # Analizar DB1
    print(f"\n{'─'*70}")
    print(f"  tui_recomendador.db")
    print(f"{'─'*70}")
    stats1 = analizar_db(DB1_PATH)
    print(f"  Total registros: {stats1['total']}")
    print(f"  Textos únicos: {stats1['textos_unicos']}")
    print(f"\n  Por fuente:")
    for f, n in stats1['fuentes']:
        print(f"    {f}: {n}")
    print(f"\n  Top 10 destinos:")
    for d, n in stats1['destinos'][:10]:
        print(f"    {d}: {n}")
    print(f"\n  Por idioma:")
    for i, n in stats1['idiomas']:
        print(f"    {i}: {n}")
    
    # Analizar DB2
    print(f"\n{'─'*70}")
    print(f"  tui_recomendador-javier.db")
    print(f"{'─'*70}")
    stats2 = analizar_db(DB2_PATH)
    print(f"  Total registros: {stats2['total']}")
    print(f"  Textos únicos: {stats2['textos_unicos']}")
    print(f"\n  Por fuente:")
    for f, n in stats2['fuentes']:
        print(f"    {f}: {n}")
    print(f"\n  Top 10 destinos:")
    for d, n in stats2['destinos'][:10]:
        print(f"    {d}: {n}")
    print(f"\n  Por idioma:")
    for i, n in stats2['idiomas']:
        print(f"    {i}: {n}")
    
    # Comparación
    print(f"\n{'─'*70}")
    print(f"  COMPARACIÓN Y CRUCE")
    print(f"{'─'*70}")
    
    hashes1 = stats1['hashes']
    hashes2 = stats2['hashes']
    comunes = hashes1 & hashes2
    solo_db1 = hashes1 - hashes2
    solo_db2 = hashes2 - hashes1
    union = hashes1 | hashes2
    
    print(f"  Únicos en tui_recomendador.db:        {len(hashes1)}")
    print(f"  Únicos en tui_recomendador-javier.db: {len(hashes2)}")
    print(f"  En COMÚN (duplicados):                {len(comunes)}")
    print(f"  Solo en tui_recomendador.db:          {len(solo_db1)}")
    print(f"  Solo en javier.db:                    {len(solo_db2)}")
    print(f"  UNIÓN (total sin duplicados):         {len(union)}")
    
    if min(len(hashes1), len(hashes2)) > 0:
        print(f"  % de cruce:                           {len(comunes)/min(len(hashes1),len(hashes2))*100:.1f}%")
    
    # Preguntar si unificar
    print(f"\n{'─'*70}")
    print(f"  RESUMEN")
    print(f"{'─'*70}")
    print(f"  Si unificamos → {len(union)} reseñas únicas")
    print(f"  Se ganarían {len(solo_db2)} reseñas nuevas de javier.db")
    print(f"  Se eliminarían {len(comunes)} duplicados")
    
    respuesta = input(f"\n  ¿Unificar javier.db → tui_recomendador.db? (s/n): ").strip().lower()
    if respuesta == "s":
        insertadas = unificar_databases(DB1_PATH, DB2_PATH)
        total_final = sqlite3.connect(DB1_PATH).execute("SELECT COUNT(*) FROM resenas").fetchone()[0]
        print(f"\n  ✅ Unificación completada:")
        print(f"     Reseñas nuevas insertadas: {insertadas}")
        print(f"     Total final en tui_recomendador.db: {total_final}")
    else:
        print(f"\n  Cancelado. No se modificó ninguna BD.")
    
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
