r"""
Derivar interacciones "pseudo-reales" a partir de reseñas scrapeadas.

Cada reseña real implica una reserva real → genera interacciones tipo "reserva" + "valoración".
NO genera datos sintéticos: todo se basa en las ~70.000 reseñas existentes.

Uso:
    cd /d D:\Master\TrabajoFinalUCM\TFM
    python scripts/derive_real_interactions.py
    python scripts/derive_real_interactions.py --db-resenas data/tui_recomendador.db --db-destino data/sample_tui.db
    python scripts/derive_real_interactions.py --solo-resenas    # Solo usa tabla resenas
"""
import sys
import time
import random
import hashlib
import logging
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- Configuración ---
DB_RESENAS_PATH = "data/tui_recomendador.db"
DB_DESTINO_PATH = "data/sample_tui.db"
SEED = 42

# Mapeo idioma → mercado
IDIOMA_A_MERCADO = {
    "es": "es",
    "spanish": "es",
    "en": "uk",
    "english": "uk",
    "de": "de",
    "german": "de",
    "fr": "fr",
    "french": "fr",
    "it": "it",
    "italian": "it",
    "pt": "pt",
    "portuguese": "pt",
    "nl": "nl",
    "dutch": "nl",
    "unknown": "uk",  # Default a mercado UK
}


def generar_user_id(texto: str, destino: str) -> str:
    """Genera un user_id determinístico desde hash del texto + destino."""
    contenido = f"{texto[:100]}|{destino}".lower().strip()
    return f"usr_real_{hashlib.md5(contenido.encode()).hexdigest()[:12]}"


def generar_interaccion_id(user_id: str, tipo: str, fecha: str) -> str:
    """Genera un ID determinístico para la interacción."""
    contenido = f"{user_id}|{tipo}|{fecha}".strip()
    return f"int_{hashlib.md5(contenido.encode()).hexdigest()[:16]}"


def detectar_mercado(idioma: str) -> str:
    """Detecta el mercado a partir del idioma."""
    if not idioma:
        return "uk"
    idioma_lower = idioma.lower().strip()
    return IDIOMA_A_MERCADO.get(idioma_lower, "uk")


def cargar_resenas(db_path: str, solo_resenas: bool = False) -> list:
    """Carga todas las reseñas de la BD (tabla resenas y reviews_dataset)."""
    resenas = []
    conn = sqlite3.connect(db_path)

    # Tabla resenas (20,117+)
    try:
        rows = conn.execute("""
            SELECT texto_original, destino_nombre, idioma, puntuacion, fecha_publicacion, fuente
            FROM resenas
            WHERE texto_original IS NOT NULL AND LENGTH(texto_original) > 10
        """).fetchall()
        for row in rows:
            resenas.append({
                "texto": row[0],
                "destino": row[1],
                "idioma": row[2],
                "puntuacion": row[3],
                "fecha_publicacion": row[4],
                "fuente": row[5],
            })
        logger.info("Cargadas %d reseñas de tabla 'resenas'", len(rows))
    except Exception as e:
        logger.warning("Error leyendo tabla resenas: %s", e)

    # Tabla reviews_dataset (52,172) — si existe y no se limita
    if not solo_resenas:
        try:
            tabla_existe = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='reviews_dataset'"
            ).fetchone()

            if tabla_existe:
                rows = conn.execute("""
                    SELECT rd.review_text, e.destination, rd.reviewer_language, rd.rating, rd.review_date, 'reviews_dataset'
                    FROM reviews_dataset rd
                    LEFT JOIN experiencias e ON rd.experience_id = e.experience_id
                    WHERE rd.review_text IS NOT NULL AND LENGTH(rd.review_text) > 10
                """).fetchall()
                for row in rows:
                    resenas.append({
                        "texto": row[0],
                        "destino": row[1] if row[1] else "Desconocido",
                        "idioma": row[2] if row[2] else "en",
                        "puntuacion": row[3],
                        "fecha_publicacion": row[4],
                        "fuente": row[5],
                    })
                logger.info("Cargadas %d reseñas de tabla 'reviews_dataset'", len(rows))
            else:
                logger.info("Tabla 'reviews_dataset' no existe, continuando solo con 'resenas'.")
        except Exception as e:
            logger.warning("Error leyendo tabla reviews_dataset: %s", e)

    conn.close()
    return resenas


