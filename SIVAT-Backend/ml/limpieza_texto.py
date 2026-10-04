"""
Normalizacion de texto compartida por entrenamiento e inferencia (debe ser
identica en ambos lados, o el vectorizador TF-IDF ve tokens distintos a los
que vio en entrenamiento). Sigue el paso 2-4 del Algoritmo 1 del Informe IA/ML:
minusculas, quitar URLs/numeros/signos/tildes, quitar palabras vacias y tokens <= 2.
"""
import re
import unicodedata

import nltk
from nltk.corpus import stopwords

_RE_URL = re.compile(r"https?://\S+|www\.\S+")
_RE_NO_ALFA = re.compile(r"[^a-zA-Z\s]")
_RE_ESPACIOS = re.compile(r"\s+")


def _quitar_tildes(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


try:
    _stopwords_raw = stopwords.words("spanish")
except LookupError:
    nltk.download("stopwords", quiet=True)
    _stopwords_raw = stopwords.words("spanish")

# Mismo tratamiento de tildes que el texto, para que el filtro siga funcionando
# despues de _quitar_tildes (NLTK trae "más", "según", etc. con tilde).
STOPWORDS_ES = {_quitar_tildes(w) for w in _stopwords_raw}


def limpiar_texto(texto: str) -> str:
    texto = texto.lower()
    texto = _RE_URL.sub(" ", texto)
    texto = _quitar_tildes(texto)
    texto = _RE_NO_ALFA.sub(" ", texto)
    texto = _RE_ESPACIOS.sub(" ", texto).strip()

    tokens = [t for t in texto.split() if len(t) > 2 and t not in STOPWORDS_ES]
    return " ".join(tokens)
