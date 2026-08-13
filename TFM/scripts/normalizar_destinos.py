"""
Normalización de nombres de destinos y completar cobertura.

1. Mapea variantes de nombres a los 39 destinos estándar
2. Completa seguridad_destinos para todos los 39
3. Completa conectividad_destinos para todos los 39
4. Elimina registros que no mapean a ningún destino estándar

Ejecución:
    cd /d D:\\Master\\TrabajoFinalUCM\\TFM
    python scripts/normalizar_destinos.py
"""
import sys
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "tui_recomendador.db"

# Los 39 destinos ESTÁNDAR (con tildes correctas)
DESTINOS_39 = [
    "Mallorca", "Tenerife", "Ibiza", "Costa del Sol", "Barcelona",
    "Madrid", "Málaga", "Sevilla", "Valencia", "Gran Canaria",
    "Alicante", "Bilbao", "San Sebastián", "Córdoba", "Granada",
    "Cádiz", "Fuerteventura", "Lanzarote", "Menorca", "Antalya",
    "Rodas", "Santorini", "Hurghada", "Punta Cana", "Cancún",
    "Riviera Maya", "Dubái", "Maldivas", "Bali", "Phuket",
    "Marrakech", "Cabo Verde", "Split", "Creta", "Sicilia",
    "Cerdeña", "Costa Amalfitana", "Algarve", "Túnez",
]

# Mapeo EXHAUSTIVO de variantes → destino estándar
MAPEO_NOMBRES = {
    # Sin tildes → con tildes
    "Malaga": "Málaga", "Málaga": "Málaga",
    "Cordoba": "Córdoba", "Córdoba": "Córdoba",
    "Cadiz": "Cádiz", "Cádiz": "Cádiz",
    "Cancun": "Cancún", "Cancún": "Cancún",
    "Dubai": "Dubái", "Dubái": "Dubái",
    "San Sebastian": "San Sebastián", "San Sebastián": "San Sebastián",
    "Cerdeña": "Cerdeña", "Cerdena": "Cerdeña", "Sardinia": "Cerdeña",
    "Tunez": "Túnez", "Túnez": "Túnez", "Tunisia": "Túnez",
    # Variantes con sufijos de búsqueda
    "Alicante turismo": "Alicante",
    "Valencia turismo": "Valencia",
    "Bilbao turismo": "Bilbao",
    "San Sebastián turismo": "San Sebastián",
    "Córdoba turismo": "Córdoba",
    "Cádiz turismo": "Cádiz",
    "Granada turismo": "Granada",
    "Sevilla turismo": "Sevilla",
    "Madrid turismo": "Madrid",
    "Barcelona turismo": "Barcelona",
    "Málaga turismo": "Málaga",
    "Mallorca turismo": "Mallorca",
    "Tenerife turismo": "Tenerife",
    "Ibiza turismo": "Ibiza",
    "Menorca turismo": "Menorca",
    "Fuerteventura turismo": "Fuerteventura",
    "Lanzarote turismo": "Lanzarote",
    "Gran Canaria turismo": "Gran Canaria",
    # Variantes con "tourism" / "holidays" / "travel"
    "Split Croatia tourism": "Split",
    "Cerdeña Sardinia tourism": "Cerdeña",
    "Costa Amalfitana tourism": "Costa Amalfitana",
    "Algarve Portugal tourism": "Algarve",
    "Túnez Tunisia tourism": "Túnez",
    "Cabo Verde tourism": "Cabo Verde",
    "Dubái Dubai tourism": "Dubái",
    "Marrakech tourism": "Marrakech",
    "Maldivas Maldives tourism": "Maldivas",
    "Phuket Thailand tourism": "Phuket",
    "Bali Indonesia tourism": "Bali",
    "Creta Crete tourism": "Creta",
    "Sicilia Sicily tourism": "Sicilia",
    "Hurghada tourism": "Hurghada",
    "Punta Cana tourism": "Punta Cana",
    "Cancún tourism": "Cancún",
    "Riviera Maya tourism": "Riviera Maya",
    "Santorini tourism": "Santorini",
    "Rodas tourism": "Rodas",
    "Antalya tourism": "Antalya",
    # Variantes de escritura
    "València": "Valencia",
    "Eivissa": "Ibiza",
    "Palma de Mallorca": "Mallorca",
    "Palma": "Mallorca",
    "Playa del Carmen": "Riviera Maya",
    "Tulum": "Riviera Maya",
    "Abu Dhabi": "Dubái",
    "Agadir": "Marrakech",
    "Alanya": "Antalya",
    "Benalmádena": "Costa del Sol",
    "Fuengirola": "Costa del Sol",
    "Torremolinos": "Costa del Sol",
    "Marbella": "Costa del Sol",
    "Nerja": "Costa del Sol",
    "Puerto de la Cruz": "Tenerife",
    "Santa Cruz de Tenerife": "Tenerife",
    "Las Palmas": "Gran Canaria",
    "Palmas de Gran Canaria": "Gran Canaria",
    "Rhodes": "Rodas",
    "Crete": "Creta",
    "Sicily": "Sicilia",
    "Sardinia": "Cerdeña",
    "Amalfi Coast": "Costa Amalfitana",
    "Cape Verde": "Cabo Verde",
    "Maldives": "Maldivas",
    "Marrakesh": "Marrakech",
    "Marrakesch": "Marrakech",
    # Nombres exactos (para que no se pierdan)
    "Mallorca": "Mallorca", "Tenerife": "Tenerife", "Ibiza": "Ibiza",
    "Costa del Sol": "Costa del Sol", "Barcelona": "Barcelona",
    "Madrid": "Madrid", "Sevilla": "Sevilla", "Valencia": "Valencia",
    "Gran Canaria": "Gran Canaria", "Alicante": "Alicante",
    "Bilbao": "Bilbao", "Granada": "Granada",
    "Fuerteventura": "Fuerteventura", "Lanzarote": "Lanzarote",
    "Menorca": "Menorca", "Antalya": "Antalya", "Rodas": "Rodas",
    "Santorini": "Santorini", "Hurghada": "Hurghada",
    "Punta Cana": "Punta Cana", "Riviera Maya": "Riviera Maya",
    "Maldivas": "Maldivas", "Bali": "Bali", "Phuket": "Phuket",
    "Marrakech": "Marrakech", "Cabo Verde": "Cabo Verde",
    "Split": "Split", "Creta": "Creta", "Sicilia": "Sicilia",
    "Costa Amalfitana": "Costa Amalfitana", "Algarve": "Algarve",
}

