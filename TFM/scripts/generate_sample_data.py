"""
Generador de datos sintéticos realistas para el Motor de Recomendación TUI.

Genera paquetes turísticos, reseñas e indicadores de destino sintéticos
para poder avanzar con embeddings y modelo sin depender del scraping externo.

Uso:
    python scripts/generate_sample_data.py --database-url sqlite:///data/sample_tui.db
"""

import argparse
import random
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# Asegurar imports del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.models import IndicadorDestino, Paquete, Resena
from src.data.repository import Repositorio

# ---------------------------------------------------------------------------
# Semilla fija para reproducibilidad
# ---------------------------------------------------------------------------
random.seed(42)

# ---------------------------------------------------------------------------
# Datos maestros
# ---------------------------------------------------------------------------

DESTINOS = [
    # (nombre, país, zona_geográfica)
    ("Mallorca", "España", "Mediterráneo"),
    ("Tenerife", "España", "Mediterráneo"),
    ("Ibiza", "España", "Mediterráneo"),
    ("Costa del Sol", "España", "Mediterráneo"),
    ("Lanzarote", "España", "Mediterráneo"),
    ("Fuerteventura", "España", "Mediterráneo"),
    ("Creta", "Grecia", "Mediterráneo"),
    ("Santorini", "Grecia", "Mediterráneo"),
    ("Rodas", "Grecia", "Mediterráneo"),
    ("Antalya", "Turquía", "Mediterráneo"),
    ("Hurghada", "Egipto", "Mediterráneo"),
    ("Cancún", "México", "Caribe"),
    ("Riviera Maya", "México", "Caribe"),
    ("Punta Cana", "República Dominicana", "Caribe"),
    ("Cuba", "Cuba", "Caribe"),
]

CATEGORIAS = ["playa", "cultura", "aventura", "bienestar", "gastronomia", "naturaleza"]
TEMPORADAS = ["Alta", "Media", "Baja"]
MERCADOS = ["es", "de", "uk"]
CIUDADES_SALIDA = ["Madrid", "Barcelona", "Frankfurt", "Múnich", "Londres", "Mánchester"]

# Hoteles por zona (inventados pero creíbles)
HOTELES_MEDITERRANEO = [
    "Hotel Sol Marina", "Grand Resort Azul", "Mediterranean Palace",
    "Playa Dorada Resort", "Costa Brava Suites", "Aegean Breeze Hotel",
    "Sunset Bay Resort", "Hotel Mar Turquesa", "Porto Blanco Suites",
    "Hotel Isla del Sol", "Blue Lagoon Resort", "Paradise Beach Hotel",
    "Hotel Luna de Miel", "Crystal Waters Resort", "El Faro Grand Hotel",
    "Bahía Dorada Club", "Hotel Sierra y Mar", "Oasis Mediterráneo",
    "Hotel Coral Beach", "Riviera Exclusive Club",
]

HOTELES_CARIBE = [
    "Caribe Royal Resort", "Playa Turquesa All-Inclusive", "Grand Palladium Caribe",
    "Hotel Coco Palm", "Bahía Azul Resort & Spa", "Caribbean Dreams Hotel",
    "Tropical Paradise Club", "Hotel Arena Blanca", "Coral Bay Suites",
    "Palm Beach Grand Resort", "Hotel Sol Caribeño", "Diamante Beach Resort",
    "Mayan Riviera Club", "Hotel Flamingo Caribe", "Ocean Breeze Resort",
]

