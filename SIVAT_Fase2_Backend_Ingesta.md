# Fase 2: Backend e Ingesta de Datos - Proyecto SIVAT

**Periodo de Ejecución:** Semanas 3 - 4 del proyecto.
**Tecnologías Principales:** Python, FastAPI, PostgreSQL, Git.

Esta fase establece la columna vertebral del sistema SIVAT. Se encarga de la recolección en tiempo real de información desde fuentes externas, la estructuración de la base de datos y la exposición de servicios RESTful asíncronos para los módulos de Inteligencia Artificial y el dashboard web.

## 2.1. Estructura Base del Proyecto y Arquitectura
Para garantizar una latencia de procesamiento óptima (menor a 5 segundos por lote) y manejar múltiples peticiones concurrentes a APIs externas, el backend se estructura de forma asíncrona.

### Tareas Operativas:
1.  **Configuración del entorno:** Creación y activación de un entorno virtual en Python (`venv`) para aislar dependencias de manera limpia.
2.  **Gestión de dependencias:** Configurar `requirements.txt` integrando paquetes esenciales: `fastapi`, `uvicorn`, `sqlalchemy`, `asyncpg` (driver asíncrono para PostgreSQL), `httpx` (para peticiones a APIs externas) y `pydantic`.
3.  **Arquitectura de directorios modular:**
    *   `/api`: Enrutadores (`routers`) y controladores de endpoints RESTful.
    *   `/core`: Configuraciones globales, gestión de variables de entorno y middleware de seguridad.
    *   `/db`: Conexión a la base de datos PostgreSQL y gestión de migraciones (ej. mediante Alembic).
    *   `/models`: Definición de modelos ORM y esquemas de validación de datos.
    *   `/services`: Lógica de integración y captura de datos desde fuentes externas.

## 2.2. Diseño e Integración de la Base de Datos (PostgreSQL)
Implementación de un repositorio central relacional estructurado para garantizar la persistencia del histórico de análisis, orígenes y auditoría de decisiones.

### Tablas y Entidades Críticas:
*   **`FuenteExterna` (Source Data):** Almacenamiento temporal y metadatos de la información recolectada de redes y portales (texto crudo procesado, origen, marca de tiempo).
*   **`Tendencia` (Trending Topic):** Registro histórico de temas, volumen de menciones y velocidad de crecimiento temporal.
*   **`Afirmacion` (Claim):** Extracción de afirmaciones específicas identificadas en publicaciones virales para su futura verificación.
*   **`DecisionEditorial` (Editorial Decision):** Tabla clave para registrar la validación humana obligatoria. Enlazará la recomendación de la IA con la decisión final del periodista (aceptación, rechazo u observación).

## 2.3. Módulo de Ingesta de Datos (Integración de APIs)
Desarrollo de los conectores asíncronos (usando `httpx`) para la captura de datos en tiempo real que alimentarán los algoritmos de extracción y tendencias.

### Servicios a Implementar:
1.  **Servicio GDELT Project:**
    *   Conexión a los feeds de GDELT para extraer artículos, monitorear eventos web y clasificar metadatos de noticias relevantes dentro del contexto peruano.
2.  **Servicio API de X (Twitter) v2:**
    *   Configuración de endpoints de streaming o polling avanzado para capturar publicaciones virales, tendencias emergentes y conversaciones digitales de alto impacto.
3.  **Servicio YouTube Data API:**
    *   Integración para buscar y recuperar metadatos (descripciones, transcripciones) de canales de noticias y eventos coyunturales (ej. mensajes a la nación, protestas).

## 2.4. Capa de Seguridad, Privacidad y Cumplimiento Normativo
Implementación estricta de mecanismos de protección para evitar la exposición de datos personales, respetando la Ley N.° 29733 de Protección de Datos Personales del Perú.

### Controles de Anonimización:
*   **Middleware de Sanitización:** Los textos recolectados por los conectores pasarán por un proceso de limpieza que eliminará metadatos sensibles y nombres de usuarios explícitos de individuos comunes antes de insertarlos en PostgreSQL.
*   **Seudonimización (Hashing):** Si el modelo de tendencias requiere rastrear usuarios únicos para evitar contar bots como múltiples personas, se aplicará cifrado (ej. SHA-256) sobre los IDs reales.
*   **Minimización de Datos:** Conservar únicamente el contenido estrictamente necesario para la evaluación semántica y la generación del scoring de confiabilidad.

## 2.5. Logging y Preparación de Trazabilidad
Preparación de la arquitectura transversal para respaldar la auditoría y explicabilidad que se requerirá al integrar el motor NLP/RAG.

### Tareas:
*   Configuración de logs estructurados (JSON) para registrar latencias de consumo de APIs, fallas de red y respuestas del sistema.
*   Diseñar esquemas en base de datos listos para registrar la **versión exacta del modelo IA** y el repositorio de **fuentes consultadas**, asegurando la trazabilidad completa (IA analiza -> IA recomienda -> Periodista valida -> Editor decide).