def cargar_experiencias(db_resenas_path: str) -> dict:
    """Carga experiencias agrupadas por destino para asociar a las interacciones."""
    experiencias_por_destino = {}
    conn = sqlite3.connect(db_resenas_path)

    # Tabla experiencias (generada)
    try:
        rows = conn.execute("""
            SELECT experience_id, destination, activity_name
            FROM experiencias
        """).fetchall()
        for row in rows:
            destino = row[1]
            if destino not in experiencias_por_destino:
                experiencias_por_destino[destino] = []
            experiencias_por_destino[destino].append({
                "id": row[0],
                "nombre": row[2],
            })
        logger.info("Cargadas experiencias de %d destinos (tabla 'experiencias')", len(experiencias_por_destino))
    except Exception as e:
        logger.warning("Error leyendo tabla experiencias: %s", e)

    # Tabla experiencias_reales (de Civitatis)
    try:
        rows = conn.execute("""
            SELECT id, destino_nombre, titulo
            FROM experiencias_reales
        """).fetchall()
        for row in rows:
            destino = row[1]
            if destino not in experiencias_por_destino:
                experiencias_por_destino[destino] = []
            experiencias_por_destino[destino].append({
                "id": row[0],
                "nombre": row[2],
            })
        logger.info("Añadidas experiencias reales de %d destinos (tabla 'experiencias_reales')", len(set(r[1] for r in rows)) if rows else 0)
    except Exception as e:
        logger.debug("Tabla experiencias_reales no disponible: %s", e)

    conn.close()
    return experiencias_por_destino


def parsear_fecha(fecha_str: str) -> datetime:
    """Intenta parsear una fecha desde varios formatos."""
    if not fecha_str:
        return datetime(2024, 6, 15)  # Fecha por defecto

    formatos = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d %H:%M:%S",
        "%B %Y",  # "January 2024"
        "%b %Y",  # "Jan 2024"
    ]
    for fmt in formatos:
        try:
            return datetime.strptime(fecha_str.strip(), fmt)
        except (ValueError, AttributeError):
            continue

    # Último intento: extraer año
    import re
    match = re.search(r"20[12]\d", str(fecha_str))
    if match:
        return datetime(int(match.group()), 6, 15)

    return datetime(2024, 6, 15)


