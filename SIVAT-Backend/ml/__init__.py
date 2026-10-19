# En Windows, PyTorch (embeddings del Módulo de Tendencias, ver
# ml/agrupamiento.py) falla con WinError 1114 si scikit-learn cargó antes su
# propia DLL de OpenMP: se carga primero. Sin PyTorch el resto de ml/ funciona
# igual; en procesos donde scikit-learn ya cargó, falla con OSError y se omite.
try:
    import torch  # noqa: F401
except (ImportError, OSError):
    pass
