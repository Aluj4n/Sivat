import { useCallback, useEffect, useState } from 'react';
import MedidorConfianza from '../components/MedidorConfianza/MedidorConfianza';
import type { PanelNoticias } from '../components/PanelFeed/PanelFeed';
import { titularDe } from '../utils/texto';
import './Dashboard.css';

// Dashboard principal de SIVAT: todo con datos reales del sistema.
//   - Resumen (feed de 24 h y flujo editorial): GET /api/v1/dashboard/resumen
//   - Tendencias: GET /api/v1/tendencias (Módulo de Tendencias)
//   - Cola de validación: GET/POST /api/v1/verificacion

const API = '/api/v1';
const REFRESCO_MS = 60_000;
const TENDENCIAS_A_MOSTRAR = 5;
const COLA_A_MOSTRAR = 5;

type Decision = 'Aceptado' | 'Rechazado' | 'Observado';

interface DecisionInfo {
  decision_periodista: Decision;
  comentarios: string | null;
  fecha_decision: string;
}

interface Evaluacion {
  afirmacion_id: number;
  texto: string;
  confianza_modelo: number | null;
  palabras_analizadas: number;
  fuente_origen: string | null;
  fecha_evaluacion: string;
  decision?: DecisionInfo | null;
}

interface Resumen {
  feed: {
    horas: number;
    total: number;
    por_panel: Record<PanelNoticias, number>;
    por_tipo: ({ tipo: string } & Record<PanelNoticias, number>)[];
  };
  afirmaciones: {
    evaluadas: number;
    pendientes: number;
    decisiones: Record<Decision, number>;
  };
}

interface Tendencia {
  id: number;
  terminos: string[];
  titular_representativo: string;
  volumen: number;
  recientes: number;
  fuentes: number;
  prioridad: 'Alta' | 'Media' | 'Baja';
}

interface Props {
  onNavegar: (vista: 'tendencias' | 'validacion') => void;
}

function formatearFecha(iso?: string): string {
  if (!iso) return '';
  return new Date(iso).toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short' });
}

const numero = (n: number) => n.toLocaleString('es-PE');

