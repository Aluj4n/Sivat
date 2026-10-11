from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base

class FuenteExterna(Base):
    __tablename__ = "fuente_externa"
    id = Column(Integer, primary_key=True, index=True)
    origen = Column(String(50), index=True) # e.g., 'X', 'YouTube', 'GDELT'
    identificador_externo = Column(String(255), unique=True, index=True)
    texto_procesado = Column(Text)
    metadatos = Column(Text) # JSON string or specific columns
    fecha_recoleccion = Column(DateTime(timezone=True), server_default=func.now())

    # Campos normalizados para presentación en el Dashboard (paneles Perú/Internacionales)
    titular = Column(String(500), nullable=True)
    imagen_url = Column(String(1000), nullable=True)
    url_original = Column(String(1000), nullable=True)
    pais = Column(String(100), nullable=True, index=True) # 'PE', 'INTL', o país de origen según GDELT
    fecha_publicacion = Column(DateTime(timezone=True), nullable=True)
    # RESTRICCIÓN ÉTICA: nivel de confianza basado en transparencia/trazabilidad, NO un veredicto de veracidad
    nivel_confianza_calculado = Column(String(50), nullable=True)

class NoticiaFeed(Base):
    """
    Feed temporal del panel Internacionales. Todo lo que se jala de GDELT y
    YouTube cae aquí y se borra a las 24 h (minimización de datos, Ley 29733).
    Solo cuando un periodista pulsa "Validar" la noticia se copia a
    FuenteExterna (permanente) y entra al flujo de verificación.
    """
    __tablename__ = "noticia_feed"
    id = Column(Integer, primary_key=True, index=True)
    origen = Column(String(50), index=True)
    identificador_externo = Column(String(255), unique=True, index=True, nullable=False)
    titular = Column(String(500), nullable=True)
    texto_procesado = Column(Text, nullable=True)
    imagen_url = Column(String(1000), nullable=True)
    url_original = Column(String(1000), nullable=True)
    pais = Column(String(100), nullable=True)
    fecha_publicacion = Column(DateTime(timezone=True), nullable=True)
    metadatos = Column(Text, nullable=True)
    fecha_captura = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    en_validacion = Column(Boolean, nullable=False, default=False)
    afirmacion_id = Column(Integer, ForeignKey("afirmacion.id"), nullable=True)


class Tendencia(Base):
    __tablename__ = "tendencia"
    id = Column(Integer, primary_key=True, index=True)
    tema = Column(String(255), index=True)
    volumen_menciones = Column(Integer, default=0)
    velocidad_crecimiento = Column(Float, default=0.0)
    fecha_registro = Column(DateTime(timezone=True), server_default=func.now())

class Afirmacion(Base):
    __tablename__ = "afirmacion"
    id = Column(Integer, primary_key=True, index=True)
    contenido = Column(Text, nullable=False)
    fuente_id = Column(Integer, ForeignKey("fuente_externa.id"))
    confianza_ia = Column(Float, nullable=True) # Computed later by RAG
    fecha_extraccion = Column(DateTime(timezone=True), server_default=func.now())
    
    fuente = relationship("FuenteExterna")

class EvaluacionIA(Base):
    """
    Resultado del motor de IA sobre una Afirmacion (Business Case, seccion 5.2:
    "Formalizacion del nivel de confianza explicable"). Se guarda desagregado
    a proposito -- nunca una cifra unica ni un veredicto verdadero/falso (RNF-08).

    Por ahora solo el clasificador de senal (TF-IDF + Random Forest, ver ml/)
    esta conectado, asi que los campos de evidencia (que dependen del modulo
    RAG, E2 del Acta de Alcance, aun no construido) quedan nullable hasta que
    ese modulo exista.
    """
    __tablename__ = "evaluacion_ia"
    id = Column(Integer, primary_key=True, index=True)
    afirmacion_id = Column(Integer, ForeignKey("afirmacion.id"), nullable=False)

    # Señal del clasificador de patrones de desinformación (ml/entrenar_clasificador.py)
    probabilidad_desinformacion = Column(Float, nullable=False)
    version_modelo = Column(String(100), nullable=False)  # RNF-07: trazabilidad del modelo usado

    # Desagregado de evidencia (Business Case 5.2) -- pendiente del módulo RAG (E2)
    nivel_evidencia_disponible = Column(String(20), nullable=True)  # Alto/Medio/Bajo
    fuentes_coincidentes = Column(Integer, nullable=True)
    fuentes_contradictorias = Column(Integer, nullable=True)
    fuente_oficial_encontrada = Column(Boolean, nullable=True)
    cobertura_evidencia = Column(String(20), nullable=True)

    # RESTRICCIÓN ÉTICA: jamás "verdadero/falso" -- solo una recomendación de proceso
    recomendacion_sistema = Column(String(100), nullable=False, default="Requiere validación periodística")
    fecha_evaluacion = Column(DateTime(timezone=True), server_default=func.now())

    afirmacion = relationship("Afirmacion")


class DecisionEditorial(Base):
    __tablename__ = "decision_editorial"
    id = Column(Integer, primary_key=True, index=True)
    afirmacion_id = Column(Integer, ForeignKey("afirmacion.id"))
    recomendacion_ia = Column(String(50)) # e.g., 'Alta Probabilidad de Falsedad'
    decision_periodista = Column(String(50)) # 'Aceptado', 'Rechazado', 'Observado'
    comentarios = Column(Text, nullable=True)
    fecha_decision = Column(DateTime(timezone=True), server_default=func.now())
    
    afirmacion = relationship("Afirmacion")
