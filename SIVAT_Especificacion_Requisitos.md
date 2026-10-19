# Especificación de Requisitos del Software (SRS) - Proyecto SIVAT

## 1. Información General
* **Proyecto:** SIVAT — Sistema Inteligente de Asistencia para Verificación Periodística y Análisis de Tendencias.
* **Cliente:** Unidad de Redacción Digital y Verificación de Canal N (Grupo El Comercio).
* **Plazo del MVP:** 16 semanas, ejecutado entre el 01/09/2026 y el 21/12/2026.
* **Presupuesto máximo:** S/ 20,000.

## 2. Propósito y Alcance (MVP)
El propósito es centralizar y acelerar la verificación de afirmaciones virales y dar seguimiento al sentimiento digital. **SIVAT no determina la veracidad de una noticia; asiste la verificación**.
* **Principio rector:** IA analiza → IA recomienda → periodista valida → editor decide.
* **Núcleo obligatorio:** Identificación de afirmaciones, recuperación de evidencias (RAG), fuentes trazables y dashboard web.
* **Componentes complementarios:** Detección de tendencias, análisis de sentimiento y scoring avanzado.
* **Fuera de alcance:** Aplicación móvil y análisis de propagación de narrativas.

## 3. Requisitos Funcionales Principales (RF)
* **RF-01:** Detectar automáticamente temas o narrativas en tendencia (GDELT, X, YouTube).
* **RF-02 a RF-04:** Identificar afirmaciones, recuperar evidencias relacionadas (RAG) y generar un nivel de confianza desagregado.
* **RF-05:** Procesar el sentimiento observado en conversaciones digitales.
* **RF-06 a RF-08:** Presentar un dashboard web, integrarse con APIs externas y almacenar el histórico en un repositorio central.
* **RF-09 a RF-11:** Registrar obligatoriamente la validación del periodista, el feedback de la evidencia y la decisión editorial final.

## 4. Requisitos No Funcionales (RNF) y Reglas de Negocio
* **Rendimiento (RNF-01):** El procesamiento por lote de comentarios debe ser menor a 5 segundos.
* **Cumplimiento y Privacidad (RNF-02):** Anonimización estricta bajo la Ley N.° 29733 de Protección de Datos Personales.
* **Explicabilidad (RNF-03) y Ética (RNF-08):** Mostrar siempre las fuentes utilizadas e impedir que el sistema emita automáticamente un veredicto de "verdadero/falso".

## 5. Interfaces del Sistema
* El Dashboard web debe desarrollarse en React y contar con las siguientes interfaces específicas:
    * Tendencias.
    * Noticias Perú y Noticias Internacionales.
    * Búsqueda.
    * Infiltrado (investigación de sospechas).
    * Verificación y Validación.
