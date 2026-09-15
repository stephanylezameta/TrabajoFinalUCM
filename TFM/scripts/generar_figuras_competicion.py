"""
Genera dos figuras para la presentacion de la competicion de becas:
  1) diagrama del pipeline de extremo a extremo (slide 4)
  2) comparativa de los 3 escenarios de re-ranking (slide 8)

Salida:
  docs/assets_ppt/pipeline.png
  docs/assets_ppt/escenarios.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

TUI_BLUE = "#002D72"
TUI_ACCENT = "#E60078"
LIGHT = "#F2F4F8"
GREY = "#555A66"
CARD = "#0B3D91"

OUT = Path(__file__).resolve().parent.parent / "docs" / "assets_ppt"
OUT.mkdir(parents=True, exist_ok=True)


# -----------------------------------------------------------------------------
# 1) Pipeline
# -----------------------------------------------------------------------------
def figura_pipeline():
    fig, ax = plt.subplots(figsize=(12, 3.6), dpi=200)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 3.6)
    ax.axis("off")

    bloques = [
        ("1 · Ingesta\n& scraping", "TUI, Booking,\nTripAdvisor, Reddit,\nEurostat, INE, AEMET"),
        ("2 · Embeddings", "Transformer multilingue\n+ vector hibrido"),
        ("3 · Recomendador", "Coseno + LightFM\n(WARP)"),
        ("4 · TDRS +\nre-ranking", "8 factores\nredistribucion"),
        ("5 · LLM +\ndashboard", "Explicabilidad\n+ producto"),
    ]

    n = len(bloques)
    bw, bh = 1.95, 1.7
    gap = (12 - n * bw) / (n + 1)
    y = 1.1
    centers = []
    for i, (titulo, sub) in enumerate(bloques):
        x = gap + i * (bw + gap)
        centers.append((x + bw / 2, y + bh / 2))
        box = FancyBboxPatch(
            (x, y), bw, bh,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            linewidth=0, facecolor=TUI_BLUE if i % 2 == 0 else CARD,
        )
        ax.add_patch(box)
        ax.text(x + bw / 2, y + bh - 0.42, titulo, ha="center", va="center",
                color="white", fontsize=11.5, fontweight="bold")
        ax.text(x + bw / 2, y + 0.5, sub, ha="center", va="center",
                color="#C9D6F0", fontsize=8.2)

    for i in range(n - 1):
        x0 = centers[i][0] + bw / 2
        x1 = centers[i + 1][0] - bw / 2
        arr = FancyArrowPatch((x0, y + bh / 2), (x1, y + bh / 2),
                              arrowstyle="-|>", mutation_scale=16,
                              color=TUI_ACCENT, linewidth=2.2)
        ax.add_patch(arr)

    ax.text(6, 3.25, "Pipeline de extremo a extremo",
            ha="center", va="center", fontsize=15, fontweight="bold",
            color=TUI_BLUE)
    ax.text(6, 0.42, "Configuracion centralizada · base de datos · API · dashboard reproducible",
            ha="center", va="center", fontsize=9.5, color=GREY, style="italic")

    fig.tight_layout()
    path = OUT / "pipeline.png"
    fig.savefig(path, transparent=True, bbox_inches="tight")
    plt.close(fig)
    return path


# -----------------------------------------------------------------------------
# 2) Escenarios de re-ranking
# -----------------------------------------------------------------------------
def figura_escenarios():
    # pesos alpha/beta/gamma/delta/lambda del config.yml
    escenarios = {
        "Tradicional": [1.0, 0.0, 0.0, 0.0, 0.0],
        "Redistribucion\nmoderada": [0.5, 0.2, 0.1, 0.1, 0.1],
        "Redistribucion\nintensiva": [0.3, 0.3, 0.15, 0.15, 0.1],
    }
    componentes = ["Afinidad", "Diversificacion", "Cobertura", "Sostenibilidad", "Saturacion"]
    colores = [TUI_BLUE, TUI_ACCENT, "#00A3A3", "#4CAF50", "#FF9800"]

    fig, ax = plt.subplots(figsize=(11, 4.3), dpi=200)
    nombres = list(escenarios.keys())
    x = np.arange(len(nombres))
    bottoms = np.zeros(len(nombres))
    datos = np.array([escenarios[k] for k in nombres])  # filas=escenario

    for j, comp in enumerate(componentes):
        valores = datos[:, j]
        ax.bar(x, valores, bottom=bottoms, width=0.55,
               label=comp, color=colores[j], edgecolor="white", linewidth=1.2)
        bottoms += valores

    ax.set_xticks(x)
    ax.set_xticklabels(nombres, fontsize=11, fontweight="bold", color=TUI_BLUE)
    ax.set_ylabel("Peso en el score de re-ranking", fontsize=10, color=GREY)
    ax.set_title("Del ranking clasico a la redistribucion: mismos candidatos, distinto peso",
                 fontsize=13, fontweight="bold", color=TUI_BLUE, pad=14)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GREY)
    ax.spines["bottom"].set_color(GREY)
    ax.tick_params(colors=GREY)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=5,
              frameon=False, fontsize=9)

    ax.annotate(">=30% destinos distintos en el top",
                xy=(2, 1.0), xytext=(1.35, 1.15),
                fontsize=9, color=TUI_ACCENT, fontweight="bold",
                ha="center")

    fig.tight_layout()
    path = OUT / "escenarios.png"
    fig.savefig(path, transparent=False, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return path


if __name__ == "__main__":
    p1 = figura_pipeline()
    p2 = figura_escenarios()
    log = OUT.parent / "_figuras_log.txt"
    log.write_text(f"OK\n{p1}\n{p2}\n", encoding="utf-8")
    print("OK", p1, p2)
