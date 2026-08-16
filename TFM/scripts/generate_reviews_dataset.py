"""
Generador de ~50.000 reseñas con sentiment score para experiencias turísticas.

Lee los bookings con left_review=1 y genera reseñas realistas en español,
inglés y alemán, con sentiment_score correlacionado con el rating.

Inserta en tabla `reviews_dataset` de la BD principal.
NO borra datos existentes. Seed=42 para reproducibilidad.

Ejecución:
    cd /d D:\\Master\\TrabajoFinalUCM\\TFM
    python scripts/generate_reviews_dataset.py
    python scripts/generate_reviews_dataset.py --db data/tui_recomendador.db
    python scripts/generate_reviews_dataset.py --help
"""

import argparse
import json
import logging
import sqlite3
import sys
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
logger = logging.getLogger("generate_reviews")

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

SEED = 42

# ---------------------------------------------------------------------------
# Banco de frases por idioma y rango de rating
# ---------------------------------------------------------------------------

# ESPAÑOL - Rating 5
FRASES_ES_5 = [
    "Una experiencia increíble, totalmente recomendable",
    "El guía fue excepcional y muy conocedor",
    "Perfecto para familias, los niños disfrutaron mucho",
    "Relación calidad-precio excelente",
    "Sin duda repetiría esta actividad",
    "Lo mejor que hemos hecho en vacaciones",
    "Organización impecable de principio a fin",
    "Superó todas nuestras expectativas",
    "Una joya escondida que no te puedes perder",
    "El mejor recuerdo de nuestro viaje",
    "Absolutamente maravilloso, merece cada céntimo",
    "Nos trataron de forma excepcional",
    "Experiencia única e inolvidable",
    "Todo perfecto, sin ninguna queja",
    "El guía hizo que la experiencia fuera mágica",
    "Increíblemente bien organizado y divertido",
    "Lo recomiendo al 100%, no os lo perdáis",
    "De las mejores cosas que he hecho en mi vida",
    "Paisajes espectaculares y servicio de primera",
    "Volveríamos sin dudarlo ni un segundo",
]

# ESPAÑOL - Rating 4
FRASES_ES_4 = [
    "Muy buena experiencia en general",
    "Buena relación calidad-precio, aunque algo corta",
    "El guía fue amable y profesional",
    "Disfrutamos mucho, solo el tiempo fue un poco justo",
    "Recomendable, aunque había bastante gente",
    "Bien organizado, quizá un poco caro",
    "Bonita actividad, repetiríamos con más tiempo",
    "El lugar es precioso, la organización mejorable",
    "Experiencia positiva, el transporte podría mejorar",
    "Nos gustó bastante, faltó un poco más de explicación",
    "Muy bien en general, el punto de encuentro confuso",
    "Buena actividad para pasar la mañana",
    "Contentos con la experiencia, aunque esperábamos más",
    "El personal fue atento, las instalaciones correctas",
    "Merece la pena, pero reservad con antelación",
    "Buen servicio, solo que el grupo era demasiado grande",
    "Interesante y educativa, un poco larga",
    "Bonita excursión, aunque el precio es algo elevado",
    "La pasamos bien, el guía podría ser más dinámico",
    "Actividad entretenida, cumple con lo prometido",
]

# ESPAÑOL - Rating 3
FRASES_ES_3 = [
    "Está bien pero esperaba más por el precio",
    "Experiencia correcta, nada del otro mundo",
    "Cumple su función, pero no es especial",
    "Regular, hay opciones mejores en la zona",
    "Ni bien ni mal, algo básico para lo que cobran",
    "Aceptable, pero la descripción prometía más",
    "Pasable, el guía no fue muy entusiasta",
    "No está mal pero no repetiría",
    "Correcto pero algo decepcionante",
    "La experiencia fue normalita",
    "Esperaba algo más, fue bastante estándar",
    "No destaca especialmente frente a otras opciones",
    "Cumplió mínimamente con lo esperado",
    "Intermedio, ni genial ni terrible",
    "Podría estar mejor organizado",
    "Para pasar el rato está bien, poco más",
    "La actividad fue corta para el precio",
    "Mejorable en varios aspectos",
    "No me arrepiento pero tampoco lo recomendaría",
    "Justo lo mínimo esperado, sin sorpresas",
]

