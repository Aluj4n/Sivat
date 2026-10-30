import { useCallback, useEffect, useState } from 'react';
import ControlesDecision from '../components/ControlesDecision/ControlesDecision';
import EvidenciaPanel from '../components/EvidenciaPanel/EvidenciaPanel';
import MedidorConfianza from '../components/MedidorConfianza/MedidorConfianza';
import type { Evaluacion } from '../tipos/verificacion';
import { formatearFecha } from '../utils/fecha';
import { generarInformePDF } from '../utils/informe';
import { titularDe } from '../utils/texto';
import './Validacion.css';

const API_BASE = '/api/v1/verificacion';
const MAX_EN_COLA = 200;

function TextoAnalizado({ evaluacion }: { evaluacion: Evaluacion }) {
  const titular = titularDe(evaluacion.texto);
  const cuerpo = evaluacion.texto.slice(evaluacion.texto.indexOf(titular) + titular.length).trim();
  return (
    <>
      <p className="cola-texto">{titular}</p>
      {cuerpo && (
        <details className="cola-cuerpo">
          <summary>Ver texto analizado ({evaluacion.palabras_analizadas} palabras)</summary>
          <p>{cuerpo}</p>
        </details>
      )}
    </>
  );
}

function MetaFuente({ evaluacion }: { evaluacion: Evaluacion }) {
  return (
    <span className="cola-meta">
      {evaluacion.fuente_origen ? `${evaluacion.fuente_origen} · ` : 'Ingreso manual · '}
      {formatearFecha(evaluacion.fecha_evaluacion)} · modelo {evaluacion.version_modelo}
      {evaluacion.url_original && (
        <>
          {' · '}
          <a href={evaluacion.url_original} target="_blank" rel="noopener noreferrer">
            Ver fuente ↗
          </a>
        </>
      )}
    </span>
  );
}

