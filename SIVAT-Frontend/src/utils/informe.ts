import type { Evaluacion } from '../tipos/verificacion';
import { formatearFecha } from './fecha';
import { titularDe } from './texto';

// Informe de verificación de una afirmación ya validada. Se arma como HTML y
// se abre el diálogo de impresión del navegador, donde se elige "Guardar como
// PDF": no hace falta ninguna librería de PDF.

const MAX_CARACTERES_TEXTO = 3000;

function esc(valor: string | number | null | undefined): string {
  return String(valor ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function enlace(url: string | null, texto: string): string {
  return url ? `<a href="${esc(url)}">${esc(texto)}</a>` : esc(texto);
}

function filaDato(etiqueta: string, valor: string): string {
  return `<tr><th>${esc(etiqueta)}</th><td>${valor}</td></tr>`;
}

const ESTILOS = `
  @page { size: A4; margin: 18mm 16mm; }
  * { box-sizing: border-box; }
  body { font-family: "Segoe UI", Roboto, Arial, sans-serif; color: #1c2b3a; font-size: 11pt; line-height: 1.45; margin: 0; }
  header { border-bottom: 3px solid #1c527e; padding-bottom: 10px; margin-bottom: 18px; display: flex; justify-content: space-between; align-items: flex-end; }
  header h1 { font-size: 18pt; margin: 0; color: #1c527e; }
  header span { font-size: 9pt; color: #5a6b7b; text-align: right; }
  h2 { font-size: 12.5pt; color: #1c527e; margin: 20px 0 8px; border-bottom: 1px solid #dbe3eb; padding-bottom: 4px; }
  .afirmacion { font-size: 13pt; font-weight: 700; margin: 0 0 6px; }
  .conclusion { border: 1.5px solid #1c527e; border-radius: 8px; padding: 12px 14px; margin: 14px 0; }
  .conclusion strong { font-size: 15pt; display: block; margin-top: 2px; }
  .conclusion small { color: #5a6b7b; }
  table { width: 100%; border-collapse: collapse; font-size: 10pt; }
  th, td { text-align: left; vertical-align: top; padding: 5px 8px; border-bottom: 1px solid #e5e9ee; }
  table.datos th { width: 34%; color: #5a6b7b; font-weight: 600; }
  table.evidencia thead th { background: #f1f5f9; font-weight: 700; }
  ul { margin: 4px 0; padding-left: 18px; }
  li { margin: 2px 0; }
  .texto { white-space: pre-line; font-size: 9.5pt; color: #3d4a57; background: #f8fafc; border-radius: 6px; padding: 10px 12px; }
  a { color: #1c527e; word-break: break-all; }
  .nota { font-size: 8.5pt; color: #5a6b7b; margin-top: 24px; border-top: 1px solid #dbe3eb; padding-top: 8px; }
  .vacio { color: #5a6b7b; font-style: italic; }
`;

function tablaEvidencia(evaluacion: Evaluacion, tipo: 'verificacion' | 'medio'): string {
  const items = evaluacion.evidencias.filter((e) => e.tipo === tipo);
  if (items.length === 0) {
    return `<p class="vacio">${tipo === 'verificacion' ? 'No se encontraron verificaciones similares.' : 'No se encontraron medios con información similar.'}</p>`;
  }
  const filas = items
    .map(
      (e) => `<tr>
        <td>${esc(e.origen)}</td>
        <td>${enlace(e.url, e.titulo ?? '')}</td>
        ${tipo === 'verificacion' ? `<td>${esc(e.calificacion ?? '—')}</td>` : ''}
        <td>${Math.round(e.similitud * 100)}%</td>
      </tr>`,
    )
    .join('');
  return `<table class="evidencia">
    <thead><tr><th>${tipo === 'verificacion' ? 'Verificador' : 'Medio'}</th><th>Título</th>
    ${tipo === 'verificacion' ? '<th>Calificación del verificador</th>' : ''}<th>Similitud</th></tr></thead>
    <tbody>${filas}</tbody></table>`;
}

function construirInforme(evaluacion: Evaluacion): string {
  const decision = evaluacion.decision;
  const titular = titularDe(evaluacion.texto);
  const cuerpo = evaluacion.texto.slice(evaluacion.texto.indexOf(titular) + titular.length).trim();
  const textoRecortado =
    cuerpo.length > MAX_CARACTERES_TEXTO ? `${cuerpo.slice(0, MAX_CARACTERES_TEXTO)}…` : cuerpo;
  const generado = formatearFecha(new Date().toISOString());

  return `<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Informe SIVAT - afirmación ${evaluacion.afirmacion_id}</title>
<style>${ESTILOS}</style></head>
<body>
  <header>
    <h1>SIVAT · Informe de verificación</h1>
    <span>Afirmación n.° ${evaluacion.afirmacion_id}<br>Generado: ${esc(generado)}</span>
  </header>

  <p class="afirmacion">${esc(titular)}</p>
  <table class="datos">
    ${filaDato('Fuente', esc(evaluacion.fuente_origen ?? 'Ingreso manual'))}
    ${evaluacion.url_original ? filaDato('Enlace original', enlace(evaluacion.url_original, evaluacion.url_original)) : ''}
    ${filaDato('Fecha de análisis', esc(formatearFecha(evaluacion.fecha_evaluacion)))}
  </table>

  <div class="conclusion">
    <small>Conclusión del periodista</small>
    <strong>${esc(decision?.conclusion ?? 'Sin conclusión registrada')}</strong>
    ${decision?.comentarios ? `<p>${esc(decision.comentarios)}</p>` : ''}
    <small>Validada el ${esc(formatearFecha(decision?.fecha_decision))}</small>
  </div>

  <h2>Análisis de SIVAT</h2>
  <table class="datos">
    ${filaDato(
      'Confianza del modelo de texto',
      evaluacion.confianza_modelo === null
        ? `Texto insuficiente para el modelo (${evaluacion.palabras_analizadas} palabras)`
        : `${evaluacion.confianza_modelo}% · ${esc(evaluacion.senal)}`,
    )}
    ${filaDato('Versión del modelo', esc(evaluacion.version_modelo))}
    ${filaDato('Evidencia disponible', esc(evaluacion.nivel_evidencia_disponible ?? 'No se buscó'))}
    ${filaDato('Fuentes coincidentes / contradictorias', `${evaluacion.fuentes_coincidentes ?? 0} / ${evaluacion.fuentes_contradictorias ?? 0}`)}
  </table>
  ${evaluacion.explicacion.length ? `<ul>${evaluacion.explicacion.map((r) => `<li>${esc(r)}</li>`).join('')}</ul>` : ''}

  <h2>Verificaciones similares</h2>
  ${tablaEvidencia(evaluacion, 'verificacion')}

  <h2>Medios que publicaron información similar</h2>
  ${tablaEvidencia(evaluacion, 'medio')}

  ${textoRecortado ? `<h2>Texto analizado</h2><div class="texto">${esc(textoRecortado)}</div>` : ''}

  <p class="nota">
    SIVAT asiste la verificación con evidencia trazable y no emite veredictos: la conclusión de este informe
    es del periodista. Las calificaciones de la tabla de verificaciones pertenecen a cada verificador. La
    confianza del modelo mide patrones de redacción, no comprueba hechos.
  </p>
</body></html>`;
}

/** Abre el informe en una pestaña nueva y lanza el diálogo de impresión (Guardar como PDF). */
export function generarInformePDF(evaluacion: Evaluacion): boolean {
  const ventana = window.open('', '_blank');
  if (!ventana) return false;  // ventana emergente bloqueada
  ventana.document.open();
  ventana.document.write(construirInforme(evaluacion));
  ventana.document.close();
  ventana.addEventListener('afterprint', () => ventana.close());
  // Espera a que el documento termine de pintarse antes de imprimir
  ventana.setTimeout(() => {
    ventana.focus();
    ventana.print();
  }, 300);
  return true;
}
