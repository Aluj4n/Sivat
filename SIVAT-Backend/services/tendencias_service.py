"""
Módulo de Tendencias: alerta temprana y priorización para la redacción.

Cada ciclo agrupa por tema lo que hay en el feed (últimas 24 h, por panel)
con embeddings multilingües + HDBSCAN (ver ml/agrupamiento.py y el
experimento en ml/experimento_tendencias.py), describe cada tema (términos
clave, titular representativo, cuántas fuentes, redes contra medios, ritmo de
crecimiento, verificación relacionada) y le asigna una PRIORIDAD DE
VERIFICACIÓN con reglas explicables.

RESTRICCIÓN ÉTICA (RNF-08): la prioridad dice qué conviene revisar primero,
nunca si el tema es verdadero o falso. El flujo sigue igual: el periodista
elige una noticia del tema y la envía a Validación.
"""
import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from ml.agrupamiento import agrupar_hdbscan, representativo, terminos_clave, vectores_e5
from ml.limpieza_texto import limpiar_texto
from models.entities import EvidenciaVerificacion, NoticiaFeed, Tendencia
from services.evidencia_service import ORIGENES_SOCIALES, es_medio_reconocido
from services.normalizacion import PANEL_INTERNACIONAL, PANEL_PERU, panel_de

logger = logging.getLogger(__name__)

MIN_NOTICIAS_PANEL = 30
# Un tema de uno o dos sitios suele ser una plantilla, una transmisión en vivo
# o publicidad, no una tendencia
MIN_FUENTES_TEMA = 3
HORAS_RECIENTES = 3
# Mismo tema en el ciclo anterior si su centro está así de cerca (coseno, e5).
# Medido en ciclos reales: el mismo tema da >= 0.986 y temas distintos llegan
# a 0.93-0.97 (e5 comprime las similitudes), así que el umbral va alto
UMBRAL_MISMO_TEMA = 0.97
# Similitud TF-IDF con el titular del tema para mostrar una verificación relacionada
UMBRAL_VERIFICACION_TEMA = 0.20
DIAS_HISTORIAL = 7

# Páginas de portada que GDELT registra como si fueran artículos ("Inicio | Diario X")
_RE_GENERICO = re.compile(r"^\s*(inicio|home|portada|últimas noticias|noticias)\s*(\||-|$)|\|\s*(inicio|home)\s*$",
                          re.IGNORECASE)


def es_titular_util(titular: Optional[str]) -> bool:
    return bool(titular) and len(titular.split()) >= 4 and not _RE_GENERICO.search(titular)


def fuente_de(origen: Optional[str], metadatos: Optional[str]) -> str:
    # GDELT agrupa miles de medios: la fuente real es el dominio del artículo
    if origen == "GDELT" and metadatos:
        try:
            return json.loads(metadatos).get("dominio") or origen
        except ValueError:
            pass
    return origen or "desconocido"


def _momento(noticia: NoticiaFeed) -> datetime:
    # La fecha de publicación si es creíble; si no, cuándo se capturó
    publicada, capturada = noticia.fecha_publicacion, noticia.fecha_captura
    return publicada if publicada and publicada <= capturada else capturada


