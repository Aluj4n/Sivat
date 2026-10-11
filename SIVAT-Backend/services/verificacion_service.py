from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from models.entities import Afirmacion, EvaluacionIA
from services.clasificador_service import VERSION_MODELO, predecir_probabilidad

RECOMENDACION_SISTEMA = "Requiere validación periodística"


async def evaluar_y_guardar(
    db: AsyncSession, texto: str, fuente_id: Optional[int] = None
) -> Tuple[Afirmacion, EvaluacionIA]:
    """
    Corre el clasificador sobre `texto` y persiste la Afirmacion (enlazada a su
    FuenteExterna si viene del feed, para trazabilidad RNF-06) y su EvaluacionIA.
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
        version_modelo=VERSION_MODELO,
        recomendacion_sistema=RECOMENDACION_SISTEMA,
    )
    db.add(evaluacion)
    await db.flush()

    return afirmacion, evaluacion