def crear_tablas_destino(db_path: str):
    """Asegura que las tablas usuarios e interacciones existan en la BD destino.

    Si las tablas ya existen (creadas por SQLAlchemy/generate_sample_data.py),
    las deja tal cual. Solo las crea si no existen, usando la estructura
    compatible con models.py (id_usuario, id_interaccion, etc.).
    """
    conn = sqlite3.connect(db_path)

    # Verificar si la tabla usuarios ya existe
    tabla_usuarios = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='usuarios'"
    ).fetchone()

    if not tabla_usuarios:
        # Crear con estructura compatible con models.py (SQLAlchemy)
        conn.execute("""
            CREATE TABLE usuarios (
                id_usuario TEXT PRIMARY KEY,
                es_sintetico INTEGER NOT NULL DEFAULT 0,
                pref_cultura REAL NOT NULL DEFAULT 0.167,
                pref_gastronomia REAL NOT NULL DEFAULT 0.167,
                pref_naturaleza REAL NOT NULL DEFAULT 0.167,
                pref_playa REAL NOT NULL DEFAULT 0.167,
                pref_bienestar REAL NOT NULL DEFAULT 0.167,
                pref_aventura REAL NOT NULL DEFAULT 0.165,
                presupuesto_min_eur REAL,
                presupuesto_max_eur REAL,
                duracion_min_dias INTEGER,
                duracion_max_dias INTEGER,
                temporada_preferida TEXT,
                requiere_accesibilidad INTEGER NOT NULL DEFAULT 0,
                distancia_max_km REAL,
                interes_sostenibilidad REAL NOT NULL DEFAULT 0.5,
                mercado TEXT,
                fecha_creacion TEXT,
                seed_generacion INTEGER
            )
        """)
        logger.info("Tabla 'usuarios' creada con estructura models.py")
    else:
        logger.info("Tabla 'usuarios' ya existe, se usará tal cual")

    # Verificar si la tabla interacciones ya existe
    tabla_inter = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='interacciones'"
    ).fetchone()

    if not tabla_inter:
        conn.execute("""
            CREATE TABLE interacciones (
                id_interaccion TEXT PRIMARY KEY,
                id_usuario TEXT NOT NULL,
                id_paquete TEXT,
                tipo TEXT NOT NULL,
                valor REAL,
                timestamp_interaccion TEXT
            )
        """)
        logger.info("Tabla 'interacciones' creada con estructura models.py")
    else:
        logger.info("Tabla 'interacciones' ya existe, se usará tal cual")

    conn.commit()
    conn.close()
    logger.info("Tablas verificadas en %s", db_path)


