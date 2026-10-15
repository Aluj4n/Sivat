"""
Descarga las fuentes de datos de los dos modelos de SIVAT a data/raw/.
Todas son públicas y de uso académico; las licencias y referencias están
en FUENTES. Cada descarga se guarda una vez: volver a ejecutar no repite
nada salvo con --refrescar.

    python -m ml.fuentes_datos [--refrescar]
"""
import argparse
from html import unescape as html_unescape
import json
import re
import sys
import time
from pathlib import Path

import httpx

from core.config import settings

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
USER_AGENT = "SIVAT/1.0 (proyecto academico UPN - verificacion periodistica)"

FUENTES = {
    "fakedes": {
        "descripcion": "Spanish Fake News Corpus / FakeDeS (Posadas-Durán et al., 2019; Gómez-Adorno et al., 2021)",
        "licencia": "CC BY 4.0",
        "url": "https://github.com/jpposadas/FakeNewsCorpusSpanish",
    },
    "factspan": {
        "descripcion": "FactSpan: X-Fact + Data Commons ClaimReview posterior a 2020 (Saju, 2025)",
        "licencia": "CC BY 4.0",
        "url": "https://zenodo.org/records/15084388",
    },
    "datacommons": {
        "descripcion": "Data Commons ClaimReview feed (Google Fact Check Tools)",
        "licencia": "CC BY 4.0 (compilación); cada marcado según su sdLicense",
        "url": "https://datacommons.org/factcheck/download",
    },
    "google_factcheck": {
        "descripcion": "Google Fact Check Tools API, búsquedas en español",
        "licencia": "Términos de Google; contenido de cada verificador",
        "url": "https://developers.google.com/fact-check/tools/api",
    },
    "upm": {
        "descripcion": "Spanish Fake News Dataset (Tretiakov, D'Antonio Maceiras y Martín, UPM, 2025)",
        "licencia": "CC BY 4.0, uso académico no comercial",
        "url": "https://zenodo.org/records/15592391",
    },
}

FAKEDES_BASE = "https://raw.githubusercontent.com/jpposadas/FakeNewsCorpusSpanish/master/"
FACTSPAN_URL = "https://zenodo.org/records/15084388/files/FactSpan.csv?download=1"
UPM_URL = "https://zenodo.org/api/records/15592391/files/esp_fake_news.csv/content"
# Versión vigente del feed (se regenera a diario en el mismo bucket público)
DATACOMMONS_FEED = "https://storage.googleapis.com/datacommons-feeds/claimreview/latest/data.json"
FACTCHECK_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