# Plantillas de descripciones por categoría (español)
DESCRIPCIONES_PLANTILLAS = {
    "playa": [
        "Disfruta de {dias} noches en el {hotel} con todo incluido. Playa de arena blanca, piscina infinita y actividades acuáticas para toda la familia. Ideal para quienes buscan relax bajo el sol {zona}.",
        "Escapada de {dias} noches al {hotel} frente al mar. Régimen todo incluido con gastronomía local, snorkel y excursiones en barco. Un paraíso para los amantes del sol y la playa.",
        "Vacaciones de ensueño en {destino}: {dias} noches en el {hotel} con acceso directo a la playa. Spa, deportes náuticos y cenas temáticas incluidas. Perfecto para parejas y familias.",
        "{dias} noches de playa en {destino}. El {hotel} ofrece tumbonas privadas, chiringuito y club infantil. Todo incluido con shows nocturnos y excursiones opcionales.",
    ],
    "cultura": [
        "Descubre la riqueza cultural de {destino} durante {dias} noches en el {hotel}. Incluye visitas guiadas a monumentos históricos, museos y barrios tradicionales. Una inmersión cultural completa.",
        "Viaje cultural de {dias} noches a {destino} con estancia en el {hotel}. Excursiones a yacimientos arqueológicos, degustación de gastronomía local y talleres artesanales incluidos.",
        "Explora la historia milenaria de {destino}: {dias} noches en el {hotel} con programa cultural completo. Tours por la ciudad antigua, mercados locales y espectáculos folclóricos.",
    ],
    "aventura": [
        "Aventura sin límites en {destino}: {dias} noches en el {hotel} con actividades de adrenalina. Senderismo, kayak, tirolinas y excursiones todoterreno incluidos en el paquete.",
        "{dias} noches de aventura en {destino}. El {hotel} es tu base para rutas de trekking, buceo, escalada y recorridos en quad por paisajes espectaculares.",
        "Paquete aventura en {destino}: {dias} noches con alojamiento en el {hotel}. Incluye rafting, rutas en bicicleta de montaña y exploración de cuevas y parques naturales.",
    ],
    "bienestar": [
        "Retiro de bienestar en {destino}: {dias} noches en el {hotel} con programa spa completo. Masajes balineses, yoga al amanecer, circuito termal y alimentación detox incluidos.",
        "Relax total en {destino} durante {dias} noches. El {hotel} dispone de spa de 2000m², piscinas termales y programa de mindfulness. Desconexión garantizada.",
        "{dias} noches de bienestar en el {hotel} de {destino}. Tratamientos faciales, hidroterapia, clases de pilates y menús saludables diseñados por nutricionistas.",
    ],
    "gastronomia": [
        "Ruta gastronómica en {destino}: {dias} noches en el {hotel} con experiencias culinarias únicas. Cenas con chef, visitas a mercados locales y clases de cocina tradicional.",
        "Sabores de {destino}: {dias} noches en el {hotel} con programa gastronómico exclusivo. Maridajes de vinos, degustación de productos km0 y tours a bodegas locales.",
        "{dias} noches de inmersión gastronómica en {destino}. El {hotel} ofrece 5 restaurantes temáticos, showcooking diario y excursiones a granjas y almazaras.",
    ],
    "naturaleza": [
        "Escapada natural a {destino}: {dias} noches en el {hotel} rodeado de paisajes vírgenes. Rutas de observación de aves, senderos costeros y excursiones a parques naturales.",
        "Conéctate con la naturaleza en {destino}: {dias} noches en el {hotel}. Programa de ecoturismo con snorkel en reservas marinas, visita a volcanes y paseos a caballo.",
        "{dias} noches en el corazón natural de {destino}. El {hotel} ofrece jardines botánicos, avistamiento de delfines y rutas guiadas por bosques y acantilados.",
    ],
}

