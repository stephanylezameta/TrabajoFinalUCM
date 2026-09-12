import json
import time
import urllib.request
import urllib.error

BASE = "https://javier-tui-recomendador-api.greenbush-59ba65d9.eastus2.azurecontainerapps.io"
OUT = "scripts/_diag_chat_out.txt"

body = {
    "mensaje": "playa tranquila en septiembre",
    "historial": [],
    "session_id": None,
}
lines = []
for intento in range(1, 4):
    t0 = time.time()
    try:
        req = urllib.request.Request(
            f"{BASE}/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        dt = round(time.time() - t0, 1)
        lines.append(f"[intento {intento}] OK en {dt}s")
        lines.append("  CLAVES: " + ", ".join(data.keys()))
        lines.append("  TIENE_RANKINGS: " + str("rankings" in data))
        if "rankings" in data and isinstance(data["rankings"], dict):
            lines.append("  ESCENARIOS: " + ", ".join(data["rankings"].keys()))
        break
    except urllib.error.HTTPError as e:
        dt = round(time.time() - t0, 1)
        cuerpo = ""
        try:
            cuerpo = e.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        lines.append(f"[intento {intento}] HTTP {e.code} en {dt}s | {cuerpo}")
    except Exception as e:
        dt = round(time.time() - t0, 1)
        lines.append(f"[intento {intento}] ERROR en {dt}s: {e!r}")
    time.sleep(5)

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