# Temas variados para que la muestra de Google no quede sesgada a un tema
CONSULTAS_GOOGLE = [
    # Temas generales de desinformación
    "vacuna", "covid", "salud", "cáncer", "medicamento", "elecciones", "fraude electoral", "gobierno", "presidente",
    "congreso", "ministro", "alcalde", "economía", "inflación", "dólar", "impuestos", "pensiones", "empleo",
    "migrantes", "frontera", "deportación", "guerra", "Ucrania", "Israel", "Gaza", "Venezuela", "Cuba", "México",
    "Argentina", "Colombia", "Chile", "Perú", "Ecuador", "Bolivia", "España", "Estados Unidos", "policía",
    "delincuencia", "violencia", "terremoto", "huracán", "clima", "calentamiento", "incendio", "agua", "energía",
    "inteligencia artificial", "WhatsApp", "Facebook", "TikTok", "video", "foto", "imagen", "audio", "mensaje",
    "estafa", "banco", "educación", "escuela", "universidad", "ciencia", "NASA", "religión", "papa", "iglesia",
    "fútbol", "deporte", "famoso", "cantante", "actor", "alimentos", "comida", "animales", "transporte", "avión",
    "mujeres", "feminismo", "aborto", "LGBT", "racismo", "China", "Rusia", "Trump", "OTAN",
    # Países, regiones y ciudades
    "Uruguay", "Paraguay", "Guatemala", "Honduras", "El Salvador", "Nicaragua", "Costa Rica", "Panamá",
    "República Dominicana", "Puerto Rico", "Brasil", "Canadá", "Francia", "Alemania", "Italia", "Reino Unido",
    "Unión Europea", "Irán", "India", "Japón", "Corea", "África", "Marruecos", "Cataluña", "Andalucía", "Madrid",
    "Barcelona", "Buenos Aires", "Bogotá", "Santiago", "Lima", "Quito", "La Paz", "Caracas", "Ciudad de México",
    "Miami", "Texas", "California", "Nueva York", "Florida", "Medellín", "Monterrey", "Guayaquil", "Valencia",
    # Instituciones y actores
    "ONU", "OMS", "FMI", "Banco Mundial", "Corte Suprema", "Fiscalía", "Ejército", "militares", "senado",
    "diputados", "partido", "oposición", "candidato", "campaña", "encuesta", "votos", "referéndum", "constitución",
    "ley", "decreto", "reforma", "juez", "tribunal", "cárcel", "narcotráfico", "cártel", "corrupción",
    "Biden", "Milei", "Petro", "Boric", "Sheinbaum", "López Obrador", "Maduro", "Bukele", "Noboa", "Arce",
    "Sánchez", "Feijóo", "Vox", "Lula", "Putin", "Zelenski", "Netanyahu", "Elon Musk", "Bill Gates", "Soros",
    # Cifras y estadísticas (traen tanto verdaderas como falsas sobre datos)
    "porcentaje", "millones", "aumentó", "disminuyó", "creció", "récord", "cifra", "tasa", "estadística",
    "salario", "pobreza", "desempleo", "PIB", "exportaciones", "importaciones", "presupuesto", "deuda", "gasto",
    "inversión", "precio", "gasolina", "combustible", "luz", "tarifa", "vivienda", "alquiler", "homicidios",
    "femicidios", "accidentes", "muertes", "casos", "población", "nacimientos", "turismo", "producción",
    # Salud y ciencia
    "virus", "pandemia", "gripe", "dengue", "sarampión", "viruela", "hospital", "médicos", "dieta", "diabetes",
    "corazón", "embarazo", "niños", "ancianos", "suplemento", "remedio", "plantas", "5G", "radiación", "espacio",
    "planeta", "sol", "luna", "eclipse", "cambio climático", "contaminación", "plástico", "océano", "glaciar",
    # Tecnología, redes y formatos
    "Twitter", "Instagram", "YouTube", "Telegram", "Google", "celular", "aplicación", "hackeo", "datos personales",
    "deepfake", "captura de pantalla", "meme", "noticia", "periodista", "medio", "entrevista", "discurso",
    "declaración", "tuit", "publicación", "cadena", "viral",
    # Sociedad y otros
    "protesta", "manifestación", "huelga", "sindicato", "trabajadores", "jubilados", "estudiantes", "indígenas",
    "refugiados", "asilo", "visa", "pasaporte", "seguridad", "robo", "secuestro", "armas", "drogas", "alcohol",
    "lotería", "bono", "subsidio", "ayuda", "donación", "cultura", "música", "cine", "televisión", "Mundial",
    "Juegos Olímpicos", "Real Madrid", "Messi", "boda", "muerte de", "fallecido", "accidente", "explosión",
    "inundación", "sequía", "lluvias", "tormenta", "volcán", "tsunami", "ovni", "conspiración",
]
PAGINAS_POR_CONSULTA = 8

# El feed de Data Commons no trae el idioma: se detecta por palabras
# funcionales del español frente al portugués (el idioma más parecido)
_ES = {"el", "los", "las", "del", "que", "una", "para", "con", "por", "está", "son", "fue", "como", "pero", "más",
       "sobre", "muestra", "dijo", "según", "años", "también", "hay", "sus", "sin", "esta", "este"}
_PT = {"não", "uma", "dos", "das", "com", "em", "é", "foi", "são", "pelo", "pela", "mostra", "também", "mais", "ao",
       "na", "no", "seu", "sua"}
_DOMINIOS_NO_ES = re.compile(r"\.(br|pt|it|id|in|de|fr)$|boatos\.org|uol\.com|comprova|tempo\.co|pagellapolitica|"
                             r"factly|youturn|factcrescendo")


def es_espanol(texto: str) -> bool:
    palabras = re.findall(r"\w+", texto.lower())
    if len(palabras) < 4:
        return False
    es = sum(p in _ES for p in palabras)
    pt = sum(p in _PT and p not in _ES for p in palabras)
    return es >= 2 and es > 2 * pt


def _dominio(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url or "").split("/")[0].lower()