# Reseñas en español
RESENAS_ES = [
    "Estuvimos en {destino} la semana pasada y fue increíble. El hotel tenía vistas al mar y la comida era espectacular. Lo único malo fue el calor extremo en agosto.",
    "Viaje familiar a {destino}. Los niños disfrutaron muchísimo de la piscina y las actividades. El hotel estaba impecable y el personal muy amable. Repetiremos seguro.",
    "Nos alojamos 10 días en {destino} y quedamos encantados. Playas cristalinas, excursiones bien organizadas y buena relación calidad-precio. Muy recomendable.",
    "Decepcionante la experiencia en {destino}. El hotel necesita una renovación urgente y la comida era repetitiva. Las excursiones sí merecieron la pena.",
    "Vacaciones perfectas en {destino}. Todo incluido de verdad: bebidas premium, restaurantes à la carte y entretenimiento nocturno de calidad. Volveremos.",
    "Primera vez en {destino} y me ha conquistado. La cultura local es fascinante, la gente muy acogedora y los paisajes de otro mundo. El hotel básico pero limpio.",
    "Fuimos a {destino} en temporada baja y fue un acierto. Menos gente, precios más bajos y clima agradable. El hotel superó nuestras expectativas.",
    "Horrible experiencia en {destino}. Overbooking en el hotel, cambio de habitación tres veces y servicio al cliente inexistente. No volvería.",
    "Escapada romántica a {destino}: el hotel boutique era una joya escondida. Cena en la terraza con vistas al atardecer y spa privado. Mágico.",
    "Viaje de grupo a {destino}. El hotel grande e impersonal pero las actividades estaban genial. El buceo y las excursiones en barco fueron lo mejor.",
    "Relación calidad-precio excelente en {destino}. El todo incluido cubría todo lo necesario y las instalaciones estaban bien mantenidas.",
    "El transfer desde el aeropuerto a {destino} fue caótico pero el resto del viaje perfecto. Hotel con playa privada y snorkel incluido.",
    "Viajé sola a {destino} y me sentí muy segura. El hotel tenía buen ambiente y conocí gente genial en las excursiones organizadas.",
    "Nuestro aniversario en {destino} fue inolvidable. Suite con jacuzzi, cena bajo las estrellas y un atardecer que no olvidaré nunca.",
    "El hotel en {destino} estaba lejos de la playa, cosa que no indicaban en la web. Por lo demás, el servicio era correcto y la comida variada.",
]

# Reseñas en inglés
RESENAS_EN = [
    "We spent a week in {destino} and it was amazing. Crystal clear water, friendly staff, and the all-inclusive package was great value for money.",
    "Disappointing trip to {destino}. The hotel photos were misleading and the room was tiny. However, the beach itself was beautiful.",
    "Absolutely loved {destino}! The snorkeling was world-class, food was delicious, and the hotel had everything we needed. Would definitely return.",
    "Family holiday in {destino} - kids had a blast at the kids club while we enjoyed the spa. Hotel was clean and well-maintained.",
    "Great budget option in {destino}. Don't expect luxury but the location is perfect and the beach is right at your doorstep.",
    "Romantic getaway to {destino}. The sunset dinners on the beach were incredible. Hotel staff went above and beyond for our anniversary.",
    "Visited {destino} in low season - much quieter and cheaper. Weather was still warm and sunny. Highly recommend avoiding peak months.",
    "The food in {destino} was the highlight of the trip. Local restaurants far better than hotel dining. Must try the seafood!",
    "Mixed feelings about {destino}. Beautiful scenery but overcrowded beaches and overpriced excursions. Hotel pool area was lovely though.",
    "Best holiday ever in {destino}! The hotel was 5-star quality, entertainment every night, and the excursions were well organized.",
    "Spent 10 days in {destino} and could easily have stayed longer. Such a relaxing destination with so much to explore.",
    "The water sports in {destino} were fantastic - jet skiing, parasailing, and diving all available from the hotel beach.",
    "Lovely trip but the hotel in {destino} was under construction during our stay. Noisy mornings but evenings were peaceful.",
    "Can't fault our holiday in {destino}. From booking to checkout, everything was smooth. Already planning our next visit!",
    "Travelled solo to {destino} and made great friends at the hotel. The group excursions are perfect for solo travellers.",
]


# ---------------------------------------------------------------------------
# Funciones generadoras
# ---------------------------------------------------------------------------