# ESPAÑOL - Rating 1-2
FRASES_ES_12 = [
    "No merece la pena, dinero tirado",
    "Pésima organización, llegamos tarde a todo",
    "El guía no sabía ni dónde estaba",
    "Una estafa, no se corresponde con la descripción",
    "Horrible experiencia, no lo recomiendo a nadie",
    "Perdimos el tiempo y el dinero",
    "Muy decepcionante, todo mal organizado",
    "No volvería ni regalado",
    "Desastroso, cancelaron sin avisar",
    "La peor actividad de nuestro viaje",
    "Engañoso, las fotos no tienen nada que ver",
    "Mala atención al cliente, imposible contactar",
    "Demasiado caro para lo que ofrecen",
    "Nos sentimos estafados",
    "Inaceptable, el servicio fue deplorable",
    "Totalmente desorganizado y caótico",
    "No cumplieron con nada de lo prometido",
    "Una pérdida total de tiempo",
    "Vergonzoso trato al cliente",
    "Quiero mi dinero de vuelta",
]

# INGLÉS - Rating 5
FRASES_EN_5 = [
    "Absolutely loved this experience!",
    "The guide was amazing and very informative",
    "Best excursion we've ever done",
    "Great value for money",
    "Highly recommend to everyone",
    "A must-do when visiting this area",
    "Exceeded all our expectations",
    "Perfect organization from start to finish",
    "Unforgettable experience, worth every penny",
    "The highlight of our holiday",
    "Truly exceptional service and attention",
    "We had the time of our lives",
    "Couldn't have asked for a better experience",
    "Outstanding guide with incredible knowledge",
    "A perfect day out for the whole family",
    "Simply breathtaking, no words can describe it",
    "Five stars isn't enough for this",
    "Would do it again in a heartbeat",
    "The staff went above and beyond",
    "An absolute gem, don't miss it",
]

# INGLÉS - Rating 4
FRASES_EN_4 = [
    "Great overall experience, slightly rushed",
    "Good value, the guide was knowledgeable",
    "Really enjoyed it, just a bit crowded",
    "Would recommend, though could be longer",
    "Nice activity, well organized",
    "Very good experience, minor issues with timing",
    "Enjoyable day out, a bit pricey though",
    "The location was stunning, logistics were okay",
    "Fun experience, transport could be improved",
    "Happy with this booking, met expectations",
    "Good activity for a half day",
    "Solid experience, nothing extraordinary",
    "The guide was friendly and informative",
    "Quite good, group size was a bit large",
    "Nice way to spend the morning",
    "Good experience, meeting point was confusing",
    "Worthwhile activity, book in advance",
    "Enjoyed ourselves, the pace was a bit fast",
    "Interesting and educational tour",
    "Pleasant experience, delivers what it promises",
]

# INGLÉS - Rating 3
FRASES_EN_3 = [
    "Average experience, expected more for the price",
    "It was okay, nothing special",
    "Decent but wouldn't do it again",
    "Mediocre, there are better options",
    "Not bad but not great either",
    "The description was misleading",
    "Just okay, guide wasn't very engaging",
    "Standard tourist experience",
    "Fair enough, could be better",
    "Middle of the road, no complaints but no praise",
    "Acceptable but overpriced for what you get",
    "It was fine, just rather basic",
    "Could have been much better organized",
    "Underwhelming compared to other activities",
    "Not terrible but I wouldn't recommend it",
    "Below my expectations based on reviews",
    "The activity was too short for the price",
    "Room for improvement in several areas",
    "Neither here nor there, quite forgettable",
    "Meets minimum expectations, no more",
]

# INGLÉS - Rating 1-2
FRASES_EN_12 = [
    "Terrible experience, total waste of money",
    "Awful organization, never again",
    "The guide was completely clueless",
    "Complete scam, nothing like advertised",
    "Worst activity we've ever booked",
    "Disappointing from start to finish",
    "Save your money, don't bother",
    "Absolutely dreadful, avoid at all costs",
    "They cancelled without notice",
    "Ruined our day, completely disorganized",
    "Misleading photos and description",
    "Customer service was non-existent",
    "Overpriced and underdelivered",
    "Felt like we were being ripped off",
    "Unacceptable level of service",
    "Total chaos, nothing went right",
    "Did not deliver on any promise",
    "A complete waste of our time",
    "Appalling treatment of customers",
    "I want a full refund",
]

