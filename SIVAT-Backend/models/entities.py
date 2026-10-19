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
    Feed temporal de los paneles Perú e Internacionales (el país decide el
    panel). Todo lo que se jala de GDELT, medios RSS, Bluesky, Reddit y
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


class EvidenciaVerificacion(Base):
    """
    Base de conocimiento del módulo RAG (E2 del Acta de Alcance): verificaciones
    ya publicadas por verificadores (RSS) o halladas en Google Fact Check.
    Es contenido público y se conserva: una verificación sigue sirviendo meses
    después, a diferencia del feed de noticias.
    """
    __tablename__ = "evidencia_verificacion"
    id = Column(Integer, primary_key=True, index=True)
    origen = Column(String(100), index=True)  # verificador, p. ej. 'Maldito Bulo'
    via = Column(String(30))  # 'rss' | 'google_factcheck'
    identificador_externo = Column(String(255), unique=True, index=True, nullable=False)
    titulo = Column(String(500), nullable=False)
    resumen = Column(Text, nullable=True)
    # Calificación que dio el verificador (no SIVAT): Falso, Engañoso, Verdadero...
    calificacion = Column(String(50), nullable=True)
    url = Column(String(1000), nullable=True)
    fecha_publicacion = Column(DateTime(timezone=True), nullable=True)
    fecha_captura = Column(DateTime(timezone=True), server_default=func.now())


class EvidenciaAfirmacion(Base):
    """
    Evidencia encontrada para una afirmación al evaluarla. Es una copia (no una
    FK) porque las noticias de medios salen del feed temporal, que se borra a
    las 24 h, y la evidencia debe seguir visible para la decisión editorial.
    """
    __tablename__ = "evidencia_afirmacion"
    id = Column(Integer, primary_key=True, index=True)
    afirmacion_id = Column(Integer, ForeignKey("afirmacion.id"), nullable=False, index=True)
    tipo = Column(String(20), nullable=False)  # 'verificacion' | 'medio'
    origen = Column(String(100))
    titulo = Column(String(500))
    url = Column(String(1000), nullable=True)
    calificacion = Column(String(50), nullable=True)
    similitud = Column(Float, nullable=False)
    fecha_publicacion = Column(DateTime(timezone=True), nullable=True)


class Tendencia(Base):
    """
    Un tema del feed en un ciclo del Módulo de Tendencias (agrupamiento no
    supervisado, ver services/tendencias_service.py). Cada ciclo guarda una
    foto; `grupo_id` sigue al mismo tema entre ciclos para medir su evolución.
    Solo agregados del tema (nada de autores, Ley 29733); se conserva 7 días.

    RESTRICCIÓN ÉTICA (RNF-08): `prioridad` es prioridad de VERIFICACIÓN
    (qué conviene revisar primero), nunca un juicio de veracidad del tema.
    """
    __tablename__ = "tendencia"
    id = Column(Integer, primary_key=True, index=True)
    panel = Column(String(20), index=True, nullable=False)  # 'peru' | 'internacional'
    grupo_id = Column(String(36), index=True, nullable=False)
    ejecucion = Column(DateTime(timezone=True), index=True, nullable=False)
    primera_vez = Column(DateTime(timezone=True), nullable=False)
    tema = Column(String(255), index=True)  # términos clave (c-TF-IDF)
    titular_representativo = Column(String(500))
    volumen_menciones = Column(Integer, default=0)
    fuentes_distintas = Column(Integer, default=0)
    menciones_redes = Column(Integer, default=0)
    menciones_medios_reconocidos = Column(Integer, default=0)
    recientes = Column(Integer, default=0)  # publicaciones en las últimas horas
    velocidad_crecimiento = Column(Float, default=0.0)  # ritmo reciente / ritmo previo
    prioridad = Column(String(10), nullable=False)  # Alta | Media | Baja
    motivos = Column(Text)  # JSON: por qué esa prioridad (explicable)
    verificacion = Column(Text, nullable=True)  # JSON: verificación relacionada, si existe
    noticia_ids = Column(Text)  # JSON: ids de noticia_feed del tema
    centroide = Column(Text)  # JSON: vector medio, para reconocer el tema en el próximo ciclo
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

    # Señal del clasificador de patrones de desinformación (ml/entrenar_modelos.py, Modelo A)
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
