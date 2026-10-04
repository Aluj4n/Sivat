"""
Normaliza y une los dos splits crudos del Spanish Fake News Corpus
(Posadas-Duran et al., 2019; mirror en huggingface.co/datasets/sayalaruano/FakeNewsCorpusSpanish)
citado en el Informe IA/ML de SIVAT (seccion 1.1 / Tabla 2) en un unico corpus D
con el esquema {titular, texto, etiqueta} que espera el Algoritmo 1 (EntrenarClasificadorSIVAT).

train.csv y test.csv tienen nombres de columna y codificacion de la etiqueta
distintos entre si; aqui se homogenizan.
"""
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _normalizar_train(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8")
    df = df.rename(columns={"Headline": "titular", "Text": "texto", "Category": "etiqueta_raw"})
    df["etiqueta"] = (df["etiqueta_raw"] == "Fake").astype(int)
    return df[["titular", "texto", "etiqueta"]]


def _normalizar_test(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8")
    df = df.rename(columns={"HEADLINE": "titular", "TEXT": "texto", "CATEGORY": "etiqueta_raw"})
    # En test.csv: 0 = Fake, 1 = True (confirmado por fuente: AFPFactual -> 0, medios establecidos -> 1)
    df["etiqueta"] = (df["etiqueta_raw"] == 0).astype(int)
    return df[["titular", "texto", "etiqueta"]]


def cargar_corpus() -> pd.DataFrame:
    train = _normalizar_train(DATA_DIR / "fnc_train.csv")
    test = _normalizar_test(DATA_DIR / "fnc_test.csv")
    corpus = pd.concat([train, test], ignore_index=True)

    corpus["titular"] = corpus["titular"].fillna("")
    corpus["texto"] = corpus["texto"].fillna("")
    corpus = corpus[corpus["texto"].str.strip() != ""]
    corpus = corpus.drop_duplicates(subset=["texto"]).reset_index(drop=True)

    return corpus


if __name__ == "__main__":
    corpus = cargar_corpus()
    print(f"Total noticias: {len(corpus)}")
    print(corpus["etiqueta"].value_counts().rename({1: "Fake", 0: "True"}))
