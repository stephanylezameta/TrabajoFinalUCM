"""
Integrar los 3 CSV nuevos en la BD principal tui_recomendador.db.

1. clima_todos_los_destinos.csv → enriquecer tabla clima_destinos (añadir temp_agua, humedad, dias_lluvia)
2. conectividad_y_pasajeros_2025.csv → nueva tabla conectividad_destinos
3. seguridad_y_sanidad_banco_mundial.csv → nueva tabla seguridad_destinos

Ejecución:
    cd /d D:\\Master\\TrabajoFinalUCM\\TFM
    python scripts/integrar_csvs_nuevos.py
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

# Mapeo de nombres en el CSV clima → nombres de destinos en nuestra BD
MAPEO_CLIMA_DESTINOS = {
    "Abu Dhabi": "Dubái",  # Usamos Abu Dhabi como proxy del clima de EAU/Dubái
    "Agadir": "Marrakech",  # Proxy para Marruecos
    "Alanya": "Antalya",  # Costa turca
    "Algarve": "Algarve",
    "Alicante": "Alicante",
    "Bali": "Bali",
    "Barcelona": "Barcelona",
    "Bilbao": "Bilbao",
    "Cabo Verde": "Cabo Verde",
    "Cádiz": "Cádiz",
    "Cancún": "Cancún",
    "Córdoba": "Córdoba",
    "Costa del Sol": "Costa del Sol",
    "Creta": "Creta",
    "Cerdeña": "Cerdeña",
    "Costa Amalfitana": "Costa Amalfitana",
    "Dubái": "Dubái",
    "Fuerteventura": "Fuerteventura",
    "Gran Canaria": "Gran Canaria",
    "Granada": "Granada",
    "Hurghada": "Hurghada",
    "Ibiza": "Ibiza",
    "Lanzarote": "Lanzarote",
    "Madrid": "Madrid",
    "Málaga": "Málaga",
    "Mallorca": "Mallorca",
    "Maldivas": "Maldivas",
    "Marrakech": "Marrakech",
    "Menorca": "Menorca",
    "Phuket": "Phuket",
    "Punta Cana": "Punta Cana",
    "Riviera Maya": "Riviera Maya",
    "Rodas": "Rodas",
    "San Sebastián": "San Sebastián",
    "San Sebastian": "San Sebastián",
    "Santorini": "Santorini",
    "Sevilla": "Sevilla",
    "Sicilia": "Sicilia",
    "Split": "Split",
    "Tenerife": "Tenerife",
    "Túnez": "Túnez",
    "Valencia": "Valencia",
    "València": "Valencia",
}

# Mapeo ISO → país para nuestros destinos
ISO_A_PAIS = {
    "ESP": "España",
    "TUR": "Turquía",
    "GRC": "Grecia",
    "EGY": "Egipto",
    "DOM": "República Dominicana",
    "MEX": "México",
    "ARE": "Emiratos Árabes Unidos",
    "MDV": "Maldivas",
    "IDN": "Indonesia",
    "THA": "Tailandia",
    "MAR": "Marruecos",
    "CPV": "Cabo Verde",
    "HRV": "Croacia",
    "ITA": "Italia",
    "PRT": "Portugal",
    "TUN": "Túnez",
}

# Mapeo de destinos a ISO para seguridad
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

# Mapeo conectividad: termino_original → destino nuestro
MAPEO_CONECTIVIDAD = {
    "Alicante": "Alicante", "Barcelona": "Barcelona", "Bilbao": "Bilbao",
    "Cádiz": "Cádiz", "Córdoba": "Córdoba", "San Sebastian": "San Sebastián",
    "Eivissa": "Ibiza", "Granada": "Granada", "Madrid": "Madrid",
    "Málaga": "Málaga", "Palma": "Mallorca", "Palmas de Gran Canaria": "Gran Canaria",
    "Puerto de la Cruz": "Tenerife", "Santa Cruz de Tenerife": "Tenerife",
    "Sevilla": "Sevilla", "València": "Valencia", "Marbella": "Costa del Sol",
    "Benalmádena": "Costa del Sol", "Fuengirola": "Costa del Sol",
    "Torremolinos": "Costa del Sol",
    "Dubái": "Dubái", "Playa del Carmen": "Riviera Maya",
    "Maldivas": "Maldivas", "Bali": "Bali",
    "Tailandia Phuket": "Phuket", "Sri Lanka": "Maldivas",
}


def integrar_clima(conn: sqlite3.Connection) -> int:
    """Enriquece clima_destinos con temp_agua, humedad, dias_lluvia del CSV nuevo."""
    csv_path = PROJECT_ROOT / "data" / "clima_todos_los_destinos.csv"
    if not csv_path.exists():
        print("  ⚠ No se encontró clima_todos_los_destinos.csv")
        return 0

    df = pd.read_csv(str(csv_path))
    print(f"  CSV clima: {len(df)} filas, {df['lugar'].nunique()} lugares")

    # Añadir columnas nuevas a la tabla si no existen
    columnas_existentes = [row[1] for row in conn.execute("PRAGMA table_info(clima_destinos)").fetchall()]
    
    nuevas_cols = {
        "temp_agua": "REAL",
        "humedad_pct": "REAL",
        "dias_lluvia": "INTEGER",
    }
    for col, tipo in nuevas_cols.items():
        if col not in columnas_existentes:
            conn.execute(f"ALTER TABLE clima_destinos ADD COLUMN {col} {tipo}")
            print(f"    Columna '{col}' añadida a clima_destinos")
    conn.commit()

    # Actualizar registros existentes y/o insertar nuevos
    insertados = 0
    actualizados = 0

    for _, row in df.iterrows():
        lugar = row['lugar']
        destino = MAPEO_CLIMA_DESTINOS.get(lugar)
        if not destino:
            continue

        # Parsear year_month
        try:
            anio = int(row['year_month'].split('-')[0])
            mes = int(row['year_month'].split('-')[1])
        except (ValueError, IndexError):
            continue

        temp_agua = row.get('temp_media_agua_c')
        humedad = row.get('humedad_media_pct')
        dias_lluvia = row.get('dias_lluvia')

        # Intentar actualizar registro existente
        cursor = conn.execute(
            "UPDATE clima_destinos SET temp_agua = ?, humedad_pct = ?, dias_lluvia = ? WHERE destino_nombre = ? AND anio = ? AND mes = ?",
            (temp_agua, humedad, dias_lluvia, destino, anio, mes)
        )
        if cursor.rowcount > 0:
            actualizados += 1
        else:
            # Insertar nuevo registro
            id_reg = hashlib.md5(f"{destino}|{anio}|{mes}|clima_csv".encode()).hexdigest()[:32]
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO clima_destinos
                    (id, destino_nombre, latitud, longitud, anio, mes, temp_media, temp_max, temp_min,
                     precipitacion_mm, horas_sol, temp_agua, humedad_pct, dias_lluvia, fecha_extraccion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    id_reg, destino, 0.0, 0.0, anio, mes,
                    row.get('temp_media_aire_c'), None, None,
                    row.get('precipitacion_total_mm'),
                    row.get('horas_sol_totales'),
                    temp_agua, humedad, dias_lluvia,
                    datetime.now().isoformat()
                ))
                insertados += 1
            except sqlite3.IntegrityError:
                pass

    conn.commit()
    print(f"  ✓ Clima: {actualizados} actualizados, {insertados} insertados")
    return actualizados + insertados


def integrar_conectividad(conn: sqlite3.Connection) -> int:
    """Crea tabla conectividad_destinos desde el CSV de pasajeros."""
    csv_path = PROJECT_ROOT / "data" / "conectividad_y_pasajeros_2025.csv"
    if not csv_path.exists():
        print("  ⚠ No se encontró conectividad_y_pasajeros_2025.csv")
        return 0

    df = pd.read_csv(str(csv_path))
    print(f"  CSV conectividad: {len(df)} filas")

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

    insertados = 0
    # Agrupar por destino mapeado (algunos comparten aeropuerto)
    destinos_procesados = set()

    for _, row in df.iterrows():
        termino = row['termino_original']
        destino = MAPEO_CONECTIVIDAD.get(termino)
        if not destino or destino in destinos_procesados:
            continue
        
        destinos_procesados.add(destino)
        id_reg = hashlib.md5(f"conectividad|{destino}".encode()).hexdigest()[:32]

        try:
            conn.execute("""
                INSERT OR REPLACE INTO conectividad_destinos
                (id, destino_nombre, iata_destino, rutas_directas_ES, rutas_directas_UK,
                 rutas_directas_DE, vuelos_semanales, asientos_semanales, pasajeros_anuales,
                 grupo, fecha_extraccion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                id_reg, destino,
                str(row.get('iata_destino', '')),
                int(row.get('rutas_directas_ES', 0)),
                int(row.get('rutas_directas_UK', 0)),
                int(row.get('rutas_directas_DE', 0)),
                int(row.get('vuelos_semanales_estimados', 0)),
                int(row.get('asientos_semanales_ofertados', 0)),
                int(row.get('pasajeros_anuales_estimados', 0)),
                str(row.get('grupo', '')),
                datetime.now().isoformat()
            ))
            insertados += 1
        except Exception as e:
            print(f"    Error {destino}: {e}")

    conn.commit()
    print(f"  ✓ Conectividad: {insertados} destinos insertados")
    return insertados


