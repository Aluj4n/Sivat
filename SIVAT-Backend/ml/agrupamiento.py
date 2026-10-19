"""
Agrupamiento de noticias por tema (Módulo de Tendencias, aprendizaje no
supervisado). Lo comparten el experimento (ml/experimento_tendencias.py) y el
servicio del backend (services/tendencias_service.py), así ambos agrupan igual.

  Representación: embeddings de multilingual-e5-small (titulares en cualquier
    idioma con el mismo significado quedan cerca: "Congreso aprueba vacancia" y
    "Parlamento destituye a la presidenta") o TF-IDF + SVD como comparación.
  Algoritmos: HDBSCAN (no hay que fijar cuántos temas existen y deja como ruido
    lo que no pertenece a ninguna tendencia), K-Means y DBSCAN como comparación.
"""
from collections import OrderedDict

import numpy as np
from sklearn.cluster import DBSCAN, HDBSCAN, KMeans
from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.preprocessing import normalize

from ml.limpieza_texto import STOPWORDS_ES, limpiar_texto

MODELO_E5 = "intfloat/multilingual-e5-small"
# Titulares y posts son cortos: 128 tokens alcanzan y es ~4 veces más rápido que 512
MAX_TOKENS = 128
MAX_CACHE = 60_000
SEMILLA = 42

_modelo = None
_cache: "OrderedDict[str, np.ndarray]" = OrderedDict()


def _modelo_e5():
    global _modelo
    if _modelo is None:
        from sentence_transformers import SentenceTransformer  # pesado: solo si se usa

        _modelo = SentenceTransformer(MODELO_E5, device="cpu")
        _modelo.max_seq_length = MAX_TOKENS
    return _modelo


def vectores_e5(textos: list) -> np.ndarray:
    """
    Vectores normalizados (384 dim). Caché en memoria por texto: cada ciclo
    del backend solo calcula los titulares nuevos del feed.
    """
    faltan = list(dict.fromkeys(t for t in textos if t not in _cache))
    if faltan:
        # e5 espera el prefijo "query: " en tareas de agrupamiento y clasificación
        nuevos = _modelo_e5().encode([f"query: {t}" for t in faltan], batch_size=64,
                                     normalize_embeddings=True, show_progress_bar=False)
        for texto, vector in zip(faltan, nuevos):
            _cache[texto] = vector
        while len(_cache) > MAX_CACHE:
            _cache.popitem(last=False)
    for texto in textos:
        _cache.move_to_end(texto)
    return np.stack([_cache[t] for t in textos])


def vectores_tfidf(textos: list, dimensiones: int = 100) -> np.ndarray:
    tfidf = TfidfVectorizer(min_df=2, ngram_range=(1, 2), sublinear_tf=True).fit_transform(
        [limpiar_texto(t) for t in textos])
    svd = TruncatedSVD(n_components=min(dimensiones, tfidf.shape[1] - 1), random_state=SEMILLA)
    return normalize(svd.fit_transform(tfidf))


def reducir(X: np.ndarray, dimensiones: int = 50) -> np.ndarray:
    # HDBSCAN y DBSCAN separan mejor (y más rápido) en pocas dimensiones
    if X.shape[1] <= dimensiones:
        return X
    return normalize(PCA(n_components=dimensiones, random_state=SEMILLA).fit_transform(X))


def agrupar_hdbscan(X: np.ndarray, min_tamano: int = 5) -> np.ndarray:
    # Etiqueta -1 = ruido: noticias que no forman parte de ninguna tendencia
    return HDBSCAN(min_cluster_size=min_tamano, min_samples=3).fit_predict(reducir(X))


def agrupar_kmeans(X: np.ndarray, k: int) -> np.ndarray:
    return KMeans(n_clusters=k, n_init=4, random_state=SEMILLA).fit_predict(X)


def agrupar_dbscan(X: np.ndarray, eps: float, min_muestras: int = 5) -> np.ndarray:
    # eps en distancia coseno. Con vectores normalizados equivale a euclidiana
    # sqrt(2 * eps), que usa un árbol de búsqueda en vez de comparar todos con todos
    return DBSCAN(eps=float(np.sqrt(2 * eps)), min_samples=min_muestras).fit_predict(normalize(X))


def terminos_clave(textos: list, etiquetas: np.ndarray, n: int = 5) -> dict:
    """
    c-TF-IDF (como BERTopic): las palabras más frecuentes en un grupo y raras
    en los demás, para nombrar cada tema sin que un humano lo rotule.
    """
    grupos = sorted(g for g in set(etiquetas) if g != -1)
    if not grupos:
        return {}
    documentos = [" ".join(limpiar_texto(t) for t, e in zip(textos, etiquetas) if e == g) for g in grupos]
    conteo = CountVectorizer(stop_words=list(STOPWORDS_ES), ngram_range=(1, 1), min_df=1)
    matriz = conteo.fit_transform(documentos).toarray().astype(float)
    tf = matriz / np.maximum(matriz.sum(axis=1, keepdims=True), 1)
    idf = np.log(1 + matriz.sum(axis=1).mean() / np.maximum(matriz.sum(axis=0), 1))
    puntajes = tf * idf
    vocabulario = np.array(conteo.get_feature_names_out())
    return {g: [w for w in vocabulario[np.argsort(-puntajes[i])[:n]]] for i, g in enumerate(grupos)}


def representativo(X: np.ndarray, indices: np.ndarray) -> int:
    # La noticia más cercana al centro del grupo: su titular describe el tema
    centro = X[indices].mean(axis=0)
    return int(indices[np.argmax(X[indices] @ centro)])