# ISO → datos de seguridad por país
SEGURIDAD_POR_ISO = {
    "ESP": {"pais": "España", "camas": 2.97, "homicidios": 0.63, "nivel": "muy_seguro"},
    "TUR": {"pais": "Turquía", "camas": 3.04, "homicidios": 2.61, "nivel": "seguro"},
    "GRC": {"pais": "Grecia", "camas": 4.21, "homicidios": 0.85, "nivel": "muy_seguro"},
    "EGY": {"pais": "Egipto", "camas": 1.43, "homicidios": 2.51, "nivel": "seguro"},
    "DOM": {"pais": "Rep. Dominicana", "camas": 1.6, "homicidios": 12.2, "nivel": "precaucion"},
    "MEX": {"pais": "México", "camas": 0.98, "homicidios": 25.6, "nivel": "precaucion"},
    "ARE": {"pais": "Emiratos Árabes", "camas": 1.36, "homicidios": 0.49, "nivel": "muy_seguro"},
    "MDV": {"pais": "Maldivas", "camas": 4.3, "homicidios": 0.8, "nivel": "muy_seguro"},
    "IDN": {"pais": "Indonesia", "camas": 1.04, "homicidios": 0.4, "nivel": "muy_seguro"},
    "THA": {"pais": "Tailandia", "camas": 2.1, "homicidios": 2.9, "nivel": "seguro"},
    "MAR": {"pais": "Marruecos", "camas": 1.0, "homicidios": 1.24, "nivel": "muy_seguro"},
    "CPV": {"pais": "Cabo Verde", "camas": 2.1, "homicidios": 5.6, "nivel": "moderado"},
    "HRV": {"pais": "Croacia", "camas": 5.5, "homicidios": 0.87, "nivel": "muy_seguro"},
    "ITA": {"pais": "Italia", "camas": 3.14, "homicidios": 0.53, "nivel": "muy_seguro"},
    "PRT": {"pais": "Portugal", "camas": 3.5, "homicidios": 0.78, "nivel": "muy_seguro"},
    "TUN": {"pais": "Túnez", "camas": 2.3, "homicidios": 3.0, "nivel": "seguro"},
}