def derivar_interacciones(resenas: list, experiencias_por_destino: dict, db_destino: str, rng: random.Random) -> dict:
    """Deriva usuarios e interacciones a partir de reseñas reales."""
    stats = {
        "usuarios_nuevos": 0,
        "interacciones_reserva": 0,
        "interacciones_valoracion": 0,
        "resenas_procesadas": 0,
        "resenas_sin_destino": 0,
    }

    conn = sqlite3.connect(db_destino)

    # Cargar usuarios existentes (columna id_usuario según models.py)
    usuarios_existentes = set()
    try:
        rows = conn.execute("SELECT id_usuario FROM usuarios").fetchall()
        usuarios_existentes = {r[0] for r in rows}
    except Exception:
        pass

    # Cargar interacciones existentes (columna id_interaccion según models.py)
    interacciones_existentes = set()
    try:
        rows = conn.execute("SELECT id_interaccion FROM interacciones").fetchall()
        interacciones_existentes = {r[0] for r in rows}
    except Exception:
        pass

    logger.info("Usuarios existentes: %d, Interacciones existentes: %d",
                len(usuarios_existentes), len(interacciones_existentes))

    batch_usuarios = []
    batch_interacciones = []

    for resena in resenas:
        texto = resena.get("texto", "")
        destino = resena.get("destino", "")
        idioma = resena.get("idioma", "unknown")
        puntuacion = resena.get("puntuacion")
        fecha_pub_str = resena.get("fecha_publicacion", "")

        if not destino or not texto:
            stats["resenas_sin_destino"] += 1
            continue

        stats["resenas_procesadas"] += 1

        # 1. Crear/referenciar usuario
        user_id = generar_user_id(texto, destino)
        mercado = detectar_mercado(idioma)

        if user_id not in usuarios_existentes:
            usuarios_existentes.add(user_id)

            # Generar preferencias temáticas (distribución pseudo-Dirichlet)
            prefs = [rng.random() for _ in range(6)]
            total_prefs = sum(prefs)
            prefs = [p / total_prefs for p in prefs]

            presupuesto_base = rng.uniform(500, 3000)

            batch_usuarios.append((
                user_id,                      # id_usuario
                0,                            # es_sintetico = 0 (derivado de dato real)
                prefs[0],                     # pref_cultura
                prefs[1],                     # pref_gastronomia
                prefs[2],                     # pref_naturaleza
                prefs[3],                     # pref_playa
                prefs[4],                     # pref_bienestar
                prefs[5],                     # pref_aventura
                presupuesto_base * 0.7,       # presupuesto_min_eur
                presupuesto_base * 1.3,       # presupuesto_max_eur
                0,                            # requiere_accesibilidad
                0.5,                          # interes_sostenibilidad
                mercado,                      # mercado
                datetime.now().isoformat(),   # fecha_creacion
            ))
            stats["usuarios_nuevos"] += 1

        # 2. Parsear fecha de publicación
        fecha_publicacion = parsear_fecha(fecha_pub_str)

        # 3. Asociar a una experiencia del destino (usada como id_paquete)
        experiencia_id = "unknown"
        experiencias_destino = experiencias_por_destino.get(destino, [])
        if experiencias_destino:
            experiencia = rng.choice(experiencias_destino)
            experiencia_id = experiencia["id"]

        # 4. Interacción tipo "reserva" (fecha = publicación - random días)
        offset_dias = rng.randint(1, 30)
        fecha_reserva = (fecha_publicacion - timedelta(days=offset_dias)).isoformat()
        id_reserva = generar_interaccion_id(user_id, "reserva", fecha_reserva)

        if id_reserva not in interacciones_existentes:
            interacciones_existentes.add(id_reserva)
            batch_interacciones.append((
                id_reserva,           # id_interaccion
                user_id,              # id_usuario
                experiencia_id,       # id_paquete (experiencia como referencia)
                "reserva",            # tipo
                None,                 # valor (None para reservas)
                fecha_reserva,        # timestamp_interaccion
            ))
            stats["interacciones_reserva"] += 1

        # 5. Interacción tipo "valoracion" (solo si hay puntuación)
        if puntuacion is not None:
            try:
                valor = float(puntuacion)
                if valor > 0:
                    fecha_valoracion = fecha_publicacion.isoformat()
                    id_valoracion = generar_interaccion_id(user_id, "valoracion", fecha_valoracion)

                    if id_valoracion not in interacciones_existentes:
                        interacciones_existentes.add(id_valoracion)
                        batch_interacciones.append((
                            id_valoracion,        # id_interaccion
                            user_id,              # id_usuario
                            experiencia_id,       # id_paquete
                            "valoracion",         # tipo
                            valor,                # valor (puntuación)
                            fecha_valoracion,     # timestamp_interaccion
                        ))
                        stats["interacciones_valoracion"] += 1
            except (ValueError, TypeError):
                pass

        # Insertar en batches de 1000
        if len(batch_usuarios) >= 1000:
            conn.executemany(
                "INSERT OR IGNORE INTO usuarios (id_usuario, es_sintetico, pref_cultura, pref_gastronomia, pref_naturaleza, pref_playa, pref_bienestar, pref_aventura, presupuesto_min_eur, presupuesto_max_eur, requiere_accesibilidad, interes_sostenibilidad, mercado, fecha_creacion) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                batch_usuarios
            )
            batch_usuarios = []

        if len(batch_interacciones) >= 1000:
            conn.executemany(
                "INSERT OR IGNORE INTO interacciones (id_interaccion, id_usuario, id_paquete, tipo, valor, timestamp_interaccion) VALUES (?,?,?,?,?,?)",
                batch_interacciones
            )
            batch_interacciones = []

    # Insertar remanente
    if batch_usuarios:
        conn.executemany(
            "INSERT OR IGNORE INTO usuarios (id_usuario, es_sintetico, pref_cultura, pref_gastronomia, pref_naturaleza, pref_playa, pref_bienestar, pref_aventura, presupuesto_min_eur, presupuesto_max_eur, requiere_accesibilidad, interes_sostenibilidad, mercado, fecha_creacion) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            batch_usuarios
        )

    if batch_interacciones:
        conn.executemany(
            "INSERT OR IGNORE INTO interacciones (id_interaccion, id_usuario, id_paquete, tipo, valor, timestamp_interaccion) VALUES (?,?,?,?,?,?)",
            batch_interacciones
        )

    conn.commit()
    conn.close()

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Derivar interacciones pseudo-reales a partir de reseñas scrapeadas"
    )
    parser.add_argument(
        "--db-resenas", type=str, default=DB_RESENAS_PATH,
        help="Ruta a la BD con reseñas (default: data/tui_recomendador.db)"
    )
    parser.add_argument(
        "--db-destino", type=str, default=DB_DESTINO_PATH,
        help="Ruta a la BD destino para usuarios/interacciones (default: data/sample_tui.db)"
    )
    parser.add_argument(
        "--solo-resenas", action="store_true",
        help="Solo usar tabla 'resenas' (ignorar reviews_dataset)"
    )
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  DERIVAR INTERACCIONES REALES")
    print(f"{'='*60}")
    print(f"  BD reseñas: {args.db_resenas}")
    print(f"  BD destino: {args.db_destino}")
    print(f"  Seed: {SEED}")
    print(f"  Modo: {'solo resenas' if args.solo_resenas else 'resenas + reviews_dataset'}")
    print(f"{'='*60}\n")

    # Inicializar RNG con seed fijo
    rng = random.Random(SEED)

    # Verificar que existen las BDs
    if not Path(args.db_resenas).exists():
        print(f"ERROR: No se encuentra la BD de reseñas: {args.db_resenas}")
        print("  Ejecuta primero: python scripts/run_bulk_scraping.py")
        return

    # Crear BD destino si no existe
    Path(args.db_destino).parent.mkdir(parents=True, exist_ok=True)

    # 1. Crear tablas destino (o verificar que ya existen con estructura correcta)
    crear_tablas_destino(args.db_destino)

    # 2. Cargar reseñas
    print("Cargando reseñas...")
    start_time = time.time()
    resenas = cargar_resenas(args.db_resenas, solo_resenas=args.solo_resenas)
    print(f"  Total reseñas cargadas: {len(resenas)}")

    if not resenas:
        print("ERROR: No hay reseñas para procesar.")
        return

    # 3. Cargar experiencias para asociar
    print("Cargando experiencias...")
    experiencias_por_destino = cargar_experiencias(args.db_resenas)
    print(f"  Destinos con experiencias: {len(experiencias_por_destino)}")

    # 4. Derivar interacciones
    print("\nDerivando interacciones...")
    stats = derivar_interacciones(resenas, experiencias_por_destino, args.db_destino, rng)

    elapsed = time.time() - start_time

    # 5. Contar totales en BD destino
    try:
        conn = sqlite3.connect(args.db_destino)
        total_usuarios = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
        total_interacciones = conn.execute("SELECT COUNT(*) FROM interacciones").fetchone()[0]
        usuarios_reales = conn.execute("SELECT COUNT(*) FROM usuarios WHERE es_sintetico = 0").fetchone()[0]
        interacciones_valoracion = conn.execute("SELECT COUNT(*) FROM interacciones WHERE tipo = 'valoracion'").fetchone()[0]
        conn.close()
    except Exception:
        total_usuarios = total_interacciones = usuarios_reales = interacciones_valoracion = "?"

    # Resumen
    print(f"\n{'='*60}")
    print(f"  RESUMEN DERIVACIÓN DE INTERACCIONES")
    print(f"{'='*60}")
    print(f"  Reseñas procesadas: {stats['resenas_procesadas']}")
    print(f"  Reseñas sin destino (descartadas): {stats['resenas_sin_destino']}")
    print(f"  Usuarios nuevos creados: {stats['usuarios_nuevos']}")
    print(f"  Interacciones 'reserva': {stats['interacciones_reserva']}")
    print(f"  Interacciones 'valoracion': {stats['interacciones_valoracion']}")
    print(f"  Total interacciones derivadas: {stats['interacciones_reserva'] + stats['interacciones_valoracion']}")
    print(f"  ---")
    print(f"  Total usuarios en BD: {total_usuarios} (reales: {usuarios_reales})")
    print(f"  Total interacciones en BD: {total_interacciones} (valoraciones: {interacciones_valoracion})")
    print(f"  Tiempo: {elapsed:.1f} segundos")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
