import { useCallback, useEffect, useState } from 'react';
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
  senal: string;
  recomendacion_sistema: string;
  version_modelo: string;
  nivel_evidencia_disponible: string | null;
  fuentes_coincidentes: number | null;
  fuentes_contradictorias: number | null;
  fuente_oficial_encontrada: boolean | null;
  cobertura_evidencia: string | null;
  fecha_evaluacion?: string;
  decision?: DecisionInfo | null;
}

// Mismos umbrales que services/clasificador_service.py — magnitud de evidencia,
// nunca una etiqueta de verdadero/falso (RNF-08).
function nivelConfianza(prob: number): { label: string; color: string } {
  if (prob >= 0.66) return { label: 'Alto', color: 'var(--seq-500)' };
  if (prob >= 0.33) return { label: 'Medio', color: 'var(--seq-350)' };
  return { label: 'Bajo', color: 'var(--seq-200)' };
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
            const nivel = nivelConfianza(e.probabilidad_desinformacion);
            return (
              <li key={e.afirmacion_id} className="cola-item">
                <div className="cola-info">
                  <p className="cola-texto">{e.texto}</p>
                  <span className="cola-meta">
                    {formatearFecha(e.fecha_evaluacion)} · {e.senal} · modelo {e.version_modelo}
                  </span>
                </div>
                <div className="cola-acciones">
                  <span className="nivel-confianza">
                    <span className="nivel-confianza-dot" style={{ backgroundColor: nivel.color }} />
                    Confianza: {nivel.label} ({(e.probabilidad_desinformacion * 100).toFixed(0)}%)
                  </span>
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
                    IA: {e.senal} · {formatearFecha(e.fecha_evaluacion)}
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
