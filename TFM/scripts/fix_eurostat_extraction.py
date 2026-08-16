"""
Extracción corregida de datos Eurostat para los 8 destinos internacionales faltantes.

El script original asumía formato 'YYYYMNN' pero Eurostat usa 'YYYY-MM'.
Además maneja correctamente la respuesta multidimensional (c_resid x time).
"""
import hashlib
import json
import sqlite3
import sys
import time as time_module
from datetime import datetime
from pathlib import Path
from functools import reduce
import operator

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "tui_recomendador.db"

EUROSTAT_BASE_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/tour_occ_nim"
)

# Mapeo de código Eurostat a destinos
EUROSTAT_PAIS_A_DESTINOS = {
    "EL": ["Rodas", "Santorini", "Creta"],           # Grecia
    "IT": ["Sicilia", "Cerdeña", "Costa Amalfitana"],  # Italia
    "HR": ["Split"],                                    # Croacia
    "PT": ["Algarve"],                                  # Portugal
}


def generar_id(destino, fuente, tipo, anio, mes):
    clave = f"{destino}|{fuente}|{tipo}|{anio}|{mes}"
    return hashlib.md5(clave.encode()).hexdigest()[:32]


def extraer_eurostat_corregido():
    """Extracción corregida que maneja el formato real de la API Eurostat."""
    
    conn = sqlite3.connect(str(DB_PATH))
    
    # Asegurar tabla existe
    conn.execute("""
        CREATE TABLE IF NOT EXISTS indicadores_destino (
            id_indicador TEXT PRIMARY KEY,
            destino_nombre TEXT NOT NULL,
            fuente TEXT NOT NULL,
            tipo_indicador TEXT NOT NULL,
            valor REAL NOT NULL,
            anio INTEGER NOT NULL,
            mes INTEGER,
            fecha_extraccion TEXT
        )
    """)
    conn.commit()
    
    total_insertados = 0
    
    for geo_code, destinos in EUROSTAT_PAIS_A_DESTINOS.items():
        print(f"\nConsultando Eurostat: geo={geo_code} -> {destinos}")
        
        params = {
            "format": "JSON",
            "lang": "EN",
            "freq": "M",
            "unit": "NR",
            "nace_r2": "I551",
            "geo": geo_code,
        }
        
        try:
            resp = requests.get(EUROSTAT_BASE_URL, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  Error: {e}")
            continue
        
        valores = data.get("value", {})
        dims = data.get("dimension", {})
        sizes = data.get("size", [])
        dim_ids = data.get("id", [])
        
        if not valores:
            print(f"  Sin valores para {geo_code}")
            continue
        
        # Build dimension info
        # Each dimension has an index mapping label -> position
        dim_info = {}
        for dim_id in dim_ids:
            dim_data = dims.get(dim_id, {})
            cat = dim_data.get("category", {})
            idx = cat.get("index", {})
            dim_info[dim_id] = idx
        
        print(f"  Dimensiones: {dim_ids}")
        print(f"  Tamaños: {sizes}")
        print(f"  Valores totales: {len(valores)}")
        
        # Get time dimension index
        time_idx = dim_info.get("time", {})
        # Get c_resid index (we want TOTAL)
        c_resid_idx = dim_info.get("c_resid", {})
        
        # Find position of 'TOTAL' in c_resid
        total_pos = c_resid_idx.get("TOTAL", None)
        if total_pos is None:
            print(f"  TOTAL no encontrado en c_resid, usando FOR (extranjeros)")
            total_pos = c_resid_idx.get("FOR", 0)
        
        # Calculate the flat index for each time period with c_resid=TOTAL
        # Flat index = sum(pos_i * product(sizes[i+1:]))
        # dim_ids = ['freq', 'c_resid', 'unit', 'nace_r2', 'geo', 'time']
        # sizes   = [  1,       3,        1,       1,        1,     437 ]
        
        # For TOTAL: freq=0, c_resid=total_pos, unit=0, nace_r2=0, geo=0, time=varies
        registros_insertados = 0
        
        for time_label, time_pos in time_idx.items():
            # Parse time: "2022-01" -> anio=2022, mes=1
            try:
                parts = time_label.split("-")
                anio = int(parts[0])
                mes = int(parts[1])
            except (ValueError, IndexError):
                continue
            
            # Only 2022-2025
            if anio < 2022 or anio > 2025:
                continue
            
            # Calculate flat index for this time period with TOTAL residency
            # positions: [0, total_pos, 0, 0, 0, time_pos]
            positions = [0, total_pos, 0, 0, 0, time_pos]
            
            # flat_index = pos[0]*prod(sizes[1:]) + pos[1]*prod(sizes[2:]) + ... + pos[n-1]*sizes[n] + pos[n]
            flat_idx = 0
            for i, pos in enumerate(positions):
                # Product of all sizes after position i
                remaining = sizes[i+1:] if i+1 < len(sizes) else [1]
                stride = reduce(operator.mul, remaining, 1)
                flat_idx += pos * stride
            
            # Look up value
            valor = valores.get(str(flat_idx))
            if valor is None:
                continue
            
            # Distribute among destinations
            valor_por_destino = float(valor) / len(destinos)
            
            for destino in destinos:
                id_ind = generar_id(destino, "eurostat", "pernoctaciones_pais_mensual", anio, mes)
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO indicadores_destino
                        (id_indicador, destino_nombre, fuente, tipo_indicador,
                         valor, anio, mes, fecha_extraccion)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        id_ind, destino, "eurostat", "pernoctaciones_pais_mensual",
                        round(valor_por_destino, 2), anio, mes,
                        datetime.now().isoformat()
                    ))
                    registros_insertados += 1
                except sqlite3.IntegrityError:
                    pass
        
        conn.commit()
        total_insertados += registros_insertados
        print(f"  -> {registros_insertados} registros insertados para {geo_code}")
        time_module.sleep(1)
    
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"TOTAL: {total_insertados} registros insertados desde Eurostat")
    print(f"Destinos cubiertos: {[d for ds in EUROSTAT_PAIS_A_DESTINOS.values() for d in ds]}")
    print(f"{'='*60}")


if __name__ == "__main__":
    extraer_eurostat_corregido()