def _descargar(client: httpx.Client, url: str, destino: Path, refrescar: bool) -> Path:
    if destino.exists() and not refrescar:
        print(f"  ya existe {destino.name}")
        return destino
    with client.stream("GET", url) as respuesta:
        respuesta.raise_for_status()
        with open(destino, "wb") as f:
            for bloque in respuesta.iter_bytes():
                f.write(bloque)
    print(f"  descargado {destino.name} ({destino.stat().st_size / 1e6:.1f} MB)")
    return destino


def descargar_fakedes(client: httpx.Client, refrescar: bool) -> None:
    for nombre in ("train.xlsx", "development.xlsx", "test.xlsx"):
        _descargar(client, FAKEDES_BASE + nombre, RAW_DIR / f"fakedes_{nombre}", refrescar)


def descargar_factspan(client: httpx.Client, refrescar: bool) -> None:
    _descargar(client, FACTSPAN_URL, RAW_DIR / "factspan.csv", refrescar)


def descargar_upm(client: httpx.Client, refrescar: bool) -> None:
    _descargar(client, UPM_URL, RAW_DIR / "upm_esp_fake_news.csv", refrescar)


def descargar_datacommons(client: httpx.Client, refrescar: bool) -> None:
    """
    El feed completo pesa ~200 MB y trae todos los idiomas: se descarga, se
    filtra lo que está en español y se conserva solo eso.
    """
    destino = RAW_DIR / "datacommons_es.jsonl"
    if destino.exists() and not refrescar:
        print(f"  ya existe {destino.name}")
        return

    temporal = _descargar(client, DATACOMMONS_FEED, RAW_DIR / "datacommons_feed.json", refrescar=True)

    with open(temporal, encoding="utf-8") as f:
        elementos = json.load(f)["dataFeedElement"]
    total = 0
    with open(destino, "w", encoding="utf-8") as salida:
        for elemento in elementos:
            for item in elemento.get("item") or []:
                if not isinstance(item, dict):
                    continue
                afirmacion = item.get("claimReviewed") or ""
                dominio = _dominio(item.get("url", ""))
                if not es_espanol(afirmacion) or _DOMINIOS_NO_ES.search(dominio):
                    continue
                calificacion = (item.get("reviewRating") or {}).get("alternateName")
                salida.write(json.dumps({
                    "afirmacion": afirmacion,
                    "calificacion": calificacion,
                    "verificador": dominio,
                    "fecha": item.get("datePublished"),
                    "url": item.get("url"),
                }, ensure_ascii=False) + "\n")
                total += 1
    temporal.unlink()
    print(f"  {total} verificaciones en español -> {destino.name}")


def descargar_google_factcheck(client: httpx.Client, refrescar: bool) -> None:
    """
    Incremental: recuerda qué búsquedas ya se hicieron (y sus resultados) y
    solo ejecuta las nuevas, así ampliar CONSULTAS_GOOGLE no repite trabajo.
    """
    destino = RAW_DIR / "google_factcheck_es.jsonl"
    registro = RAW_DIR / "google_factcheck_consultas.json"
    if refrescar:
        destino.unlink(missing_ok=True)
        registro.unlink(missing_ok=True)

    vistas = set()
    if destino.exists():
        with open(destino, encoding="utf-8") as f:
            vistas = {json.loads(linea).get("url") for linea in f if linea.strip()}
    hechas = set(json.loads(registro.read_text(encoding="utf-8"))) if registro.exists() else set()
    if destino.exists() and not hechas:
        # Descarga anterior a este registro: sus consultas eran el bloque inicial
        hechas = set(CONSULTAS_GOOGLE[:CONSULTAS_GOOGLE.index("OTAN") + 1])
    pendientes = [c for c in CONSULTAS_GOOGLE if c not in hechas]
    print(f"  {len(vistas)} ya descargadas, {len(pendientes)} consultas nuevas")

    clave = settings.GOOGLE_FACTCHECK_API_KEY or settings.YOUTUBE_API_KEY
    with open(destino, "a", encoding="utf-8") as salida:
        for consulta in pendientes:
            token = None
            for _ in range(PAGINAS_POR_CONSULTA):
                params = {"query": consulta, "languageCode": "es", "pageSize": 100, "key": clave}
                if token:
                    params["pageToken"] = token
                datos = _pedir_con_reintentos(client, params)
                if datos is None:
                    break
                for claim in datos.get("claims", []):
                    revision = (claim.get("claimReview") or [{}])[0]
                    url = revision.get("url") or claim.get("text")
                    if url in vistas:
                        continue
                    vistas.add(url)
                    salida.write(json.dumps({
                        "afirmacion": claim.get("text"),
                        "calificacion": revision.get("textualRating"),
                        "verificador": _dominio(revision.get("url", "")) or (revision.get("publisher") or {}).get("site"),
                        "fecha": revision.get("reviewDate") or claim.get("claimDate"),
                        "url": revision.get("url"),
                    }, ensure_ascii=False) + "\n")
                token = datos.get("nextPageToken")
                if not token:
                    break
            hechas.add(consulta)
            registro.write_text(json.dumps(sorted(hechas), ensure_ascii=False), encoding="utf-8")
            print(f"  {consulta}: acumuladas {len(vistas)}")
    print(f"  {len(vistas)} verificaciones -> {destino.name}")