def integrar_seguridad(conn: sqlite3.Connection) -> int:
    """Crea tabla seguridad_destinos desde el CSV del Banco Mundial."""
    csv_path = PROJECT_ROOT / "data" / "seguridad_y_sanidad_banco_mundial.csv"
    if not csv_path.exists():
        print("  ⚠ No se encontró seguridad_y_sanidad_banco_mundial.csv")
        return 0

    df = pd.read_csv(str(csv_path))
    print(f"  CSV seguridad: {len(df)} filas (países)")

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

    # Indexar por ISO
    df_indexed = df.set_index('iso')

    insertados = 0
    for destino, iso in DESTINO_A_ISO.items():
        if iso not in df_indexed.index:
            continue

        row = df_indexed.loc[iso]
        camas = row.get('camas_hospital_1000hab')
        homicidios = row.get('tasa_homicidios_100mil')

        # Clasificar nivel de seguridad
        if pd.notna(homicidios):
            if homicidios < 2:
                nivel = "muy_seguro"
            elif homicidios < 5:
                nivel = "seguro"
            elif homicidios < 10:
                nivel = "moderado"
            else:
                nivel = "precaucion"
        else:
            nivel = "sin_datos"

        id_reg = hashlib.md5(f"seguridad|{destino}".encode()).hexdigest()[:32]
        pais = ISO_A_PAIS.get(iso, iso)

        try:
            conn.execute("""
                INSERT OR REPLACE INTO seguridad_destinos
                (id, destino_nombre, pais, iso, camas_hospital_1000hab,
                 tasa_homicidios_100mil, nivel_seguridad, fecha_extraccion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                id_reg, destino, pais, iso,
                float(camas) if pd.notna(camas) else None,
                float(homicidios) if pd.notna(homicidios) else None,
                nivel,
                datetime.now().isoformat()
            ))
            insertados += 1
        except Exception as e:
            print(f"    Error {destino}: {e}")

    conn.commit()
    print(f"  ✓ Seguridad: {insertados} destinos insertados")
    return insertados


def main():
    print("=" * 60)
    print("  INTEGRAR CSVs NUEVOS → tui_recomendador.db")
    print("=" * 60)
    print(f"  BD: {DB_PATH}")
    print()

    conn = sqlite3.connect(str(DB_PATH))

    # 1. Clima (enriquecer)
    print("[1/3] Clima (temp_agua, humedad, dias_lluvia)...")
    n1 = integrar_clima(conn)

    # 2. Conectividad (nueva tabla)
    print("\n[2/3] Conectividad aérea (rutas, vuelos, pasajeros)...")
    n2 = integrar_conectividad(conn)

    # 3. Seguridad (nueva tabla)
    print("\n[3/3] Seguridad y sanidad (Banco Mundial)...")
    n3 = integrar_seguridad(conn)

    conn.close()

    # Resumen
    print(f"\n{'=' * 60}")
    print("  RESUMEN")
    print(f"{'=' * 60}")
    print(f"  Clima enriquecido: {n1} registros")
    print(f"  Conectividad: {n2} destinos")
    print(f"  Seguridad: {n3} destinos")
    print(f"  Total: {n1 + n2 + n3} registros integrados")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