# ALEMÁN - Rating 5
FRASES_DE_5 = [
    "Wirklich fantastische Erfahrung!",
    "Der Reiseführer war ausgezeichnet",
    "Sehr empfehlenswert für Familien",
    "Tolles Preis-Leistungs-Verhältnis",
    "Absolut unvergesslich, ein Muss!",
    "Die beste Aktivität unseres Urlaubs",
    "Perfekte Organisation, alles top",
    "Hat alle Erwartungen übertroffen",
    "Ein echtes Highlight, nicht verpassen",
    "Hervorragender Service von Anfang bis Ende",
    "Wir hatten eine wunderbare Zeit",
    "Kann ich nur wärmstens empfehlen",
    "Der Guide war unglaublich kompetent",
    "Atemberaubend schön und gut organisiert",
    "Würden wir sofort wieder machen",
    "Ein unvergessliches Erlebnis für die ganze Familie",
    "Perfekt in jeder Hinsicht",
    "Das Team war außerordentlich freundlich",
    "Jeden Euro wert, absolut top",
    "Die schönste Erinnerung an unsere Reise",
]

# ALEMÁN - Rating 4
FRASES_DE_4 = [
    "Insgesamt eine sehr gute Erfahrung",
    "Gutes Preis-Leistungs-Verhältnis, etwas kurz",
    "Der Guide war freundlich und kompetent",
    "Hat Spaß gemacht, nur etwas voll",
    "Empfehlenswert, aber etwas teuer",
    "Gut organisiert, schöne Erfahrung",
    "Schöne Aktivität, würden es nochmal machen",
    "Tolles Erlebnis, Transport ausbaufähig",
    "Positive Erfahrung mit kleinen Abzügen",
    "Haben es genossen, Treffpunkt etwas verwirrend",
    "Guter Ausflug für einen halben Tag",
    "Solide Erfahrung, nichts Außergewöhnliches",
    "Netter Zeitvertreib, Gruppe etwas groß",
    "Gute Aktivität, frühzeitig buchen",
    "Interessant und lehrreich, etwas zu lang",
    "Schöne Exkursion, Preis etwas hoch",
    "Zufrieden mit der Erfahrung insgesamt",
    "Der Ort war wunderschön, Logistik okay",
    "Spaßiger Ausflug, Tempo etwas hoch",
    "Nette Aktivität, erfüllt die Erwartungen",
]

# ALEMÁN - Rating 3
FRASES_DE_3 = [
    "Geht so, hatte mir mehr erwartet",
    "Durchschnittliche Erfahrung, nichts Besonderes",
    "In Ordnung, aber nicht wiederholenswert",
    "Mittelmäßig, es gibt bessere Optionen",
    "Weder gut noch schlecht",
    "Die Beschreibung war etwas irreführend",
    "Okay, der Guide war nicht sehr engagiert",
    "Standard-Touristenangebot",
    "Akzeptabel, könnte besser sein",
    "Für den Preis zu wenig geboten",
    "Es war in Ordnung, recht einfach",
    "Organisation hätte besser sein können",
    "Enttäuschend im Vergleich zu Alternativen",
    "Nicht schlecht, aber auch nicht empfehlenswert",
    "Unter meinen Erwartungen",
    "Zu kurz für den aufgerufenen Preis",
    "Verbesserungsbedarf in mehreren Bereichen",
    "Ziemlich vergesslich, weder gut noch schlecht",
    "Erfüllt Mindestansprüche, nicht mehr",
    "Naja, geht so, war okay",
]