def _pedir_con_reintentos(client: httpx.Client, params: dict, intentos: int = 4):
    # La API responde 503 de forma esporádica: se reintenta con espera creciente
    for intento in range(intentos):
        respuesta = client.get(FACTCHECK_URL, params=params)
        if respuesta.status_code == 200:
            return respuesta.json()
        if respuesta.status_code in (429, 500, 503):
            time.sleep(2 * (intento + 1))
            continue
        print(f"    error {respuesta.status_code}: {respuesta.text[:120]}")
        return None
    return None


GDELT_GKG_URL = "http://data.gdeltproject.org/gdeltv2/{marca}.translation.gkg.csv.zip"
# Dos archivos de 15 min por mes (día 8 y 22 a mediodía) desde 2019: titulares
# de todo el período de las afirmaciones, para el experimento de titulares
ANIO_INICIO_TITULARES = 2019


def descargar_titulares_medios(client: httpx.Client, refrescar: bool) -> None:
    """
    Titulares en español de medios reconocidos, desde los archivos históricos
    de GDELT. Solo para el experimento "titulares como confiables" del
    Modelo B (etiqueta aproximada: que un medio reconocido lo publique no
    prueba que sea cierto).
    """
    from datetime import date

    from services.evidencia_service import es_medio_reconocido
    from services.gdelt_service import _parsear_gkg

    destino = RAW_DIR / "titulares_medios_es.jsonl"
    if destino.exists() and not refrescar:
        print(f"  ya existe {destino.name}")
        return

    hoy = date.today()
    marcas = [
        f"{anio}{mes:02d}{dia:02d}120000"
        for anio in range(ANIO_INICIO_TITULARES, hoy.year + 1)
        for mes in range(1, 13)
        for dia in (8, 22)
        if date(anio, mes, dia) < hoy
    ]
    vistas, total = set(), 0
    with open(destino, "w", encoding="utf-8") as salida:
        for marca in marcas:
            try:
                respuesta = client.get(GDELT_GKG_URL.format(marca=marca))
                respuesta.raise_for_status()
                articulos = _parsear_gkg(respuesta.content, "spa")
            except Exception as e:
                print(f"  {marca}: no disponible ({e!r})")
                continue
            nuevos = 0
            for a in articulos:
                titulo = html_unescape(a["titulo"]).strip()
                if not es_medio_reconocido(a["dominio"]) or titulo in vistas:
                    continue
                vistas.add(titulo)
                salida.write(json.dumps({
                    "titular": titulo, "medio": a["dominio"], "fecha": a["fecha"], "url": a["url"],
                }, ensure_ascii=False) + "\n")
                nuevos += 1
            total += nuevos
            print(f"  {marca}: +{nuevos} (total {total})")
    print(f"  {total} titulares -> {destino.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refrescar", action="store_true", help="vuelve a descargar aunque ya exista")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        for nombre, funcion in [
            ("FakeDeS", descargar_fakedes),
            ("FactSpan", descargar_factspan),
            ("UPM", descargar_upm),
            ("Data Commons", descargar_datacommons),
            ("Google Fact Check", descargar_google_factcheck),
            ("Titulares de medios (GDELT)", descargar_titulares_medios),
        ]:
            print(f"[{nombre}]")
            funcion(client, args.refrescar)

    with open(RAW_DIR / "FUENTES.json", "w", encoding="utf-8") as f:
        json.dump(FUENTES, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
