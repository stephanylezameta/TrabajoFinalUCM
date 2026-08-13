"""
Generador de ~6.000 experiencias turísticas para la tabla `experiencias`.

Genera experiencias sintéticas con distribuciones realistas de precio,
duración, rating y estacionalidad para 39 destinos y 10 categorías.

Inserta en `data/tui_recomendador.db` tabla `experiencias`.
NO borra datos existentes. Usa INSERT OR IGNORE para idempotencia.
Seed=42 para reproducibilidad.

Ejecución:
    cd /d D:\\Master\\TrabajoFinalUCM\\TFM
    python scripts/generate_experiences_catalog.py
    python scripts/generate_experiences_catalog.py --db data/tui_recomendador.db
    python scripts/generate_experiences_catalog.py --help
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

# Asegurar imports del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

SEED = 42

CATEGORIAS = [
    "Excursions & Day Trips",
    "Attractions & Guided Tours",
    "Water Activities",
    "Food & Drink Experiences",
    "Cultural Experiences",
    "Adventure & Outdoor",
    "Wellness & Spa",
    "Night Tours & Entertainment",
    "Local Experiences",
    "Transport & Transfers",
]

DESTINOS = [
    "Mallorca", "Tenerife", "Ibiza", "Costa del Sol", "Barcelona",
    "Madrid", "Málaga", "Sevilla", "Valencia", "Gran Canaria",
    "Alicante", "Bilbao", "San Sebastián", "Córdoba", "Granada",
    "Cádiz", "Fuerteventura", "Lanzarote", "Menorca", "Antalya",
    "Rodas", "Santorini", "Hurghada", "Punta Cana", "Cancún",
    "Riviera Maya", "Dubái", "Maldivas", "Bali", "Phuket",
    "Marrakech", "Cabo Verde", "Split", "Creta", "Sicilia",
    "Cerdeña", "Costa Amalfitana", "Algarve", "Túnez",
]

# Tipo de destino para estacionalidad
DESTINOS_TIPO = {
    "Mallorca": "playa_europa", "Tenerife": "tropical", "Ibiza": "playa_europa",
    "Costa del Sol": "playa_europa", "Barcelona": "cultural", "Madrid": "cultural",
    "Málaga": "playa_europa", "Sevilla": "cultural", "Valencia": "playa_europa",
    "Gran Canaria": "tropical", "Alicante": "playa_europa", "Bilbao": "cultural",
    "San Sebastián": "cultural", "Córdoba": "cultural", "Granada": "cultural",
    "Cádiz": "playa_europa", "Fuerteventura": "tropical", "Lanzarote": "tropical",
    "Menorca": "playa_europa", "Antalya": "playa_europa", "Rodas": "playa_europa",
    "Santorini": "playa_europa", "Hurghada": "tropical", "Punta Cana": "tropical",
    "Cancún": "tropical", "Riviera Maya": "tropical", "Dubái": "tropical",
    "Maldivas": "tropical", "Bali": "tropical", "Phuket": "tropical",
    "Marrakech": "cultural", "Cabo Verde": "tropical", "Split": "playa_europa",
    "Creta": "playa_europa", "Sicilia": "playa_europa", "Cerdeña": "playa_europa",
    "Costa Amalfitana": "playa_europa", "Algarve": "playa_europa", "Túnez": "playa_europa",
}

# Factor de precio por destino
FACTOR_PRECIO_DESTINO = {
    "Dubái": 2.5, "Maldivas": 3.0, "Bali": 0.7, "Marrakech": 0.6, "Túnez": 0.5,
    "Phuket": 0.7, "Hurghada": 0.6, "Cabo Verde": 0.8, "Punta Cana": 1.2,
    "Cancún": 1.3, "Riviera Maya": 1.2, "Antalya": 0.7,
}

# Precio base medio por categoría
PRECIO_BASE = {
    "Excursions & Day Trips": 80,
    "Attractions & Guided Tours": 35,
    "Water Activities": 60,
    "Food & Drink Experiences": 50,
    "Cultural Experiences": 30,
    "Adventure & Outdoor": 90,
    "Wellness & Spa": 70,
    "Night Tours & Entertainment": 40,
    "Local Experiences": 45,
    "Transport & Transfers": 25,
}

# Duración (min, max) en horas por categoría
DURACION_RANGO = {
    "Excursions & Day Trips": (4.0, 10.0),
    "Attractions & Guided Tours": (2.0, 5.0),
    "Water Activities": (1.5, 4.0),
    "Food & Drink Experiences": (2.0, 4.0),
    "Cultural Experiences": (1.5, 3.0),
    "Adventure & Outdoor": (3.0, 8.0),
    "Wellness & Spa": (1.0, 3.0),
    "Night Tours & Entertainment": (2.0, 5.0),
    "Local Experiences": (2.0, 4.0),
    "Transport & Transfers": (0.5, 2.0),
}

# Features posibles
FEATURES_POOL = [
    "Skip-the-line", "Wheelchair accessible", "Free cancellation",
    "Mobile ticket", "Instant confirmation", "Small group",
    "Private tour", "Hotel pickup", "Audio guide", "Professional guide",
]

# Estacionalidad mensual (ene-dic) base ~50, pico ~200
ESTACIONALIDAD = {
    "playa_europa": [30, 35, 50, 80, 120, 180, 200, 200, 150, 80, 40, 35],
    "cultural": [60, 65, 80, 150, 180, 130, 120, 110, 170, 160, 80, 70],
    "tropical": [180, 170, 150, 100, 70, 50, 45, 50, 60, 90, 160, 190],
}

# ---------------------------------------------------------------------------
# Templates de nombres por categoría
# ---------------------------------------------------------------------------

TEMPLATES = {
    "Excursions & Day Trips": [
        "Excursión a {lugar} desde {destino}",
        "Day trip to {lugar} desde {destino}",
        "Tour de un día por {zona} en {destino}",
        "Excursión en grupo a {lugar}",
        "Ruta panorámica por {zona} de {destino}",
        "Visita completa a {lugar} con transporte",
        "Excursión privada por {zona}",
    ],
    "Water Activities": [
        "Snorkel en {destino}",
        "Paseo en barco por la costa de {destino}",
        "Kayak en {playa} de {destino}",
        "Buceo de bautismo en {destino}",
        "Excursión en catamarán por {destino}",
        "Jet ski en {playa}",
        "Paddle surf en {destino}",
        "Tour en velero al atardecer",
        "Parasailing en {playa} de {destino}",
    ],
    "Food & Drink Experiences": [
        "Tour gastronómico por {barrio} de {destino}",
        "Clase de cocina {tipo} en {destino}",
        "Cata de vinos en {region}",
        "Ruta de tapas por {destino}",
        "Experiencia culinaria en mercado de {destino}",
        "Degustación de productos locales en {destino}",
        "Cena con espectáculo en {destino}",
        "Brunch gourmet con vistas en {destino}",
    ],
    "Cultural Experiences": [
        "Visita guiada a {monumento} de {destino}",
        "Free tour por el casco antiguo de {destino}",
        "Entrada a {museo} en {destino}",
        "Tour histórico por {destino}",
        "Visita a {monumento} con guía experto",
        "Recorrido cultural por {barrio} de {destino}",
        "Tour de arte urbano en {destino}",
        "Visita nocturna a {monumento}",
    ],
    "Adventure & Outdoor": [
        "Senderismo en {montaña} cerca de {destino}",
        "Quad por {zona} de {destino}",
        "Parapente en la costa de {destino}",
        "Barranquismo en {zona}",
        "Escalada guiada en {montaña}",
        "Tirolina sobre {zona} en {destino}",
        "Safari en 4x4 por {zona}",
        "Bicicleta de montaña en {destino}",
    ],
    "Wellness & Spa": [
        "Spa y hammam en {destino}",
        "Yoga al amanecer en {destino}",
        "Masaje balinés en {destino}",
        "Circuito termal completo en {destino}",
        "Retiro de bienestar en {destino}",
        "Sesión de meditación guiada",
        "Tratamiento facial premium en {destino}",
        "Experiencia relax con aromaterapia",
    ],
    "Night Tours & Entertainment": [
        "Pub crawl en {destino}",
        "Espectáculo flamenco en {destino}",
        "Crucero al atardecer en {destino}",
        "Tour nocturno por {destino}",
        "Show de cabaret en {destino}",
        "Noche de astronomía en {zona}",
        "Cena-espectáculo tradicional en {destino}",
        "Ruta de cócteles por {barrio} de {destino}",
    ],
    "Local Experiences": [
        "Taller de cerámica en {destino}",
        "Visita a mercado local de {destino}",
        "Experiencia con pescadores en {destino}",
        "Clase de baile tradicional en {destino}",
        "Taller de artesanía local en {destino}",
        "Día en una granja orgánica cerca de {destino}",
        "Encuentro con artesanos de {destino}",
        "Experiencia fotográfica por {destino}",
    ],
    "Transport & Transfers": [
        "Transfer aeropuerto-hotel en {destino}",
        "Alquiler de scooter en {destino}",
        "Bus turístico {destino}",
        "Transfer privado en {destino}",
        "Alquiler de bicicleta por {destino}",
        "Servicio de chofer por {destino}",
        "Transfer compartido aeropuerto {destino}",
        "Traslado al puerto de {destino}",
    ],
    "Attractions & Guided Tours": [
        "Entrada a {parque_tematico} en {destino}",
        "Ticket para {acuario} de {destino}",
        "Observatorio panorámico de {destino}",
        "Visita guiada premium por {destino}",
        "Entrada combinada museos de {destino}",
        "Tour en segway por {destino}",
        "Billete para noria de {destino}",
        "Entrada VIP a {parque_tematico}",
    ],
}

# Datos de relleno para templates
LUGARES = [
    "Sierra Norte", "Volcán Teide", "Cabo de Gata", "Montserrat",
    "Isla de Tabarca", "Cuevas del Drach", "Serra de Tramuntana",
    "Parque Nacional", "Cascadas del río", "Pueblo blanco",
    "Isla vecina", "Acantilados", "Reserva natural", "Lago interior",
]

ZONAS = [
    "la costa norte", "el interior", "la zona histórica", "las montañas",
    "el puerto", "la bahía", "el desierto", "la sierra", "el valle",
    "los viñedos", "la campiña", "las colinas",
]

PLAYAS = [
    "Playa Principal", "Playa del Norte", "Cala Azul", "Playa Dorada",
    "Playa Blanca", "Costa Sur", "Bahía Cristalina", "Cala Escondida",
]

BARRIOS = [
    "el centro", "el barrio antiguo", "la zona portuaria", "el ensanche",
    "el barrio bohemio", "la zona comercial", "el casco histórico",
]

MONUMENTOS = [
    "la Catedral", "el Alcázar", "la Fortaleza", "el Palacio Real",
    "las Murallas", "la Mezquita", "el Castillo", "la Basílica",
    "el Anfiteatro", "la Torre",
]

MUSEOS = [
    "Museo de Arte Moderno", "Museo Arqueológico", "Museo Marítimo",
    "Museo de Historia", "Galería Nacional", "Museo de Ciencias",
]

MONTANAS = [
    "Sierra Nevada", "Serra de Tramuntana", "Pirineos", "Atlas",
    "Montañas locales", "Volcán", "Cordillera costera",
]

REGIONES_VINO = [
    "la región vinícola", "los viñedos locales", "la bodega centenaria",
    "la ruta del vino", "la zona de denominación de origen",
]

TIPOS_COCINA = [
    "mediterránea", "tradicional", "fusion", "local",
    "de mercado", "vegana", "de autor",
]

PARQUES_TEMATICOS = [
    "Aquapark", "Parque Acuático", "Parque de Atracciones",
    "Zoo & Aquarium", "Parque Temático", "Mundo Marino",
]

ACUARIOS = [
    "Oceanario", "Acuario Municipal", "Sea Life", "Aquarium",
]


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def _generar_nombre(rng: np.random.Generator, categoria: str, destino: str) -> str:
    """Genera un nombre de actividad realista usando templates."""
    templates = TEMPLATES[categoria]
    template = rng.choice(templates)

    # Reemplazar placeholders
    nombre = template.replace("{destino}", destino)
    nombre = nombre.replace("{lugar}", rng.choice(LUGARES))
    nombre = nombre.replace("{zona}", rng.choice(ZONAS))
    nombre = nombre.replace("{playa}", rng.choice(PLAYAS))
    nombre = nombre.replace("{barrio}", rng.choice(BARRIOS))
    nombre = nombre.replace("{monumento}", rng.choice(MONUMENTOS))
    nombre = nombre.replace("{museo}", rng.choice(MUSEOS))
    nombre = nombre.replace("{montaña}", rng.choice(MONTANAS))
    nombre = nombre.replace("{region}", rng.choice(REGIONES_VINO))
    nombre = nombre.replace("{tipo}", rng.choice(TIPOS_COCINA))
    nombre = nombre.replace("{parque_tematico}", rng.choice(PARQUES_TEMATICOS))
    nombre = nombre.replace("{acuario}", rng.choice(ACUARIOS))

    return nombre


def _generar_duracion(rng: np.random.Generator, categoria: str) -> float:
    """Genera duración con distribución normal truncada dentro del rango."""
    lo, hi = DURACION_RANGO[categoria]
    media = (lo + hi) / 2
    std = (hi - lo) / 4  # ~95% dentro del rango
    valor = rng.normal(media, std)
    valor = np.clip(valor, lo, hi)
    return round(float(valor), 1)


def _generar_precio(rng: np.random.Generator, categoria: str, destino: str) -> float:
    """Genera precio con distribución lognormal ajustada por destino."""
    base = PRECIO_BASE[categoria]
    factor = FACTOR_PRECIO_DESTINO.get(destino, 1.0)

    # Lognormal: mu y sigma para que la media sea ~base
    mu = np.log(base) - 0.5 * 0.3**2
    sigma = 0.3
    precio = float(rng.lognormal(mu, sigma)) * factor
    # Clamp mínimo 5€
    precio = max(5.0, precio)
    return round(precio, 2)


def _generar_rating(rng: np.random.Generator) -> float:
    """Genera rating con distribución Beta(8,2) escalada a [2.5, 5.0]."""
    beta_val = rng.beta(8, 2)
    rating = 2.5 + beta_val * 2.5
    return round(float(rating), 1)


def _generar_review_count(rng: np.random.Generator) -> int:
    """Genera número de reviews con distribución lognormal."""
    valor = float(rng.lognormal(5, 1.2))
    valor = np.clip(valor, 10, 5000)
    return int(valor)


def _generar_features(rng: np.random.Generator) -> str:
    """Genera JSON list de 2-5 features aleatorias."""
    n = int(rng.integers(2, 6))  # 2 a 5
    features = rng.choice(FEATURES_POOL, size=n, replace=False).tolist()
    return json.dumps(features, ensure_ascii=False)


def _generar_monthly_availability(rng: np.random.Generator, destino: str) -> str:
    """Genera JSON list de 12 enteros con estacionalidad por tipo de destino."""
    tipo = DESTINOS_TIPO.get(destino, "cultural")
    base_pattern = ESTACIONALIDAD[tipo]

    # Añadir variabilidad individual (±20%)
    monthly = []
    for base_val in base_pattern:
        noise = rng.normal(1.0, 0.15)
        val = int(base_val * noise)
        val = max(10, val)
        monthly.append(val)

    return json.dumps(monthly)


# ---------------------------------------------------------------------------
# Generación principal
# ---------------------------------------------------------------------------

def generar_experiencias(rng: np.random.Generator) -> list[dict]:
    """Genera ~6000 experiencias (≈150 por destino)."""
    experiencias = []
    exp_counter = 100000

    experiencias_por_destino = 150

    for destino in DESTINOS:
        # Distribuir categorías: ~15 experiencias por categoría por destino
        for _ in range(experiencias_por_destino):
            categoria = rng.choice(CATEGORIAS)

            experience_id = f"EXP_{exp_counter:06d}"
            exp_counter += 1

            activity_name = _generar_nombre(rng, categoria, destino)
            duration_hrs = _generar_duracion(rng, categoria)
            price_eur = _generar_precio(rng, categoria, destino)
            rating = _generar_rating(rng)
            review_count = _generar_review_count(rng)
            main_features = _generar_features(rng)
            monthly_availability = _generar_monthly_availability(rng, destino)

            experiencias.append({
                "experience_id": experience_id,
                "activity_name": activity_name,
                "category": categoria,
                "destination": destino,
                "duration_hrs": duration_hrs,
                "price_eur": price_eur,
                "rating": rating,
                "review_count": review_count,
                "main_features": main_features,
                "monthly_availability": monthly_availability,
                "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

    return experiencias


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS experiencias (
    experience_id TEXT PRIMARY KEY,
    activity_name TEXT NOT NULL,
    category TEXT NOT NULL,
    destination TEXT NOT NULL,
    duration_hrs REAL,
    price_eur REAL,
    rating REAL,
    review_count INTEGER,
    main_features TEXT,
    monthly_availability TEXT,
    fecha_creacion TEXT NOT NULL
);
"""

