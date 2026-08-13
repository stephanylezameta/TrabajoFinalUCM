"""
Generador de ~150.000 interacciones REALISTAS basadas en estacionalidad real.

Lee datos de indicadores_destino (INE + Google Trends) y clima_destinos para
generar interacciones con distribución temporal y geográfica realista.

Inserta en `data/sample_tui.db`:
- 5.000 usuarios nuevos (es_sintetico=1)
- ~150.000 interacciones nuevas

NO borra datos existentes. Solo añade. Seed=42 para reproducibilidad.

Ejecución:
    cd /d D:\\Master\\TrabajoFinalUCM\\TFM
    python scripts/generate_realistic_bookings.py
    python scripts/generate_realistic_bookings.py --usuarios 5000 --interacciones 150000
    python scripts/generate_realistic_bookings.py --help
"""

import argparse
import hashlib
import json
import logging
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

# Asegurar imports del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("generate_bookings")

# ---------------------------------------------------------------------------
# Constantes y datos maestros
# ---------------------------------------------------------------------------

SEED = 42

# Todos los destinos con popularidad relativa (Zipf-like)
# Barcelona, Mallorca, Tenerife concentran ~40% del tráfico
DESTINOS_POPULARIDAD = {
    "Barcelona": 100,
    "Mallorca": 95,
    "Tenerife": 85,
    "Cancún": 80,
    "Madrid": 70,
    "Costa del Sol": 65,
    "Ibiza": 60,
    "Riviera Maya": 55,
    "Punta Cana": 50,
    "Antalya": 48,
    "Dubái": 45,
    "Santorini": 40,
    "Gran Canaria": 38,
    "Málaga": 35,
    "Valencia": 33,
    "Sevilla": 30,
    "Bali": 28,
    "Maldivas": 27,
    "Hurghada": 25,
    "Rodas": 24,
    "Alicante": 22,
    "Granada": 20,
    "Creta": 19,
    "Lanzarote": 18,
    "Fuerteventura": 17,
    "Menorca": 16,
    "Bilbao": 15,
    "San Sebastián": 14,
    "Phuket": 13,
    "Marrakech": 12,
    "Cádiz": 11,
    "Córdoba": 10,
    "Cabo Verde": 9,
    "Split": 8,
    "Sicilia": 7,
    "Cerdeña": 6,
    "Costa Amalfitana": 5,
    "Algarve": 5,
    "Túnez": 4,
}

# Categorías de destino (para matching con preferencias de usuario)
DESTINOS_CATEGORIAS = {
    "Barcelona": ["cultura", "gastronomia", "playa"],
    "Mallorca": ["playa", "cultura", "naturaleza"],
    "Tenerife": ["playa", "naturaleza", "aventura"],
    "Cancún": ["playa", "aventura", "cultura"],
    "Madrid": ["cultura", "gastronomia", "aventura"],
    "Costa del Sol": ["playa", "gastronomia", "cultura"],
    "Ibiza": ["playa", "bienestar", "gastronomia"],
    "Riviera Maya": ["playa", "cultura", "aventura"],
    "Punta Cana": ["playa", "bienestar", "aventura"],
    "Antalya": ["playa", "cultura", "aventura"],
    "Dubái": ["bienestar", "cultura", "aventura"],
    "Santorini": ["cultura", "playa", "gastronomia"],
    "Gran Canaria": ["playa", "naturaleza", "aventura"],
    "Málaga": ["playa", "cultura", "gastronomia"],
    "Valencia": ["playa", "cultura", "gastronomia"],
    "Sevilla": ["cultura", "gastronomia", "aventura"],
    "Bali": ["cultura", "playa", "bienestar"],
    "Maldivas": ["playa", "bienestar", "naturaleza"],
    "Hurghada": ["playa", "aventura", "naturaleza"],
    "Rodas": ["playa", "cultura", "naturaleza"],
    "Alicante": ["playa", "cultura", "gastronomia"],
    "Granada": ["cultura", "naturaleza", "aventura"],
    "Creta": ["playa", "cultura", "naturaleza"],
    "Lanzarote": ["playa", "naturaleza", "cultura"],
    "Fuerteventura": ["playa", "naturaleza", "aventura"],
    "Menorca": ["playa", "naturaleza", "cultura"],
    "Bilbao": ["cultura", "gastronomia", "naturaleza"],
    "San Sebastián": ["gastronomia", "playa", "cultura"],
    "Phuket": ["playa", "cultura", "aventura"],
    "Marrakech": ["cultura", "aventura", "gastronomia"],
    "Cádiz": ["playa", "cultura", "gastronomia"],
    "Córdoba": ["cultura", "gastronomia"],
    "Cabo Verde": ["playa", "naturaleza", "aventura"],
    "Split": ["playa", "cultura", "naturaleza"],
    "Sicilia": ["cultura", "playa", "gastronomia"],
    "Cerdeña": ["playa", "naturaleza", "cultura"],
    "Costa Amalfitana": ["cultura", "gastronomia", "playa"],
    "Algarve": ["playa", "naturaleza", "gastronomia"],
    "Túnez": ["cultura", "playa", "aventura"],
}

