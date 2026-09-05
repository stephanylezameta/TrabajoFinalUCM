"""Genera `.streamlit/secrets.toml` a partir de un fichero con la URL de la API.

Sirve para no copiar la function key a mano ni dejarla en el historial de la
terminal. El fichero generado está excluido por `.gitignore`.

Uso:
    python scripts/setup_local_secrets.py ..\\..\\propuesta_diseno\\API_AZURE.txt
    python scripts/setup_local_secrets.py --url "https://...?code=..."
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse, urlunparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SECRETS_PATH = PROJECT_ROOT / ".streamlit" / "secrets.toml"

TEMPLATE = """# Generado por scripts/setup_local_secrets.py
# NO subir este fichero al repositorio.

TUI_RECO_API_BASE = "{base}"
TUI_RECO_API_KEY = "{key}"
TUI_RECO_API_TIMEOUT = "{timeout}"
"""


def extract_url(text: str) -> str:
    """Encuentra la primera URL http(s) del texto, con o sin sintaxis PowerShell."""
    match = re.search(r"https?://[^\s'\"<>]+", text)
    if not match:
        raise SystemExit("No se encontró ninguna URL en el fichero indicado.")
    return match.group(0)


def split_url(url: str) -> tuple[str, str]:
    """Separa la URL base de la function key del querystring ``code``."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    key = (params.get("code") or [""])[0]
    base = urlunparse(parsed._replace(query="", fragment=""))
    return base, key


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, help="Fichero que contiene la URL")
    parser.add_argument("--url", help="URL completa, como alternativa al fichero")
    parser.add_argument("--timeout", default="30", help="Timeout en segundos (30 por defecto)")
    parser.add_argument("--force", action="store_true", help="Sobrescribe secrets.toml si ya existe")
    args = parser.parse_args()

    if args.url:
        url = args.url
    elif args.source:
        if not args.source.exists():
            raise SystemExit(f"No existe el fichero {args.source}")
        url = extract_url(args.source.read_text(encoding="utf-8", errors="replace"))
    else:
        parser.error("Indica un fichero de origen o --url")

    base, key = split_url(url)
    if not key:
        print("Aviso: la URL no incluye ?code=. Se escribirá solo la base.", file=sys.stderr)

    if SECRETS_PATH.exists() and not args.force:
        raise SystemExit(
            f"{SECRETS_PATH} ya existe. Usa --force para sobrescribirlo."
        )

    SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SECRETS_PATH.write_text(
        TEMPLATE.format(base=base, key=key, timeout=args.timeout), encoding="utf-8"
    )
    # Nunca se imprime la clave: solo su longitud, para poder confirmar que se leyó.
    print(f"Escrito {SECRETS_PATH}")
    print(f"  base: {base}")
    print(f"  key : {'*' * 8} ({len(key)} caracteres)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