def _generar_uuid() -> str:
    """Genera un UUID v4 determinista usando random (con seed fijada)."""
    return str(uuid.UUID(int=random.getrandbits(128), version=4))


def generar_paquetes(n: int = 100) -> list[Paquete]:
    """Genera n paquetes turísticos sintéticos realistas."""
    paquetes = []

    for i in range(n):
        destino_nombre, destino_pais, zona = random.choice(DESTINOS)
        categoria = random.choice(CATEGORIAS)
        temporada = random.choice(TEMPORADAS)
        mercado = random.choice(MERCADOS)
        ciudad_salida = random.choice(CIUDADES_SALIDA)
        duracion = random.randint(5, 14)

        # Seleccionar hotel según zona
        if zona == "Caribe":
            hotel = random.choice(HOTELES_CARIBE)
        else:
            hotel = random.choice(HOTELES_MEDITERRANEO)

        # Precio correlacionado con duración y zona
        precio_base = random.randint(400, 3000)
        if zona == "Caribe":
            precio_base = max(800, precio_base)  # Caribe más caro
        if temporada == "Alta":
            precio_base = int(precio_base * random.uniform(1.1, 1.4))
        elif temporada == "Baja":
            precio_base = int(precio_base * random.uniform(0.7, 0.9))
        precio_base = min(precio_base, 3000)

        # Fecha de salida aleatoria en 2025
        mes_salida = random.randint(1, 12)
        dia_salida = random.randint(1, 28)
        fecha_sal = date(2025, mes_salida, dia_salida)
        fecha_vuel = fecha_sal + timedelta(days=duracion)

        # Nivel de ocupación
        nivel_ocupacion = round(random.uniform(0.2, 0.95), 2)

        # Capacidad y plazas
        capacidad = random.choice([50, 80, 100, 120, 150, 200])
        plazas_disponibles = int(capacidad * (1 - nivel_ocupacion))

        # Estrellas del hotel
        estrellas = random.choice([3.0, 3.5, 4.0, 4.5, 5.0])

        # Generar descripción
        zona_adj = "mediterráneo" if zona == "Mediterráneo" else "caribeño"
        plantillas = DESCRIPCIONES_PLANTILLAS[categoria]
        plantilla = random.choice(plantillas)
        descripcion = plantilla.format(
            dias=duracion,
            hotel=hotel,
            destino=destino_nombre,
            zona=zona_adj,
        )

        # Nombre comercial del paquete
        nombre_paquete = f"TUI {categoria.capitalize()} {destino_nombre} - {duracion} noches"

        paquete = Paquete(
            id_paquete=_generar_uuid(),
            mercado=mercado,
            destino_nombre=destino_nombre,
            destino_pais=destino_pais,
            zona_geografica=zona,
            categoria=categoria,
            nombre_paquete=nombre_paquete,
            descripcion_texto=descripcion,
            nombre_hotel=hotel,
            estrellas_hotel=estrellas,
            ciudad_salida=ciudad_salida,
            fecha_salida=fecha_sal,
            fecha_vuelta=fecha_vuel,
            duracion_dias=duracion,
            precio_base_eur=float(precio_base),
            moneda_original="EUR",
            precio_original=float(precio_base),
            capacidad_plazas=capacidad,
            plazas_disponibles=plazas_disponibles,
            nivel_ocupacion=nivel_ocupacion,
            temporada=temporada,
            accesibilidad_destino=random.randint(1, 3),
            indicador_sostenibilidad_tui=random.choice([True, False]),
            sensibilidad_ambiental=round(random.uniform(0.1, 0.9), 2),
            num_valoraciones_hotel=random.randint(50, 2000),
            puntuacion_media_hotel=round(random.uniform(6.5, 9.8), 1),
            url_fuente=f"https://www.tui.com/paquetes/{destino_nombre.lower().replace(' ', '-')}/{i}",
            fecha_extraccion=datetime(2025, 1, 15, 10, 0, 0),
            version_scraper="synthetic-v1.0",
        )

        paquetes.append(paquete)

    return paquetes