# Estacionalidad por defecto (fallback si no hay datos reales)
ESTACIONALIDAD_DEFAULT = {
    # Destinos de playa: pico en verano
    "playa": {1: 0.3, 2: 0.3, 3: 0.5, 4: 0.6, 5: 0.7, 6: 0.9,
              7: 1.0, 8: 1.0, 9: 0.8, 10: 0.5, 11: 0.3, 12: 0.4},
    # Destinos culturales: primavera y otoño
    "cultura": {1: 0.4, 2: 0.4, 3: 0.7, 4: 0.9, 5: 0.9, 6: 0.8,
                7: 0.7, 8: 0.6, 9: 0.8, 10: 0.9, 11: 0.5, 12: 0.5},
    # Destinos tropicales/Canarias: invierno europeo
    "tropical": {1: 0.9, 2: 0.9, 3: 0.8, 4: 0.6, 5: 0.4, 6: 0.3,
                 7: 0.4, 8: 0.5, 9: 0.4, 10: 0.5, 11: 0.7, 12: 1.0},
}

# Destinos con estacionalidad tropical (invierno europeo)
DESTINOS_TROPICALES = {
    "Punta Cana", "Cancún", "Riviera Maya", "Dubái", "Maldivas",
    "Bali", "Phuket", "Cabo Verde", "Tenerife", "Gran Canaria",
    "Fuerteventura", "Lanzarote", "Hurghada", "Marrakech"
}

# Destinos principalmente culturales
DESTINOS_CULTURALES = {
    "Madrid", "Sevilla", "Córdoba", "Granada", "Bilbao",
    "San Sebastián", "Marrakech", "Costa Amalfitana"
}


# ---------------------------------------------------------------------------
# Funciones de lectura de datos reales
# ---------------------------------------------------------------------------

def cargar_estacionalidad_real(db_path: Path) -> dict[str, dict[int, float]]:
    """
    Lee indicadores_destino para obtener estacionalidad real por destino/mes.
    Devuelve {destino: {mes: valor_medio}}.
    """
    estacionalidad = {}

    if not db_path.exists():
        logger.warning(f"BD no encontrada: {db_path}, usando estacionalidad default")
        return estacionalidad

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute("""
            SELECT destino_nombre, mes, AVG(valor) as valor_medio
            FROM indicadores_destino
            WHERE mes IS NOT NULL
            GROUP BY destino_nombre, mes
            ORDER BY destino_nombre, mes
        """)

        for row in cursor:
            destino, mes, valor = row
            if destino not in estacionalidad:
                estacionalidad[destino] = {}
            estacionalidad[destino][mes] = valor

    except sqlite3.OperationalError as e:
        logger.warning(f"Error leyendo indicadores: {e}")
    finally:
        conn.close()

    return estacionalidad


def cargar_clima(db_path: Path) -> dict[str, dict[int, float]]:
    """
    Lee clima_destinos para ponderar temporadas.
    Devuelve {destino: {mes: temp_media}}.
    """
    clima = {}

    if not db_path.exists():
        return clima

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute("""
            SELECT destino_nombre, mes, AVG(temp_media) as temp
            FROM clima_destinos
            GROUP BY destino_nombre, mes
        """)

        for row in cursor:
            destino, mes, temp = row
            if destino not in clima:
                clima[destino] = {}
            clima[destino][mes] = temp

    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()

    return clima


