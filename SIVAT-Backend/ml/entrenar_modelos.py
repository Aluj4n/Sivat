"""
Entrena y evalúa los dos modelos de SIVAT (Informe IA/ML, Algoritmo 1,
ampliado con lo que pide el sílabo: KNN, Gradient Boosting, red neuronal,
matriz de confusión, curvas y análisis por fuente).

  Modelo A, artículos (>= 200 palabras): FakeDeS completo con su partición
    oficial (train 2019 / test IberLEF 2021).
  Modelo B, afirmaciones y rumores cortos: verificaciones reales, con
    partición temporal (entrena hasta 2024, prueba 2025-2026).

    python -m ml.entrenar_modelos [--modelo articulos|afirmaciones|ambos]

Resultados (métricas y figuras para el paper) en ml/resultados/; los modelos
serializados en models_ml/ (no se suben a git).
"""
import argparse
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.decomposition import TruncatedSVD
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, average_precision_score, balanced_accuracy_score, confusion_matrix, f1_score,
    precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, GroupKFold, StratifiedKFold, cross_val_predict
from sklearn.naive_bayes import ComplementNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from ml import figuras
from ml.limpieza_texto import limpiar_texto

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data"
MODELOS_DIR = BASE / "models_ml"
RESULTADOS_DIR = Path(__file__).resolve().parent / "resultados"
SEMILLA = 42
CV = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEMILLA)


# --- Algoritmos ---------------------------------------------------------------

def _tfidf() -> TfidfVectorizer:
    return TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=100_000)


def algoritmos(pesos: bool) -> dict:
    """
    (pipeline, grilla) por algoritmo. `pesos` activa class_weight="balanced"
    donde el algoritmo lo admite (compensa el desbalance del Modelo B). KNN,
    Naive Bayes y la red neuronal no lo admiten; para ellos el desbalance se
    compensa con la variante de submuestreo.
    """
    cw = "balanced" if pesos else None
    svd = lambda: TruncatedSVD(n_components=300, random_state=SEMILLA)  # noqa: E731 - denso para GB y MLP
    return {
        "regresion_logistica": (
            Pipeline([("tfidf", _tfidf()), ("clf", LogisticRegression(max_iter=3000, class_weight=cw))]),
            {"clf__C": [0.3, 1.0, 3.0, 10.0]},
        ),
        "naive_bayes": (
            Pipeline([("tfidf", _tfidf()), ("clf", ComplementNB())]),
            {"clf__alpha": [0.1, 0.3, 1.0]},
        ),
        "svm_lineal": (
            # Calibrado para obtener probabilidades (el medidor las necesita)
            Pipeline([("tfidf", _tfidf()), ("clf", CalibratedClassifierCV(
                LinearSVC(class_weight=cw, dual="auto", max_iter=5000), cv=3))]),
            {"clf__estimator__C": [0.1, 0.5, 1.0]},
        ),
        "random_forest": (
            Pipeline([("tfidf", _tfidf()), ("clf", RandomForestClassifier(
                n_estimators=300, class_weight="balanced_subsample" if pesos else None,
                n_jobs=-1, random_state=SEMILLA))]),
            {"clf__max_depth": [None, 60]},
        ),
        "knn": (
            Pipeline([("tfidf", _tfidf()), ("clf", KNeighborsClassifier(metric="cosine", weights="distance"))]),
            {"clf__n_neighbors": [5, 15, 31]},
        ),
        "gradient_boosting": (
            Pipeline([("tfidf", _tfidf()), ("svd", svd()), ("clf", HistGradientBoostingClassifier(
                class_weight=cw, random_state=SEMILLA))]),
            {"clf__learning_rate": [0.05, 0.1], "clf__max_iter": [200]},
        ),
        "red_neuronal_mlp": (
            Pipeline([("tfidf", _tfidf()), ("svd", svd()), ("clf", MLPClassifier(
                hidden_layer_sizes=(128,), early_stopping=True, max_iter=200, random_state=SEMILLA))]),
            {"clf__alpha": [1e-4, 1e-3]},
        ),
    }


# --- Métricas -----------------------------------------------------------------

