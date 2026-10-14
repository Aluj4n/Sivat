import { useCallback, useEffect, useState } from 'react';
import EvidenciaPanel, { type Evidencia } from '../components/EvidenciaPanel/EvidenciaPanel';
import MedidorConfianza from '../components/MedidorConfianza/MedidorConfianza';
import './Validacion.css';

const API_BASE = '/api/v1/verificacion';

type Decision = 'Aceptado' | 'Rechazado' | 'Observado';

interface DecisionInfo {
  decision_periodista: Decision;
  comentarios: string | null;
  fecha_decision: string;
}

interface Evaluacion {
  afirmacion_id: number;
  texto: string;
  probabilidad_desinformacion: number;
  confianza_modelo: number;
  senal: string;
  recomendacion_sistema: string;
  version_modelo: string;
  fuente_origen: string | null;
  url_original: string | null;
  evidencia_buscada: boolean;
  nivel_evidencia_disponible: string | null;
  fuentes_coincidentes: number | null;
  fuentes_contradictorias: number | null;
  fuente_oficial_encontrada: boolean | null;
  cobertura_evidencia: string | null;
  explicacion: string[];
  evidencias: Evidencia[];
  fecha_evaluacion?: string;
  decision?: DecisionInfo | null;
}

function formatearFecha(iso?: string): string {
  if (!iso) return '';
  return new Date(iso).toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short' });
}

export default function Validacion() {
  const [texto, setTexto] = useState('');
  const [analizando, setAnalizando] = useState(false);
  const [errorAnalisis, setErrorAnalisis] = useState<string | null>(null);
  const [cola, setCola] = useState<Evaluacion[]>([]);
  const [cargandoCola, setCargandoCola] = useState(true);
  const [decidiendoId, setDecidiendoId] = useState<number | null>(null);
  const [buscandoEvidenciaId, setBuscandoEvidenciaId] = useState<number | null>(null);

  const cargarCola = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/recientes?limit=50`);
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

  const handleDecision = async (afirmacionId: number, decision: Decision) => {
    setDecidiendoId(afirmacionId);
    try {
      const response = await fetch(`${API_BASE}/${afirmacionId}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision }),
      });
      if (!response.ok) throw new Error('No se pudo registrar la decisión');
      await cargarCola();
    } catch (err) {
      console.error('Error al registrar decisión', err);
    } finally {
      setDecidiendoId(null);
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

  const pendientes = cola.filter((e) => !e.decision);
  const validadas = cola.filter((e) => e.decision);

  return (
    <div className="validacion-view">
      <div className="validacion-header">
        <div>
          <h1>Validación</h1>
          <p>El clasificador analiza patrones de posible desinformación; la decisión final siempre la registra el periodista.</p>
        </div>
        <div className="validacion-flujo">IA analiza → IA recomienda → periodista valida → editor decide</div>
      </div>

      <section className="panel analizar-panel">
        <h2>Analizar una afirmación o noticia</h2>
        <textarea
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder="Pega aquí el texto de la afirmación o rumor a evaluar…"
          rows={4}
        />
        <div className="analizar-footer">
          {errorAnalisis && <span className="analizar-error">{errorAnalisis}</span>}
          <button type="button" onClick={handleAnalizar} disabled={analizando}>
            {analizando ? 'Analizando…' : 'Analizar'}
          </button>
        </div>
      </section>

      <section className="panel">
        <h2>Pendientes de validación</h2>
        <span className="panel-subtitle">{pendientes.length} afirmación(es) esperando revisión periodística</span>

        {cargandoCola && <p className="validacion-estado">Cargando…</p>}
        {!cargandoCola && pendientes.length === 0 && (
          <p className="validacion-estado">No hay afirmaciones pendientes. Analiza una arriba para empezar.</p>
        )}

        <ul className="cola-lista">
          {pendientes.map((e) => {
            return (
              <li key={e.afirmacion_id} className="cola-item">
                <div className="cola-info">
                  <p className="cola-texto">{e.texto}</p>
                  <span className="cola-meta">
                    {e.fuente_origen ? `${e.fuente_origen} · ` : 'Ingreso manual · '}
                    {formatearFecha(e.fecha_evaluacion)} · modelo {e.version_modelo}
                    {e.url_original && (
                      <>
                        {' · '}
                        <a href={e.url_original} target="_blank" rel="noopener noreferrer">
                          Ver fuente ↗
                        </a>
                      </>
                    )}
                  </span>
                </div>
                <div className="cola-acciones">
                  <MedidorConfianza confianza={e.confianza_modelo} />
                  <div className="cola-botones">
                    <button
                      type="button"
                      disabled={decidiendoId === e.afirmacion_id}
                      onClick={() => handleDecision(e.afirmacion_id, 'Aceptado')}
                    >
                      Aceptar
                    </button>
                    <button
                      type="button"
                      disabled={decidiendoId === e.afirmacion_id}
                      onClick={() => handleDecision(e.afirmacion_id, 'Observado')}
                    >
                      Observar
                    </button>
                    <button
                      type="button"
                      disabled={decidiendoId === e.afirmacion_id}
                      onClick={() => handleDecision(e.afirmacion_id, 'Rechazado')}
                    >
                      Rechazar
                    </button>
                  </div>
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
          })}
        </ul>
      </section>

      {validadas.length > 0 && (
        <section className="panel">
          <h2>Ya validadas</h2>
          <span className="panel-subtitle">Decisión editorial registrada, diferenciada de la recomendación de la IA</span>
          <ul className="cola-lista">
            {validadas.map((e) => (
              <li key={e.afirmacion_id} className="cola-item">
                <div className="cola-info">
                  <p className="cola-texto">{e.texto}</p>
                  <span className="cola-meta">
                    Confianza del modelo: {e.confianza_modelo}% · {formatearFecha(e.fecha_evaluacion)}
                  </span>
                </div>
                <span className={`decision-badge decision-${e.decision!.decision_periodista.toLowerCase()}`}>
                  {e.decision!.decision_periodista} · {formatearFecha(e.decision!.fecha_decision)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