def cargar_paquetes_existentes(db_path: Path) -> list[dict]:
    """Lee paquetes de sample_tui.db para asociar interacciones."""
    paquetes = []

    if not db_path.exists():
        return paquetes

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute("""
            SELECT id_paquete, destino_nombre, precio_base_eur, 
                   duracion_dias, categoria
            FROM paquetes
            LIMIT 10000
        """)

        for row in cursor:
            paquetes.append({
                "id_paquete": row[0],
                "destino_nombre": row[1],
                "precio": row[2],
                "duracion": row[3],
                "categoria": row[4],
            })

    except sqlite3.OperationalError as e:
        logger.warning(f"Error leyendo paquetes: {e}")
    finally:
        conn.close()

    return paquetes


# ---------------------------------------------------------------------------
# Generación de usuarios
# ---------------------------------------------------------------------------

def generar_usuarios(n_usuarios: int, rng: np.random.Generator) -> list[dict]:
    """
    Genera n_usuarios con perfiles coherentes.
    
    - Preferencias temáticas via Dirichlet (suman 1.0)
    - Presupuesto: lognormal
    - Mercado: 50% ES, 30% DE, 20% UK
    """
    usuarios = []

    # Distribución de mercados
    mercados_prob = [0.50, 0.30, 0.20]
    mercados_opciones = ["es", "de", "uk"]

    for i in range(n_usuarios):
        id_usuario = str(uuid.uuid4())

        # Preferencias Dirichlet (alfa bajo = más especializados)
        alpha = rng.uniform(0.3, 0.8, size=6)
        prefs = rng.dirichlet(alpha)

        # Presupuesto lognormal
        presupuesto_medio = rng.lognormal(mean=7.0, sigma=0.5)  # ~1100€
        presupuesto_medio = np.clip(presupuesto_medio, 300, 5000)
        presupuesto_min = presupuesto_medio * rng.uniform(0.6, 0.8)
        presupuesto_max = presupuesto_medio * rng.uniform(1.3, 2.0)

        # Duración preferida
        duracion_media = rng.normal(8, 2)
        duracion_min = max(3, int(duracion_media - rng.integers(1, 3)))
        duracion_max = min(21, int(duracion_media + rng.integers(2, 5)))

        # Mercado
        mercado = rng.choice(mercados_opciones, p=mercados_prob)

        # Temporada preferida
        temporadas = ["Alta", "Media", "Baja", None]
        temporada = rng.choice(temporadas, p=[0.3, 0.3, 0.2, 0.2])

        # Accesibilidad y sostenibilidad
        requiere_accesibilidad = bool(rng.random() < 0.08)
        interes_sostenibilidad = float(rng.beta(2, 5))

        usuario = {
            "id_usuario": id_usuario,
            "es_sintetico": 1,
            "pref_cultura": float(prefs[0]),
            "pref_gastronomia": float(prefs[1]),
            "pref_naturaleza": float(prefs[2]),
            "pref_playa": float(prefs[3]),
            "pref_bienestar": float(prefs[4]),
            "pref_aventura": float(prefs[5]),
            "presupuesto_min_eur": float(round(presupuesto_min, 2)),
            "presupuesto_max_eur": float(round(presupuesto_max, 2)),
            "duracion_min_dias": duracion_min,
            "duracion_max_dias": duracion_max,
            "temporada_preferida": str(temporada) if temporada else None,
            "requiere_accesibilidad": int(requiere_accesibilidad),
            "distancia_max_km": float(rng.choice([3000, 5000, 8000, 12000])) if rng.random() > 0.2 else None,
            "interes_sostenibilidad": float(round(interes_sostenibilidad, 3)),
            "mercado": mercado,
            "fecha_creacion": datetime.now().isoformat(),
            "seed_generacion": SEED,
        }

        usuarios.append(usuario)

    return usuarios


# ---------------------------------------------------------------------------
# Generación de interacciones
# ---------------------------------------------------------------------------

