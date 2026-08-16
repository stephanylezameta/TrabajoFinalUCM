"""
Generador de ~150.000 reservas de clientes para la tabla `customer_bookings`.

Genera reservas sintéticas con distribuciones realistas de canales, países,
idiomas, grupos de edad y estacionalidad, basándose en el catálogo de
experiencias existente en la tabla `experiencias`.

Inserta en `data/tui_recomendador.db` tabla `customer_bookings`.
NO borra datos existentes. Usa INSERT OR IGNORE para idempotencia.
Seed=42 para reproducibilidad.

Ejecución:
    cd /d D:\\Master\\TrabajoFinalUCM\\TFM
    python scripts/generate_customer_bookings.py
    python scripts/generate_customer_bookings.py --db data/tui_recomendador.db --total 150000
    python scripts/generate_customer_bookings.py --help
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

# Asegurar imports del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

SEED = 42

# Canales de compra y sus pesos
SOURCE_CHANNELS = ["Web", "Mobile", "Travel Agent", "Phone", "Partner"]
SOURCE_CHANNEL_WEIGHTS = [0.35, 0.30, 0.15, 0.10, 0.10]

# Países de origen y sus pesos
COUNTRIES = [
    "Spain", "Germany", "United Kingdom", "France", "Netherlands",
    "Italy", "Sweden", "Belgium", "Switzerland", "Portugal",
    "Austria", "Denmark", "Norway", "Ireland", "Poland",
]
COUNTRY_WEIGHTS = [
    0.22, 0.18, 0.14, 0.09, 0.07,
    0.06, 0.04, 0.04, 0.03, 0.03,
    0.03, 0.02, 0.02, 0.02, 0.01,
]

# Mapeo país → idioma
COUNTRY_LANGUAGE = {
    "Spain": "Spanish",
    "Germany": "German",
    "United Kingdom": "English",
    "France": "French",
    "Netherlands": "Dutch",
    "Italy": "Italian",
    "Sweden": "English",
    "Belgium": "French",
    "Switzerland": "German",
    "Portugal": "Spanish",
    "Austria": "German",
    "Denmark": "English",
    "Norway": "English",
    "Ireland": "English",
    "Poland": "English",
}

# Grupos de edad y sus pesos
AGE_GROUPS = ["18-25", "26-35", "36-45", "46-55", "56-65", "65+"]
AGE_GROUP_WEIGHTS = [0.10, 0.25, 0.25, 0.20, 0.12, 0.08]

# Popularidad extra por destino (multiplicador para destinos top)
DESTINATION_POPULARITY = {
    "Barcelona": 3.0,
    "Mallorca": 2.8,
    "Tenerife": 2.5,
    "Ibiza": 2.2,
    "Costa del Sol": 2.0,
    "Madrid": 1.8,
    "Gran Canaria": 1.7,
    "Cancún": 1.6,
    "Punta Cana": 1.5,
    "Dubái": 1.5,
    "Riviera Maya": 1.4,
    "Málaga": 1.3,
    "Valencia": 1.3,
    "Alicante": 1.2,
    "Sevilla": 1.2,
}

# Rango de fechas de booking
BOOKING_DATE_START = datetime(2022, 1, 1)
BOOKING_DATE_END = datetime(2025, 6, 30)
BOOKING_DATE_RANGE_DAYS = (BOOKING_DATE_END - BOOKING_DATE_START).days

# Probabilidad de dejar reseña
REVIEW_PROBABILITY = 0.35

# Probabilidad de repetir mismo destino
SAME_DESTINATION_PROBABILITY = 0.30

# Parámetros para número de bookings por cliente (negativa binomial)
NB_N = 5       # número de éxitos
NB_P = 0.25    # probabilidad de éxito

# Número base de clientes
NUM_CUSTOMERS_BASE = 10000

# IDs iniciales
CUSTOMER_ID_START = 1000000
BOOKING_ID_START = 3000000

# Batch size para inserción
BATCH_SIZE = 10000


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def cargar_experiencias(db_path: str) -> list[dict]:
    """Carga experiencias desde la base de datos."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT experience_id, destination, price_eur, monthly_availability
        FROM experiencias
    """)

    experiencias = []
    for row in cursor.fetchall():
        experiencias.append({
            "experience_id": row["experience_id"],
            "destination": row["destination"],
            "price_eur": row["price_eur"],
            "monthly_availability": json.loads(row["monthly_availability"]),
        })

    conn.close()
    return experiencias


def construir_indice_por_destino(experiencias: list[dict]) -> dict:
    """Construye un índice de experiencias agrupadas por destino."""
    por_destino = {}
    for exp in experiencias:
        dest = exp["destination"]
        if dest not in por_destino:
            por_destino[dest] = []
        por_destino[dest].append(exp)
    return por_destino


def calcular_pesos_destino(experiencias: list[dict]) -> tuple[list[str], np.ndarray]:
    """Calcula pesos de selección de destino basados en popularidad y volumen."""
    # Contar experiencias por destino
    conteo = {}
    for exp in experiencias:
        dest = exp["destination"]
        conteo[dest] = conteo.get(dest, 0) + 1

    destinos = list(conteo.keys())
    pesos = np.array([
        conteo[d] * DESTINATION_POPULARITY.get(d, 1.0)
        for d in destinos
    ], dtype=np.float64)

    # Normalizar
    pesos /= pesos.sum()
    return destinos, pesos


def seleccionar_experiencia_por_mes(
    rng: np.random.Generator,
    experiencias_destino: list[dict],
    mes: int,
) -> dict:
    """Selecciona una experiencia del destino ponderada por disponibilidad mensual."""
    # Obtener disponibilidad del mes para cada experiencia
    disponibilidades = np.array([
        exp["monthly_availability"][mes]
        for exp in experiencias_destino
    ], dtype=np.float64)

    # Normalizar pesos
    total = disponibilidades.sum()
    if total == 0:
        # Fallback: selección uniforme
        return experiencias_destino[rng.integers(0, len(experiencias_destino))]

    pesos = disponibilidades / total
    idx = rng.choice(len(experiencias_destino), p=pesos)
    return experiencias_destino[idx]


def generar_bookings(
    rng: np.random.Generator,
    experiencias: list[dict],
    total_objetivo: int,
) -> list[dict]:
    """Genera reservas de clientes."""

    # Preparar índices
    por_destino = construir_indice_por_destino(experiencias)
    destinos, pesos_destino = calcular_pesos_destino(experiencias)

    # Generar clientes y sus número de bookings
    # Usamos negativa binomial para distribución realista
    bookings_por_cliente = rng.negative_binomial(NB_N, NB_P, size=NUM_CUSTOMERS_BASE)
    # Clamp entre 5 y 30
    bookings_por_cliente = np.clip(bookings_por_cliente, 5, 30)

    # Ajustar número de clientes para alcanzar el total objetivo
    total_estimado = bookings_por_cliente.sum()
    if total_estimado < total_objetivo:
        # Agregar más clientes si es necesario
        extra_needed = total_objetivo - total_estimado
        avg_bookings = bookings_por_cliente.mean()
        extra_customers = int(np.ceil(extra_needed / avg_bookings))
        extra_bookings = rng.negative_binomial(NB_N, NB_P, size=extra_customers)
        extra_bookings = np.clip(extra_bookings, 5, 30)
        bookings_por_cliente = np.concatenate([bookings_por_cliente, extra_bookings])

    # Truncar para no pasarnos mucho del objetivo
    cumsum = np.cumsum(bookings_por_cliente)
    num_clientes = int(np.searchsorted(cumsum, total_objetivo, side="right")) + 1
    num_clientes = min(num_clientes, len(bookings_por_cliente))
    bookings_por_cliente = bookings_por_cliente[:num_clientes]

    print(f"         → Clientes generados: {num_clientes:,}")
    print(f"         → Bookings estimados: {int(bookings_por_cliente.sum()):,}")

    # Generar bookings
    all_bookings = []
    booking_counter = BOOKING_ID_START

    for i in range(num_clientes):
        customer_id = f"CUST_{CUSTOMER_ID_START + i:07d}"
        n_bookings = int(bookings_por_cliente[i])

        # Atributos fijos del cliente
        country = rng.choice(COUNTRIES, p=COUNTRY_WEIGHTS)
        language = COUNTRY_LANGUAGE[country]
        age_group = rng.choice(AGE_GROUPS, p=AGE_GROUP_WEIGHTS)

        # Destino "favorito" del cliente (coherencia)
        destino_favorito = rng.choice(destinos, p=pesos_destino)

        for j in range(n_bookings):
            # Decidir destino: 30% probabilidad de repetir favorito
            if j > 0 and rng.random() < SAME_DESTINATION_PROBABILITY:
                destino_elegido = destino_favorito
            else:
                destino_elegido = rng.choice(destinos, p=pesos_destino)
                if j == 0:
                    destino_favorito = destino_elegido

            # Generar fechas
            booking_offset = rng.integers(0, BOOKING_DATE_RANGE_DAYS)
            booking_date = BOOKING_DATE_START + timedelta(days=int(booking_offset))
            travel_offset = rng.integers(14, 181)  # 14 a 180 días después
            travel_date = booking_date + timedelta(days=int(travel_offset))

            # Mes del travel_date para estacionalidad (0-indexed)
            travel_month = travel_date.month - 1

            # Seleccionar experiencia ponderada por estacionalidad
            experiencias_dest = por_destino.get(destino_elegido, [])
            if not experiencias_dest:
                continue

            experiencia = seleccionar_experiencia_por_mes(
                rng, experiencias_dest, travel_month
            )

            # Precio con variación ±15%
            price_factor = rng.uniform(0.85, 1.15)
            price_paid = round(experiencia["price_eur"] * price_factor, 2)

            # Canal de compra
            source_channel = rng.choice(SOURCE_CHANNELS, p=SOURCE_CHANNEL_WEIGHTS)

            # Reseña
            left_review = int(rng.random() < REVIEW_PROBABILITY)

            # Booking ID
            booking_id = f"BOOK_{booking_counter:07d}"
            booking_counter += 1

            all_bookings.append({
                "booking_id": booking_id,
                "customer_id": customer_id,
                "experience_id": experiencia["experience_id"],
                "booking_date": booking_date.strftime("%Y-%m-%d"),
                "travel_date": travel_date.strftime("%Y-%m-%d"),
                "price_paid_eur": price_paid,
                "source_channel": source_channel,
                "country": country,
                "language": language,
                "age_group": age_group,
                "left_review": left_review,
            })

        # Progreso
        if len(all_bookings) >= 25000 and len(all_bookings) % 25000 < n_bookings:
            print(f"         → Progreso: {len(all_bookings):,} reservas generadas...")

    # Truncar al total objetivo si nos pasamos
    if len(all_bookings) > total_objetivo:
        all_bookings = all_bookings[:total_objetivo]

    return all_bookings


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS customer_bookings (
    booking_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    experience_id TEXT NOT NULL,
    booking_date TEXT NOT NULL,
    travel_date TEXT NOT NULL,
    price_paid_eur REAL NOT NULL,
    source_channel TEXT NOT NULL,
    country TEXT NOT NULL,
    language TEXT NOT NULL,
    age_group TEXT NOT NULL,
    left_review INTEGER NOT NULL DEFAULT 0
);
"""

