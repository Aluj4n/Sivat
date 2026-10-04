from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey
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
    pais = Column(String(10), nullable=True, index=True) # 'PE', 'INTL', o código de país de GDELT
    fecha_publicacion = Column(DateTime(timezone=True), nullable=True)
    # RESTRICCIÓN ÉTICA: nivel de confianza basado en transparencia/trazabilidad, NO un veredicto de veracidad
    nivel_confianza_calculado = Column(String(50), nullable=True)

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

class DecisionEditorial(Base):
    __tablename__ = "decision_editorial"
    id = Column(Integer, primary_key=True, index=True)
    afirmacion_id = Column(Integer, ForeignKey("afirmacion.id"))
    recomendacion_ia = Column(String(50)) # e.g., 'Alta Probabilidad de Falsedad'
    decision_periodista = Column(String(50)) # 'Aceptado', 'Rechazado', 'Observado'
    comentarios = Column(Text, nullable=True)
    fecha_decision = Column(DateTime(timezone=True), server_default=func.now())
    
    afirmacion = relationship("Afirmacion")