def obtener_estacionalidad_destino(destino: str, mes: int,
                                    estacionalidad_real: dict,
                                    clima: dict) -> float:
    """
    Obtiene el factor de estacionalidad para un destino en un mes dado.
    Usa datos reales si disponibles, si no usa patrón hardcodeado.
    """
    # 1. Intentar datos reales
    if destino in estacionalidad_real and mes in estacionalidad_real[destino]:
        val = estacionalidad_real[destino][mes]
        max_val = max(estacionalidad_real[destino].values())
        if max_val > 0:
            return val / max_val
        return 0.5

    # 2. Fallback por tipo de destino (verano=alta demanda playas, primavera=cultura)
    if destino in DESTINOS_TROPICALES:
        return ESTACIONALIDAD_DEFAULT["tropical"].get(mes, 0.5)
    elif destino in DESTINOS_CULTURALES:
        return ESTACIONALIDAD_DEFAULT["cultura"].get(mes, 0.5)
    else:
        return ESTACIONALIDAD_DEFAULT["playa"].get(mes, 0.5)


def elegir_destino_para_usuario(usuario: dict, rng: np.random.Generator,
                                 destinos_list: list[str],
                                 destinos_probs: np.ndarray) -> str:
    """
    Elige un destino ponderado por:
    1. Popularidad global (Zipf/power-law)
    2. Afinidad con preferencias del usuario
    """
    prefs_usuario = {
        "cultura": usuario["pref_cultura"],
        "gastronomia": usuario["pref_gastronomia"],
        "naturaleza": usuario["pref_naturaleza"],
        "playa": usuario["pref_playa"],
        "bienestar": usuario["pref_bienestar"],
        "aventura": usuario["pref_aventura"],
    }

    afinidades = np.zeros(len(destinos_list))
    for i, destino in enumerate(destinos_list):
        cats = DESTINOS_CATEGORIAS.get(destino, ["playa"])
        afinidad = sum(prefs_usuario.get(cat, 0) for cat in cats)
        afinidades[i] = afinidad

    # 60% popularidad + 40% afinidad personal
    if afinidades.sum() > 0:
        afinidades_norm = afinidades / afinidades.sum()
    else:
        afinidades_norm = np.ones(len(destinos_list)) / len(destinos_list)

    probs_combinadas = 0.6 * destinos_probs + 0.4 * afinidades_norm
    probs_combinadas = probs_combinadas / probs_combinadas.sum()

    return rng.choice(destinos_list, p=probs_combinadas)