DESTINO_A_ISO = {
    "Mallorca": "ESP", "Tenerife": "ESP", "Ibiza": "ESP", "Costa del Sol": "ESP",
    "Barcelona": "ESP", "Madrid": "ESP", "Málaga": "ESP", "Sevilla": "ESP",
    "Valencia": "ESP", "Gran Canaria": "ESP", "Alicante": "ESP", "Bilbao": "ESP",
    "San Sebastián": "ESP", "Córdoba": "ESP", "Granada": "ESP", "Cádiz": "ESP",
    "Fuerteventura": "ESP", "Lanzarote": "ESP", "Menorca": "ESP",
    "Antalya": "TUR", "Rodas": "GRC", "Santorini": "GRC", "Creta": "GRC",
    "Hurghada": "EGY", "Punta Cana": "DOM", "Cancún": "MEX", "Riviera Maya": "MEX",
    "Dubái": "ARE", "Maldivas": "MDV", "Bali": "IDN", "Phuket": "THA",
    "Marrakech": "MAR", "Cabo Verde": "CPV", "Split": "HRV",
    "Sicilia": "ITA", "Cerdeña": "ITA", "Costa Amalfitana": "ITA",
    "Algarve": "PRT", "Túnez": "TUN",
}


def normalizar_tabla(conn, tabla, col_destino):
    """Normaliza nombres de destinos en una tabla. Retorna (actualizados, eliminados)."""
    try:
        df = pd.read_sql(f"SELECT DISTINCT [{col_destino}] FROM [{tabla}]", conn)
        nombres_actuales = df[col_destino].dropna().tolist()
    except Exception as e:
        print(f"    Error leyendo {tabla}: {e}")
        return 0, 0

    actualizados = 0
    for nombre in nombres_actuales:
        if nombre in DESTINOS_39:
            continue  # Ya está correcto
        
        nuevo_nombre = MAPEO_NOMBRES.get(nombre)
        if nuevo_nombre and nuevo_nombre in DESTINOS_39:
            cursor = conn.execute(
                f"UPDATE [{tabla}] SET [{col_destino}] = ? WHERE [{col_destino}] = ?",
                (nuevo_nombre, nombre)
            )
            actualizados += cursor.rowcount

    conn.commit()

    # Contar cuántos NO mapean a ningún destino estándar
    df_post = pd.read_sql(f"SELECT [{col_destino}], COUNT(*) as n FROM [{tabla}] GROUP BY [{col_destino}]", conn)
    no_mapeados = df_post[~df_post[col_destino].isin(DESTINOS_39)]
    eliminados = 0

    # NO eliminar — solo reportar los que no mapean
    if len(no_mapeados) > 0:
        total_no_map = no_mapeados['n'].sum()
        print(f"    ⚠ {len(no_mapeados)} nombres no mapeados ({total_no_map} registros) — se conservan")
        if len(no_mapeados) <= 10:
            for _, row in no_mapeados.iterrows():
                print(f"      - \"{row[col_destino]}\" ({row['n']} reg)")

    return actualizados, eliminados


def completar_seguridad(conn):
    """Asegura que los 39 destinos tengan datos de seguridad."""
    insertados = 0
    
    # Verificar tabla existe
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seguridad_destinos (
            id TEXT PRIMARY KEY,
            destino_nombre TEXT NOT NULL,
            pais TEXT NOT NULL,
            iso TEXT NOT NULL,
            camas_hospital_1000hab REAL,
            tasa_homicidios_100mil REAL,
            nivel_seguridad TEXT,
            fecha_extraccion TEXT NOT NULL,
            UNIQUE(destino_nombre)
        )
    """)
    conn.commit()

    for destino in DESTINOS_39:
        # Verificar si ya existe
        existe = conn.execute(
            "SELECT 1 FROM seguridad_destinos WHERE destino_nombre = ?", (destino,)
        ).fetchone()
        
        if existe:
            continue

        iso = DESTINO_A_ISO.get(destino)
        if not iso or iso not in SEGURIDAD_POR_ISO:
            continue

        datos = SEGURIDAD_POR_ISO[iso]
        id_reg = hashlib.md5(f"seguridad|{destino}".encode()).hexdigest()[:32]

        conn.execute("""
            INSERT OR IGNORE INTO seguridad_destinos
            (id, destino_nombre, pais, iso, camas_hospital_1000hab,
             tasa_homicidios_100mil, nivel_seguridad, fecha_extraccion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            id_reg, destino, datos["pais"], iso,
            datos["camas"], datos["homicidios"], datos["nivel"],
            datetime.now().isoformat()
        ))
        insertados += 1

    conn.commit()
    return insertados


