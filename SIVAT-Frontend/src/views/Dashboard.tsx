import './Dashboard.css';

// Vista de avance visual del Dashboard principal de SIVAT. Todos los datos son
// estáticos (mock) — representan cómo se verá el panel una vez conectado a los
// módulos de tendencias, RAG y scoring explicable descritos en el Business Case
// y el Acta de Alcance (E5, E6, E7). Ningún dato aquí es real ni funcional.

interface StatTile {
  label: string;
  value: string;
  delta?: string;
  deltaPositivo?: boolean;
  sparkline: number[];
}

const KPIS: StatTile[] = [
  {
    label: 'Tiempo promedio de verificación',
    value: '0 min',
    delta: '...',
    deltaPositivo: true,
    sparkline: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  },
  {
    label: 'Tendencias activas detectadas',
    value: '0',
    delta: '...',
    deltaPositivo: true,
    sparkline: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  },
  {
    label: 'Alertas por validar',
    value: '0',
    delta: '...',
    sparkline: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  },
  {
    label: 'Noticias/rumores ingeridos hoy',
    value: '0',
    delta: '...',
    sparkline: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  },
];

const MENCIONES_24H = [
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0,
];

const INGESTA_POR_FUENTE = [
  { fuente: 'GDELT', valor: 0, color: 'var(--series-1)' },
  { fuente: 'X (Twitter)', valor: 0, color: 'var(--series-2)' },
  { fuente: 'YouTube', valor: 0, color: 'var(--series-3)' },
];

interface Tendencia {
  tema: string;
  volumen: number;
  velocidad: string;
  deteccion: string;
}

const TENDENCIAS: Tendencia[] = [
  { tema: '...', volumen: 0, velocidad: '+0%', deteccion: '...' },
  { tema: '...', volumen: 0, velocidad: '+0%', deteccion: '...' },
  { tema: '...', volumen: 0, velocidad: '+0%', deteccion: '...' },
  { tema: '...', volumen: 0, velocidad: '+0%', deteccion: '...' },
];

type NivelConfianza = 'Alto' | 'Medio' | 'Bajo';

interface AlertaValidacion {
  afirmacion: string;
  fuente: string;
  nivel: NivelConfianza;
}

const COLA_VALIDACION: AlertaValidacion[] = [
  {
    afirmacion: '"..."',
    fuente: '...',
    nivel: 'Medio',
  },
  {
    afirmacion: '"..."',
    fuente: '...',
    nivel: 'Bajo',
  },
  {
    afirmacion: '"..."',
    fuente: '...',
    nivel: 'Alto',
  },
  {
    afirmacion: '"..."',
    fuente: '...',
    nivel: 'Bajo',
  },
];

const NIVEL_CONFIANZA_COLOR: Record<NivelConfianza, string> = {
  Alto: 'var(--seq-500)',
  Medio: 'var(--seq-350)',
  Bajo: 'var(--seq-200)',
};