def metricas(y, proba, umbral: float = 0.5) -> dict:
    pred = (proba >= umbral).astype(int)
    return {
        "f1_macro": round(f1_score(y, pred, average="macro"), 4),
        "exactitud_balanceada": round(balanced_accuracy_score(y, pred), 4),
        "exactitud": round(accuracy_score(y, pred), 4),
        "precision_desinformacion": round(precision_score(y, pred, zero_division=0), 4),
        "recall_desinformacion": round(recall_score(y, pred, zero_division=0), 4),
        "recall_confiable": round(recall_score(y, pred, pos_label=0, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y, proba), 4),
        "pr_auc_desinformacion": round(average_precision_score(y, proba), 4),
        "matriz_confusion": confusion_matrix(y, pred, labels=[0, 1]).tolist(),
        "umbral": round(float(umbral), 3),
    }


def mejor_umbral(y, proba) -> float:
    # Umbral que maximiza F1 macro sobre predicciones fuera de pliegue del
    # entrenamiento (nunca sobre la prueba)
    candidatos = np.linspace(0.05, 0.95, 91)
    return float(max(candidatos, key=lambda u: f1_score(y, (proba >= u).astype(int), average="macro")))


def comparar(X_train, y_train, X_test, y_test, pesos: bool, solo: list | None = None) -> tuple[list, dict]:
    resultados, ajustados = [], {}
    for nombre, (pipeline, grilla) in algoritmos(pesos).items():
        if solo and nombre not in solo:
            continue
        inicio = time.time()
        busqueda = GridSearchCV(pipeline, grilla, cv=CV, scoring="f1_macro", n_jobs=-1)
        busqueda.fit(X_train, y_train)
        proba = busqueda.best_estimator_.predict_proba(X_test)[:, 1]
        fila = {
            "modelo": nombre,
            "mejores_parametros": busqueda.best_params_,
            "f1_macro_cv": round(busqueda.best_score_, 4),
            "prueba": metricas(y_test, proba),
            "segundos": round(time.time() - inicio, 1),
        }
        resultados.append(fila)
        ajustados[nombre] = (busqueda.best_estimator_, proba)
        print(f"  [{nombre}] F1 macro CV={fila['f1_macro_cv']} | prueba F1 macro={fila['prueba']['f1_macro']} "
              f"AUC={fila['prueba']['roc_auc']} ({fila['segundos']} s)")
    return resultados, ajustados


def _guardar(nombre: str, contenido: dict) -> None:
    RESULTADOS_DIR.mkdir(exist_ok=True)
    with open(RESULTADOS_DIR / f"{nombre}.json", "w", encoding="utf-8") as f:
        json.dump(contenido, f, ensure_ascii=False, indent=2, default=str)


# --- Modelo A: artículos ------------------------------------------------------

def entrenar_articulos() -> None:
    print("\n=== Modelo A: artículos (FakeDeS) ===")
    corpus = pd.read_csv(DATA_DIR / "corpus_articulos.csv")
    corpus["x"] = (corpus["titular"].fillna("") + " " + corpus["texto"].fillna("")).map(limpiar_texto)
    train, test = corpus[corpus["particion"] == "train"], corpus[corpus["particion"] == "test"]

    resultados, ajustados = comparar(train["x"], train["etiqueta"], test["x"], test["etiqueta"], pesos=False)
    mejor = max(resultados, key=lambda r: r["f1_macro_cv"])  # se elige por CV, no por la prueba
    pipeline, proba = ajustados[mejor["modelo"]]

    # Línea base: solo el largo del texto. Si rinde parecido, el corpus tiene
    # un atajo (en FakeDeS las falsas son más cortas) y hay que reportarlo.
    largo = lambda df: np.log1p(df["palabras"].to_numpy()).reshape(-1, 1)  # noqa: E731
    base_largo = LogisticRegression().fit(largo(train), train["etiqueta"])
    linea_base_largo = metricas(test["etiqueta"], base_largo.predict_proba(largo(test))[:, 1])

    contenido = {
        "corpus": "FakeDeS (Posadas-Durán 2019 + IberLEF 2021)",
        "n_train": len(train), "n_test": len(test),
        "modelo_seleccionado": mejor["modelo"],
        "criterio_seleccion": "mayor F1 macro en validación cruzada (5 pliegues) sobre train",
        "resultados": resultados,
        "linea_base_solo_largo": linea_base_largo,
    }
    _guardar("metricas_articulos", contenido)
    MODELOS_DIR.mkdir(exist_ok=True)
    joblib.dump({"pipeline": pipeline, "umbral": 0.5, "version": "articulos_v2_fakedes1538",
                 "modelo": mejor["modelo"]}, MODELOS_DIR / "modelo_articulos.joblib")

    figuras.comparacion_modelos(resultados, "articulos", "Modelo A · artículos: F1 macro en la prueba IberLEF 2021",
                                RESULTADOS_DIR, referencia=linea_base_largo["f1_macro"], etiqueta_referencia="Solo largo del texto")
    figuras.matriz_confusion(mejor["prueba"]["matriz_confusion"], "articulos",
                             f"Modelo A · {figuras.NOMBRES[mejor['modelo']]} · prueba IberLEF 2021", RESULTADOS_DIR)
    top = sorted(resultados, key=lambda r: r["f1_macro_cv"], reverse=True)[:3]
    figuras.curvas(test["etiqueta"].to_numpy(), {r["modelo"]: ajustados[r["modelo"]][1] for r in top},
                   "articulos", "Modelo A · artículos", RESULTADOS_DIR)
    print(f"  Seleccionado: {mejor['modelo']} | línea base solo largo F1 macro={linea_base_largo['f1_macro']}")


