"""
Carga el clasificador de señal de desinformación entrenado offline
(ml/entrenar_clasificador.py) y lo expone para inferencia en el request.

RESTRICCIÓN ÉTICA (RNF-08, Business Case 5.2): este servicio nunca devuelve
"verdadero/falso". `predecir_probabilidad` entrega una probabilidad cruda y
`clasificar_senal` la traduce a una etiqueta cualitativa de *patrones de
posible desinformación*, no un veredicto de veracidad.
"""
from functools import lru_cache
from pathlib import Path

import joblib

from ml.limpieza_texto import limpiar_texto

MODELOS_DIR = Path(__file__).resolve().parent.parent / "models_ml"
MODELO_PATH = MODELOS_DIR / "clasificador_desinformacion.joblib"

# Debe coincidir con ml/entrenar_clasificador.py (RNF-07: trazabilidad del modelo)
VERSION_MODELO = "v1_tfidf_1248noticias"

UMBRAL_ALTO = 0.66
UMBRAL_MEDIO = 0.33


@lru_cache(maxsize=1)
def _cargar_modelo():
    if not MODELO_PATH.exists():
        raise RuntimeError(
            f"No se encontró el modelo entrenado en {MODELO_PATH}. "
            "Ejecuta `python -m ml.entrenar_clasificador` primero."
        )
    return joblib.load(MODELO_PATH)


def predecir_probabilidad(texto: str) -> float:
    """
    Devuelve la probabilidad [0,1] de que el texto tenga patrones asociados a
    posible desinformación, según el clasificador entrenado.
    """
    modelo = _cargar_modelo()
    texto_limpio = limpiar_texto(texto)

    if hasattr(modelo, "predict_proba"):
        proba = modelo.predict_proba([texto_limpio])[0]
        return float(proba[1])  # clase 1 = "Fake" (ver ml/preparar_datos.py)

    # Fallback para modelos sin predict_proba (p.ej. si se reentrena con SVM lineal)
    decision = modelo.decision_function([texto_limpio])[0]
    import math

    return 1 / (1 + math.exp(-decision))


def clasificar_senal(probabilidad: float) -> str:
    if probabilidad >= UMBRAL_ALTO:
        return "Alta probabilidad de patrones de desinformación"
    if probabilidad >= UMBRAL_MEDIO:
        return "Probabilidad media de patrones de desinformación"
    return "Baja probabilidad de patrones de desinformación"
