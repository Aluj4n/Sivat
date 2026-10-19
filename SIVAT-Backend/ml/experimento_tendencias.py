"""
Experimento del Módulo de Tendencias (aprendizaje no supervisado): compara
representaciones (embeddings e5 contra TF-IDF + SVD) y algoritmos (HDBSCAN,
K-Means con k elegido por silueta, DBSCAN con eps elegido por silueta) sobre
una foto real del feed de las últimas 24 h, por panel.

Métricas internas (no hay etiquetas de tema): silueta y Davies-Bouldin sobre
las noticias agrupadas, cantidad de grupos, % de ruido y diversidad de
fuentes por grupo (un tema real lo cubren varios medios; un grupo de un solo
sitio suele ser plantilla o publicidad). Resultados y figura PCA en
ml/resultados/.

Hallazgo: las métricas internas favorecen a TF-IDF, pero sus grupos juntan
titulares que solo comparten palabras ("Temblor ... sábado 17 de octubre"
con "Horóscopo ... sábado 17 de octubre"), mientras e5 agrupa por evento.
Por eso se guardan también los temas principales de ambas representaciones,
para la comparación cualitativa, y el sistema usa e5 + HDBSCAN.

    python -m ml.experimento_tendencias [--horas 24]
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import asyncpg
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.metrics import davies_bouldin_score, silhouette_score

from core.config import settings
from ml import figuras
from ml.agrupamiento import (
    agrupar_dbscan, agrupar_hdbscan, agrupar_kmeans, reducir, representativo, terminos_clave, vectores_e5,
    vectores_tfidf,
)
from services.tendencias_service import es_titular_util, fuente_de

RESULTADOS_DIR = Path(__file__).resolve().parent / "resultados"
MUESTRA_SILUETA = 5000
SEMILLA = 42


async def _cargar_feed(horas: int) -> pd.DataFrame:
    conexion = await asyncpg.connect(settings.DATABASE_URL.replace("+asyncpg", ""))
    try:
        filas = await conexion.fetch(
            "SELECT id, origen, titular, pais, metadatos FROM noticia_feed "
            "WHERE fecha_captura > now() - make_interval(hours => $1)", horas)
    finally:
        await conexion.close()
    df = pd.DataFrame([dict(f) for f in filas])
    df["panel"] = np.where(df["pais"].fillna("").str.lower().isin(["peru", "perú", "pe"]), "peru", "internacional")
    df["fuente"] = [fuente_de(o, m) for o, m in zip(df["origen"], df["metadatos"])]
    return df[df["titular"].map(es_titular_util)].reset_index(drop=True)


def _metricas(X: np.ndarray, etiquetas: np.ndarray, fuentes: pd.Series) -> dict:
    agrupadas = etiquetas >= 0
    grupos = len(set(etiquetas[agrupadas]))
    fila = {"grupos": grupos, "ruido": round(float(1 - agrupadas.mean()), 3)}
    if grupos >= 2:
        Xa, ea = X[agrupadas], etiquetas[agrupadas]
        fila["silueta"] = round(float(silhouette_score(Xa, ea, metric="cosine", random_state=SEMILLA,
                                                       sample_size=min(MUESTRA_SILUETA, len(ea)))), 4)
        fila["davies_bouldin"] = round(float(davies_bouldin_score(Xa, ea)), 4)
        por_grupo = pd.Series(fuentes[agrupadas].to_numpy()).groupby(ea).nunique()
        fila["grupos_con_3_o_mas_fuentes"] = round(float((por_grupo >= 3).mean()), 3)
    return fila


def _mejor_por_silueta(X, candidatos: dict, fuentes) -> tuple:
    mejor = None
    for parametro, agrupar in candidatos.items():
        etiquetas = agrupar()
        fila = _metricas(X, etiquetas, fuentes)
        if fila.get("silueta") is not None and (mejor is None or fila["silueta"] > mejor[1]["silueta"]):
            mejor = (parametro, fila, etiquetas)
    return mejor


def comparar_panel(df: pd.DataFrame) -> tuple[list, dict]:
    textos = df["titular"].str.slice(0, 300).tolist()
    resultados, guardados = [], {}
    for rep, vectorizar in [("e5", vectores_e5), ("tfidf", vectores_tfidf)]:
        inicio = time.time()
        X = vectorizar(textos)
        segundos_vectorizar = round(time.time() - inicio, 1)
        Xr = reducir(X)
        for algoritmo in ("hdbscan", "kmeans", "dbscan"):
            inicio = time.time()
            if algoritmo == "hdbscan":
                etiquetas = agrupar_hdbscan(X)
                parametro, fila = "min_cluster_size=5", _metricas(Xr, etiquetas, df["fuente"])
            elif algoritmo == "kmeans":
                ks = [k for k in (10, 20, 40, 80, 160) if k < len(df) / 5]
                parametro, fila, etiquetas = _mejor_por_silueta(
                    Xr, {f"k={k}": (lambda k=k: agrupar_kmeans(Xr, k)) for k in ks}, df["fuente"])
            else:
                parametro, fila, etiquetas = _mejor_por_silueta(
                    Xr, {f"eps={e}": (lambda e=e: agrupar_dbscan(Xr, e)) for e in (0.05, 0.1, 0.15, 0.2)},
                    df["fuente"])
            fila.update({"representacion": rep, "algoritmo": algoritmo, "parametro": parametro,
                         "segundos": round(time.time() - inicio, 1), "segundos_vectorizar": segundos_vectorizar})
            resultados.append(fila)
            guardados[(rep, algoritmo)] = (X, etiquetas)
            print(f"  [{rep} + {algoritmo}] {fila}", flush=True)
    return resultados, guardados


def _temas(df: pd.DataFrame, X: np.ndarray, etiquetas: np.ndarray, n: int = 15) -> list:
    textos = df["titular"].tolist()
    terminos = terminos_clave(textos, etiquetas)
    tamanos = pd.Series(etiquetas[etiquetas >= 0]).value_counts().head(n)
    salida = []
    for grupo, tamano in tamanos.items():
        indices = np.where(etiquetas == grupo)[0]
        salida.append({"terminos": terminos[grupo], "noticias": int(tamano),
                       "fuentes": int(df["fuente"].iloc[indices].nunique()),
                       "titular_representativo": textos[representativo(X, indices)]})
    return salida


def figura_pca(X: np.ndarray, etiquetas: np.ndarray, terminos: dict, panel: str) -> None:
    """
    Dispersión 2D (PCA) de los grupos. Solo los 3 temas más grandes llevan
    color (orden fijo de la paleta); el resto de grupos en gris y el ruido
    más tenue, para que la figura no dependa de distinguir decenas de colores.
    """
    puntos = PCA(n_components=2, random_state=SEMILLA).fit_transform(X)
    top = pd.Series(etiquetas[etiquetas >= 0]).value_counts().head(3).index.tolist()
    fig, ax = plt.subplots(figsize=(8, 6))
    ruido = etiquetas == -1
    otros = (~ruido) & ~np.isin(etiquetas, top)
    ax.scatter(*puntos[ruido].T, s=4, color=figuras.GRILLA, label="Sin tendencia (ruido)", linewidths=0)
    ax.scatter(*puntos[otros].T, s=6, color=figuras.TENUE, alpha=0.6, label="Otros temas", linewidths=0)
    for color, grupo in zip(figuras.SERIES, top):
        ax.scatter(*puntos[etiquetas == grupo].T, s=14, color=color, edgecolors=figuras.SUPERFICIE,
                   linewidths=0.6, label=", ".join(terminos[grupo][:3]))
    ax.set_xticks([])
    ax.set_yticks([])
    for lado in ax.spines.values():
        lado.set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(1.0, 1.0), labelcolor=figuras.TEXTO)
    nombre = {"peru": "Perú", "internacional": "Internacional"}[panel]
    ax.set_title(f"Tendencias · panel {nombre} · embeddings e5 + HDBSCAN (PCA 2D)", loc="left", fontsize=10)
    figuras._guardar(fig, RESULTADOS_DIR, f"tendencias_pca_{panel}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--horas", type=int, default=24)
    args = parser.parse_args()

    df = asyncio.run(_cargar_feed(args.horas))
    contenido = {"horas": args.horas, "paneles": {}}
    for panel in ("peru", "internacional"):
        datos = df[df["panel"] == panel].reset_index(drop=True)
        print(f"\n=== Panel {panel}: {len(datos)} noticias ===", flush=True)
        resultados, guardados = comparar_panel(datos)
        X, etiquetas = guardados[("e5", "hdbscan")]
        contenido["paneles"][panel] = {
            "noticias": len(datos), "fuentes_distintas": int(datos["fuente"].nunique()),
            "resultados": resultados,
            "temas_principales": {
                f"{rep}_hdbscan": _temas(datos, *guardados[(rep, "hdbscan")]) for rep in ("e5", "tfidf")
            },
        }
        figura_pca(reducir(X), etiquetas, terminos_clave(datos["titular"].tolist(), etiquetas), panel)

    RESULTADOS_DIR.mkdir(exist_ok=True)
    with open(RESULTADOS_DIR / "metricas_tendencias.json", "w", encoding="utf-8") as f:
        json.dump(contenido, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