# --- Modelo B: afirmaciones ---------------------------------------------------

def _titulares_entrenamiento(anio_limite: int) -> pd.DataFrame:
    ruta = DATA_DIR / "raw" / "titulares_medios_es.jsonl"
    if not ruta.exists():
        return pd.DataFrame(columns=["texto", "etiqueta"])
    t = pd.read_json(ruta, lines=True)
    t["anio"] = t["fecha"].astype(str).str[:4].astype(int)
    t = t[t["anio"] < anio_limite]  # solo del período de entrenamiento
    return pd.DataFrame({"texto": t["titular"], "etiqueta": 0})


def entrenar_afirmaciones() -> None:
    print("\n=== Modelo B: afirmaciones ===")
    corpus = pd.read_csv(DATA_DIR / "corpus_afirmaciones.csv")
    corpus["x"] = corpus["texto"].map(limpiar_texto)
    corpus = corpus[corpus["x"].str.len() > 0]
    train = corpus[corpus["particion_temporal"] == "train"].reset_index(drop=True)
    test = corpus[corpus["particion_temporal"] == "test"].reset_index(drop=True)
    print(f"  train={len(train)} (confiables {int((train.etiqueta == 0).sum())}) | "
          f"test={len(test)} (confiables {int((test.etiqueta == 0).sum())})")

    # 1) Todos los algoritmos con pesos de clase
    print(" Variante 1: pesos de clase")
    resultados, ajustados = comparar(train["x"], train["etiqueta"], test["x"], test["etiqueta"], pesos=True)
    top3 = [r["modelo"] for r in sorted(resultados, key=lambda r: r["f1_macro_cv"], reverse=True)[:3]]

    variantes = {"pesos_de_clase": resultados}

    # 2) Submuestreo de la clase mayoritaria a 3 falsas por cada confiable
    print(" Variante 2: submuestreo 1:3")
    confiables = train[train.etiqueta == 0]
    falsas = train[train.etiqueta == 1].sample(n=min(3 * len(confiables), (train.etiqueta == 1).sum()),
                                               random_state=SEMILLA)
    sub = pd.concat([confiables, falsas])
    variantes["submuestreo_1_a_3"], _ = comparar(sub["x"], sub["etiqueta"], test["x"], test["etiqueta"],
                                                 pesos=False, solo=top3)

    # 3) Experimento: titulares de medios reconocidos como "confiables" (solo
    #    en entrenamiento; la prueba sigue siendo solo de verificadores)
    titulares = _titulares_entrenamiento(int(test["anio"].min()))
    if len(titulares):
        print(f" Variante 3: + {len(titulares)} titulares de medios como confiables")
        titulares["x"] = titulares["texto"].map(limpiar_texto)
        con_tit = pd.concat([train[["x", "etiqueta"]], titulares[["x", "etiqueta"]]])
        variantes["mas_titulares_de_medios"], _ = comparar(con_tit["x"], con_tit["etiqueta"], test["x"],
                                                           test["etiqueta"], pesos=True, solo=top3)

    # 4) Sin los rumores de la UPM (solo falsos y más largos: posible atajo)
    print(" Variante 4: sin rumores UPM")
    sin_upm = train[train["dataset"] != "upm"]
    variantes["sin_upm"], _ = comparar(sin_upm["x"], sin_upm["etiqueta"], test["x"], test["etiqueta"],
                                       pesos=True, solo=top3[:1])

    # Modelo final: mejor algoritmo de la variante 1 (por CV) con umbral
    # ajustado sobre predicciones fuera de pliegue del entrenamiento
    mejor = max(resultados, key=lambda r: r["f1_macro_cv"])
    pipeline, proba_test = ajustados[mejor["modelo"]]
    proba_oof = cross_val_predict(pipeline, train["x"], train["etiqueta"], cv=CV, method="predict_proba",
                                  n_jobs=-1)[:, 1]
    umbral = mejor_umbral(train["etiqueta"], proba_oof)
    final = metricas(test["etiqueta"], proba_test, umbral)

    # Prueba por verificador: pliegues agrupados por verificador (uno nunca
    # aparece a la vez en entrenamiento y validación). Si cae mucho frente a la
    # validación cruzada normal, el modelo aprende el estilo de cada verificador.
    con_ver = train[train["verificador"].notna()].reset_index(drop=True)
    puntajes = []
    for idx_tr, idx_va in GroupKFold(n_splits=5).split(con_ver["x"], con_ver["etiqueta"], con_ver["verificador"]):
        tr, va = con_ver.iloc[idx_tr], con_ver.iloc[idx_va]
        if va["etiqueta"].nunique() < 2:
            continue
        p = pipeline.fit(tr["x"], tr["etiqueta"]).predict_proba(va["x"])[:, 1]
        puntajes.append(f1_score(va["etiqueta"], (p >= umbral).astype(int), average="macro"))
    pipeline.fit(train["x"], train["etiqueta"])  # se reentrena con todo tras la prueba por grupos

    contenido = {
        "corpus": "Verificaciones en español: FactSpan, Data Commons, Google Fact Check, UPM",
        "n_train": len(train), "n_test": len(test),
        "particion": "temporal: entrenamiento hasta 2024, prueba 2025-2026",
        "modelo_seleccionado": mejor["modelo"],
        "variantes": variantes,
        "final_con_umbral_ajustado": final,
        "f1_macro_por_verificador_no_visto": {
            "media": round(float(np.mean(puntajes)), 4) if puntajes else None,
            "desviacion": round(float(np.std(puntajes)), 4) if puntajes else None,
            "pliegues": len(puntajes),
        },
    }
    _guardar("metricas_afirmaciones", contenido)
    joblib.dump({"pipeline": pipeline, "umbral": umbral, "version": f"afirmaciones_v1_{len(corpus)}",
                 "modelo": mejor["modelo"]}, MODELOS_DIR / "modelo_afirmaciones.joblib")

    figuras.comparacion_modelos(resultados, "afirmaciones",
                                "Modelo B · afirmaciones: F1 macro en la prueba 2025-2026", RESULTADOS_DIR)
    figuras.matriz_confusion(final["matriz_confusion"], "afirmaciones",
                             f"Modelo B · {figuras.NOMBRES[mejor['modelo']]} · prueba 2025-2026 (umbral {umbral:.2f})", RESULTADOS_DIR)
    figuras.curvas(test["etiqueta"].to_numpy(), {m: ajustados[m][1] for m in top3},
                   "afirmaciones", "Modelo B · afirmaciones", RESULTADOS_DIR)
    print(f"  Seleccionado: {mejor['modelo']} | umbral={umbral:.2f} | prueba F1 macro={final['f1_macro']} | "
          f"por verificador no visto={contenido['f1_macro_por_verificador_no_visto']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--modelo", choices=["articulos", "afirmaciones", "ambos"], default="ambos")
    args = parser.parse_args()
    if args.modelo in ("articulos", "ambos"):
        entrenar_articulos()
    if args.modelo in ("afirmaciones", "ambos"):
        entrenar_afirmaciones()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