/** Barras apiladas por tipo de fuente: Perú e Internacional (2 series, orden fijo de color). */
function ChartIngesta({ datos }: { datos: Resumen['feed']['por_tipo'] }) {
  const w = 520;
  const barH = 22;
  const gap = 18;
  const padLeft = 96;
  const padRight = 64;
  const innerW = w - padLeft - padRight;
  const max = Math.max(...datos.map((d) => d.peru + d.internacional), 1);
  const h = datos.length * (barH + gap);

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="bar-chart" role="img"
         aria-label="Noticias capturadas por tipo de fuente, Perú e Internacional">
      {datos.map((d, i) => {
        const y = i * (barH + gap) + gap / 2;
        const anchoPeru = (d.peru / max) * innerW;
        const anchoIntl = (d.internacional / max) * innerW;
        // 2px de superficie entre los dos segmentos para que se lean como piezas separadas
        const separacion = anchoPeru > 0 && anchoIntl > 0 ? 2 : 0;
        return (
          <g key={d.tipo}>
            <text x={padLeft - 12} y={y + barH / 2 + 4} className="chart-axis-label" textAnchor="end">{d.tipo}</text>
            <rect x={padLeft} y={y} width={innerW} height={barH} className="bar-track" rx="4" />
            {anchoPeru > 0 && (
              <rect x={padLeft} y={y} width={anchoPeru} height={barH} rx="4" className="serie-peru">
                <title>{`${d.tipo} · Perú: ${numero(d.peru)}`}</title>
              </rect>
            )}
            {anchoIntl > 0 && (
              <rect x={padLeft + anchoPeru + separacion} y={y} width={Math.max(anchoIntl - separacion, 1)} height={barH}
                    rx="4" className="serie-internacional">
                <title>{`${d.tipo} · Internacional: ${numero(d.internacional)}`}</title>
              </rect>
            )}
            <text x={padLeft + anchoPeru + anchoIntl + 8} y={y + barH / 2 + 4} className="chart-value-label">
              {numero(d.peru + d.internacional)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/** Una barra por estado del flujo editorial (una sola serie: magnitud, sin verde/rojo). */
function ChartDecisiones({ afirmaciones }: { afirmaciones: Resumen['afirmaciones'] }) {
  const filas = [
    { estado: 'Pendientes', valor: afirmaciones.pendientes, pendiente: true },
    { estado: 'Aceptadas', valor: afirmaciones.decisiones.Aceptado, pendiente: false },
    { estado: 'Observadas', valor: afirmaciones.decisiones.Observado, pendiente: false },
    { estado: 'Rechazadas', valor: afirmaciones.decisiones.Rechazado, pendiente: false },
  ];
  const w = 520;
  const barH = 22;
  const gap = 18;
  const padLeft = 96;
  const padRight = 48;
  const innerW = w - padLeft - padRight;
  const max = Math.max(...filas.map((f) => f.valor), 1);
  const h = filas.length * (barH + gap);

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="bar-chart" role="img" aria-label="Estado editorial de las afirmaciones">
      {filas.map((f, i) => {
        const y = i * (barH + gap) + gap / 2;
        const ancho = (f.valor / max) * innerW;
        return (
          <g key={f.estado}>
            <text x={padLeft - 12} y={y + barH / 2 + 4} className="chart-axis-label" textAnchor="end">{f.estado}</text>
            <rect x={padLeft} y={y} width={innerW} height={barH} className="bar-track" rx="4" />
            {ancho > 0 && (
              <rect x={padLeft} y={y} width={ancho} height={barH} rx="4"
                    className={f.pendiente ? 'serie-pendiente' : 'serie-decision'}>
                <title>{`${f.estado}: ${f.valor}`}</title>
              </rect>
            )}
            <text x={padLeft + ancho + 8} y={y + barH / 2 + 4} className="chart-value-label">{f.valor}</text>
          </g>
        );
      })}
    </svg>
  );
}

export default function Dashboard({ onNavegar }: Props) {
  const [resumen, setResumen] = useState<Resumen | null>(null);
  const [evaluaciones, setEvaluaciones] = useState<Evaluacion[]>([]);
  const [panelTendencias, setPanelTendencias] = useState<PanelNoticias>('peru');
  const [tendencias, setTendencias] = useState<Tendencia[] | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [decidiendoId, setDecidiendoId] = useState<number | null>(null);

  const cargar = useCallback(async () => {
    try {
      const [respuestaResumen, respuestaCola] = await Promise.all([
        fetch(`${API}/dashboard/resumen`),
        fetch(`${API}/verificacion/recientes?limit=50`),
      ]);
      if (!respuestaResumen.ok || !respuestaCola.ok) throw new Error();
      setResumen(await respuestaResumen.json());
      setEvaluaciones(await respuestaCola.json());
      setError(null);
    } catch {
      setError('No se pudieron cargar los datos del Dashboard.');
    } finally {
      setCargando(false);
    }
  }, []);

  const cargarTendencias = useCallback(async () => {
    try {
      const respuesta = await fetch(`${API}/tendencias?panel=${panelTendencias}`);
      if (!respuesta.ok) throw new Error();
      const datos = await respuesta.json();
      setTendencias(datos.tendencias.slice(0, TENDENCIAS_A_MOSTRAR));
    } catch {
      setTendencias([]);
    }
  }, [panelTendencias]);

  useEffect(() => {
    cargar();
    const intervalo = setInterval(cargar, REFRESCO_MS);
    return () => clearInterval(intervalo);
  }, [cargar]);

  useEffect(() => {
    cargarTendencias();
    const intervalo = setInterval(cargarTendencias, REFRESCO_MS);
    return () => clearInterval(intervalo);
  }, [cargarTendencias]);

  const handleDecision = async (afirmacionId: number, decision: Decision) => {
    setDecidiendoId(afirmacionId);
    try {
      const response = await fetch(`${API}/verificacion/${afirmacionId}/decision`, {
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
  const valor = (n: number | undefined) => (cargando || n === undefined ? '—' : numero(n));

  return (
    <div className="dashboard-view">
      <div className="dashboard-header">
        <div>
          <h1>Dashboard</h1>
          <p>Vista general de SIVAT: lo que entra al sistema, lo que está creciendo y lo que espera revisión.</p>
        </div>
        <div className="dashboard-flujo" title="Principio de supervisión humana, transversal a todo SIVAT">
          IA analiza → IA recomienda → periodista valida → editor decide
        </div>
      </div>

      {error && <p className="dashboard-error">{error}</p>}

      <div className="dashboard-kpis">
        <div className="stat-tile">
          <span className="stat-tile-label">Alertas por validar</span>
          <div className="stat-tile-body">
            <span className="stat-tile-value">{valor(resumen?.afirmaciones.pendientes)}</span>
          </div>
          <span className="stat-tile-delta">Afirmaciones analizadas sin decisión editorial</span>
        </div>

        <div className="stat-tile">
          <span className="stat-tile-label">Noticias capturadas ({resumen?.feed.horas ?? 24} h)</span>
          <div className="stat-tile-body">
            <span className="stat-tile-value">{valor(resumen?.feed.total)}</span>
          </div>
          <span className="stat-tile-delta">
            {resumen
              ? `Perú ${numero(resumen.feed.por_panel.peru)} · Internacional ${numero(resumen.feed.por_panel.internacional)}`
              : 'Perú e Internacional'}
          </span>
        </div>

        <div className="stat-tile">
          <span className="stat-tile-label">Afirmaciones evaluadas</span>
          <div className="stat-tile-body">
            <span className="stat-tile-value">{valor(resumen?.afirmaciones.evaluadas)}</span>
          </div>
          <span className="stat-tile-delta">Total analizado por la IA (modelo y evidencia)</span>
        </div>
      </div>

      <div className="dashboard-grid-2">
        <section className="panel">
          <h2>Decisiones editoriales</h2>
          <span className="panel-subtitle">Estado de las afirmaciones analizadas: la IA recomienda, la persona decide</span>
          {resumen ? <ChartDecisiones afirmaciones={resumen.afirmaciones} /> : <p className="validacion-estado">Cargando…</p>}
        </section>

        <section className="panel">
          <h2>Ingesta por fuente</h2>
          <span className="panel-subtitle">Noticias y publicaciones capturadas en las últimas {resumen?.feed.horas ?? 24} h</span>
          <div className="chart-leyenda" aria-hidden="true">
            <span><i className="serie-peru" /> Perú</span>
            <span><i className="serie-internacional" /> Internacional</span>
          </div>
          {resumen ? <ChartIngesta datos={resumen.feed.por_tipo} /> : <p className="validacion-estado">Cargando…</p>}
        </section>
      </div>

      <div className="dashboard-grid-2">
        <section className="panel">
          <div className="panel-cabecera">
            <div>
              <h2>Tendencias emergentes</h2>
              <span className="panel-subtitle">Temas ordenados por prioridad de verificación, no por veracidad</span>
            </div>
            <div className="dashboard-selector" role="tablist" aria-label="Panel de tendencias">
              {(['peru', 'internacional'] as PanelNoticias[]).map((p) => (
                <button key={p} type="button" role="tab" aria-selected={panelTendencias === p}
                        className={panelTendencias === p ? 'is-activo' : ''} onClick={() => setPanelTendencias(p)}>
                  {p === 'peru' ? 'Perú' : 'Internacional'}
                </button>
              ))}
            </div>
          </div>

          {tendencias === null && <p className="validacion-estado">Cargando…</p>}
          {tendencias?.length === 0 && (
            <p className="validacion-estado">Aún no hay tendencias calculadas para este panel.</p>
          )}
          <ul className="dashboard-tendencias">
            {tendencias?.map((t) => (
              <li key={t.id}>
                <div className="dashboard-tendencia-info">
                  <span className="dashboard-tendencia-titular">{t.titular_representativo}</span>
                  <span className="dashboard-tendencia-meta">
                    {t.terminos.slice(0, 3).join(' · ')} — {numero(t.volumen)} publicaciones de {t.fuentes} fuentes
                  </span>
                </div>
                <div className="dashboard-tendencia-lado">
                  <span className={`dashboard-prioridad prioridad-${t.prioridad.toLowerCase()}`}>{t.prioridad}</span>
                  <span className="dashboard-tendencia-recientes">+{t.recientes} en 3 h</span>
                </div>
              </li>
            ))}
          </ul>
          <button type="button" className="dashboard-ver-mas" onClick={() => onNavegar('tendencias')}>
            Ver todas las tendencias →
          </button>
        </section>

        <section className="panel">
          <h2>Cola de validación</h2>
          <span className="panel-subtitle">Afirmaciones analizadas a la espera de decisión periodística</span>

          {cargando && <p className="validacion-estado">Cargando…</p>}
          {!cargando && pendientes.length === 0 && (
            <p className="validacion-estado">No hay afirmaciones pendientes. Envía una noticia a validar desde los paneles.</p>
          )}

          <ul className="validacion-lista">
            {pendientes.slice(0, COLA_A_MOSTRAR).map((e) => (
              <li key={e.afirmacion_id} className="validacion-item">
                <div className="validacion-info">
                  <p className="validacion-afirmacion">{titularDe(e.texto)}</p>
                  <span className="validacion-fuente">
                    {e.fuente_origen ?? 'Ingreso manual'} · {formatearFecha(e.fecha_evaluacion)}
                  </span>
                </div>
                <div className="validacion-acciones">
                  <MedidorConfianza confianza={e.confianza_modelo} palabras={e.palabras_analizadas} compacto />
                  <div className="validacion-botones">
                    {(['Aceptado', 'Observado', 'Rechazado'] as Decision[]).map((decision) => (
                      <button key={decision} type="button" disabled={decidiendoId === e.afirmacion_id}
                              onClick={() => handleDecision(e.afirmacion_id, decision)}>
                        {decision === 'Aceptado' ? 'Aceptar' : decision === 'Observado' ? 'Observar' : 'Rechazar'}
                      </button>
                    ))}
                  </div>
                </div>
              </li>
            ))}
          </ul>
          {(resumen?.afirmaciones.pendientes ?? 0) > COLA_A_MOSTRAR && (
            <button type="button" className="dashboard-ver-mas" onClick={() => onNavegar('validacion')}>
              Ver las {resumen?.afirmaciones.pendientes} pendientes en Validación →
            </button>
          )}
        </section>
      </div>
    </div>
  );
}