INSERT_SQL = """
INSERT OR IGNORE INTO experiencias (
    experience_id, activity_name, category, destination,
    duration_hrs, price_eur, rating, review_count,
    main_features, monthly_availability, fecha_creacion
) VALUES (
    :experience_id, :activity_name, :category, :destination,
    :duration_hrs, :price_eur, :rating, :review_count,
    :main_features, :monthly_availability, :fecha_creacion
);
"""


def insertar_experiencias(db_path: str, experiencias: list[dict]) -> dict:
    """Inserta experiencias en la base de datos. Retorna estadísticas."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Crear tabla si no existe
    cursor.execute(CREATE_TABLE_SQL)

    # Contar registros antes
    cursor.execute("SELECT COUNT(*) FROM experiencias")
    count_before = cursor.fetchone()[0]

    # Insertar
    cursor.executemany(INSERT_SQL, experiencias)
    conn.commit()

    # Contar registros después
    cursor.execute("SELECT COUNT(*) FROM experiencias")
    count_after = cursor.fetchone()[0]

    insertados = count_after - count_before
    duplicados = len(experiencias) - insertados

    # Top 5 destinos por número de experiencias
    cursor.execute("""
        SELECT destination, COUNT(*) as total
        FROM experiencias
        GROUP BY destination
        ORDER BY total DESC
        LIMIT 5
    """)
    top5_destinos = cursor.fetchall()

    # Estadísticas por categoría
    cursor.execute("""
        SELECT category, COUNT(*) as total
        FROM experiencias
        GROUP BY category
        ORDER BY total DESC
    """)
    por_categoria = cursor.fetchall()

    conn.close()

    return {
        "total_generadas": len(experiencias),
        "insertadas": insertados,
        "duplicadas": duplicados,
        "total_en_tabla": count_after,
        "top5_destinos": top5_destinos,
        "por_categoria": por_categoria,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Genera ~6.000 experiencias turísticas sintéticas en la tabla `experiencias`."
    )
    parser.add_argument(
        "--db",
        type=str,
        default="data/tui_recomendador.db",
        help="Ruta a la base de datos SQLite (default: data/tui_recomendador.db)",
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
    print("  GENERADOR DE EXPERIENCIAS TURÍSTICAS")
    print("=" * 60)
    print(f"\n  Base de datos: {db_path}")
    print(f"  Destinos: {len(DESTINOS)}")
    print(f"  Categorías: {len(CATEGORIAS)}")
    print(f"  Experiencias objetivo: ~{len(DESTINOS) * 150}")
    print(f"  Seed: {SEED}")
    print()

    # Generar datos
    rng = np.random.default_rng(SEED)
    print("  [1/2] Generando experiencias...")
    experiencias = generar_experiencias(rng)
    print(f"         → {len(experiencias)} experiencias generadas")

    # Insertar en BD
    print("  [2/2] Insertando en base de datos...")
    stats = insertar_experiencias(str(db_path), experiencias)

    # Resumen
    print("\n" + "=" * 60)
    print("  RESUMEN")
    print("=" * 60)
    print(f"\n  Total generadas:    {stats['total_generadas']:>6,}")
    print(f"  Insertadas (nuevas): {stats['insertadas']:>6,}")
    print(f"  Duplicadas (ignoradas): {stats['duplicadas']:>6,}")
    print(f"  Total en tabla:     {stats['total_en_tabla']:>6,}")

    print("\n  Top 5 destinos:")
    for destino, total in stats["top5_destinos"]:
        print(f"    - {destino:<20} {total:>4} experiencias")

    print("\n  Por categoría:")
    for categoria, total in stats["por_categoria"]:
        print(f"    - {categoria:<35} {total:>4}")

    print("\n" + "=" * 60)
    print("  ✓ Proceso completado exitosamente")
    print("=" * 60)


if __name__ == "__main__":
    main()
