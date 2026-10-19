# SIVAT

**Sistema Inteligente de Asistencia para Verificación Periodística y Análisis de Tendencias**, desarrollado para la Unidad de Redacción Digital y Verificación de Canal N.

SIVAT capta noticias y rumores de medios y redes sociales en tiempo real, detecta los temas que están creciendo y ayuda al periodista a verificarlos con un modelo de machine learning y evidencia de verificadores.

> **Principio rector:** IA analiza → IA recomienda → periodista valida → editor decide.
>
> SIVAT **nunca** emite un veredicto automático de verdadero o falso (RNF-08). Todo lo que muestra son señales y evidencia para que una persona decida.

Proyecto académico del curso *Sistemas Inteligentes y Machine Learning* (UPN).

---

## Funcionalidades

| Vista | Qué hace |
|---|---|
| **Dashboard** | Resumen en vivo: noticias capturadas en 24 h, ingesta por fuente, decisiones editoriales, tendencias emergentes y cola de validación. |
| **Perú** | Feed en vivo de noticias sobre Perú (Canal N, RPP, Andina, El Comercio, La República y más), con botón **Validar**. |
| **Internacionales** | Feed en vivo de noticias y rumores internacionales (GDELT, medios RSS, Bluesky, Reddit, YouTube). |
| **Tendencias** | Agrupa el feed por tema con IA y ordena los temas por **prioridad de verificación** (qué conviene revisar primero). |
| **Validación** | Analiza una noticia o enlace: modelo de clasificación, evidencia de verificadores y medios (RAG) y decisión del periodista. |

### Componentes de inteligencia artificial

- **Modelo A, artículos (aprendizaje supervisado):** TF-IDF + Random Forest entrenado con FakeDeS (IberLEF 2021), F1 macro 0,727. Solo se aplica a textos de 200 palabras o más.
- **Módulo RAG de evidencia:** busca verificaciones (RSS de verificadores y Google Fact Check) y cobertura de medios similares por similitud coseno.
- **Módulo de Tendencias (aprendizaje no supervisado):** embeddings multilingües (`multilingual-e5-small`) + HDBSCAN. Asigna la prioridad con reglas explicables.

Las métricas y figuras de los experimentos están en [`SIVAT-Backend/ml/resultados/`](SIVAT-Backend/ml/resultados/).

---

## Tecnologías

- **Backend:** Python 3.12, FastAPI, SQLAlchemy (async), PostgreSQL 15
- **Machine learning:** scikit-learn, PyTorch (CPU), sentence-transformers, trafilatura, NLTK
- **Frontend:** React 19, TypeScript, Vite
- **Base de datos:** PostgreSQL en Docker

```
SIVAT/
├── SIVAT-Backend/
│   ├── api/              # Endpoints REST (noticias, verificación, tendencias, dashboard)
│   ├── services/         # Ingesta de fuentes, RAG, clasificador, tendencias
│   ├── ml/               # Descarga de datos, entrenamiento, experimentos y resultados
│   ├── models/           # Tablas de la base de datos
│   ├── models_ml/        # Modelo entrenado (modelo_articulos.joblib)
│   ├── main.py           # Arranque de la API y ciclos automáticos de ingesta
│   ├── init_db.py        # Crea las tablas
│   └── docker-compose.yml
└── SIVAT-Frontend/
    └── src/              # Vistas y componentes de React
```

---

## Requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Python 3.12](https://www.python.org/downloads/)
- [Node.js 22](https://nodejs.org/) o superior
- Una clave de API de Google Cloud con **YouTube Data API v3** y **Fact Check Tools API** habilitadas (opcional, ver abajo)

---

## Instalación y ejecución

Los comandos están escritos para **PowerShell en Windows**.

### 1. Clonar el repositorio

```powershell
git clone <url-del-repositorio>
cd SIVAT
```

### 2. Levantar la base de datos

```powershell
cd SIVAT-Backend
docker compose up -d
```

Crea un contenedor `sivat_postgres` con PostgreSQL en el puerto **5433**. No hay que configurar nada más.

### 3. Crear el entorno de Python e instalar dependencias

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

La instalación tarda varios minutos, porque incluye PyTorch.

### 4. Crear el archivo `.env`

El archivo `.env` va en `SIVAT-Backend/` y **no se sube al repositorio**, porque contiene claves. Pídeselo al equipo o créalo con estas variables:

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:password@localhost:5433/sivat_db` (coincide con `docker-compose.yml`) |
| `YOUTUBE_API_KEY` | Clave de Google Cloud. Se usa para YouTube y para Google Fact Check. Sin una clave válida, esas dos fuentes fallan y el resto sigue funcionando. |
| `X_API_BEARER_TOKEN` | Obligatoria, pero X no se usa por ahora: puede ser cualquier texto. |
| `SECRET_KEY` | Cualquier texto largo. |

Variables opcionales:
- `GOOGLE_FACTCHECK_API_KEY`: clave propia para Fact Check; si falta, se usa la de YouTube.
- `GDELT_INGESTA_HABILITADA`, `YOUTUBE_INGESTA_HABILITADA`, `BLUESKY_INGESTA_HABILITADA`, `REDDIT_INGESTA_HABILITADA`, `RSS_INGESTA_HABILITADA`, `TENDENCIAS_HABILITADAS`: `true` o `false` para activar o apagar cada proceso.

### 5. Verificar el modelo entrenado

El archivo `SIVAT-Backend/models_ml/modelo_articulos.joblib` viene en el repositorio. Si falta, todo funciona menos la validación, que responde con error 503. Para regenerarlo, ver [Reentrenar los modelos](#reentrenar-los-modelos).

### 6. Crear las tablas

```powershell
python init_db.py
```

### 7. Iniciar el backend

```powershell
$env:PYTHONIOENCODING="utf-8"
uvicorn main:app --port 8000
```

- La API queda en http://localhost:8000. La documentación interactiva está en http://localhost:8000/docs.
- Al arrancar se inician solos los ciclos de ingesta y de tendencias.

### 8. Iniciar el frontend

En **otra terminal**:

```powershell
cd SIVAT-Frontend
npm install
npm run dev
```

Abre **http://localhost:5173**.

---

## Primera ejecución: qué esperar

- **Paneles Perú e Internacionales:** se llenan en los primeros minutos, a medida que cada fuente cumple su ciclo (GDELT cada 3 min, RSS y Bluesky cada 5, Reddit cada 10, YouTube cada 15).
- **Tendencias:**
  - La primera vez se descarga el modelo de embeddings (~470 MB).
  - El primer cálculo tarda unos 2 minutos; luego se recalcula cada 15 minutos en unos segundos.
  - Con poco contenido en el feed puede no haber tendencias todavía.
- **Lo no validado se borra a las 24 h** (minimización de datos, Ley 29733). Lo que un periodista envía a validación se guarda de forma permanente.

---

## Reentrenar los modelos

Los datos descargados (`data/`) no se suben al repositorio. Para reproducir el entrenamiento, desde `SIVAT-Backend/` y con el entorno activado:

```powershell
python -m ml.fuentes_datos          # descarga los datasets (tarda; Google Fact Check requiere la clave)
python -m ml.preparar_corpus        # arma los corpus
python -m ml.entrenar_modelos       # entrena y evalúa, y guarda el modelo en models_ml/
python -m ml.experimento_tendencias # compara algoritmos de agrupamiento (requiere datos en el feed)
```

Las métricas y figuras se guardan en `ml/resultados/`.

---

## Problemas comunes

| Problema | Solución |
|---|---|
| `Field required` al iniciar el backend | Falta el archivo `.env` o alguna variable obligatoria. |
| No conecta a la base de datos | Revisa que Docker esté abierto y el contenedor activo (`docker ps`). El puerto es **5433**, no 5432. |
| Validar devuelve error 503 | Falta `models_ml/modelo_articulos.joblib`. |
| `WinError 1114` al cargar PyTorch | PyTorch debe cargarse antes que scikit-learn. Ya está resuelto en `ml/__init__.py`; inicia siempre el backend con `uvicorn main:app`. |
| Error con la tabla `tendencia` en una base de datos antigua | `init_db.py` no modifica tablas existentes. Si la tabla viene de una versión anterior y está vacía, bórrala (`docker exec sivat_postgres psql -U postgres -d sivat_db -c "drop table tendencia;"`) y vuelve a ejecutar `init_db.py`. |
| Errores de caracteres en la consola | Ejecuta `$env:PYTHONIOENCODING="utf-8"` antes de iniciar el backend. |

---

## Datos y licencias

Los datos se usan solo con fines académicos.

- **Entrenamiento:** FakeDeS / Spanish Fake News Corpus (CC BY 4.0), FactSpan (CC BY 4.0), Data Commons ClaimReview (CC BY 4.0), Spanish Fake News Dataset UPM (CC BY 4.0, uso académico).
- **Tiempo real:** fuentes públicas (GDELT, RSS de medios y verificadores, Bluesky, Reddit, YouTube Data API, Google Fact Check Tools API).
- **Privacidad:** SIVAT no guarda autores de publicaciones de redes sociales.
