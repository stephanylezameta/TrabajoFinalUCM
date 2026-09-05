"""Descarga a local una fotografía por destino del catálogo.

Sirve las imágenes desde el repo en lugar de depender de una llamada a Wikipedia
en cada carga del dashboard. Las fotos se obtienen mediante la API de MediaWiki
(el mismo camino que ``destination_image_service``, que ya filtra banderas y
escudos), se reescalan y se guardan en ``assets/destinations/`` con un
``credits.json`` de atribución.

Se descarga vía la API de MediaWiki y no por URL directa de Commons porque las
descargas directas en ráfaga reciben HTTP 429. La API tolera un ritmo pausado.

Uso:
    python scripts/download_destination_images.py
    python scripts/download_destination_images.py --force
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.destination_image_service import get_destination_image  # noqa: E402
from utils.text import slugify  # noqa: E402

OUT_DIR = PROJECT_ROOT / "assets" / "destinations"
USER_AGENT = "TUI-TDRS-DashboardImages/1.0 (TFM UCM; descarga puntual)"

_PAUSE_SECONDS = 3.0
_MAX_WIDTH = 1280
_JPEG_QUALITY = 82

# Los 16 destinos del catálogo del simulador. Para varios se añade un término de
# desambiguación entre paréntesis: la búsqueda de Wikipedia lo usa pero no forma
# parte del nombre con el que se guarda el fichero.
DESTINATIONS: list[tuple[str, str]] = [
    ("Algarve", "Algarve playa"),
    ("Mallorca", "Mallorca costa"),
    ("Menorca", "Menorca cala"),
    ("Split", "Split Croacia"),
    ("Dubrovnik", "Dubrovnik ciudad vieja"),
    ("Zadar", "Zadar Croacia"),
    ("Creta", "Creta isla"),
    ("Naxos", "Naxos isla Grecia"),
    ("Maldivas", "Maldivas islas"),
    ("Cabo Verde", "Cabo Verde playa"),
    ("Cancun", "Cancún playa"),
    ("Sevilla", "Sevilla ciudad"),
    ("Ronda", "Ronda Málaga"),
    ("Carmona", "Carmona Sevilla"),
    ("Osuna", "Osuna Sevilla"),
    ("Alentejo", "Alentejo paisaje"),
]


def _resize_and_save(data: bytes, dest: Path) -> int:
    from PIL import Image  # import diferido: solo lo usa este script

    image = Image.open(io.BytesIO(data))
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    if image.width > _MAX_WIDTH:
        height = round(image.height * _MAX_WIDTH / image.width)
        image = image.resize((_MAX_WIDTH, height), Image.LANCZOS)
    image.save(dest, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
    return dest.stat().st_size


def _fetch_bytes(url: str, retries: int = 3) -> bytes:
    last: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code == 429:
                time.sleep(_PAUSE_SECONDS * (attempt + 2))
                continue
            raise
    raise last if last else RuntimeError("descarga fallida")


def _resolve_image_url(name: str, search_hint: str) -> tuple[str, str] | None:
    """Devuelve (url, credito) de la mejor foto encontrada, o None."""
    # get_destination_image ya prueba título exacto y búsqueda, en es y en, y
    # descarta banderas, escudos y mapas.
    for query in (name, search_hint):
        image = get_destination_image(query)
        if image:
            return image["url"], image.get("credit", "Wikipedia / Wikimedia Commons")
        time.sleep(_PAUSE_SECONDS)
    return None


def main(force: bool) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    credits: dict[str, dict[str, str]] = {}
    ok = 0
    failed: list[str] = []

    for name, hint in DESTINATIONS:
        dest = OUT_DIR / f"{slugify(name)}.jpg"
        if dest.exists() and not force:
            print(f"  ya existe   {name}")
            ok += 1
            credits[name] = {"file": dest.name, "credit": _existing_credit(name)}
            continue

        get_destination_image.cache_clear()
        resolved = _resolve_image_url(name, hint)
        if not resolved:
            print(f"  SIN FOTO    {name}")
            failed.append(name)
            time.sleep(_PAUSE_SECONDS)
            continue

        url, credit = resolved
        try:
            size = _resize_and_save(_fetch_bytes(url), dest)
            credits[name] = {"file": dest.name, "credit": credit}
            print(f"  descargada  {name:<14} {dest.name}  ({size/1024:.0f} KB)")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  FALLO       {name:<14} {exc}")
            failed.append(name)
        time.sleep(_PAUSE_SECONDS)

    _write_credits(credits)
    print(f"\n{ok}/{len(DESTINATIONS)} imágenes en {OUT_DIR}")
    if failed:
        print(f"Sin foto local: {', '.join(failed)} (usarán el fallback a Wikipedia en vivo).")
    return 0


def _existing_credit(name: str) -> str:
    path = OUT_DIR / "credits.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8")).get(name, {}).get("credit", "")
        except (OSError, ValueError):
            pass
    return "Wikipedia / Wikimedia Commons"


def _write_credits(new: dict[str, dict[str, str]]) -> None:
    path = OUT_DIR / "credits.json"
    merged: dict[str, dict[str, str]] = {}
    if path.exists():
        try:
            merged = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            merged = {}
    merged.update(new)
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Vuelve a descargar aunque exista.")
    args = parser.parse_args()
    raise SystemExit(main(args.force))
