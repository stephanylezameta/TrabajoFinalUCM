"""
Recolector de posts de Reddit sobre destinos turísticos usando la API de
Arctic Shift (https://arctic-shift.photon-reddit.com).

Contexto: en 2026 Reddit cerró el registro autoservicio de apps para su
Data API legado (la que usa PRAW). El acceso ahora requiere una solicitud
de soporte con espera de varias semanas y, para uso académico, pasar por
el programa "Reddit for Researchers" (aprobación ética + institución
patrocinadora). Además, el uso de datos de Reddit como input para
entrenar modelos de IA/ML requiere consentimiento explícito por separado.

Arctic Shift es un proyecto de terceros (no afiliado a Reddit) que expone
datos históricos de Reddit ya archivados (basados en los dumps de
PushShift) a través de una API REST gratuita, sin autenticación ni
aprobación previa. Es la alternativa recomendada para este TFM mientras
no se resuelva el acceso oficial.

Limitación importante: los datos cubren principalmente el histórico
(no el contenido posteado en las últimas horas/días). Para este proyecto
es aceptable, ya que la petición explícita del equipo es usar datos de
2025 hacia atrás.

API pública, sin garantías de uptime — no debe considerarse una fuente
100% estable, pero es la mejor alternativa disponible sin aprobación.
"""

from __future__ import annotations

import logging
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://arctic-shift.photon-reddit.com"

# Mismo namespace usado en reddit_collector_praw.py para que, si en el
# futuro se recupera el acceso oficial vía PRAW, los ids deterministas
# sean coherentes entre ambas fuentes (mismo post de Reddit = mismo
# id_resena, sin importar qué collector lo trajo).
_NAMESPACE_REDDIT = uuid.UUID("6f1b1a2e-2f3a-4b7a-9c2d-3a6a2e1b7f10")


def _id_deterministico(fuente: str, id_externo: str) -> str:
    """Genera un UUID determinista a partir de la fuente y el id externo."""
    clave = f"{fuente}:{id_externo}"
    return str(uuid.uuid5(_NAMESPACE_REDDIT, clave))