def generar_interacciones(usuarios: list[dict], paquetes: list[dict],
                          estacionalidad_real: dict, clima: dict,
                          n_interacciones: int,
                          rng: np.random.Generator) -> list[dict]:
    """
    Genera interacciones realistas.
    
    - 60% visualizaciones, 30% reservas, 10% valoraciones
    - Destino con distribución power-law + afinidad usuario
    - Mes proporcional a estacionalidad real del destino
    - Valoraciones: normal(4.0, 0.7) truncada en [1, 5]
    """
    interacciones = []

    # Distribución de destinos (power-law)
    destinos_list = list(DESTINOS_POPULARIDAD.keys())
    popularidades = np.array([DESTINOS_POPULARIDAD[d] for d in destinos_list], dtype=float)
    popularidades_zipf = popularidades ** 1.5
    destinos_probs = popularidades_zipf / popularidades_zipf.sum()

    # Indexar paquetes por destino
    paquetes_por_destino = {}
    for paq in paquetes:
        dest = paq["destino_nombre"]
        if dest not in paquetes_por_destino:
            paquetes_por_destino[dest] = []
        paquetes_por_destino[dest].append(paq)

    # Interacciones por usuario (distribución variable)
    n_usuarios = len(usuarios)
    interacciones_por_usuario = rng.negative_binomial(5, 0.15, size=n_usuarios)
    factor = n_interacciones / interacciones_por_usuario.sum()
    interacciones_por_usuario = (interacciones_por_usuario * factor).astype(int)
    diff = n_interacciones - interacciones_por_usuario.sum()
    if diff > 0:
        indices = rng.choice(n_usuarios, size=abs(diff), replace=True)
        for idx in indices:
            interacciones_por_usuario[idx] += 1
    elif diff < 0:
        indices = rng.choice(n_usuarios, size=abs(diff), replace=True)
        for idx in indices:
            if interacciones_por_usuario[idx] > 0:
                interacciones_por_usuario[idx] -= 1

    tipos_interaccion = ["visualizacion", "reserva", "valoracion"]
    tipos_probs = [0.60, 0.30, 0.10]
    anios_posibles = [2022, 2023, 2024, 2025]

    logger.info(f"Generando {n_interacciones} interacciones para {n_usuarios} usuarios...")

    for i, usuario in enumerate(usuarios):
        n_inter = int(interacciones_por_usuario[i])
        if n_inter == 0:
            continue

        for _ in range(n_inter):
            destino = elegir_destino_para_usuario(
                usuario, rng, destinos_list, destinos_probs
            )

            # Mes proporcional a estacionalidad
            meses = list(range(1, 13))
            pesos_mes = np.array([
                obtener_estacionalidad_destino(destino, m, estacionalidad_real, clima)
                for m in meses
            ])
            if pesos_mes.sum() == 0:
                pesos_mes = np.ones(12)
            pesos_mes = pesos_mes / pesos_mes.sum()
            mes = rng.choice(meses, p=pesos_mes)

            anio = rng.choice(anios_posibles, p=[0.15, 0.25, 0.35, 0.25])
            dia = rng.integers(1, 29)
            hora = rng.integers(6, 23)
            minuto = rng.integers(0, 60)
            try:
                timestamp = datetime(anio, mes, dia, hora, minuto)
            except ValueError:
                timestamp = datetime(anio, mes, 1, hora, minuto)

            tipo = rng.choice(tipos_interaccion, p=tipos_probs)

            # Valor según tipo
            if tipo == "valoracion":
                valor = float(np.clip(rng.normal(4.0, 0.7), 1.0, 5.0))
                valor = round(valor, 1)
            elif tipo == "reserva":
                if destino in paquetes_por_destino and paquetes_por_destino[destino]:
                    paq = rng.choice(paquetes_por_destino[destino])
                    valor = paq["precio"] if paq["precio"] else rng.uniform(500, 2500)
                else:
                    valor = float(round(rng.lognormal(7.0, 0.4), 2))
            else:
                valor = 1.0

            # Elegir paquete asociado
            if destino in paquetes_por_destino and paquetes_por_destino[destino]:
                paq = rng.choice(paquetes_por_destino[destino])
                id_paquete = paq["id_paquete"]
            else:
                id_paquete = hashlib.md5(
                    f"paq_{destino}_{rng.integers(0, 100)}".encode()
                ).hexdigest()[:36]

            interacciones.append({
                "id_interaccion": str(uuid.uuid4()),
                "id_usuario": usuario["id_usuario"],
                "id_paquete": id_paquete,
                "tipo": tipo,
                "valor": valor,
                "timestamp_interaccion": timestamp.isoformat(),
            })

        if (i + 1) % 500 == 0:
            logger.info(f"  Procesados {i + 1}/{n_usuarios} usuarios "
                       f"({len(interacciones)} interacciones generadas)")

    return interacciones


# ---------------------------------------------------------------------------
# Inserción en BD
# ---------------------------------------------------------------------------