# ALEMÁN - Rating 1-2
FRASES_DE_12 = [
    "Zu teuer für das Gebotene",
    "Furchtbare Organisation, nie wieder",
    "Der Guide hatte keine Ahnung",
    "Totale Abzocke, nicht wie beschrieben",
    "Schlimmste Aktivität unseres Urlaubs",
    "Von Anfang bis Ende enttäuschend",
    "Spart euch das Geld",
    "Absolut schrecklich, auf keinen Fall buchen",
    "Wurde ohne Vorwarnung abgesagt",
    "Hat unseren Tag ruiniert",
    "Irreführende Fotos und Beschreibung",
    "Kundenservice nicht existent",
    "Überteuert und enttäuschend",
    "Wir fühlten uns abgezockt",
    "Inakzeptabler Service",
    "Totales Chaos, nichts hat funktioniert",
    "Nichts von den Versprechen eingehalten",
    "Komplette Zeitverschwendung",
    "Unmögliche Behandlung der Kunden",
    "Ich möchte mein Geld zurück",
]

# FRANCÉS - Rating 5
FRASES_FR_5 = [
    "Expérience absolument fantastique!",
    "Le guide était exceptionnel et très cultivé",
    "Parfait pour les familles",
    "Excellent rapport qualité-prix",
    "Je recommande vivement à tous",
    "Le meilleur moment de nos vacances",
    "Organisation parfaite du début à la fin",
    "A dépassé toutes nos attentes",
    "Un incontournable lors de votre visite",
    "Inoubliable, vaut chaque centime",
]

# FRANCÉS - Rating 4
FRASES_FR_4 = [
    "Très bonne expérience dans l'ensemble",
    "Bon rapport qualité-prix, un peu court",
    "Le guide était sympathique et professionnel",
    "Nous avons bien profité, un peu bondé",
    "Recommandable, un peu cher cependant",
    "Bien organisé, belle expérience",
    "Agréable activité, nous referions",
    "Bonne activité pour une demi-journée",
    "Expérience positive, petit bémol logistique",
    "Satisfaits de la réservation",
]

# FRANCÉS - Rating 3
FRASES_FR_3 = [
    "Correct mais j'attendais mieux",
    "Expérience moyenne, rien de spécial",
    "Passable, il y a mieux dans le coin",
    "Ni bien ni mal, assez basique",
    "La description était trompeuse",
    "Standard, le guide manquait d'enthousiasme",
    "Acceptable mais trop cher",
    "Bof, pas terrible",
    "Pourrait être mieux organisé",
    "Ne vaut pas vraiment le prix demandé",
]

# FRANCÉS - Rating 1-2
FRASES_FR_12 = [
    "Terrible, une perte d'argent totale",
    "Organisation catastrophique",
    "Le guide était incompétent",
    "Arnaque totale, rien à voir avec la description",
    "Pire expérience de nos vacances",
    "Décevant du début à la fin",
    "Gardez votre argent",
    "Absolument affreux, à éviter",
    "Annulé sans prévenir",
    "Je veux un remboursement",
]

# HOLANDÉS - Rating 5
FRASES_NL_5 = [
    "Absoluut fantastische ervaring!",
    "De gids was uitstekend",
    "Zeer aanbevolen voor gezinnen",
    "Uitstekende prijs-kwaliteitverhouding",
    "Een must-do, onvergetelijk",
    "Het beste van onze vakantie",
    "Perfect georganiseerd",
    "Overtrof al onze verwachtingen",
    "Geweldige service van begin tot eind",
    "Zouden het zo weer doen",
]

# HOLANDÉS - Rating 4
FRASES_NL_4 = [
    "Over het geheel een goede ervaring",
    "Goed geprijsd, iets te kort",
    "De gids was vriendelijk en deskundig",
    "Leuk, maar een beetje druk",
    "Aanbevolen, hoewel iets duur",
    "Goed georganiseerd, mooie ervaring",
    "Leuke activiteit voor een halve dag",
    "Positieve ervaring, kleine verbeterpunten",
    "Tevreden met de boeking",
    "Mooie locatie, logistiek oké",
]

# HOLANDÉS - Rating 3
FRASES_NL_3 = [
    "Oké maar verwachtte meer",
    "Gemiddelde ervaring, niets bijzonders",
    "Redelijk, er zijn betere opties",
    "Niet slecht maar ook niet goed",
    "De beschrijving was misleidend",
    "Standaard toeristenactiviteit",
    "Acceptabel maar te duur",
    "Mwah, kon beter",
    "Voldoet aan minimale verwachtingen",
    "Niet herhaalbaar, matig",
]

