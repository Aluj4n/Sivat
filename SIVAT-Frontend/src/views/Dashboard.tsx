import { useCallback, useEffect, useState } from 'react';
import MedidorConfianza from '../components/MedidorConfianza/MedidorConfianza';
import './Dashboard.css';

// Dashboard principal de SIVAT. Los KPIs y la "cola de validación" ya usan
// datos reales del clasificador (GET/POST /api/v1/verificacion). Tendencias
// emergentes, menciones 24h e ingesta por fuente siguen siendo una muestra
// ilustrativa: dependen de los módulos de Tendencias y RAG (E5/E2 del Acta de
// Alcance), que todavía no existen — quedan marcados como "muestra".

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
  fecha_evaluacion: string;
  decision?: DecisionInfo | null;
}

function formatearFecha(iso?: string): string {
  if (!iso) return '';
  return new Date(iso).toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short' });
}

function tiempoPromedioDecisionMin(evaluaciones: Evaluacion[]): number | null {
  const resueltas = evaluaciones.filter((e) => e.decision);
  if (resueltas.length === 0) return null;
  const totalMin = resueltas.reduce((acc, e) => {
    const inicio = new Date(e.fecha_evaluacion).getTime();
    const fin = new Date(e.decision!.fecha_decision).getTime();
    return acc + (fin - inicio) / 60000;
  }, 0);
  return totalMin / resueltas.length;
}

// --- Datos ilustrativos (módulos de Tendencias/RAG aún no construidos) ---

const MENCIONES_24H_MUESTRA = [
  120, 132, 128, 140, 155, 150, 165, 180, 210, 260, 310, 340, 365, 352, 338,
  320, 300, 285, 270, 255, 248, 240, 235, 230,
];

const INGESTA_POR_FUENTE_MUESTRA = [
  { fuente: 'GDELT', valor: 92, color: 'var(--series-1)' },
  { fuente: 'X (Twitter)', valor: 54, color: 'var(--series-2)' },
  { fuente: 'YouTube', valor: 38, color: 'var(--series-3)' },
];

const TENDENCIAS_MUESTRA = [
  { tema: 'Mensaje a la nación — reforma tributaria', volumen: 4820, velocidad: '+340%', deteccion: 'hace 8 min' },
  { tema: 'Protesta en Lima Centro', volumen: 3110, velocidad: '+210%', deteccion: 'hace 14 min' },
  { tema: 'Resultado preliminar JNE', volumen: 2675, velocidad: '+155%', deteccion: 'hace 21 min' },
];

function ChartMenciones() {
  const w = 640;
  const h = 200;
  const padLeft = 40;
  const padBottom = 24;
  const padTop = 12;
  const innerW = w - padLeft - 12;
  const innerH = h - padTop - padBottom;

  const max = Math.max(...MENCIONES_24H_MUESTRA);
  const rango = max || 1;

  const puntos = MENCIONES_24H_MUESTRA.map((v, i) => {
    const x = padLeft + (i / (MENCIONES_24H_MUESTRA.length - 1)) * innerW;
    const y = padTop + innerH - (v / rango) * innerH;
    return { x, y, v };
  });

  const linePath = puntos.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  const areaPath = `${linePath} L${puntos[puntos.length - 1].x.toFixed(1)},${padTop + innerH} L${puntos[0].x.toFixed(1)},${padTop + innerH} Z`;
  const ticksY = [0, Math.round(max / 2), max];
  const ultimo = puntos[puntos.length - 1];

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="line-chart" role="img" aria-label="Menciones en conversación digital, muestra ilustrativa">
      {ticksY.map((t) => {
        const y = padTop + innerH - (t / rango) * innerH;
        return (
          <g key={t}>
            <line x1={padLeft} y1={y} x2={w - 12} y2={y} className="chart-gridline" />
            <text x={padLeft - 8} y={y + 3} className="chart-axis-label" textAnchor="end">{t}</text>
          </g>
        );
      })}
      <path d={areaPath} className="chart-area" />
      <path d={linePath} className="chart-line" />
      <circle cx={ultimo.x} cy={ultimo.y} r="4" className="chart-end-dot" />
      <text x={ultimo.x} y={ultimo.y - 10} className="chart-end-label" textAnchor="end">{ultimo.v}</text>
      <text x={padLeft} y={h - 4} className="chart-axis-label">hace 24h</text>
      <text x={w - 12} y={h - 4} className="chart-axis-label" textAnchor="end">ahora</text>
    </svg>
  );
}

function ChartFuentes() {
  const w = 480;
  const barH = 22;
  const gap = 20;
  const padLeft = 96;
  const padRight = 56;
  const maxVal = Math.max(...INGESTA_POR_FUENTE_MUESTRA.map((f) => f.valor));
  const innerW = w - padLeft - padRight;
  const h = INGESTA_POR_FUENTE_MUESTRA.length * (barH + gap);

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="bar-chart" role="img" aria-label="Ingesta por fuente, muestra ilustrativa">
      {INGESTA_POR_FUENTE_MUESTRA.map((f, i) => {
        const y = i * (barH + gap) + gap / 2;
        const width = (f.valor / maxVal) * innerW;
        return (
          <g key={f.fuente}>
            <text x={padLeft - 12} y={y + barH / 2 + 4} className="chart-axis-label" textAnchor="end">{f.fuente}</text>
            <rect x={padLeft} y={y} width={innerW} height={barH} className="bar-track" rx="4" />
            <rect x={padLeft} y={y} width={width} height={barH} rx="4" fill={f.color} />
            <text x={padLeft + width + 8} y={y + barH / 2 + 4} className="chart-value-label">{f.valor}</text>
          </g>
        );
      })}
    </svg>
  );
}