def insertar_usuarios(conn: sqlite3.Connection, usuarios: list[dict]) -> int:
    """Inserta usuarios verificando que no existan duplicados por ID."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id_usuario TEXT PRIMARY KEY,
            es_sintetico INTEGER NOT NULL DEFAULT 1,
            pref_cultura REAL NOT NULL DEFAULT 0.0,
            pref_gastronomia REAL NOT NULL DEFAULT 0.0,
            pref_naturaleza REAL NOT NULL DEFAULT 0.0,
            pref_playa REAL NOT NULL DEFAULT 0.0,
            pref_bienestar REAL NOT NULL DEFAULT 0.0,
            pref_aventura REAL NOT NULL DEFAULT 0.0,
            presupuesto_min_eur REAL,
            presupuesto_max_eur REAL,
            duracion_min_dias INTEGER,
            duracion_max_dias INTEGER,
            temporada_preferida TEXT,
            requiere_accesibilidad INTEGER NOT NULL DEFAULT 0,
            distancia_max_km REAL,
            interes_sostenibilidad REAL NOT NULL DEFAULT 0.0,
            mercado TEXT,
            fecha_creacion TEXT,
            seed_generacion INTEGER
        )
    """)
    conn.commit()

    insertados = 0
    for u in usuarios:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO usuarios
                (id_usuario, es_sintetico, pref_cultura, pref_gastronomia,
                 pref_naturaleza, pref_playa, pref_bienestar, pref_aventura,
                 presupuesto_min_eur, presupuesto_max_eur, duracion_min_dias,
                 duracion_max_dias, temporada_preferida, requiere_accesibilidad,
                 distancia_max_km, interes_sostenibilidad, mercado,
                 fecha_creacion, seed_generacion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                u["id_usuario"], u["es_sintetico"],
                u["pref_cultura"], u["pref_gastronomia"],
                u["pref_naturaleza"], u["pref_playa"],
                u["pref_bienestar"], u["pref_aventura"],
                u["presupuesto_min_eur"], u["presupuesto_max_eur"],
                u["duracion_min_dias"], u["duracion_max_dias"],
                u["temporada_preferida"], u["requiere_accesibilidad"],
                u["distancia_max_km"], u["interes_sostenibilidad"],
                u["mercado"], u["fecha_creacion"], u["seed_generacion"]
            ))
            insertados += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    return insertados