def prioridad_de(datos: dict) -> tuple[str, List[str]]:
    """
    Reglas explicables (sistema experto): cada motivo suma puntos y se muestra
    al periodista tal cual. Alta >= 4, Media >= 2, Baja el resto. Lo que más
    pesa es lo típico de un rumor: crece rápido y circula en redes sin medios.
    """
    puntos, motivos = 0, []
    if datos["recientes"] >= 5 and datos["velocidad"] >= 2:
        puntos += 2
        motivos.append(f"Creciendo rápido: {datos['recientes']} publicaciones en las últimas {HORAS_RECIENTES} h")
    if datos["nuevo"] and datos["recientes"] >= 3:
        puntos += 1
        motivos.append("Tema nuevo en este ciclo")
    proporcion_redes = datos["redes"] / max(datos["volumen"], 1)
    if proporcion_redes >= 0.5:
        puntos += 2
        motivos.append(f"Circula sobre todo en redes sociales ({proporcion_redes:.0%})")
    elif datos["redes"] >= 3:
        puntos += 1
        motivos.append(f"También circula en redes sociales ({datos['redes']} publicaciones)")
    if datos["medios_reconocidos"] == 0:
        puntos += 1
        motivos.append("Sin cobertura de medios reconocidos")
    # Informativos, sin puntos. Difusión: una noticia que cubren muchos medios
    # ya está siendo contrastada; no es el perfil de un rumor. Verificación:
    # casi ningún tema tiene una previa y sumar por eso subiría todo.
    if datos["fuentes"] >= 10:
        motivos.append(f"Amplia difusión: {datos['fuentes']} fuentes distintas")
    if datos["verificacion"]:
        v = datos["verificacion"]
        motivos.append(f"Hay una verificación relacionada de {v['origen']}"
                       + (f" ({v['calificacion']})" if v.get("calificacion") else ""))
    else:
        motivos.append("Sin verificación previa relacionada")
    nivel = "Alta" if puntos >= 4 else "Media" if puntos >= 2 else "Baja"
    return nivel, motivos


async def _verificaciones(db: AsyncSession) -> List[EvidenciaVerificacion]:
    resultado = await db.execute(
        select(EvidenciaVerificacion).order_by(EvidenciaVerificacion.fecha_publicacion.desc().nullslast()).limit(5000)
    )
    return list(resultado.scalars().all())


def _verificaciones_relacionadas(consultas: List[str], verificaciones: List[EvidenciaVerificacion]) -> List[Optional[dict]]:
    """Para cada tema, la verificación más parecida (TF-IDF, igual que el RAG) si supera el umbral."""
    if not consultas or not verificaciones:
        return [None] * len(consultas)
    documentos = [limpiar_texto(f"{v.titulo} {(v.resumen or '')[:300]}") for v in verificaciones]
    matriz = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True).fit_transform(
        [limpiar_texto(c) for c in consultas] + documentos)
    similitudes = cosine_similarity(matriz[:len(consultas)], matriz[len(consultas):])
    salida = []
    for fila in similitudes:
        mejor = int(np.argmax(fila))
        if fila[mejor] < UMBRAL_VERIFICACION_TEMA:
            salida.append(None)
            continue
        v = verificaciones[mejor]
        salida.append({"origen": v.origen, "titulo": v.titulo, "url": v.url, "calificacion": v.calificacion,
                       "similitud": round(float(fila[mejor]), 3)})
    return salida


async def _temas_previos(db: AsyncSession, panel: str) -> List[Tendencia]:
    ultima = await db.scalar(select(func.max(Tendencia.ejecucion)).where(Tendencia.panel == panel))
    if ultima is None:
        return []
    resultado = await db.execute(select(Tendencia).where(Tendencia.panel == panel, Tendencia.ejecucion == ultima))
    return list(resultado.scalars().all())


def _emparejar(centroides: np.ndarray, previos: List[Tendencia]) -> Dict[int, Tendencia]:
    """Cada tema nuevo hereda el grupo_id del tema previo más parecido (uno a uno)."""
    if not previos or not len(centroides):
        return {}
    anteriores = np.array([json.loads(p.centroide) for p in previos])
    similitudes = centroides @ anteriores.T
    pares = sorted(((similitudes[i, j], i, j) for i in range(len(centroides)) for j in range(len(previos))
                    if similitudes[i, j] >= UMBRAL_MISMO_TEMA), reverse=True)
    usados_i, usados_j, emparejados = set(), set(), {}
    for _, i, j in pares:
        if i not in usados_i and j not in usados_j:
            emparejados[i] = previos[j]
            usados_i.add(i)
            usados_j.add(j)
    return emparejados


