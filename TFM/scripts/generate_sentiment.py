"""
Genera sentimiento estimado para las reseñas reales scrapeadas (tabla
'resenas'), que no tienen rating/puntuacion de ninguna fuente.

Modelo: cardiffnlp/twitter-xlm-roberta-base-sentiment (XLM-RoBERTa
multilingue, 3 clases: negative/neutral/positive). Elegido por ser el
enfoque mas validado entre proyectos TFM anteriores del mismo desafio
TUI (2 de 5 equipos usaron XLM-RoBERTa con buenos resultados).

Guarda el resultado en una tabla nueva 'resenas_sentimiento' (no
modifica la tabla 'resenas' original). Reanudable: si se corta a mitad
de camino, la proxima corrida continua donde quedo (no reprocesa
reseñas ya evaluadas).

Uso:
    cd TFM
    python scripts/generate_sentiment.py
    python scripts/generate_sentiment.py --db data/tui_recomendador.db --batch-size 32
    python scripts/generate_sentiment.py --limite 500   # prueba rapida
"""
import argparse
import sqlite3
import sys
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-sentiment"

# Mapeo de etiqueta del modelo a score numerico en [0,1], coherente con
# la escala de sentiment_score que ya usa reviews_dataset (sintetico).
LABEL_TO_SCORE_BASE = {
    "negative": 0.15,
    "neutral": 0.5,
    "positive": 0.85,
}


def crear_tabla(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS resenas_sentimiento (
            id_resena TEXT PRIMARY KEY,
            sentiment_label TEXT NOT NULL,
            sentiment_score REAL NOT NULL,
            confianza REAL NOT NULL,
            modelo TEXT NOT NULL,
            fecha_procesamiento TEXT NOT NULL
        )
    """)
    conn.commit()


def obtener_pendientes(conn: sqlite3.Connection, limite: int | None) -> list[tuple[str, str]]:
    """Reseñas que aún no tienen sentimiento calculado."""
    sql = """
        SELECT r.id_resena, r.texto_original
        FROM resenas r
        LEFT JOIN resenas_sentimiento s ON r.id_resena = s.id_resena
        WHERE s.id_resena IS NULL
          AND r.texto_original IS NOT NULL
          AND LENGTH(r.texto_original) > 15
    """
    if limite:
        sql += f" LIMIT {int(limite)}"
    return conn.execute(sql).fetchall()


def calcular_score(label: str, prob: float) -> float:
    """Combina la etiqueta y la probabilidad del modelo en un score [0,1].

    Ej: 'positive' con prob 0.95 -> score cercano a 1.0
        'negative' con prob 0.95 -> score cercano a 0.0
        'neutral' siempre cerca de 0.5, independiente de la probabilidad.
    """
    base = LABEL_TO_SCORE_BASE.get(label, 0.5)
    if label == "positive":
        return round(0.5 + (prob * 0.5), 4)
    elif label == "negative":
        return round(0.5 - (prob * 0.5), 4)
    return round(base, 4)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/tui_recomendador.db")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--limite", type=int, default=None,
                         help="Procesar solo N reseñas (para pruebas rápidas)")
    parser.add_argument("--commit-every", type=int, default=200,
                         help="Guardar en la BD cada N reseñas procesadas")
    args = parser.parse_args()

    start = time.time()

    db_path = Path(args.db)
    if not db_path.exists():
        logger.error("No se encontró la base de datos en %s", db_path)
        return

    conn = sqlite3.connect(str(db_path))
    crear_tabla(conn)

    pendientes = obtener_pendientes(conn, args.limite)
    if not pendientes:
        logger.info("No hay reseñas pendientes de procesar. Todo al día.")
        conn.close()
        return

    logger.info("Reseñas pendientes: %d", len(pendientes))

    logger.info("Cargando modelo %s (puede tardar la primera vez, se descarga)...", MODEL_NAME)
    import torch
    from transformers import pipeline

    device = 0 if torch.cuda.is_available() else -1
    logger.info("Usando %s", "GPU" if device == 0 else "CPU")

    clasificador = pipeline(
        "sentiment-analysis",
        model=MODEL_NAME,
        tokenizer=MODEL_NAME,
        device=device,
        truncation=True,
        max_length=512,
    )

    procesadas = 0
    fecha_proc = time.strftime("%Y-%m-%d %H:%M:%S")

    for i in range(0, len(pendientes), args.batch_size):
        lote = pendientes[i:i + args.batch_size]
        ids = [r[0] for r in lote]
        textos = [r[1][:2000] for r in lote]  # mismo límite de truncado que embeddings

        try:
            resultados = clasificador(textos, batch_size=args.batch_size)
        except Exception as e:
            logger.warning("Error procesando lote %d-%d: %s", i, i + len(lote), e)
            continue

        for id_resena, res in zip(ids, resultados):
            label = res["label"].lower()
            prob = res["score"]
            score = calcular_score(label, prob)
            conn.execute(
                """INSERT OR REPLACE INTO resenas_sentimiento
                   (id_resena, sentiment_label, sentiment_score, confianza, modelo, fecha_procesamiento)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (id_resena, label, score, prob, MODEL_NAME, fecha_proc),
            )
            procesadas += 1

        if procesadas % args.commit_every < args.batch_size:
            conn.commit()
            elapsed = time.time() - start
            ritmo = procesadas / elapsed if elapsed > 0 else 0
            restantes = len(pendientes) - procesadas
            eta_min = (restantes / ritmo / 60) if ritmo > 0 else 0
            logger.info(
                "  Procesadas: %d/%d (%.1f/s) - ETA: %.1f min",
                procesadas, len(pendientes), ritmo, eta_min,
            )

    conn.commit()

    total_en_bd = conn.execute("SELECT COUNT(*) FROM resenas_sentimiento").fetchone()[0]
    distribucion = conn.execute(
        "SELECT sentiment_label, COUNT(*) FROM resenas_sentimiento GROUP BY sentiment_label"
    ).fetchall()
    conn.close()

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"  SENTIMIENTO GENERADO")
    print(f"{'='*60}")
    print(f"  Procesadas esta corrida: {procesadas}")
    print(f"  Total en resenas_sentimiento: {total_en_bd}")
    print(f"  Distribución:")
    for label, cnt in distribucion:
        print(f"    {label}: {cnt}")
    print(f"  Tiempo total: {elapsed/60:.1f} minutos")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()