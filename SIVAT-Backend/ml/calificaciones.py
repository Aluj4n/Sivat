"""
Unifica las calificaciones de los verificadores (texto libre en varios
idiomas: "Falso", "Engañoso", "Pants on Fire", "Verdad a medias"...) en las
dos clases del Modelo B. Las calificaciones intermedias se descartan a
propósito: una "verdad a medias" no es un ejemplo limpio de ninguna clase y
confundiría al modelo.

    1 = desinformación (falso, engañoso, sin contexto)
    0 = confiable (verdadero, mayormente verdadero)
    None = ambigua o desconocida (no se usa para entrenar)
"""
import re
from typing import Optional

DESINFORMACION = 1
CONFIABLE = 0

# El orden importa: lo ambiguo antes que "falso"/"verdadero" (p. ej. "half
# true", "partly false"), y las negaciones antes que "verdadero".
_REGLAS = [
    (r"verdad a medias|medio verdader|(?:verdader\w*|ciert\w*|true),?\s*(?:pero|but)\b|half[- ]true|parcial|partly|mixed|mixt|impreci|inexact|exagerad|"
     r"discutible|cuestionable|sin evidencia|no hay evidencia|no verificable|unproven|inconclus|en proceso|"
     r"qu[eé] sabemos|s[aá]tira|satire|opini|depende", None),
    (r"no es (?:verdad|cierto|real|verdadero)|pants on fire|mostly false|mayormente fals|\bfals[oa]s?\b|\bfalse\b|"
     r"\bfake\b|\bbulo\b|montaje|estafa|\btimo\b|inventad|fabricad|pinocho|pinocchio|incorrect|irreal", DESINFORMACION),
    (r"enga[ñn]|misleading|manipulad|contexto|context|descontext|distorsi|alterad|trucad|sacad[oa] de", DESINFORMACION),
    (r"mostly true|mayormente (?:verdader|ciert)|verdader|\btrue\b|\bcierto\b|\bcorrect[oa]?\b|\breal\b|aut[eé]ntic|"
     r"confirmad", CONFIABLE),
]
_REGLAS = [(re.compile(patron, re.IGNORECASE), clase) for patron, clase in _REGLAS]

# Etiquetas ya normalizadas de FactSpan (X-Fact + Data Commons)
FACTSPAN = {
    "False": DESINFORMACION,
    "Mostly False": DESINFORMACION,
    "True": CONFIABLE,
    "Mostly True": CONFIABLE,
    # "Partly True/Misleading" y "Partly False/Misleading": ambiguas
}


def normalizar_calificacion(calificacion) -> Optional[int]:
    texto = calificacion.strip() if isinstance(calificacion, str) else ""
    # Una calificación larga es una explicación con matices, no una etiqueta
    if not texto or len(texto) > 60:
        return None
    for patron, clase in _REGLAS:
        if patron.search(texto):
            return clase
    return None


# Algunos verificadores escriben la calificación dentro de la afirmación
# ("Falso: el video muestra..."). Si se deja, el modelo aprende a leer la
# etiqueta en vez del contenido, así que se quita del inicio.
_RE_PREFIJO = re.compile(
    r"^\s*(?:es\s+)?(?:falso|falsa|verdadero|verdadera|enga[ñn]oso|enga[ñn]osa|cierto|impreciso|bulo|fake|"
    r"false|true|misleading)\s*(?:que\b|[:.\-–—|]+)\s*",
    re.IGNORECASE,
)
_RE_COMILLAS = re.compile(r"^[\"“”'‘’«»\s]+|[\"“”'‘’«»\s]+$")


def limpiar_afirmacion(texto) -> str:
    texto = re.sub(r"\s+", " ", texto if isinstance(texto, str) else "").strip()
    texto = _RE_PREFIJO.sub("", texto)
    return _RE_COMILLAS.sub("", texto).strip()
