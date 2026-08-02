"""
Recolector de posts y comentarios de Reddit sobre destinos turísticos.

Utiliza PRAW (Python Reddit API Wrapper) para buscar en subreddits
de viajes y extraer opiniones sobre destinos. Las credenciales se
cargan desde variables de entorno.

Requisitos cubiertos: RF-1.7 (fuentes externas de reseñas), DECISIÓN-004
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Subreddits de viaje por defecto (DECISIÓN-004)
SUBREDDITS_DEFAULT: list[str] = [
    "travel",
    "solotravel",
    "backpacking",
    "Flights",
    "TravelHacks",
    "vacation",
]


class RedditCollector:
    """Recolector de posts de Reddit sobre destinos turísticos.

    Busca menciones de destinos en subreddits de viaje y extrae
    título + cuerpo del post como texto de reseña. Es robusto ante
    fallos de autenticación: nunca lanza excepciones no controladas.

    Attributes:
        subreddits: Lista de subreddits donde buscar.
        reddit: Instancia de PRAW Reddit (None si la autenticación falla).
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_agent: str | None = None,
        subreddits: list[str] | None = None,
    ) -> None:
        """Inicializa el recolector de Reddit con credenciales.

        Las credenciales se obtienen de los parámetros o, si no se pasan,
        de las variables de entorno REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET
        y REDDIT_USER_AGENT.

        Args:
            client_id: ID de la aplicación OAuth2 de Reddit.
            client_secret: Secret de la aplicación OAuth2 de Reddit.
            user_agent: User agent para las peticiones a la API.
            subreddits: Lista de subreddits donde buscar. Si no se pasa,
                        se usan los subreddits por defecto de DECISIÓN-004.
        """
        self.subreddits = subreddits or SUBREDDITS_DEFAULT
        self.reddit = None

        # Obtener credenciales
        _client_id = client_id or os.environ.get("REDDIT_CLIENT_ID", "")
        _client_secret = client_secret or os.environ.get("REDDIT_CLIENT_SECRET", "")
        _user_agent = user_agent or os.environ.get(
            "REDDIT_USER_AGENT", "tui-recomendador/1.0"
        )

        if not _client_id or not _client_secret:
            logger.warning(
                "RedditCollector: credenciales no configuradas. "
                "Se necesitan REDDIT_CLIENT_ID y REDDIT_CLIENT_SECRET."
            )
            return

        try:
            import praw

            self.reddit = praw.Reddit(
                client_id=_client_id,
                client_secret=_client_secret,
                user_agent=_user_agent,
            )
            # Verificar autenticación con una operación ligera
            _ = self.reddit.read_only
            logger.info(
                "RedditCollector: autenticado correctamente (read-only mode)"
            )
        except Exception as exc:
            logger.warning(
                "RedditCollector: no se pudo autenticar con Reddit API: %s", exc
            )
            self.reddit = None

    def collect_posts(
        self, destino: str, limite: int = 100
    ) -> list[dict[str, Any]]:
        """Recolecta posts de Reddit que mencionan un destino turístico.

        Busca en cada subreddit configurado posts que contengan el nombre
        del destino y extrae título + cuerpo como texto de reseña.

        Args:
            destino: Nombre del destino turístico a buscar (e.g. "Mallorca").
            limite: Número máximo total de posts a recolectar. Por defecto 100.

        Returns:
            Lista de diccionarios con los campos:
                - destino_nombre (str): Nombre del destino buscado.
                - fuente (str): Siempre "reddit".
                - texto_original (str): Título + cuerpo del post.
                - idioma (str): Código de idioma detectado.
                - puntuacion (float | None): Score normalizado del post (0-5).
                - fecha_publicacion (str | None): Fecha de creación ISO.
                - url_fuente (str): URL permanente del post en Reddit.
                - fecha_extraccion (str): Marca temporal ISO de extracción.

            Retorna lista vacía si PRAW no puede autenticar o la conexión falla.
        """
        if self.reddit is None:
            logger.warning(
                "RedditCollector: no se puede recolectar sin autenticación. "
                "Retornando lista vacía."
            )
            return []

        posts: list[dict[str, Any]] = []
        posts_por_subreddit = max(1, limite // len(self.subreddits))

        logger.info(
            "RedditCollector: buscando '%s' en %d subreddits (limite=%d)",
            destino,
            len(self.subreddits),
            limite,
        )

        for subreddit_name in self.subreddits:
            if len(posts) >= limite:
                break

            try:
                subreddit = self.reddit.subreddit(subreddit_name)
                resultados = subreddit.search(
                    destino, limit=posts_por_subreddit, sort="relevance"
                )

                for submission in resultados:
                    if len(posts) >= limite:
                        break

                    post = self._parsear_submission(submission, destino)
                    if post is not None:
                        posts.append(post)

            except Exception as exc:
                logger.warning(
                    "RedditCollector: error en subreddit '%s': %s",
                    subreddit_name,
                    exc,
                )
                continue

        logger.info(
            "RedditCollector: %d post(s) recolectado(s) para '%s'",
            len(posts),
            destino,
        )
        return posts

    def _parsear_submission(
        self, submission: Any, destino: str
    ) -> dict[str, Any] | None:
        """Extrae los datos de un submission de Reddit.

        Args:
            submission: Objeto Submission de PRAW.
            destino: Nombre del destino para incluir en el registro.

        Returns:
            Diccionario con los campos de la reseña, o None si el post
            no tiene contenido útil.
        """
        try:
            titulo = submission.title or ""
            cuerpo = submission.selftext or ""

            texto = f"{titulo}\n\n{cuerpo}".strip()
            if len(texto) < 20:
                return None

            # Calcular puntuación normalizada (score de Reddit → escala 0-5)
            puntuacion = self._normalizar_score(submission.score)

            # Fecha de creación
            fecha_publicacion = datetime.utcfromtimestamp(
                submission.created_utc
            ).isoformat()

            # URL permanente
            url_fuente = f"https://www.reddit.com{submission.permalink}"

            # Detectar idioma
            idioma = self._detectar_idioma(texto)

            return {
                "destino_nombre": destino,
                "fuente": "reddit",
                "texto_original": texto,
                "idioma": idioma,
                "puntuacion": puntuacion,
                "fecha_publicacion": fecha_publicacion,
                "url_fuente": url_fuente,
                "fecha_extraccion": datetime.utcnow().isoformat(),
            }

        except Exception as exc:
            logger.debug(
                "RedditCollector: no se pudo parsear submission: %s", exc
            )
            return None

    @staticmethod
    def _normalizar_score(score: int) -> float | None:
        """Normaliza el score de Reddit a una escala de 0 a 5.

        Heurística: score <= 0 → 1.0, score >= 100 → 5.0, lineal entre ambos.

        Args:
            score: Puntuación (upvotes - downvotes) del post.

        Returns:
            Puntuación normalizada en [1, 5] o None si score es None.
        """
        if score is None:
            return None
        if score <= 0:
            return 1.0
        if score >= 100:
            return 5.0
        # Interpolación lineal: 0→1, 100→5
        return 1.0 + (score / 100.0) * 4.0

    @staticmethod
    def _detectar_idioma(texto: str) -> str:
        """Detecta el idioma de un texto usando langdetect.

        Args:
            texto: Texto a analizar.

        Returns:
            Código de idioma de 2 caracteres (e.g. "es", "en", "de").
            Retorna "unknown" si la detección falla.
        """
        try:
            from langdetect import detect

            if len(texto.strip()) < 10:
                return "unknown"
            return detect(texto)
        except Exception:
            return "unknown"