def completar_conectividad(conn):
    """Asegura que los 39 destinos tengan entrada en conectividad (0 si no hay datos)."""
    insertados = 0

    conn.execute("""
        CREATE TABLE IF NOT EXISTS conectividad_destinos (
            id TEXT PRIMARY KEY,
            destino_nombre TEXT NOT NULL,
            iata_destino TEXT,
            rutas_directas_ES INTEGER DEFAULT 0,
            rutas_directas_UK INTEGER DEFAULT 0,
            rutas_directas_DE INTEGER DEFAULT 0,
            vuelos_semanales INTEGER DEFAULT 0,
            asientos_semanales INTEGER DEFAULT 0,
            pasajeros_anuales INTEGER DEFAULT 0,
            grupo TEXT,
            fecha_extraccion TEXT NOT NULL,
            UNIQUE(destino_nombre)
        )
    """)
    conn.commit()

    for destino in DESTINOS_39:
        existe = conn.execute(
            "SELECT 1 FROM conectividad_destinos WHERE destino_nombre = ?", (destino,)
        ).fetchone()
        
        if existe:
            continue

        id_reg = hashlib.md5(f"conectividad|{destino}".encode()).hexdigest()[:32]
        conn.execute("""
            INSERT OR IGNORE INTO conectividad_destinos
            (id, destino_nombre, iata_destino, rutas_directas_ES, rutas_directas_UK,
             rutas_directas_DE, vuelos_semanales, asientos_semanales, pasajeros_anuales,
             grupo, fecha_extraccion)
            VALUES (?, ?, ?, 0, 0, 0, 0, 0, 0, ?, ?)
        """, (id_reg, destino, "", "sin_datos", datetime.now().isoformat()))
        insertados += 1

    conn.commit()
    return insertados


def main():
    print("=" * 70)
    print("  NORMALIZACIÓN DE DESTINOS + COMPLETAR COBERTURA")
    print("=" * 70)
    print(f"  BD: {DB_PATH}")
    print(f"  Destinos estándar: {len(DESTINOS_39)}")
    print()

    conn = sqlite3.connect(str(DB_PATH))

    # 1. Normalizar nombres en cada tabla con columna de destino
    print("[1/4] Normalizando nombres de destinos...")
    tablas_col = {
        "resenas": "destino_nombre",
        "clima_destinos": "destino_nombre",
        "indicadores_destino": "destino_nombre",
        "destinos_caracteristicas": "destino_nombre",
        "conectividad_destinos": "destino_nombre",
        "seguridad_destinos": "destino_nombre",
    }

    total_actualizados = 0
    for tabla, col in tablas_col.items():
        print(f"  Tabla: {tabla} (columna: {col})")
        try:
            act, _ = normalizar_tabla(conn, tabla, col)
            total_actualizados += act
            if act > 0:
                print(f"    ✓ {act} registros actualizados")
            else:
                print(f"    ✓ Sin cambios necesarios")
        except Exception as e:
            print(f"    ✗ Error: {e}")

    # 2. Completar seguridad para los 39 destinos
    print(f"\n[2/4] Completando seguridad_destinos...")
    n_seg = completar_seguridad(conn)
    print(f"  ✓ {n_seg} destinos añadidos a seguridad_destinos")

    # 3. Completar conectividad para los 39 destinos
    print(f"\n[3/4] Completando conectividad_destinos...")
    n_con = completar_conectividad(conn)
    print(f"  ✓ {n_con} destinos añadidos a conectividad_destinos")

    # 4. Verificación final
    print(f"\n[4/4] Verificación final de cobertura...")
    for tabla, col in tablas_col.items():
        try:
            existentes = set(pd.read_sql(
                f"SELECT DISTINCT [{col}] FROM [{tabla}]", conn
            )[col].dropna().tolist())
            cubiertos = len([d for d in DESTINOS_39 if d in existentes])
            status = "✓" if cubiertos == 39 else "⚠"
            print(f"  {status} {tabla:<30} {cubiertos}/39")
        except Exception as e:
            print(f"  ✗ {tabla:<30} Error: {e}")

    conn.close()

    # Resumen
    print(f"\n{'=' * 70}")
    print("  RESUMEN")
    print(f"{'=' * 70}")
    print(f"  Registros normalizados: {total_actualizados}")
    print(f"  Seguridad completada: +{n_seg} destinos")
    print(f"  Conectividad completada: +{n_con} destinos")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
