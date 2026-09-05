import re
import unicodedata


def normalize_text(value: object) -> str:
    s = "" if value is None else str(value)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", " ", s.lower()).strip()
    return re.sub(r"\s+", " ", s)


def slugify(value: object) -> str:
    return normalize_text(value).replace(" ", "-")
