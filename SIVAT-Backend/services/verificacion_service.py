import logging
from typing import List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from models.entities import Afirmacion, EvaluacionIA, EvidenciaAfirmacion
from services.clasificador_service import predecir_probabilidad, version_modelo
from services.evidencia_service import buscar_y_guardar_evidencia, titular_de

logger = logging.getLogger(__name__)

RECOMENDACION_SISTEMA = "Requiere validación periodística"

# Flujo editorial: Validar -> "Ya validadas", Observar -> "En observación" (en
# seguimiento). Descartar no es un estado: borra la afirmación por completo.
# Cualquier otro valor guardado (p. ej. 'Rechazado' del flujo anterior) cuenta
# como pendiente.
DECISIONES = ("Validado", "Observado")
# Conclusión que registra el periodista al validar: el veredicto es humano,
# nunca de la IA (RNF-08)
CONCLUSIONES = ("Verdadera", "Falsa", "Engañosa", "Sin evidencia suficiente")


async def evaluar_y_guardar(
    db: AsyncSession,
    texto: str,
    fuente_id: Optional[int] = None,
    excluir_identificador: Optional[str] = None,
    texto_busqueda: Optional[str] = None,
) -> Tuple[Afirmacion, EvaluacionIA, List[EvidenciaAfirmacion]]:
    """
    Corre el clasificador sobre `texto`, busca evidencia (módulo RAG) y
    persiste la Afirmacion (enlazada a su FuenteExterna si viene del feed, para
    trazabilidad RNF-06), su EvaluacionIA y la evidencia encontrada.
    `excluir_identificador` evita que la propia noticia cuente como evidencia.
    `texto_busqueda` (el titular) se usa para el RAG: comparar afirmaciones
    funciona mejor con el titular, mientras el modelo necesita el texto completo.
    No hace commit: quien llama decide cerrar la transacción junto con sus
    propios cambios.
    """
    probabilidad = predecir_probabilidad(texto)

    afirmacion = Afirmacion(contenido=texto, fuente_id=fuente_id)
    db.add(afirmacion)
    await db.flush()

    evaluacion = EvaluacionIA(
        afirmacion_id=afirmacion.id,
        probabilidad_desinformacion=probabilidad,
        version_modelo=version_modelo(),
        recomendacion_sistema=RECOMENDACION_SISTEMA,
    )
    db.add(evaluacion)
    await db.flush()

    try:
        async with db.begin_nested():
            evidencias = await buscar_y_guardar_evidencia(
                db, evaluacion, texto_busqueda or titular_de(texto), excluir_identificador
            )
    except Exception:
        # La evaluación vale sin evidencia: queda como "no buscada" y se puede reintentar
        logger.warning("[evidencia] Falló la búsqueda de evidencia", exc_info=True)
        evidencias = []

    return afirmacion, evaluacion, evidencias