def generar_resenas(n: int = 200) -> list[Resena]:
    """Genera n reseñas sintéticas en español e inglés."""
    resenas = []
    fuentes = ["tripadvisor", "reddit", "foro"]

    for _ in range(n):
        destino_nombre, _, _ = random.choice(DESTINOS)
        idioma = random.choice(["es", "en"])

        if idioma == "es":
            plantilla = random.choice(RESENAS_ES)
        else:
            plantilla = random.choice(RESENAS_EN)

        texto = plantilla.format(destino=destino_nombre)

        # Puntuación correlacionada con sentimiento del texto
        # Reseñas con palabras negativas tienden a puntuaciones más bajas
        palabras_negativas = ["decepcionante", "horrible", "malo", "disappointing", "misleading", "mixed"]
        tiene_negativa = any(p in texto.lower() for p in palabras_negativas)
        if tiene_negativa:
            puntuacion = round(random.uniform(1.0, 3.0), 1)
        else:
            puntuacion = round(random.uniform(3.5, 5.0), 1)

        # Fecha de publicación aleatoria en 2024
        mes_pub = random.randint(1, 12)
        dia_pub = random.randint(1, 28)
        fecha_pub = datetime(2024, mes_pub, dia_pub, random.randint(8, 22), random.randint(0, 59))

        resena = Resena(
            id_resena=_generar_uuid(),
            id_paquete=None,  # Sin vincular a paquete específico
            destino_nombre=destino_nombre,
            fuente=random.choice(fuentes),
            texto_original=texto,
            idioma=idioma,
            puntuacion=puntuacion,
            fecha_publicacion=fecha_pub,
            url_fuente=f"https://www.tripadvisor.com/reviews/{destino_nombre.lower().replace(' ', '-')}",
            fecha_extraccion=datetime(2025, 1, 15, 12, 0, 0),
        )

        resenas.append(resena)

    return resenas


def generar_indicadores(n: int = 50) -> list[IndicadorDestino]:
    """Genera n indicadores de destino (nivel_ocupacion por destino y mes)."""
    indicadores = []
    fuentes_stats = ["eurostat", "ine", "unwto", "booking"]

    # Generar indicadores para destinos aleatorios en meses aleatorios
    for _ in range(n):
        destino_nombre, _, _ = random.choice(DESTINOS)
        mes = random.randint(1, 12)

        # Nivel de ocupación varía por temporada
        # Verano (jun-sep) más alto, invierno (nov-feb) más bajo
        if mes in [6, 7, 8, 9]:
            valor = round(random.uniform(0.65, 0.95), 3)
        elif mes in [11, 12, 1, 2]:
            valor = round(random.uniform(0.20, 0.55), 3)
        else:
            valor = round(random.uniform(0.40, 0.75), 3)

        indicador = IndicadorDestino(
            id_indicador=_generar_uuid(),
            destino_nombre=destino_nombre,
            fuente=random.choice(fuentes_stats),
            tipo_indicador="nivel_ocupacion",
            valor=valor,
            anio=2024,
            mes=mes,
            fecha_extraccion=datetime(2025, 1, 15, 14, 0, 0),
        )

        indicadores.append(indicador)

    return indicadores


# ---------------------------------------------------------------------------
# Persistencia y ejecución principal
# ---------------------------------------------------------------------------