function Sparkline({ datos }: { datos: number[] }) {
  const w = 72;
  const h = 24;
  const min = Math.min(...datos);
  const max = Math.max(...datos);
  const rango = max - min || 1;
  const puntos = datos.map((v, i) => {
    const x = (i / (datos.length - 1)) * w;
    const y = h - ((v - min) / rango) * h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const ultimoX = w;
  const ultimoY = h - ((datos[datos.length - 1] - min) / rango) * h;

  return (
    <svg width={w} height={h} className="sparkline" aria-hidden="true">
      <polyline points={puntos.join(' ')} className="sparkline-line" />
      <circle cx={ultimoX} cy={ultimoY} r="2.5" className="sparkline-dot" />
    </svg>
  );
}

function ChartMenciones() {
  const w = 640;
  const h = 200;
  const padLeft = 40;
  const padBottom = 24;
  const padTop = 12;
  const innerW = w - padLeft - 12;
  const innerH = h - padTop - padBottom;

  const max = Math.max(...MENCIONES_24H);
  const min = 0;
  const rango = max - min || 1;

  const puntos = MENCIONES_24H.map((v, i) => {
    const x = padLeft + (i / (MENCIONES_24H.length - 1)) * innerW;
    const y = padTop + innerH - ((v - min) / rango) * innerH;
    return { x, y, v };
  });

  const linePath = puntos.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  const areaPath = `${linePath} L${puntos[puntos.length - 1].x.toFixed(1)},${padTop + innerH} L${puntos[0].x.toFixed(1)},${padTop + innerH} Z`;

  const ticksY = [0, Math.round(max / 2), max];
  const ultimo = puntos[puntos.length - 1];

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="line-chart" role="img" aria-label="Menciones en conversación digital, últimas 24 horas">
      {ticksY.map((t) => {
        const y = padTop + innerH - ((t - min) / rango) * innerH;
        return (
          <g key={t}>
            <line x1={padLeft} y1={y} x2={w - 12} y2={y} className="chart-gridline" />
            <text x={padLeft - 8} y={y + 3} className="chart-axis-label" textAnchor="end">
              {t}
            </text>
          </g>
        );
      })}

      <path d={areaPath} className="chart-area" />
      <path d={linePath} className="chart-line" />
      <circle cx={ultimo.x} cy={ultimo.y} r="4" className="chart-end-dot" />
      <text x={ultimo.x} y={ultimo.y - 10} className="chart-end-label" textAnchor="end">
        {ultimo.v}
      </text>

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
  const maxVal = Math.max(...INGESTA_POR_FUENTE.map((f) => f.valor));
  const innerW = w - padLeft - padRight;
  const h = INGESTA_POR_FUENTE.length * (barH + gap);

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="bar-chart" role="img" aria-label="Noticias ingeridas hoy por fuente">
      {INGESTA_POR_FUENTE.map((f, i) => {
        const y = i * (barH + gap) + gap / 2;
        const width = (f.valor / maxVal) * innerW;
        return (
          <g key={f.fuente}>
            <text x={padLeft - 12} y={y + barH / 2 + 4} className="chart-axis-label" textAnchor="end">
              {f.fuente}
            </text>
            <rect x={padLeft} y={y} width={innerW} height={barH} className="bar-track" rx="4" />
            <rect x={padLeft} y={y} width={width} height={barH} rx="4" fill={f.color} />
            <text x={padLeft + width + 8} y={y + barH / 2 + 4} className="chart-value-label">
              {f.valor}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function Dashboard() {
  return (
    <div className="dashboard-view">
      <div className="dashboard-header">
        <div>
          <h1>Dashboard</h1>
        </div>
        <div className="dashboard-flujo" title="Principio de supervisión humana, transversal a todo SIVAT">
          IA analiza → IA recomienda → periodista valida → editor decide
        </div>
      </div>


      <div className="dashboard-kpis">
        {KPIS.map((kpi) => (
          <div className="stat-tile" key={kpi.label}>
            <span className="stat-tile-label">{kpi.label}</span>
            <div className="stat-tile-body">
              <span className="stat-tile-value">{kpi.value}</span>
              <Sparkline datos={kpi.sparkline} />
            </div>
            {kpi.delta && (
              <span className={`stat-tile-delta ${kpi.deltaPositivo ? 'is-positivo' : ''}`}>{kpi.delta}</span>
            )}
          </div>
        ))}
      </div>

      <div className="dashboard-grid-2">
        <section className="panel">
          <h2>Menciones en conversación digital</h2>
          <span className="panel-subtitle">Últimas 24 horas, todas las fuentes</span>
          <ChartMenciones />
        </section>

        <section className="panel">
          <h2>Ingesta por fuente</h2>
          <span className="panel-subtitle">Noticias y rumores capturados hoy</span>
          <ChartFuentes />
        </section>
      </div>

      <div className="dashboard-grid-2">
        <section className="panel">
          <h2>Tendencias emergentes</h2>
          <span className="panel-subtitle">Detectadas por volumen y velocidad de crecimiento</span>
          <ul className="tendencias-lista">
            {TENDENCIAS.map((t) => (
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
          <span className="panel-subtitle">Alertas recientes a la espera de revisión periodística</span>
          <ul className="validacion-lista">
            {COLA_VALIDACION.map((a, i) => (
              <li key={i} className="validacion-item">
                <div className="validacion-info">
                  <p className="validacion-afirmacion">{a.afirmacion}</p>
                  <span className="validacion-fuente">{a.fuente}</span>
                </div>
                <div className="validacion-acciones">
                  <span className="nivel-confianza">
                    <span
                      className="nivel-confianza-dot"
                      style={{ backgroundColor: NIVEL_CONFIANZA_COLOR[a.nivel] }}
                    />
                    Confianza: {a.nivel}
                  </span>
                  <div className="validacion-botones">
                    <button type="button" disabled title="Se habilitará con el módulo de verificación">
                      Aceptar
                    </button>
                    <button type="button" disabled title="Se habilitará con el módulo de verificación">
                      Observar
                    </button>
                    <button type="button" disabled title="Se habilitará con el módulo de verificación">
                      Rechazar
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