# HOLANDÉS - Rating 1-2
FRASES_NL_12 = [
    "Verschrikkelijk, geld weggegooid",
    "Vreselijke organisatie, nooit meer",
    "De gids had geen idee",
    "Totale oplichterij",
    "Slechtste activiteit van onze vakantie",
    "Teleurstellend van begin tot eind",
    "Bespaar je geld",
    "Absoluut verschrikkelijk, vermijd dit",
    "Zonder waarschuwing geannuleerd",
    "Ik wil mijn geld terug",
]

# ITALIANO - Rating 5
FRASES_IT_5 = [
    "Esperienza assolutamente fantastica!",
    "La guida era eccezionale e preparatissima",
    "Perfetto per famiglie con bambini",
    "Ottimo rapporto qualità-prezzo",
    "Lo consiglio vivamente a tutti",
    "Il momento più bello della vacanza",
    "Organizzazione impeccabile dall'inizio alla fine",
    "Ha superato tutte le nostre aspettative",
    "Da non perdere assolutamente",
    "Indimenticabile, vale ogni centesimo",
]

# ITALIANO - Rating 4
FRASES_IT_4 = [
    "Ottima esperienza nel complesso",
    "Buon rapporto qualità-prezzo, un po' breve",
    "La guida era simpatica e professionale",
    "Ci siamo divertiti, un po' affollato",
    "Consigliabile, anche se un po' caro",
    "Ben organizzato, bella esperienza",
    "Attività piacevole, lo rifaremmo",
    "Buona attività per mezza giornata",
    "Esperienza positiva, trasporto migliorabile",
    "Soddisfatti della prenotazione",
]

# ITALIANO - Rating 3
FRASES_IT_3 = [
    "Nella media, mi aspettavo di più",
    "Esperienza ordinaria, niente di speciale",
    "Accettabile ma non eccezionale",
    "Né buono né cattivo, abbastanza basico",
    "La descrizione era fuorviante",
    "Standard, la guida poco coinvolgente",
    "Passabile ma troppo caro",
    "Insomma, potrebbe essere meglio",
    "Soddisfa le aspettative minime",
    "Non male ma non lo rifarei",
]

# ITALIANO - Rating 1-2
FRASES_IT_12 = [
    "Terribile, soldi buttati",
    "Organizzazione pessima, mai più",
    "La guida era incompetente",
    "Truffa totale, non come descritto",
    "Peggior attività della vacanza",
    "Deludente dall'inizio alla fine",
    "Risparmiate i vostri soldi",
    "Assolutamente orribile, da evitare",
    "Cancellato senza preavviso",
    "Voglio un rimborso completo",
]

# ---------------------------------------------------------------------------
# Mapeo de frases por idioma
# ---------------------------------------------------------------------------

FRASES_POR_IDIOMA = {
    "Spanish": {5: FRASES_ES_5, 4: FRASES_ES_4, 3: FRASES_ES_3, 2: FRASES_ES_12, 1: FRASES_ES_12},
    "English": {5: FRASES_EN_5, 4: FRASES_EN_4, 3: FRASES_EN_3, 2: FRASES_EN_12, 1: FRASES_EN_12},
    "German": {5: FRASES_DE_5, 4: FRASES_DE_4, 3: FRASES_DE_3, 2: FRASES_DE_12, 1: FRASES_DE_12},
    "French": {5: FRASES_FR_5, 4: FRASES_FR_4, 3: FRASES_FR_3, 2: FRASES_FR_12, 1: FRASES_FR_12},
    "Dutch": {5: FRASES_NL_5, 4: FRASES_NL_4, 3: FRASES_NL_3, 2: FRASES_NL_12, 1: FRASES_NL_12},
    "Italian": {5: FRASES_IT_5, 4: FRASES_IT_4, 3: FRASES_IT_3, 2: FRASES_IT_12, 1: FRASES_IT_12},
}

# Sentiment score ranges por rating
SENTIMENT_RANGES = {
    5: (0.80, 1.15),
    4: (0.55, 0.85),
    3: (0.25, 0.55),
    2: (0.05, 0.30),
    1: (-0.10, 0.15),
}


# ---------------------------------------------------------------------------
# Funciones
# ---------------------------------------------------------------------------

