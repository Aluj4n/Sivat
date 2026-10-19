import { useCallback, useEffect, useState } from 'react';
import type { NoticiaFeed, PanelNoticias } from '../components/PanelFeed/PanelFeed';
import './Tendencias.css';

type Prioridad = 'Alta' | 'Media' | 'Baja';

interface PuntoHistorial {
  ejecucion: string;
  volumen: number;
}

interface Tendencia {
  id: number;
  grupo_id: string;
  terminos: string[];
  titular_representativo: string;
  volumen: number;
  fuentes: number;
  redes: number;
  medios_reconocidos: number;
  recientes: number;
  velocidad: number;
  prioridad: Prioridad;
  motivos: string[];
  verificacion: { origen: string; titulo: string; url: string | null; calificacion: string | null } | null;
  primera_vez: string;
  historial: PuntoHistorial[];
}

interface Props {
  onIrAValidacion: () => void;
}

const API = '/api/v1';
const REFRESCO_MS = 120_000; // el backend recalcula cada 15 min; se consulta seguido para no esperar
const PANELES: { id: PanelNoticias; label: string }[] = [
  { id: 'peru', label: 'Perú' },
  { id: 'internacional', label: 'Internacional' },
];

function haceCuanto(iso: string | null): string {
  if (!iso) return '';
  const minutos = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutos < 1) return 'hace instantes';
  if (minutos < 60) return `hace ${minutos} min`;
  const horas = Math.round(minutos / 60);
  return horas < 24 ? `hace ${horas} h` : `hace ${Math.round(horas / 24)} d`;
}

/** Línea de volumen del tema en cada ciclo de las últimas 24 h (una serie: sin leyenda). */
function Evolucion({ puntos }: { puntos: PuntoHistorial[] }) {
  if (puntos.length < 2) {
    return <span className="tendencia-evolucion-vacia">Primer ciclo</span>;
  }
  const ancho = 120;
  const alto = 32;
  const max = Math.max(...puntos.map((p) => p.volumen), 1);
  const coordenadas = puntos.map((p, i) => {
    const x = (i / (puntos.length - 1)) * (ancho - 4) + 2;
    const y = alto - 3 - (p.volumen / max) * (alto - 6);
    return [x, y] as const;
  });
  const ultimo = coordenadas[coordenadas.length - 1];
  const resumen = puntos.map((p) => p.volumen).join(' → ');
  return (
    <svg className="tendencia-evolucion" width={ancho} height={alto} role="img"
         aria-label={`Publicaciones por ciclo: ${resumen}`}>
      <title>{`Publicaciones por ciclo (últimas 24 h): ${resumen}`}</title>
      <polyline points={coordenadas.map(([x, y]) => `${x},${y}`).join(' ')} />
      <circle cx={ultimo[0]} cy={ultimo[1]} r={3} />
    </svg>
  );
}