def persistir_datos(
    repo: Repositorio,
    paquetes: list[Paquete],
    resenas: list[Resena],
    indicadores: list[IndicadorDestino],
) -> dict[str, int]:
    """Persiste todos los datos generados en la base de datos usando bulk insert."""
    from sqlalchemy.orm import Session as SASession

    # Crear tablas
    repo.crear_tablas()

    # Bulk insert paquetes (sin versionado para mayor velocidad en datos sintéticos)
    paquetes_ok = 0
    with repo.SessionLocal() as sesion:
        try:
            sesion.add_all(paquetes)
            sesion.commit()
            paquetes_ok = len(paquetes)
        except Exception as e:
            sesion.rollback()
            print(f"  [ERROR] Error bulk insert paquetes: {e}")
            # Fallback: uno a uno
            for paquete in paquetes:
                try:
                    repo.upsert_paquete(paquete)
                    paquetes_ok += 1
                except Exception as e2:
                    print(f"  [WARN] Error paquete {paquete.id_paquete}: {e2}")

    # Bulk insert reseñas
    resenas_ok = 0
    with repo.SessionLocal() as sesion:
        try:
            sesion.add_all(resenas)
            sesion.commit()
            resenas_ok = len(resenas)
        except Exception as e:
            sesion.rollback()
            print(f"  [ERROR] Error bulk insert reseñas: {e}")
            for resena in resenas:
                try:
                    repo.upsert_resena(resena)
                    resenas_ok += 1
                except Exception as e2:
                    print(f"  [WARN] Error reseña: {e2}")

    # Bulk insert indicadores
    indicadores_ok = 0
    with repo.SessionLocal() as sesion:
        try:
            sesion.add_all(indicadores)
            sesion.commit()
            indicadores_ok = len(indicadores)
        except Exception as e:
            sesion.rollback()
            print(f"  [ERROR] Error bulk insert indicadores: {e}")
            for indicador in indicadores:
                try:
                    repo.upsert_indicador(indicador)
                    indicadores_ok += 1
                except Exception as e2:
                    print(f"  [WARN] Error indicador: {e2}")

    return {
        "paquetes": paquetes_ok,
        "resenas": resenas_ok,
        "indicadores": indicadores_ok,
    }


def recopilar_estadisticas(
    paquetes: list[Paquete],
    resenas: list[Resena],
    indicadores: list[IndicadorDestino],
) -> dict[str, Any]:
    """
    Recopila estadísticas de los datos generados ANTES de persistir.
    
    Esto evita problemas con objetos detached de SQLAlchemy tras el commit.
    """
    # Paquetes
    zonas: dict[str, int] = {}
    categorias: dict[str, int] = {}
    temporadas: dict[str, int] = {}
    precios: list[float] = []

    for p in paquetes:
        zonas[p.zona_geografica] = zonas.get(p.zona_geografica, 0) + 1
        categorias[p.categoria] = categorias.get(p.categoria, 0) + 1
        temporadas[p.temporada] = temporadas.get(p.temporada, 0) + 1
        if p.precio_base_eur:
            precios.append(p.precio_base_eur)

    # Reseñas
    idiomas: dict[str, int] = {}
    puntuaciones: list[float] = []
    for r in resenas:
        idiomas[r.idioma] = idiomas.get(r.idioma, 0) + 1
        if r.puntuacion:
            puntuaciones.append(r.puntuacion)

    # Indicadores
    destinos_ind = set(i.destino_nombre for i in indicadores)
    valores = [i.valor for i in indicadores]

    return {
        "zonas": zonas,
        "categorias": categorias,
        "temporadas": temporadas,
        "precios": precios,
        "idiomas": idiomas,
        "puntuaciones": puntuaciones,
        "destinos_indicadores": len(destinos_ind),
        "valores_indicadores": valores,
    }