def insertar_interacciones(conn: sqlite3.Connection, interacciones: list[dict],
                           batch_size: int = 5000) -> int:
    """Inserta interacciones en batches para eficiencia."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS interacciones (
            id_interaccion TEXT PRIMARY KEY,
            id_usuario TEXT NOT NULL,
            id_paquete TEXT NOT NULL,
            tipo TEXT NOT NULL,
            valor REAL,
            timestamp_interaccion TEXT NOT NULL
        )
    """)
    conn.commit()

    insertados = 0
    for i in range(0, len(interacciones), batch_size):
        batch = interacciones[i:i + batch_size]
        for inter in batch:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO interacciones
                    (id_interaccion, id_usuario, id_paquete, tipo, valor,
                     timestamp_interaccion)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    inter["id_interaccion"], inter["id_usuario"],
                    inter["id_paquete"], inter["tipo"], inter["valor"],
                    inter["timestamp_interaccion"]
                ))
                insertados += 1
            except sqlite3.IntegrityError:
                pass

        conn.commit()
        if (i + batch_size) % 25000 == 0:
            logger.info(f"  Insertadas {min(i + batch_size, len(interacciones))}"
                       f"/{len(interacciones)} interacciones")

    return insertados


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Genera interacciones realistas basadas en estacionalidad real"
    )
    parser.add_argument(
        "--db-indicadores", type=str, default="data/tui_recomendador.db",
        help="BD con indicadores y clima (default: data/tui_recomendador.db)"
    )
    parser.add_argument(
        "--db-destino", type=str, default="data/sample_tui.db",
        help="BD destino con paquetes/usuarios/interacciones (default: data/sample_tui.db)"
    )
    parser.add_argument(
        "--usuarios", type=int, default=5000,
        help="Número de usuarios a generar (default: 5000)"
    )
    parser.add_argument(
        "--interacciones", type=int, default=150000,
        help="Número de interacciones a generar (default: 150000)"
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    db_indicadores_path = project_root / args.db_indicadores
    db_destino_path = project_root / args.db_destino

    if not db_destino_path.parent.exists():
        logger.error(f"Directorio no encontrado: {db_destino_path.parent}")
        sys.exit(1)

    print("=" * 70)
    print("GENERACIÓN DE INTERACCIONES REALISTAS")
    print("=" * 70)
    print(f"BD indicadores (lectura): {db_indicadores_path}")
    print(f"BD destino (escritura):   {db_destino_path}")
    print(f"Usuarios a generar:       {args.usuarios}")
    print(f"Interacciones a generar:  {args.interacciones}")
    print(f"Seed: {SEED}")
    print()

    # Inicializar RNG con seed fija
    rng = np.random.default_rng(SEED)

    # 1. Cargar datos de estacionalidad real
    print("[1/5] Cargando estacionalidad real desde indicadores_destino...")
    estacionalidad_real = cargar_estacionalidad_real(db_indicadores_path)
    if estacionalidad_real:
        print(f"  ✓ Datos de estacionalidad para {len(estacionalidad_real)} destinos")
    else:
        print("  ⚠ Sin datos reales, usando estacionalidad por defecto")

    # 2. Cargar clima
    print("[2/5] Cargando datos climáticos...")
    clima = cargar_clima(db_indicadores_path)
    if clima:
        print(f"  ✓ Datos climáticos para {len(clima)} destinos")
    else:
        print("  ⚠ Sin datos climáticos, usando fallback")

    # 3. Cargar paquetes existentes
    print("[3/5] Cargando paquetes existentes de sample_tui.db...")
    paquetes = cargar_paquetes_existentes(db_destino_path)
    print(f"  ✓ {len(paquetes)} paquetes cargados")

    # 4. Generar usuarios
    print(f"[4/5] Generando {args.usuarios} usuarios con perfiles coherentes...")
    usuarios = generar_usuarios(args.usuarios, rng)
    print(f"  ✓ {len(usuarios)} usuarios generados")

    # Estadísticas de usuarios
    mercados = {}
    for u in usuarios:
        m = u["mercado"]
        mercados[m] = mercados.get(m, 0) + 1
    print(f"  Distribución mercados: {mercados}")

    # 5. Generar interacciones
    print(f"[5/5] Generando {args.interacciones} interacciones realistas...")
    interacciones = generar_interacciones(
        usuarios, paquetes, estacionalidad_real, clima,
        args.interacciones, rng
    )
    print(f"  ✓ {len(interacciones)} interacciones generadas")

    # Estadísticas de interacciones
    tipos_count = {}
    for inter in interacciones:
        tipos_count[inter["tipo"]] = tipos_count.get(inter["tipo"], 0) + 1
    print(f"  Tipos: {tipos_count}")

    # Insertar en BD (SIN borrar lo existente)
    print()
    print("Insertando en base de datos (sin borrar datos previos)...")
    conn = sqlite3.connect(str(db_destino_path))

    try:
        n_usuarios_prev = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
        n_inter_prev = conn.execute("SELECT COUNT(*) FROM interacciones").fetchone()[0]
    except sqlite3.OperationalError:
        n_usuarios_prev = 0
        n_inter_prev = 0

    print(f"  Datos previos: {n_usuarios_prev} usuarios, {n_inter_prev} interacciones")

    print("  Insertando usuarios...")
    n_usuarios_ok = insertar_usuarios(conn, usuarios)
    print(f"  ✓ {n_usuarios_ok} usuarios insertados")

    print("  Insertando interacciones (esto puede tardar ~30s)...")
    n_inter_ok = insertar_interacciones(conn, interacciones)
    print(f"  ✓ {n_inter_ok} interacciones insertadas")

    try:
        n_usuarios_total = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
        n_inter_total = conn.execute("SELECT COUNT(*) FROM interacciones").fetchone()[0]
    except sqlite3.OperationalError:
        n_usuarios_total = n_usuarios_ok
        n_inter_total = n_inter_ok

    conn.close()

    # Resumen final
    print()
    print("=" * 70)
    print("RESUMEN FINAL")
    print("=" * 70)
    print(f"✓ Usuarios:       {n_usuarios_ok} nuevos (total en BD: {n_usuarios_total})")
    print(f"✓ Interacciones:  {n_inter_ok} nuevas (total en BD: {n_inter_total})")
    print(f"  Previamente existían: {n_usuarios_prev} usuarios, {n_inter_prev} interacciones")
    print()
    print("Distribución de interacciones por tipo:")
    for tipo, count in sorted(tipos_count.items()):
        pct = count / len(interacciones) * 100
        print(f"  - {tipo}: {count} ({pct:.1f}%)")
    print()
    print("Distribución de mercados de usuarios:")
    for mercado, count in sorted(mercados.items()):
        pct = count / len(usuarios) * 100
        print(f"  - {mercado}: {count} ({pct:.1f}%)")
    print()
    print(f"✓ Datos guardados en: {db_destino_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