INSERT_SQL = """
INSERT OR IGNORE INTO customer_bookings (
    booking_id, customer_id, experience_id, booking_date,
    travel_date, price_paid_eur, source_channel, country,
    language, age_group, left_review
) VALUES (
    :booking_id, :customer_id, :experience_id, :booking_date,
    :travel_date, :price_paid_eur, :source_channel, :country,
    :language, :age_group, :left_review
);
"""


def insertar_bookings(db_path: str, bookings: list[dict]) -> dict:
    """Inserta bookings en la base de datos en batches. Retorna estadísticas."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Crear tabla si no existe
    cursor.execute(CREATE_TABLE_SQL)

    # Contar registros antes
    cursor.execute("SELECT COUNT(*) FROM customer_bookings")
    count_before = cursor.fetchone()[0]

    # Insertar en batches
    total_batches = (len(bookings) + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(0, len(bookings), BATCH_SIZE):
        batch = bookings[i:i + BATCH_SIZE]
        cursor.executemany(INSERT_SQL, batch)
        conn.commit()
        batch_num = (i // BATCH_SIZE) + 1
        if batch_num % 5 == 0 or batch_num == total_batches:
            print(f"         → Batch {batch_num}/{total_batches} insertado")

    # Contar registros después
    cursor.execute("SELECT COUNT(*) FROM customer_bookings")
    count_after = cursor.fetchone()[0]

    insertados = count_after - count_before
    duplicados = len(bookings) - insertados

    # Distribución de canales
    cursor.execute("""
        SELECT source_channel, COUNT(*) as total
        FROM customer_bookings
        GROUP BY source_channel
        ORDER BY total DESC
    """)
    dist_canales = cursor.fetchall()

    # Distribución de países top 5
    cursor.execute("""
        SELECT country, COUNT(*) as total
        FROM customer_bookings
        GROUP BY country
        ORDER BY total DESC
        LIMIT 5
    """)
    top5_paises = cursor.fetchall()

    # Porcentaje con reseña
    cursor.execute("""
        SELECT
            SUM(left_review) as con_review,
            COUNT(*) as total
        FROM customer_bookings
    """)
    review_row = cursor.fetchone()
    pct_review = (review_row[0] / review_row[1] * 100) if review_row[1] > 0 else 0

    conn.close()

    return {
        "total_generadas": len(bookings),
        "insertadas": insertados,
        "duplicadas": duplicados,
        "total_en_tabla": count_after,
        "dist_canales": dist_canales,
        "top5_paises": top5_paises,
        "pct_review": pct_review,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Genera ~150.000 reservas de clientes sintéticas en la tabla `customer_bookings`."
    )
    parser.add_argument(
        "--db",
        type=str,
        default="data/tui_recomendador.db",
        help="Ruta a la base de datos SQLite (default: data/tui_recomendador.db)",
    )
    parser.add_argument(
        "--total",
        type=int,
        default=150000,
        help="Número total objetivo de reservas a generar (default: 150000)",
    )
    args = parser.parse_args()

    # Resolver ruta relativa al directorio del proyecto
    db_path = Path(args.db)
    if not db_path.is_absolute():
        project_root = Path(__file__).resolve().parent.parent
        db_path = project_root / db_path

    # Verificar que el directorio padre existe
    db_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  GENERADOR DE RESERVAS DE CLIENTES")
    print("=" * 60)
    print(f"\n  Base de datos: {db_path}")
    print(f"  Total objetivo: {args.total:,} reservas")
    print(f"  Seed: {SEED}")
    print()

    # Cargar experiencias existentes
    print("  [1/3] Cargando catálogo de experiencias...")
    experiencias = cargar_experiencias(str(db_path))
    if not experiencias:
        print("\n  ERROR: No se encontraron experiencias en la base de datos.")
        print("  Ejecuta primero: python scripts/generate_experiences_catalog.py")
        sys.exit(1)
    print(f"         → {len(experiencias):,} experiencias cargadas")
    destinos_unicos = set(exp["destination"] for exp in experiencias)
    print(f"         → {len(destinos_unicos)} destinos disponibles")

    # Generar bookings
    print("\n  [2/3] Generando reservas...")
    rng = np.random.default_rng(SEED)
    bookings = generar_bookings(rng, experiencias, args.total)
    print(f"         → {len(bookings):,} reservas generadas")

    # Insertar en BD
    print("\n  [3/3] Insertando en base de datos (batches de {:,})...".format(BATCH_SIZE))
    stats = insertar_bookings(str(db_path), bookings)

    # Resumen final
    print("\n" + "=" * 60)
    print("  RESUMEN")
    print("=" * 60)
    print(f"\n  Total generadas:       {stats['total_generadas']:>8,}")
    print(f"  Insertadas (nuevas):   {stats['insertadas']:>8,}")
    print(f"  Duplicadas (ignoradas):{stats['duplicadas']:>8,}")
    print(f"  Total en tabla:        {stats['total_en_tabla']:>8,}")

    print(f"\n  % con reseña: {stats['pct_review']:.1f}%")

    print("\n  Distribución de canales:")
    for canal, total in stats["dist_canales"]:
        pct = total / stats["total_en_tabla"] * 100
        print(f"    - {canal:<15} {total:>7,}  ({pct:.1f}%)")

    print("\n  Top 5 países:")
    for pais, total in stats["top5_paises"]:
        pct = total / stats["total_en_tabla"] * 100
        print(f"    - {pais:<20} {total:>7,}  ({pct:.1f}%)")

    print("\n" + "=" * 60)
    print("  ✓ Proceso completado exitosamente")
    print("=" * 60)


if __name__ == "__main__":
    main()
