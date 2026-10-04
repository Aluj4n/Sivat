"""
Implementa el Algoritmo 1 (EntrenarClasificadorSIVAT) del Informe IA/ML:
compara Regresion Logistica, Naive Bayes Multinomial, SVM lineal y Random
Forest sobre una representacion TF-IDF (1-2 gramas), selecciona el modelo con
mayor F1 en validacion via GridSearchCV (k=5), y lo serializa para que el
backend lo cargue en inferencia (services/clasificador_service.py).

La meta F1 >= 0.75 viene del criterio de aceptacion del Business Case (6.4)
y del Acta de Alcance.
"""
import json
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from ml.limpieza_texto import limpiar_texto
from ml.preparar_datos import cargar_corpus

MODELOS_DIR = Path(__file__).resolve().parent.parent / "models_ml"
F1_META = 0.75

MODELOS = {
    "regresion_logistica": (
        LogisticRegression(max_iter=1000, random_state=42),
        {"clf__C": [0.1, 1.0, 10.0]},
    ),
    "naive_bayes": (
        MultinomialNB(),
        {"clf__alpha": [0.1, 0.5, 1.0]},
    ),
    "svm_lineal": (
        LinearSVC(random_state=42, max_iter=5000, dual="auto"),
        {"clf__C": [0.1, 1.0, 10.0]},
    ),
    "random_forest": (
        RandomForestClassifier(random_state=42, n_jobs=-1),
        {"clf__n_estimators": [200, 400], "clf__max_depth": [None, 30]},
    ),
}


def entrenar() -> None:
    corpus = cargar_corpus()
    corpus["texto_limpio"] = (corpus["titular"] + " " + corpus["texto"]).apply(limpiar_texto)
    corpus = corpus[corpus["texto_limpio"].str.strip() != ""]

    X = corpus["texto_limpio"]
    y = corpus["etiqueta"]

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    resultados = []
    mejor_f1 = -1.0
    mejor_nombre = None
    mejor_pipeline = None

    for nombre, (modelo, grid) in MODELOS.items():
        pipeline = Pipeline(
            [
                ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
                ("clf", modelo),
            ]
        )
        busqueda = GridSearchCV(pipeline, grid, cv=5, scoring="f1", n_jobs=-1)
        busqueda.fit(X_train, y_train)

        mejor_est = busqueda.best_estimator_
        y_pred = mejor_est.predict(X_val)

        metrica = {
            "modelo": nombre,
            "mejores_parametros": busqueda.best_params_,
            "f1_cv": round(busqueda.best_score_, 4),
            "accuracy_val": round(accuracy_score(y_val, y_pred), 4),
            "precision_val": round(precision_score(y_val, y_pred), 4),
            "recall_val": round(recall_score(y_val, y_pred), 4),
            "f1_val": round(f1_score(y_val, y_pred), 4),
        }
        resultados.append(metrica)
        print(f"[{nombre}] F1_val={metrica['f1_val']} (meta >= {F1_META}) params={busqueda.best_params_}")

        if metrica["f1_val"] > mejor_f1:
            mejor_f1 = metrica["f1_val"]
            mejor_nombre = nombre
            mejor_pipeline = mejor_est

    MODELOS_DIR.mkdir(exist_ok=True)
    joblib.dump(mejor_pipeline, MODELOS_DIR / "clasificador_desinformacion.joblib")
    with open(MODELOS_DIR / "metricas_entrenamiento.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "modelo_seleccionado": mejor_nombre,
                "version_modelo": "v1_tfidf_1248noticias",
                "total_noticias": len(corpus),
                "resultados": resultados,
                "cumple_meta_f1": bool(mejor_f1 >= F1_META),
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\nMejor modelo: {mejor_nombre} (F1_val={mejor_f1}) -> {MODELOS_DIR / 'clasificador_desinformacion.joblib'}")


if __name__ == "__main__":
    entrenar()
