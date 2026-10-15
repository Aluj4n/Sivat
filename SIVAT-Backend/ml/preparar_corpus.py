"""
Arma los corpus de los dos modelos de SIVAT a partir de data/raw/ (ver
ml/fuentes_datos.py):

  data/corpus_articulos.csv     Modelo A, artículos completos (FakeDeS)
  data/corpus_afirmaciones.csv  Modelo B, afirmaciones y rumores cortos
  data/resumen_corpus.json      Conteos y controles de calidad (para el paper)

    python -m ml.preparar_corpus

Etiqueta: 1 = desinformación, 0 = confiable (igual que el modelo actual).
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

from ml.calificaciones import FACTSPAN, limpiar_afirmacion, normalizar_calificacion
from ml.limpieza_texto import limpiar_texto

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"

MIN_PALABRAS_AFIRMACION = 4
# Partición temporal del Modelo B: se entrena con lo verificado hasta este
# año y se prueba con lo posterior, para medir si generaliza a rumores nuevos
ANIO_INICIO_PRUEBA = 2025


# --- Modelo A: artículos ------------------------------------------------------

def preparar_articulos() -> pd.DataFrame:
    """
    FakeDeS completo, con su partición oficial: train + development (corpus
    2019) para entrenar y test (IberLEF 2021: COVID-19 y noticias de otros
    países) para probar, comparable con los resultados publicados.
    """
    partes = []
    for archivo, particion in [("train", "train"), ("development", "train"), ("test", "test")]:
        df = pd.read_excel(RAW_DIR / f"fakedes_{archivo}.xlsx")
        df.columns = [c.strip().lower() for c in df.columns]
        df = df.rename(columns={"topics": "topic"})
        # train/development usan "Fake"/"True"; test usa booleanos (True = real)
        categoria = df["category"]
        df["etiqueta"] = categoria.map(lambda c: 1 if c in ("Fake", False, "False", 0) else 0)
        df["particion"] = particion
        df["archivo_origen"] = archivo
        partes.append(df[["headline", "text", "etiqueta", "topic", "source", "link", "particion", "archivo_origen"]])

    corpus = pd.concat(partes, ignore_index=True).rename(columns={
        "headline": "titular", "text": "texto", "topic": "tema", "source": "fuente_medio",
    })
    corpus["titular"] = corpus["titular"].fillna("").astype(str).str.strip()
    corpus["texto"] = corpus["texto"].fillna("").astype(str).str.strip()
    corpus["tema"] = corpus["tema"].astype(str).str.strip().str.title()
    corpus = corpus[corpus["texto"] != ""]
    corpus = corpus.drop_duplicates(subset=["texto"]).reset_index(drop=True)
    corpus["palabras"] = (corpus["titular"] + " " + corpus["texto"]).str.split().str.len()
    return corpus


# --- Modelo B: afirmaciones ---------------------------------------------------

def _leer_jsonl(ruta: Path) -> pd.DataFrame:
    with open(ruta, encoding="utf-8") as f:
        return pd.DataFrame([json.loads(linea) for linea in f if linea.strip()])


def _anio(valor) -> float:
    encontrado = re.search(r"(19|20)\d{2}", str(valor or ""))
    return float(encontrado.group(0)) if encontrado else float("nan")


def _desde_factspan() -> pd.DataFrame:
    df = pd.read_csv(RAW_DIR / "factspan.csv")
    df = df[df["language"].astype(str).str.lower() == "es"]
    return pd.DataFrame({
        "texto": df["claim"],
        "calificacion_original": df["label"],
        "etiqueta": df["label"].map(FACTSPAN),
        "verificador": None,  # FactSpan no conserva el verificador
        "anio": df["claimDate"].map(_anio),
        "dataset": "factspan",
    })


def _desde_claimreview(archivo: str, dataset: str) -> pd.DataFrame:
    df = _leer_jsonl(RAW_DIR / archivo)
    return pd.DataFrame({
        "texto": df["afirmacion"],
        "calificacion_original": df["calificacion"],
        "etiqueta": df["calificacion"].map(normalizar_calificacion),
        "verificador": df["verificador"],
        "anio": df["fecha"].map(_anio),
        "dataset": dataset,
    })


def _desde_upm() -> pd.DataFrame:
    """
    Rumores falsos en su texto original (Twitter, Facebook, WhatsApp...),
    verificados por Maldita, Newtral y AFP. Solo traen la clase
    desinformación: el entrenamiento compara con y sin ellos (ver resumen,
    son más largos que el resto).
    """
    df = pd.read_csv(RAW_DIR / "upm_esp_fake_news.csv")
    return pd.DataFrame({
        "texto": df["Fake statement"],
        "calificacion_original": "Falso",
        "etiqueta": 1,
        # "Link source" es donde circuló el rumor (twitter.com...), no quien lo verificó
        "verificador": None,
        "anio": df["Date"].map(_anio),
        "dataset": "upm",
        "medio_difusion": df["Media"],
    })


def preparar_afirmaciones() -> tuple[pd.DataFrame, dict]:
    crudo = pd.concat([
        _desde_factspan(),
        _desde_claimreview("datacommons_es.jsonl", "datacommons"),
        _desde_claimreview("google_factcheck_es.jsonl", "google_factcheck"),
        _desde_upm(),
    ], ignore_index=True)
    control = {"leidas": len(crudo), "por_dataset_leidas": crudo["dataset"].value_counts().to_dict()}

    crudo["texto"] = crudo["texto"].map(limpiar_afirmacion)
    crudo = crudo[crudo["etiqueta"].notna()]
    control["descartadas_calificacion_ambigua"] = control["leidas"] - len(crudo)
    crudo = crudo[crudo["texto"].str.split().str.len() >= MIN_PALABRAS_AFIRMACION]

    # Duplicados entre fuentes (FactSpan ya incluye parte de Data Commons):
    # misma afirmación tras normalizar. Si dos fuentes la califican distinto,
    # no es un ejemplo confiable y se descarta.
    crudo["clave"] = crudo["texto"].map(limpiar_texto)
    crudo = crudo[crudo["clave"].str.len() > 0]
    etiquetas_por_clave = crudo.groupby("clave")["etiqueta"].nunique()
    conflictivas = set(etiquetas_por_clave[etiquetas_por_clave > 1].index)
    control["descartadas_etiqueta_contradictoria"] = int(crudo["clave"].isin(conflictivas).sum())
    crudo = crudo[~crudo["clave"].isin(conflictivas)]
    antes = len(crudo)
    # Ante duplicados se conserva el registro con más información (verificador y año)
    crudo = crudo.assign(_info=crudo["verificador"].notna().astype(int) + crudo["anio"].notna().astype(int))
    crudo = crudo.sort_values("_info", ascending=False).drop_duplicates("clave").drop(columns=["_info", "clave"])
    control["descartadas_duplicadas"] = antes - len(crudo)

    crudo["etiqueta"] = crudo["etiqueta"].astype(int)
    crudo["palabras"] = crudo["texto"].str.split().str.len()
    crudo["particion_temporal"] = crudo["anio"].map(
        lambda a: "test" if pd.notna(a) and a >= ANIO_INICIO_PRUEBA else "train"
    )
    return crudo.reset_index(drop=True), control


# --- Resumen ------------------------------------------------------------------

def _resumen_articulos(df: pd.DataFrame) -> dict:
    return {
        "total": len(df),
        "por_etiqueta": df["etiqueta"].map({1: "desinformacion", 0: "confiable"}).value_counts().to_dict(),
        "por_particion_y_etiqueta": pd.crosstab(df["particion"], df["etiqueta"]).to_dict(),
        "temas": df["tema"].value_counts().to_dict(),
        "mediana_palabras_por_etiqueta": df.groupby("etiqueta")["palabras"].median().to_dict(),
    }


def _resumen_afirmaciones(df: pd.DataFrame, control: dict) -> dict:
    palabra_etiqueta = df["texto"].str.contains(r"\b(?:falso|falsa|verdadero|bulo|fake)\b", case=False, regex=True)
    return {
        "total": len(df),
        "control_limpieza": control,
        "por_etiqueta": df["etiqueta"].map({1: "desinformacion", 0: "confiable"}).value_counts().to_dict(),
        "por_dataset_y_etiqueta": pd.crosstab(df["dataset"], df["etiqueta"]).to_dict(),
        "por_particion_y_etiqueta": pd.crosstab(df["particion_temporal"], df["etiqueta"]).to_dict(),
        "por_anio": df["anio"].fillna(0).astype(int).value_counts().sort_index().to_dict(),
        "verificadores_top": df["verificador"].value_counts().head(25).to_dict(),
        "mediana_palabras_por_etiqueta": df.groupby("etiqueta")["palabras"].median().to_dict(),
        "mediana_palabras_por_dataset": df.groupby("dataset")["palabras"].median().to_dict(),
        # Control de fuga de etiqueta: si una clase usa mucho más estas
        # palabras, el modelo podría aprenderlas en vez del contenido
        "porcentaje_con_palabra_de_calificacion_por_etiqueta": (
            palabra_etiqueta.groupby(df["etiqueta"]).mean().round(3).to_dict()
        ),
    }


def main() -> None:
    articulos = preparar_articulos()
    afirmaciones, control = preparar_afirmaciones()

    articulos.to_csv(DATA_DIR / "corpus_articulos.csv", index=False)
    afirmaciones.to_csv(DATA_DIR / "corpus_afirmaciones.csv", index=False)

    resumen = {
        "articulos": _resumen_articulos(articulos),
        "afirmaciones": _resumen_afirmaciones(afirmaciones, control),
    }
    with open(DATA_DIR / "resumen_corpus.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2, default=str)
    print(json.dumps(resumen, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