def crear_tabla_reviews(conn: sqlite3.Connection) -> None:
    """Crea la tabla reviews_dataset si no existe."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reviews_dataset (
            review_id TEXT PRIMARY KEY,
            experience_id TEXT NOT NULL,
            rating INTEGER NOT NULL,
            review_text TEXT NOT NULL,
            review_date TEXT NOT NULL,
            reviewer_country TEXT NOT NULL,
            reviewer_language TEXT NOT NULL,
            age_group TEXT NOT NULL,
            sentiment_score REAL NOT NULL
        )
    """)
    conn.commit()


def cargar_bookings_con_review(conn: sqlite3.Connection) -> list[dict]:
    """Carga bookings que tienen left_review=1."""
    cursor = conn.execute("""
        SELECT booking_id, customer_id, experience_id, travel_date,
               country, language, age_group
        FROM customer_bookings
        WHERE left_review = 1
    """)
    bookings = []
    for row in cursor.fetchall():
        bookings.append({
            "booking_id": row[0],
            "customer_id": row[1],
            "experience_id": row[2],
            "travel_date": row[3],
            "country": row[4],
            "language": row[5],
            "age_group": row[6],
        })
    return bookings


def generar_review_text(rng: np.random.Generator, idioma: str, rating: int) -> str:
    """Genera texto de reseña combinando 2-4 frases del banco."""
    frases_disponibles = FRASES_POR_IDIOMA.get(idioma, FRASES_POR_IDIOMA["English"])
    frases_rating = frases_disponibles.get(rating, frases_disponibles[3])

    n_frases = rng.integers(2, 5)
    n_frases = min(n_frases, len(frases_rating))

    seleccion = rng.choice(frases_rating, size=n_frases, replace=False)
    texto = ". ".join(seleccion)

    # Asegurar que termina en punto
    if not texto.endswith((".", "!", "?")):
        texto += "."

    return texto


def generar_rating(rng: np.random.Generator) -> int:
    """Genera rating 1-5 con distribución sesgada positivamente (Beta(6,2))."""
    valor_beta = rng.beta(6, 2)
    rating = int(round(valor_beta * 4 + 1))
    return max(1, min(5, rating))


def generar_sentiment_score(rng: np.random.Generator, rating: int) -> float:
    """Genera sentiment score correlacionado con rating."""
    low, high = SENTIMENT_RANGES.get(rating, (0.25, 0.55))
    score = rng.uniform(low, high)
    return round(float(score), 4)


def generar_reviews(
    rng: np.random.Generator,
    bookings: list[dict],
) -> list[dict]:
    """Genera reseñas para bookings con left_review=1."""
    reviews = []
    review_counter = 100000

    logger.info(f"Generando reseñas para {len(bookings)} bookings...")

    for i, bk in enumerate(bookings):
        # Rating
        rating = generar_rating(rng)

        # Idioma de la reseña
        idioma = bk["language"]

        # Texto de reseña
        review_text = generar_review_text(rng, idioma, rating)

        # Review date: travel_date + 1-30 días
        try:
            travel_dt = datetime.strptime(bk["travel_date"], "%Y-%m-%d")
        except (ValueError, TypeError):
            travel_dt = datetime(2024, 6, 15)
        review_offset = int(rng.integers(1, 31))
        review_date = travel_dt + timedelta(days=review_offset)

        # Sentiment score
        sentiment_score = generar_sentiment_score(rng, rating)

        review_id = f"REV_{review_counter}"
        review_counter += 1

        reviews.append({
            "review_id": review_id,
            "experience_id": bk["experience_id"],
            "rating": rating,
            "review_text": review_text,
            "review_date": review_date.strftime("%Y-%m-%d"),
            "reviewer_country": bk["country"],
            "reviewer_language": idioma,
            "age_group": bk["age_group"],
            "sentiment_score": sentiment_score,
        })

        if (i + 1) % 10000 == 0:
            logger.info(f"  Generadas {i + 1}/{len(bookings)} reseñas")

    return reviews