async def _tendencias_panel(db: AsyncSession, panel: str, noticias: List[NoticiaFeed], ahora: datetime,
                            verificaciones: List[EvidenciaVerificacion]) -> List[Tendencia]:
    textos = [n.titular[:300] for n in noticias]
    # El cálculo es pesado (CPU): fuera del bucle de eventos para no frenar la API
    X = await asyncio.to_thread(vectores_e5, textos)
    etiquetas = await asyncio.to_thread(agrupar_hdbscan, X)
    terminos = terminos_clave(textos, etiquetas)

    temas = []
    for grupo in sorted(g for g in set(etiquetas) if g != -1):
        indices = np.where(etiquetas == grupo)[0]
        miembros = [noticias[i] for i in indices]
        fuentes = {fuente_de(n.origen, n.metadatos) for n in miembros}
        if len(fuentes) < MIN_FUENTES_TEMA:
            continue
        limite_reciente = ahora - timedelta(hours=HORAS_RECIENTES)
        recientes = sum(1 for n in miembros if _momento(n) >= limite_reciente)
        previas = len(miembros) - recientes
        horas_previas = settings.RETENCION_FEED_HORAS - HORAS_RECIENTES
        # Ritmo de las últimas horas contra el ritmo del resto del día
        velocidad = (recientes / HORAS_RECIENTES) / max(previas / horas_previas, 1 / horas_previas)
        centro = X[indices].mean(axis=0)
        temas.append({
            "indices": indices,
            "miembros": miembros,
            "centroide": centro / np.linalg.norm(centro),
            "terminos": terminos[grupo],
            "titular": textos[representativo(X, indices)],
            "volumen": len(miembros),
            "fuentes": len(fuentes),
            "redes": sum(1 for n in miembros if n.origen in ORIGENES_SOCIALES),
            "medios_reconocidos": sum(1 for f in fuentes if es_medio_reconocido(f)),
            "recientes": recientes,
            "velocidad": round(min(velocidad, 99.0), 2),
        })

    relacionadas = _verificaciones_relacionadas(
        [f"{t['titular']} {' '.join(t['terminos'])}" for t in temas], verificaciones)
    previos = await _temas_previos(db, panel)
    emparejados = _emparejar(np.array([t["centroide"] for t in temas]), previos)

    filas = []
    for i, (tema, verificacion) in enumerate(zip(temas, relacionadas)):
        previo = emparejados.get(i)
        # En el primer ciclo no hay con qué comparar: nada cuenta como "nuevo"
        tema.update({"verificacion": verificacion, "nuevo": bool(previos) and previo is None})
        prioridad, motivos = prioridad_de(tema)
        filas.append(Tendencia(
            panel=panel,
            grupo_id=previo.grupo_id if previo else str(uuid.uuid4()),
            ejecucion=ahora,
            primera_vez=previo.primera_vez if previo else ahora,
            tema=", ".join(tema["terminos"])[:255],
            titular_representativo=tema["titular"][:500],
            volumen_menciones=tema["volumen"],
            fuentes_distintas=tema["fuentes"],
            menciones_redes=tema["redes"],
            menciones_medios_reconocidos=tema["medios_reconocidos"],
            recientes=tema["recientes"],
            velocidad_crecimiento=tema["velocidad"],
            prioridad=prioridad,
            motivos=json.dumps(motivos, ensure_ascii=False),
            verificacion=json.dumps(verificacion, ensure_ascii=False) if verificacion else None,
            noticia_ids=json.dumps([n.id for n in tema["miembros"]]),
            centroide=json.dumps([round(float(x), 5) for x in tema["centroide"]]),
        ))
    return filas


async def calcular_tendencias(db: AsyncSession) -> int:
    ahora = datetime.now(timezone.utc)
    limite = ahora - timedelta(hours=settings.RETENCION_FEED_HORAS)
    resultado = await db.execute(select(NoticiaFeed).where(NoticiaFeed.fecha_captura >= limite))
    noticias = [n for n in resultado.scalars().all() if es_titular_util(n.titular)]
    verificaciones = await _verificaciones(db)

    total = 0
    for panel in (PANEL_PERU, PANEL_INTERNACIONAL):
        del_panel = [n for n in noticias if panel_de(n.pais) == panel]
        if len(del_panel) < MIN_NOTICIAS_PANEL:
            continue
        filas = await _tendencias_panel(db, panel, del_panel, ahora, verificaciones)
        db.add_all(filas)
        total += len(filas)

    await db.execute(delete(Tendencia).where(Tendencia.ejecucion < ahora - timedelta(days=DIAS_HISTORIAL)))
    await db.commit()
    return total