class RedditCollectorArcticShift:
    """Recolector de posts de Reddit vía la API pública de Arctic Shift.

    No requiere credenciales. Busca posts históricos que mencionen un
    destino turístico dentro de subreddits de viajes.
    """

    subreddits_default = [
        "travel", "solotravel", "backpacking", "TravelHacks",
        "vacation", "digitalnomad", "Flights",
        # Subreddits más específicos de región/destino: suelen tener
        # menos competencia de búsqueda y más contenido sin explotar.
        "Spain", "Mexico", "greece", "travelpartners", "shoestring",
    ]

    def __init__(
        self,
        subreddits: list[str] | None = None,
        timeout: int = 20,
        pausa_entre_requests: float = 2.5,
        fecha_limite: str = "2025-01-01",
        max_reintentos: int = 4,
    ) -> None:
        """Inicializa el collector.

        Args:
            subreddits: Subreddits donde buscar. Por defecto, subreddits
                de viajes generales.
            timeout: Timeout en segundos para cada request HTTP.
            pausa_entre_requests: Segundos de espera entre requests
                sucesivos, para ser considerados con el servicio gratuito.
                Se sube de 0.5s a 2.5s por defecto para scraping masivo
                prolongado (menor riesgo de bloqueo por rate limiting).
            fecha_limite: Fecha ISO (YYYY-MM-DD) usada como límite superior
                por defecto en las búsquedas (parámetro `before`). Por
                decisión del equipo, se usan datos de 2025 hacia atrás.
            max_reintentos: Número de reintentos ante error 429 (rate
                limit) o 5xx (error del servidor), con backoff exponencial.
        """
        self.subreddits = subreddits or self.subreddits_default
        self.timeout = timeout
        self.pausa = pausa_entre_requests
        self.fecha_limite = fecha_limite
        self.max_reintentos = max_reintentos
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "tui-recomendador-tfm/1.0 (uso academico)"
        })

    def collect_posts(
        self,
        destino: str,
        limite: int = 100,
        before: str | None = None,
        after: str | None = None,
    ) -> list[dict[str, Any]]:
        """Recolecta posts históricos de Reddit sobre un destino turístico."""
        before = before or self.fecha_limite
        resultados: list[dict[str, Any]] = []
        vistos: set[str] = set()

        por_subreddit = max(1, limite // max(1, len(self.subreddits)))

        for subreddit in self.subreddits:
            if len(resultados) >= limite:
                break

            params = {
                "subreddit": subreddit,
                "query": destino,
                "limit": min(100, por_subreddit * 2),
                "before": before,
                "fields": "id,title,selftext,created_utc,score,"
                          "num_comments,subreddit,url",
            }
            if after:
                params["after"] = after

            try:
                posts = self._get_con_reintentos(params)

                for post in posts:
                    if len(resultados) >= limite:
                        break
                    pid = post.get("id")
                    if not pid or pid in vistos:
                        continue
                    vistos.add(pid)

                    resena = self._post_a_resena(post, destino, subreddit)
                    if resena:
                        resultados.append(resena)

            except requests.RequestException as exc:
                logger.warning(
                    "RedditCollectorArcticShift: error en r/%s para '%s': %s",
                    subreddit, destino, exc,
                )
            finally:
                time.sleep(self.pausa)

        logger.info(
            "RedditCollectorArcticShift: %d resultado(s) para '%s'",
            len(resultados), destino,
        )
        return resultados[:limite]

    def collect_comments(
        self,
        destino: str,
        limite: int = 100,
        before: str | None = None,
        after: str | None = None,
    ) -> list[dict[str, Any]]:
        """Recolecta comentarios históricos de Reddit sobre un destino.

        Los comentarios suelen tener mucho más volumen que los posts (cada
        post puede tener docenas de comentarios), y a menudo contienen
        opiniones más directas y específicas sobre el destino que el post
        original. Usa el endpoint /api/comments/search de Arctic Shift.
        """
        before = before or self.fecha_limite
        resultados: list[dict[str, Any]] = []
        vistos: set[str] = set()

        por_subreddit = max(1, limite // max(1, len(self.subreddits)))

        for subreddit in self.subreddits:
            if len(resultados) >= limite:
                break

            params = {
                "subreddit": subreddit,
                "body": destino,
                "limit": min(100, por_subreddit * 2),
                "before": before,
                "fields": "id,body,created_utc,score,subreddit,link_id",
            }
            if after:
                params["after"] = after

            try:
                comentarios = self._get_con_reintentos(
                    params, endpoint="comments", timeout=35
                )

                for c in comentarios:
                    if len(resultados) >= limite:
                        break
                    cid = c.get("id")
                    if not cid or cid in vistos:
                        continue
                    vistos.add(cid)

                    resena = self._comentario_a_resena(c, destino, subreddit)
                    if resena:
                        resultados.append(resena)

            except requests.RequestException as exc:
                logger.warning(
                    "RedditCollectorArcticShift: error (comments) en r/%s "
                    "para '%s': %s",
                    subreddit, destino, exc,
                )
            finally:
                time.sleep(self.pausa)

        logger.info(
            "RedditCollectorArcticShift: %d comentario(s) para '%s'",
            len(resultados), destino,
        )
        return resultados[:limite]

    def collect_all(
        self,
        destino: str,
        limite_posts: int = 50,
        limite_comentarios: int = 50,
        before: str | None = None,
        after: str | None = None,
    ) -> list[dict[str, Any]]:
        """Recolecta posts y comentarios combinados para un destino."""
        posts = self.collect_posts(destino, limite_posts, before, after)
        comentarios = self.collect_comments(
            destino, limite_comentarios, before, after
        )
        return posts + comentarios

    def _get_con_reintentos(
        self, params: dict[str, Any], endpoint: str = "posts",
        timeout: int | None = None,
    ) -> list[dict[str, Any]]:
        """Hace el request con reintentos y backoff exponencial ante 429/5xx."""
        ultimo_error: requests.RequestException | None = None

        for intento in range(self.max_reintentos + 1):
            try:
                resp = self.session.get(
                    f"{BASE_URL}/api/{endpoint}/search",
                    params=params,
                    timeout=timeout or self.timeout,
                )
                if (
                    resp.status_code == 429
                    or resp.status_code == 422
                    or resp.status_code >= 500
                ):
                    espera = self._calcular_espera(resp, intento)
                    logger.info(
                        "RedditCollectorArcticShift: %s, reintentando en %.1fs "
                        "(intento %d/%d)",
                        resp.status_code, espera, intento + 1, self.max_reintentos,
                    )
                    time.sleep(espera)
                    continue

                resp.raise_for_status()
                payload = resp.json()
                return payload.get("data", [])

            except requests.RequestException as exc:
                ultimo_error = exc
                if intento < self.max_reintentos:
                    espera = self._calcular_espera(None, intento)
                    time.sleep(espera)

        raise ultimo_error or requests.RequestException("Fallo desconocido")

    @staticmethod
    def _calcular_espera(
        resp: "requests.Response | None", intento: int
    ) -> float:
        """Calcula segundos de espera: usa Retry-After si existe, si no
        backoff exponencial con jitter (2, 4, 8, 16s... + aleatorio)."""
        if resp is not None:
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                try:
                    return float(retry_after) + random.uniform(0, 1)
                except ValueError:
                    pass
        base = min(2 ** (intento + 1), 60)
        return base + random.uniform(0, 2)

    def _post_a_resena(
        self, post: dict[str, Any], destino: str, subreddit: str
    ) -> dict[str, Any] | None:
        """Convierte un post de la API de Arctic Shift a diccionario Resena."""
        titulo = (post.get("title") or "").strip()
        cuerpo = (post.get("selftext") or "").strip()

        if not titulo and not cuerpo:
            return None

        texto = titulo
        if cuerpo and cuerpo not in ("[deleted]", "[removed]"):
            texto = f"{titulo}\n\n{cuerpo[:1500]}" if titulo else cuerpo[:1500]

        created_utc = post.get("created_utc")
        fecha_publicacion = None
        if created_utc:
            try:
                fecha_publicacion = datetime.fromtimestamp(
                    float(created_utc), tz=timezone.utc
                ).replace(tzinfo=None)
            except (ValueError, TypeError):
                pass

        return {
            "id_resena": _id_deterministico("reddit", post["id"]),
            "destino_nombre": destino,
            "fuente": "reddit",
            "texto_original": texto,
            "idioma": self._detectar_idioma(texto),
            "puntuacion": None,  # Arctic Shift no expone upvote_ratio
            "fecha_publicacion": fecha_publicacion,
            "url_fuente": (
                f"https://reddit.com/r/{subreddit}/comments/{post['id']}/"
            ),
            "fecha_extraccion": datetime.utcnow().isoformat(),
            "_meta": {
                "subreddit": subreddit,
                "reddit_id": post["id"],
                "score": post.get("score"),
                "num_comments": post.get("num_comments"),
                "fuente_extraccion": "arctic_shift",
            },
        }

    def _comentario_a_resena(
        self, c: dict[str, Any], destino: str, subreddit: str
    ) -> dict[str, Any] | None:
        """Convierte un comentario de la API de Arctic Shift a Resena."""
        body = (c.get("body") or "").strip()

        if not body or body in ("[deleted]", "[removed]") or len(body) < 20:
            return None

        created_utc = c.get("created_utc")
        fecha_publicacion = None
        if created_utc:
            try:
                fecha_publicacion = datetime.fromtimestamp(
                    float(created_utc), tz=timezone.utc
                ).replace(tzinfo=None)
            except (ValueError, TypeError):
                pass

        return {
            "id_resena": _id_deterministico("reddit_comment", c["id"]),
            "destino_nombre": destino,
            "fuente": "reddit",
            "texto_original": body[:1500],
            "idioma": self._detectar_idioma(body),
            "puntuacion": None,
            "fecha_publicacion": fecha_publicacion,
            "url_fuente": (
                f"https://reddit.com/r/{subreddit}/comments/"
                f"{(c.get('link_id') or '').replace('t3_', '')}/"
                f"comment/{c['id']}/"
            ),
            "fecha_extraccion": datetime.utcnow().isoformat(),
            "_meta": {
                "subreddit": subreddit,
                "reddit_id": c["id"],
                "score": c.get("score"),
                "fuente_extraccion": "arctic_shift",
                "tipo": "comentario",
            },
        }

    @staticmethod
    def _score_a_puntuacion_5(upvote_ratio: float | None) -> float | None:
        """Convierte upvote_ratio [0,1] a una escala aproximada [1,5]."""
        if upvote_ratio is None:
            return None
        try:
            return round(1 + (float(upvote_ratio) * 4), 2)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _detectar_idioma(texto: str) -> str:
        """Detecta idioma con langdetect."""
        try:
            from langdetect import detect
            if len(texto.strip()) < 10:
                return "unknown"
            return detect(texto)
        except Exception:
            return "unknown"