def insertar_reviews(conn: sqlite3.Connection, reviews: list[dict]) -> int:
    """Inserta reviews en la BD. Retorna número de insertadas."""
    insertadas = 0
    batch_size = 5000

    for i in range(0, len(reviews), batch_size):
        batch = reviews[i:i + batch_size]
        for rev in batch:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO reviews_dataset
                    (review_id, experience_id, rating, review_text,
                     review_date, reviewer_country, reviewer_language,
                     age_group, sentiment_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rev["review_id"], rev["experience_id"], rev["rating"],
                    rev["review_text"], rev["review_date"], rev["reviewer_country"],
                    rev["reviewer_language"], rev["age_group"], rev["sentiment_score"],
                ))
                insertadas += 1
            except sqlite3.IntegrityError:
                pass
            except Exception as e:
                logger.warning(f"Error insertando review {rev['review_id']}: {e}")

        conn.commit()
        logger.info(f"  Batch {i // batch_size + 1}: {insertadas} insertadas")

    return insertadas


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generador de ~50.000 reseñas con sentiment score"
    )
    parser.add_argument(
        "--db", type=str, default="data/tui_recomendador.db",
        help="Ruta a la base de datos SQLite (default: data/tui_recomendador.db)"
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    db_path = project_root / args.db

    if not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("📝 GENERADOR DE REVIEWS DATASET CON SENTIMENT SCORE")
    print("=" * 70)
    print(f"Base de datos: {db_path}")
    print(f"Objetivo: ~50.000 reseñas (bookings con left_review=1)")
    print(f"Idiomas: Spanish, English, German, French, Dutch, Italian")
    print(f"Seed: {SEED}")
    print()

    conn = sqlite3.connect(str(db_path))
    crear_tabla_reviews(conn)

    # Cargar bookings con reseña
    bookings = cargar_bookings_con_review(conn)
    if not bookings:
        print("❌ No hay bookings con left_review=1 en la BD.")
        print("   Ejecuta primero: python scripts/generate_customer_bookings.py")
        conn.close()
        sys.exit(1)

    print(f"🎫 Bookings con left_review=1: {len(bookings):,}")
    print()

    # Generar reviews
    rng = np.random.default_rng(SEED)
    reviews = generar_reviews(rng, bookings)
    logger.info(f"Generadas {len(reviews)} reseñas")

    # Contar existentes
    cursor = conn.execute("SELECT COUNT(*) FROM reviews_dataset")
    existentes = cursor.fetchone()[0]

    # Insertar
    insertadas = insertar_reviews(conn, reviews)
    conn.close()

    # Estadísticas
    por_rating = {}
    for r in reviews:
        rating = r["rating"]
        por_rating[rating] = por_rating.get(rating, 0) + 1

    por_idioma = {}
    for r in reviews:
        lang = r["reviewer_language"]
        por_idioma[lang] = por_idioma.get(lang, 0) + 1

    sentiments = [r["sentiment_score"] for r in reviews]

    # Resumen final
    print()
    print("=" * 70)
    print("📊 RESUMEN FINAL")
    print("=" * 70)
    print(f"✅ Reseñas generadas: {len(reviews):,}")
    print(f"✅ Reseñas insertadas: {insertadas:,}")
    print(f"ℹ️  Ya existentes en BD: {existentes:,}")
    print()
    print("⭐ Distribución de ratings:")
    for rating in sorted(por_rating.keys()):
        n = por_rating[rating]
        pct = n / len(reviews) * 100
        bar = "█" * int(pct / 2)
        print(f"   {rating}⭐: {n:>6,} ({pct:5.1f}%) {bar}")
    print()
    print("🌍 Por idioma:")
    for lang, n in sorted(por_idioma.items(), key=lambda x: x[1], reverse=True):
        print(f"   {lang}: {n:,} ({n/len(reviews)*100:.1f}%)")
    print()
    print(f"📈 Sentiment score:")
    print(f"   Media: {np.mean(sentiments):.4f}")
    print(f"   Min: {min(sentiments):.4f} | Max: {max(sentiments):.4f}")
    print(f"   Positivo (>0.5): {sum(1 for s in sentiments if s > 0.5):,}")
    print(f"   Neutro (0.2-0.5): {sum(1 for s in sentiments if 0.2 <= s <= 0.5):,}")
    print(f"   Negativo (<0.2): {sum(1 for s in sentiments if s < 0.2):,}")
    print("=" * 70)


if __name__ == "__main__":
    main()
