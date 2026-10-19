"""
Carga el Modelo A (artículos completos, entrenado en ml/entrenar_modelos.py)
y lo expone para inferencia en el request.

Solo se aplica a textos de MIN_PALABRAS_MODELO o más: el Modelo B
(afirmaciones cortas) no se usa en el sistema porque en la prueba 2025-2026
reconoció como confiables solo ~19% de las afirmaciones verdaderas (ver
ml/resultados/metricas_afirmaciones.json); para textos cortos decide la
evidencia del RAG.

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
MODELO_PATH = MODELOS_DIR / "modelo_articulos.joblib"

UMBRAL_ALTO = 0.66
UMBRAL_MEDIO = 0.33


@lru_cache(maxsize=1)
def _cargar_modelo() -> dict:
    if not MODELO_PATH.exists():
        raise RuntimeError(
            f"No se encontró el modelo entrenado en {MODELO_PATH}. "
            "Ejecuta `python -m ml.preparar_corpus` y `python -m ml.entrenar_modelos --modelo articulos`."
        )
    return joblib.load(MODELO_PATH)


def version_modelo() -> str:
    # RNF-07: cada evaluación guarda la versión del modelo que la produjo
    return _cargar_modelo()["version"]


def predecir_probabilidad(texto: str) -> float:
    """
    Devuelve la probabilidad [0,1] de que el texto tenga patrones asociados a
    posible desinformación, según el clasificador entrenado.
    """
    pipeline = _cargar_modelo()["pipeline"]
    proba = pipeline.predict_proba([limpiar_texto(texto)])[0]
    return float(proba[1])  # clase 1 = desinformación (ver ml/preparar_corpus.py)


def clasificar_senal(probabilidad: float) -> str:
    if probabilidad >= UMBRAL_ALTO:
        return "Alta probabilidad de patrones de desinformación"
    if probabilidad >= UMBRAL_MEDIO:
        return "Probabilidad media de patrones de desinformación"
    return "Baja probabilidad de patrones de desinformación"