export default function Validacion() {
  const [texto, setTexto] = useState('');
  const [analizando, setAnalizando] = useState(false);
  const [errorAnalisis, setErrorAnalisis] = useState<string | null>(null);
  const [cola, setCola] = useState<Evaluacion[]>([]);
  const [cargandoCola, setCargandoCola] = useState(true);
  const [buscandoEvidenciaId, setBuscandoEvidenciaId] = useState<number | null>(null);
  const [eliminandoId, setEliminandoId] = useState<number | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const cargarCola = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/recientes?limit=${MAX_EN_COLA}`);
      if (!response.ok) throw new Error('No se pudo obtener la cola de validación');
      const data: Evaluacion[] = await response.json();
      setCola(data);
    } catch (err) {
      console.error('Error al cargar la cola de validación', err);
    } finally {
      setCargandoCola(false);
    }
  }, []);

  useEffect(() => {
    cargarCola();
  }, [cargarCola]);

  const handleAnalizar = async () => {
    if (texto.trim().length < 10) {
      setErrorAnalisis('Escribe al menos 10 caracteres para evaluar.');
      return;
    }
    setAnalizando(true);
    setErrorAnalisis(null);
    try {
      const response = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ texto }),
      });
      if (!response.ok) {
        const detalle = await response.json().catch(() => null);
        throw new Error(detalle?.detail || 'No se pudo evaluar la afirmación.');
      }
      setTexto('');
      await cargarCola();
    } catch (err) {
      setErrorAnalisis(err instanceof Error ? err.message : 'Error desconocido al evaluar.');
    } finally {
      setAnalizando(false);
    }
  };

  const handleBuscarEvidencia = async (afirmacionId: number) => {
    setBuscandoEvidenciaId(afirmacionId);
    try {
      const response = await fetch(`${API_BASE}/${afirmacionId}/evidencia`, { method: 'POST' });
      if (!response.ok) throw new Error('No se pudo buscar evidencia');
      const actualizada: Evaluacion = await response.json();
      setCola((prev) => prev.map((e) => (e.afirmacion_id === afirmacionId ? actualizada : e)));
    } catch (err) {
      console.error('Error al buscar evidencia', err);
    } finally {
      setBuscandoEvidenciaId(null);
    }
  };

  const handleEliminar = async (afirmacionId: number) => {
    if (!window.confirm('¿Eliminar esta afirmación validada? Se borrará por completo de SIVAT y no se puede deshacer.')) {
      return;
    }
    setEliminandoId(afirmacionId);
    setAviso(null);
    try {
      const response = await fetch(`${API_BASE}/${afirmacionId}`, { method: 'DELETE' });
      if (!response.ok) throw new Error('No se pudo eliminar la afirmación.');
      setCola((prev) => prev.filter((e) => e.afirmacion_id !== afirmacionId));
    } catch (err) {
      setAviso(err instanceof Error ? err.message : 'Error al eliminar.');
    } finally {
      setEliminandoId(null);
    }
  };

  const handleInforme = (evaluacion: Evaluacion) => {
    setAviso(null);
    if (!generarInformePDF(evaluacion)) {
      setAviso('El navegador bloqueó la ventana del informe: permite las ventanas emergentes para este sitio.');
    }
  };

  const pendientes = cola.filter((e) => !e.decision);
  const observadas = cola.filter((e) => e.decision?.decision_periodista === 'Observado');
  const validadas = cola.filter((e) => e.decision?.decision_periodista === 'Validado');

  // Pendientes y observadas comparten tarjeta: cambia solo si se puede volver a observar
  const renderItemCola = (e: Evaluacion, enObservacion: boolean) => (
    <li key={e.afirmacion_id} className="cola-item">
      <div className="cola-info">
        <TextoAnalizado evaluacion={e} />
        <MetaFuente evaluacion={e} />
        {enObservacion && e.decision && (
          <span className="cola-meta">En observación desde {formatearFecha(e.decision.fecha_decision)}</span>
        )}
      </div>
      <div className="cola-acciones">
        <MedidorConfianza confianza={e.confianza_modelo} palabras={e.palabras_analizadas} />
        <ControlesDecision afirmacionId={e.afirmacion_id} permitirObservar={!enObservacion} onHecho={cargarCola} />
      </div>
      <EvidenciaPanel
        evidenciaBuscada={e.evidencia_buscada}
        nivel={e.nivel_evidencia_disponible}
        coincidentes={e.fuentes_coincidentes}
        contradictorias={e.fuentes_contradictorias}
        explicacion={e.explicacion}
        evidencias={e.evidencias}
        buscando={buscandoEvidenciaId === e.afirmacion_id}
        onBuscar={() => handleBuscarEvidencia(e.afirmacion_id)}
      />
    </li>
  );

  return (
    <div className="validacion-view">
      <div className="validacion-header">
        <div>
          <h1>Validación</h1>
          <p>El clasificador analiza patrones de posible desinformación; la conclusión siempre la registra una persona.</p>
        </div>
        <div className="validacion-flujo">IA analiza → IA recomienda → la persona valida y decide</div>
      </div>

      <section className="panel analizar-panel">
        <h2>Analizar una afirmación o noticia</h2>
        <textarea
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder="Pega el texto de la noticia o rumor, o el enlace a la noticia (se descarga su contenido)…"
          rows={4}
        />
        <div className="analizar-footer">
          {errorAnalisis && <span className="analizar-error">{errorAnalisis}</span>}
          <button type="button" onClick={handleAnalizar} disabled={analizando}>
            {analizando ? 'Analizando…' : 'Analizar'}
          </button>
        </div>
      </section>

      {/* Izquierda: lo que falta decidir. Derecha: lo ya validado. */}
      <div className="validacion-columnas">
        <div className="validacion-columna">
          <section className="panel">
            <h2>Pendientes de validación</h2>
            <span className="panel-subtitle">
              {pendientes.length} afirmación(es) esperando revisión · Validar registra tu conclusión, Observar la deja
              en seguimiento y Descartar la elimina por completo
            </span>

            {cargandoCola && <p className="validacion-estado">Cargando…</p>}
            {!cargandoCola && pendientes.length === 0 && (
              <p className="validacion-estado">No hay afirmaciones pendientes. Analiza una arriba para empezar.</p>
            )}

            <ul className="cola-lista">{pendientes.map((e) => renderItemCola(e, false))}</ul>
          </section>

          {observadas.length > 0 && (
            <section className="panel">
              <h2>En observación</h2>
              <span className="panel-subtitle">
                {observadas.length} en seguimiento · Actualiza la evidencia cuando haya novedades y luego valídala o
                descártala
              </span>
              <ul className="cola-lista">{observadas.map((e) => renderItemCola(e, true))}</ul>
            </section>
          )}
        </div>

        <div className="validacion-columna">
          <section className="panel">
            <h2>Ya validadas</h2>
            <span className="panel-subtitle">
              {validadas.length} con conclusión registrada por el periodista, diferenciada del análisis de la IA
            </span>
            {aviso && <p className="analizar-error">{aviso}</p>}
            {!cargandoCola && validadas.length === 0 && (
              <p className="validacion-estado">Aún no hay afirmaciones validadas.</p>
            )}
            <ul className="cola-lista">
              {validadas.map((e) => (
                <li key={e.afirmacion_id} className="cola-item validada-item">
                  <div className="cola-info">
                    <p className="cola-texto">{titularDe(e.texto)}</p>
                    <span className="cola-meta">
                      {e.fuente_origen ?? 'Ingreso manual'} · Confianza del modelo:{' '}
                      {e.confianza_modelo === null ? 'texto insuficiente' : `${e.confianza_modelo}%`} · validada el{' '}
                      {formatearFecha(e.decision!.fecha_decision)}
                    </span>
                    {e.decision!.comentarios && <span className="validada-comentario">«{e.decision!.comentarios}»</span>}
                  </div>
                  <div className="validada-lado">
                    <span className="conclusion-badge">{e.decision!.conclusion ?? 'Sin conclusión registrada'}</span>
                    <div className="validada-botones">
                      <button type="button" onClick={() => handleInforme(e)}>
                        Informe PDF
                      </button>
                      <button
                        type="button"
                        className="is-peligro"
                        disabled={eliminandoId === e.afirmacion_id}
                        onClick={() => handleEliminar(e.afirmacion_id)}
                      >
                        {eliminandoId === e.afirmacion_id ? 'Eliminando…' : 'Eliminar'}
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}