def mostrar_resumen(
    n_paquetes: int,
    n_resenas: int,
    n_indicadores: int,
    resultados: dict[str, int],
    stats: dict[str, Any],
) -> None:
    """Muestra un resumen de los datos generados y persistidos."""
    print("\n" + "=" * 60)
    print("  RESUMEN DE GENERACIÓN DE DATOS SINTÉTICOS")
    print("=" * 60)

    print(f"\n{'Entidad':<20} {'Generados':<12} {'Persistidos':<12}")
    print("-" * 44)
    print(f"{'Paquetes':<20} {n_paquetes:<12} {resultados['paquetes']:<12}")
    print(f"{'Reseñas':<20} {n_resenas:<12} {resultados['resenas']:<12}")
    print(f"{'Indicadores':<20} {n_indicadores:<12} {resultados['indicadores']:<12}")

    # Estadísticas de paquetes
    print("\n--- Distribución de paquetes ---")
    print(f"  Zonas: {dict(sorted(stats['zonas'].items()))}")
    print(f"  Categorías: {dict(sorted(stats['categorias'].items()))}")
    print(f"  Temporadas: {dict(sorted(stats['temporadas'].items()))}")

    precios = stats["precios"]
    if precios:
        print(f"  Precio medio: {sum(precios)/len(precios):.0f}€ (min: {min(precios):.0f}€, max: {max(precios):.0f}€)")

    # Estadísticas de reseñas
    print("\n--- Distribución de reseñas ---")
    print(f"  Idiomas: {dict(sorted(stats['idiomas'].items()))}")
    puntuaciones = stats["puntuaciones"]
    if puntuaciones:
        print(f"  Puntuación media: {sum(puntuaciones)/len(puntuaciones):.2f} (min: {min(puntuaciones):.1f}, max: {max(puntuaciones):.1f})")

    # Estadísticas de indicadores
    print("\n--- Indicadores ---")
    print(f"  Destinos cubiertos: {stats['destinos_indicadores']}")
    valores = stats["valores_indicadores"]
    if valores:
        print(f"  Ocupación media: {sum(valores)/len(valores):.3f} (min: {min(valores):.3f}, max: {max(valores):.3f})")

    print("\n" + "=" * 60)
    print("  Generación completada exitosamente.")
    print("=" * 60 + "\n")


def main() -> None:
    """Punto de entrada principal del script."""
    parser = argparse.ArgumentParser(
        description="Genera datos sintéticos realistas para el Motor de Recomendación TUI."
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default="sqlite:///data/sample_tui.db",
        help="URL de conexión SQLAlchemy (default: sqlite:///data/sample_tui.db)",
    )
    parser.add_argument(
        "--paquetes",
        type=int,
        default=100,
        help="Número de paquetes a generar (default: 100)",
    )
    parser.add_argument(
        "--resenas",
        type=int,
        default=200,
        help="Número de reseñas a generar (default: 200)",
    )
    parser.add_argument(
        "--indicadores",
        type=int,
        default=50,
        help="Número de indicadores a generar (default: 50)",
    )
    args = parser.parse_args()

    print(f"Base de datos: {args.database_url}")
    print(f"Generando {args.paquetes} paquetes, {args.resenas} reseñas, {args.indicadores} indicadores...")

    # Generar datos
    print("\n[1/4] Generando paquetes turísticos...")
    paquetes = generar_paquetes(args.paquetes)
    print(f"  -> {len(paquetes)} paquetes generados")

    print("[2/4] Generando reseñas...")
    resenas = generar_resenas(args.resenas)
    print(f"  -> {len(resenas)} reseñas generadas")

    print("[3/4] Generando indicadores de destino...")
    indicadores = generar_indicadores(args.indicadores)
    print(f"  -> {len(indicadores)} indicadores generados")

    # Recopilar estadísticas ANTES de persistir (evita DetachedInstanceError)
    stats = recopilar_estadisticas(paquetes, resenas, indicadores)

    # Persistir
    print("[4/4] Persistiendo datos en la base de datos...")
    repo = Repositorio(args.database_url)
    resultados = persistir_datos(repo, paquetes, resenas, indicadores)

    # Resumen
    mostrar_resumen(len(paquetes), len(resenas), len(indicadores), resultados, stats)


if __name__ == "__main__":
    main()