export default function Tendencias({ onIrAValidacion }: Props) {
  const [panel, setPanel] = useState<PanelNoticias>('peru');
  const [verBajas, setVerBajas] = useState(false);
  const [tendencias, setTendencias] = useState<Tendencia[]>([]);
  const [ejecucion, setEjecucion] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [abierta, setAbierta] = useState<number | null>(null);
  const [noticias, setNoticias] = useState<Record<number, NoticiaFeed[]>>({});
  const [validandoId, setValidandoId] = useState<number | null>(null);
  const [aviso, setAviso] = useState<{ tipo: 'ok' | 'error'; texto: string } | null>(null);

  const cargar = useCallback(async () => {
    try {
      const respuesta = await fetch(`${API}/tendencias?panel=${panel}`);
      if (!respuesta.ok) throw new Error();
      const datos = await respuesta.json();
      setTendencias(datos.tendencias);
      setEjecucion(datos.ejecucion);
      setError(null);
    } catch {
      setError('No se pudieron cargar las tendencias.');
    } finally {
      setCargando(false);
    }
  }, [panel]);

  useEffect(() => {
    cargar();
    const intervalo = setInterval(cargar, REFRESCO_MS);
    return () => clearInterval(intervalo);
  }, [cargar]);

  const cambiarPanel = (nuevo: PanelNoticias) => {
    setPanel(nuevo);
    setCargando(true);
    setAbierta(null);
  };

  const alternarNoticias = async (tendencia: Tendencia) => {
    if (abierta === tendencia.id) {
      setAbierta(null);
      return;
    }
    setAbierta(tendencia.id);
    if (noticias[tendencia.id]) return;
    try {
      const respuesta = await fetch(`${API}/tendencias/${tendencia.id}/noticias`);
      if (!respuesta.ok) throw new Error();
      const lista: NoticiaFeed[] = await respuesta.json();
      setNoticias((actuales) => ({ ...actuales, [tendencia.id]: lista }));
    } catch {
      setNoticias((actuales) => ({ ...actuales, [tendencia.id]: [] }));
    }
  };

  const validar = async (tendenciaId: number, noticia: NoticiaFeed) => {
    setValidandoId(noticia.id);
    setAviso(null);
    try {
      const respuesta = await fetch(`${API}/noticias/feed/${noticia.id}/validar`, { method: 'POST' });
      if (!respuesta.ok) {
        const detalle = await respuesta.json().catch(() => null);
        throw new Error(detalle?.detail || 'No se pudo enviar a validación.');
      }
      setNoticias((actuales) => ({
        ...actuales,
        [tendenciaId]: actuales[tendenciaId].map((n) => (n.id === noticia.id ? { ...n, en_validacion: true } : n)),
      }));
      setAviso({ tipo: 'ok', texto: `"${noticia.titular}" se envió a Validación.` });
    } catch (err) {
      setAviso({ tipo: 'error', texto: err instanceof Error ? err.message : 'Error al enviar a validación.' });
    } finally {
      setValidandoId(null);
    }
  };

  const conteo = (p: Prioridad) => tendencias.filter((t) => t.prioridad === p).length;
  const visibles = verBajas ? tendencias : tendencias.filter((t) => t.prioridad !== 'Baja');

  return (
    <div className="tendencias-view">
      <div className="tendencias-header">
        <div>
          <h1>Tendencias</h1>
          <p>
            Temas que agrupa la IA en el feed de las últimas 24 h, ordenados por <strong>prioridad de verificación</strong>:
            qué conviene revisar primero. No indica si un tema es verdadero o falso; eso lo decide el periodista.
          </p>
        </div>
        <div className="tendencias-paneles" role="tablist" aria-label="Panel">
          {PANELES.map((p) => (
            <button key={p.id} type="button" role="tab" aria-selected={panel === p.id}
                    className={panel === p.id ? 'is-activo' : ''} onClick={() => cambiarPanel(p.id)}>
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div className="tendencias-resumen">
        {(['Alta', 'Media', 'Baja'] as Prioridad[]).map((p) => (
          <div key={p} className={`tendencias-resumen-item prioridad-${p.toLowerCase()}`}>
            <span className="tendencias-resumen-valor">{conteo(p)}</span>
            <span className="tendencias-resumen-label">Prioridad {p.toLowerCase()}</span>
          </div>
        ))}
        <div className="tendencias-resumen-meta">
          {ejecucion ? `Actualizado ${haceCuanto(ejecucion)} · se recalcula cada 15 min` : 'Sin cálculo todavía'}
          <label className="tendencias-ver-bajas">
            <input type="checkbox" checked={verBajas} onChange={(e) => setVerBajas(e.target.checked)} />
            Mostrar prioridad baja
          </label>
        </div>
      </div>

      {aviso && (
        <div className={`tendencias-aviso is-${aviso.tipo}`} role="status">
          <span>{aviso.texto}</span>
          {aviso.tipo === 'ok' && (
            <button type="button" onClick={onIrAValidacion}>Ir a Validación →</button>
          )}
        </div>
      )}

      {cargando && <p className="tendencias-estado">Cargando tendencias…</p>}
      {!cargando && error && <p className="tendencias-estado is-error">{error}</p>}
      {!cargando && !error && visibles.length === 0 && (
        <p className="tendencias-estado">
          {ejecucion
            ? 'No hay temas con prioridad alta o media en este momento. Activa "Mostrar prioridad baja" para ver todos.'
            : 'El primer cálculo de tendencias aparece unos minutos después de iniciar el sistema.'}
        </p>
      )}

      <ol className="tendencias-lista">
        {visibles.map((t) => (
          <li key={t.id} className="tendencia">
            <div className="tendencia-cabecera">
              <span className={`tendencia-prioridad prioridad-${t.prioridad.toLowerCase()}`}>
                Prioridad {t.prioridad.toLowerCase()}
              </span>
              <div className="tendencia-terminos">
                {t.terminos.map((termino) => <span key={termino}>{termino}</span>)}
              </div>
              <Evolucion puntos={t.historial} />
            </div>

            <h2 className="tendencia-titular">{t.titular_representativo}</h2>

            <dl className="tendencia-datos">
              <div><dt>Publicaciones</dt><dd>{t.volumen}</dd></div>
              <div><dt>Últimas 3 h</dt><dd>{t.recientes}</dd></div>
              <div><dt>Fuentes</dt><dd>{t.fuentes}</dd></div>
              <div><dt>En redes</dt><dd>{t.redes}</dd></div>
              <div><dt>Medios reconocidos</dt><dd>{t.medios_reconocidos}</dd></div>
              <div><dt>Detectado</dt><dd>{haceCuanto(t.primera_vez)}</dd></div>
            </dl>

            <ul className="tendencia-motivos">
              {t.motivos.map((m) => <li key={m}>{m}</li>)}
            </ul>

            {t.verificacion && (
              <p className="tendencia-verificacion">
                Verificación relacionada ({t.verificacion.origen}
                {t.verificacion.calificacion ? ` · ${t.verificacion.calificacion}` : ''}):{' '}
                {t.verificacion.url ? (
                  <a href={t.verificacion.url} target="_blank" rel="noopener noreferrer">{t.verificacion.titulo}</a>
                ) : t.verificacion.titulo}
              </p>
            )}

            <button type="button" className="tendencia-ver" aria-expanded={abierta === t.id}
                    onClick={() => alternarNoticias(t)}>
              {abierta === t.id ? 'Ocultar publicaciones' : `Ver publicaciones (${t.volumen})`}
            </button>

            {abierta === t.id && (
              <ul className="tendencia-noticias">
                {!noticias[t.id] && <li className="tendencia-noticias-estado">Cargando…</li>}
                {noticias[t.id]?.length === 0 && (
                  <li className="tendencia-noticias-estado">Estas publicaciones ya salieron del feed (24 h).</li>
                )}
                {noticias[t.id]?.map((n) => (
                  <li key={n.id}>
                    <div className="tendencia-noticia-texto">
                      <span className="tendencia-noticia-fuente">{n.fuente_origen} · {haceCuanto(n.fecha_publicacion)}</span>
                      {n.url_original ? (
                        <a href={n.url_original} target="_blank" rel="noopener noreferrer">{n.titular}</a>
                      ) : <span>{n.titular}</span>}
                    </div>
                    {n.en_validacion ? (
                      <span className="tendencia-noticia-hecha">✓ En validación</span>
                    ) : (
                      <button type="button" disabled={validandoId === n.id} onClick={() => validar(t.id, n)}>
                        {validandoId === n.id ? 'Enviando…' : 'Validar'}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
