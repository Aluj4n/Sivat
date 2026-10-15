"""
Figuras de evaluación para el paper (PNG estático). Paleta de referencia
validada del skill de dataviz: categóricos azul/naranja/aqua (los tres
primeros espacios, seguros para daltonismo entre todos los pares), rampa
secuencial azul de un solo tono para la matriz de confusión, texto siempre
en tinta neutra y nunca del color de la serie.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score, roc_curve  # noqa: E402

SUPERFICIE = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO_2 = "#52514e"
TENUE = "#898781"
GRILLA = "#e1e0d9"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]  # orden fijo, máximo 3 series por gráfico
RAMPA_AZUL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#104281"]

NOMBRES = {
    "regresion_logistica": "Regresión logística",
    "naive_bayes": "Naive Bayes",
    "svm_lineal": "SVM lineal",
    "random_forest": "Random Forest",
    "knn": "KNN",
    "gradient_boosting": "Gradient Boosting",
    "red_neuronal_mlp": "Red neuronal (MLP)",
}

plt.rcParams.update({
    "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE, "savefig.facecolor": SUPERFICIE,
    "axes.edgecolor": GRILLA, "axes.labelcolor": TEXTO_2, "xtick.color": TEXTO_2, "ytick.color": TEXTO_2,
    "text.color": TEXTO, "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
})


def _guardar(fig, carpeta: Path, nombre: str) -> None:
    carpeta.mkdir(exist_ok=True)
    fig.savefig(carpeta / f"{nombre}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def comparacion_modelos(resultados: list, sufijo: str, titulo: str, carpeta: Path,
                        referencia: float | None = None, etiqueta_referencia: str = "") -> None:
    """Barras horizontales de F1 macro en prueba, una serie (un color), ordenadas."""
    filas = sorted(resultados, key=lambda r: r["prueba"]["f1_macro"])
    nombres = [NOMBRES.get(r["modelo"], r["modelo"]) for r in filas]
    valores = [r["prueba"]["f1_macro"] for r in filas]

    fig, ax = plt.subplots(figsize=(7, 0.45 * len(filas) + 1.2))
    ax.barh(nombres, valores, color=SERIES[0], height=0.6, edgecolor=SUPERFICIE, linewidth=2)
    for y, v in enumerate(valores):
        ax.text(v + 0.01, y, f"{v:.3f}", va="center", color=TEXTO, fontsize=9)
    if referencia is not None:
        ax.axvline(referencia, color=TENUE, linestyle="--", linewidth=1)
        # Etiqueta en una franja propia bajo la última barra: no choca con título ni eje
        ax.set_ylim(-1.1, len(filas) - 0.5)
        ax.text(referencia, -0.85, f" {etiqueta_referencia}: {referencia:.3f}", color=TEXTO_2,
                fontsize=8, va="center")
    ax.set_xlim(0, 1)
    ax.set_xlabel("F1 macro (prueba)")
    ax.xaxis.grid(True, color=GRILLA, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title(titulo, loc="left")
    _guardar(fig, carpeta, f"comparacion_{sufijo}")


def matriz_confusion(matriz: list, sufijo: str, titulo: str, carpeta: Path) -> None:
    m = np.array(matriz)
    porcentaje = m / m.sum(axis=1, keepdims=True)  # por fila: tasa de acierto de cada clase real
    cmap = LinearSegmentedColormap.from_list("azul", RAMPA_AZUL)

    fig, ax = plt.subplots(figsize=(4.6, 4))
    ax.imshow(porcentaje, cmap=cmap, vmin=0, vmax=1)
    for i in range(2):
        for j in range(2):
            oscuro = porcentaje[i, j] > 0.55
            ax.text(j, i, f"{m[i, j]:,}\n{porcentaje[i, j]:.0%}", ha="center", va="center",
                    color="#ffffff" if oscuro else TEXTO, fontsize=11, fontweight="bold")
    clases = ["Confiable", "Desinformación"]
    ax.set_xticks([0, 1], clases)
    ax.set_yticks([0, 1], clases)
    ax.set_xlabel("Predicción del modelo")
    ax.set_ylabel("Etiqueta del verificador / corpus")
    ax.tick_params(length=0)
    for lado in ax.spines.values():
        lado.set_visible(False)
    ax.set_title(titulo, loc="left", fontsize=10)
    _guardar(fig, carpeta, f"matriz_confusion_{sufijo}")


def curvas(y: np.ndarray, probas: dict, sufijo: str, titulo: str, carpeta: Path) -> None:
    """ROC y Precisión-Exhaustividad lado a lado; hasta 3 modelos (orden fijo de color)."""
    fig, (roc, pr) = plt.subplots(1, 2, figsize=(10, 4.2))
    for color, (nombre, proba) in zip(SERIES, list(probas.items())[:3]):
        etiqueta = NOMBRES.get(nombre, nombre)
        fpr, tpr, _ = roc_curve(y, proba)
        roc.plot(fpr, tpr, color=color, linewidth=2, label=f"{etiqueta} (AUC {roc_auc_score(y, proba):.3f})")
        precision, recall, _ = precision_recall_curve(y, proba)
        pr.plot(recall, precision, color=color, linewidth=2,
                label=f"{etiqueta} (AP {average_precision_score(y, proba):.3f})")

    roc.plot([0, 1], [0, 1], color=TENUE, linestyle="--", linewidth=1, label="Azar")
    pr.axhline(y.mean(), color=TENUE, linestyle="--", linewidth=1, label=f"Azar ({y.mean():.2f})")
    for ax, (xl, yl, sub) in zip((roc, pr), [("Tasa de falsos positivos", "Tasa de verdaderos positivos", "Curva ROC"),
                                             ("Exhaustividad (recall) de desinformación", "Precisión",
                                              "Curva Precisión-Exhaustividad")]):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.02)
        ax.set_xlabel(xl)
        ax.set_ylabel(yl)
        ax.grid(True, color=GRILLA, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.set_title(f"{titulo} · {sub}", loc="left", fontsize=10)
        ax.legend(frameon=False, fontsize=8, loc="lower right" if ax is roc else "lower left", labelcolor=TEXTO)
    _guardar(fig, carpeta, f"curvas_{sufijo}")