export default function Dashboard() {
  const [evaluaciones, setEvaluaciones] = useState<Evaluacion[]>([]);
  const [cargando, setCargando] = useState(true);
  const [decidiendoId, setDecidiendoId] = useState<number | null>(null);

  const cargar = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/recientes?limit=50`);
      if (!response.ok) throw new Error('No se pudo obtener la cola de validación');
      const data: Evaluacion[] = await response.json();
      setEvaluaciones(data);
    } catch (err) {
      console.error('Error al cargar datos del dashboard', err);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const handleDecision = async (afirmacionId: number, decision: Decision) => {
    setDecidiendoId(afirmacionId);
    try {
      const response = await fetch(`${API_BASE}/${afirmacionId}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision }),
      });
      if (!response.ok) throw new Error('No se pudo registrar la decisión');
      await cargar();
    } catch (err) {
      console.error('Error al registrar decisión', err);
    } finally {
      setDecidiendoId(null);
    }
  };

  const pendientes = evaluaciones.filter((e) => !e.decision);
  const tiempoPromedio = tiempoPromedioDecisionMin(evaluaciones);

  return (
    <div className="dashboard-view">
      <div className="dashboard-header">
        <div>
          <h1>Dashboard</h1>
          <p>Vista general de verificación en curso. Tendencias e ingesta por fuente son una muestra ilustrativa.</p>
        </div>
        <div className="dashboard-flujo" title="Principio de supervisión humana, transversal a todo SIVAT">
          IA analiza → IA recomienda → periodista valida → editor decide
        </div>
      </div>

      <div className="dashboard-kpis">
        <div className="stat-tile">
          <span className="stat-tile-label">Alertas por validar</span>
          <div className="stat-tile-body">
            <span className="stat-tile-value">{cargando ? '—' : pendientes.length}</span>
          </div>
          <span className="stat-tile-delta">Afirmaciones evaluadas sin decisión editorial</span>
        </div>

        <div className="stat-tile">
          <span className="stat-tile-label">Afirmaciones evaluadas</span>
          <div className="stat-tile-body">
            <span className="stat-tile-value">{cargando ? '—' : evaluaciones.length}</span>
          </div>
          <span className="stat-tile-delta">Total procesado por el clasificador</span>
        </div>

        <div className="stat-tile">
          <span className="stat-tile-label">Tiempo promedio hasta decisión</span>
          <div className="stat-tile-body">
            <span className="stat-tile-value">
              {tiempoPromedio === null ? '—' : `${tiempoPromedio.toFixed(0)} min`}
            </span>
          </div>
          <span className="stat-tile-delta">
            {tiempoPromedio === null ? 'Aún sin decisiones registradas' : 'Desde la evaluación de la IA hasta la decisión'}
          </span>
        </div>

        <div className="stat-tile">
          <span className="stat-tile-label">
            Noticias/rumores ingeridos hoy <span className="panel-muestra">muestra</span>
          </span>
          <div className="stat-tile-body">
            <span className="stat-tile-value">184</span>
          </div>
          <span className="stat-tile-delta">GDELT 92 · X 54 · YouTube 38</span>
        </div>
      </div>

      <div className="dashboard-grid-2">
        <section className="panel">
          <h2>Menciones en conversación digital <span className="panel-muestra">muestra</span></h2>
          <span className="panel-subtitle">Últimas 24 horas — ilustrativo, pendiente del módulo de tendencias</span>
          <ChartMenciones />
        </section>

        <section className="panel">
          <h2>Ingesta por fuente <span className="panel-muestra">muestra</span></h2>
          <span className="panel-subtitle">Noticias y rumores capturados hoy — ilustrativo</span>
          <ChartFuentes />
        </section>
      </div>

      <div className="dashboard-grid-2">
        <section className="panel">
          <h2>Tendencias emergentes <span className="panel-muestra">muestra</span></h2>
          <span className="panel-subtitle">Ilustrativo — pendiente del módulo de detección de tendencias (E5)</span>
          <ul className="tendencias-lista">
            {TENDENCIAS_MUESTRA.map((t) => (
              <li key={t.tema} className="tendencia-item">
                <div className="tendencia-info">
                  <span className="tendencia-tema">{t.tema}</span>
                  <span className="tendencia-meta">
                    {t.volumen.toLocaleString('es-PE')} menciones · detectada {t.deteccion}
                  </span>
                </div>
                <span className="tendencia-velocidad">{t.velocidad}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="panel">
          <h2>Cola de validación</h2>
          <span className="panel-subtitle">Alertas reales a la espera de revisión periodística</span>

          {cargando && <p className="validacion-estado">Cargando…</p>}
          {!cargando && pendientes.length === 0 && (
            <p className="validacion-estado">No hay afirmaciones pendientes. Analiza una en la vista Validación.</p>
          )}

          <ul className="validacion-lista">
            {pendientes.slice(0, 5).map((e) => {
              return (
                <li key={e.afirmacion_id} className="validacion-item">
                  <div className="validacion-info">
                    <p className="validacion-afirmacion">{e.texto}</p>
                    <span className="validacion-fuente">
                      {e.fuente_origen ?? 'Ingreso manual'} · {formatearFecha(e.fecha_evaluacion)}
                    </span>
                  </div>
                  <div className="validacion-acciones">
                    <MedidorConfianza confianza={e.confianza_modelo} compacto />
                    <div className="validacion-botones">
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
      </div>
    </div>
  );
}
