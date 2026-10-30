import { useState, type FormEvent } from 'react';
import NewsCard from '../components/NewsCard/NewsCard';
import type { NoticiaFeed, PanelNoticias } from '../components/PanelFeed/PanelFeed';
import { formatearFecha } from '../utils/fecha';
import '../components/PanelFeed/PanelFeed.css';
import './Busqueda.css';

interface AfirmacionHistorial {
  afirmacion_id: number;
  titular: string;
  fuente_origen: string | null;
  url_original: string | null;
  fecha_evaluacion: string | null;
  senal: string;
  nivel_evidencia_disponible: string | null;
  decision: 'Aceptado' | 'Rechazado' | 'Observado' | null;
  comentarios: string | null;
  fecha_decision: string | null;
}

interface Resultados {
  consulta: string;
  noticias: NoticiaFeed[];
  historial: AfirmacionHistorial[];
}

interface Props {
  onIrAValidacion: () => void;
}

const API = '/api/v1';
const FILTROS_PANEL: { id: PanelNoticias | null; label: string }[] = [
  { id: null, label: 'Todo' },
  { id: 'peru', label: 'Perú' },
  { id: 'internacional', label: 'Internacional' },
];

export default function Busqueda({ onIrAValidacion }: Props) {
  const [consulta, setConsulta] = useState('');
  const [panel, setPanel] = useState<PanelNoticias | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultados, setResultados] = useState<Resultados | null>(null);
  const [validandoId, setValidandoId] = useState<number | null>(null);
  const [aviso, setAviso] = useState<{ tipo: 'ok' | 'error'; texto: string } | null>(null);

  const buscar = async (texto: string, filtro: PanelNoticias | null) => {
    if (texto.trim().length < 2) {
      setError('Escribe al menos una palabra clave.');
      return;
    }
    setBuscando(true);
    setError(null);
    setAviso(null);
    try {
      const params = new URLSearchParams({ q: texto.trim() });
      if (filtro) params.set('panel', filtro);
      const respuesta = await fetch(`${API}/busqueda?${params}`);
      if (!respuesta.ok) {
        const detalle = await respuesta.json().catch(() => null);
        throw new Error(typeof detalle?.detail === 'string' ? detalle.detail : 'No se pudo realizar la búsqueda.');
      }
      setResultados(await respuesta.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido al buscar.');
    } finally {
      setBuscando(false);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    buscar(consulta, panel);
  };

  const cambiarPanel = (filtro: PanelNoticias | null) => {
    setPanel(filtro);
    // El filtro solo afecta al feed, pero se rehace la búsqueda para no mostrar resultados viejos
    if (resultados) buscar(resultados.consulta, filtro);
  };

  const handleValidar = async (noticia: NoticiaFeed) => {
    setValidandoId(noticia.id);
    setAviso(null);
    try {
      const respuesta = await fetch(`${API}/noticias/feed/${noticia.id}/validar`, { method: 'POST' });
      if (!respuesta.ok) {
        const detalle = await respuesta.json().catch(() => null);
        throw new Error(detalle?.detail || 'No se pudo enviar a validación.');
      }
      setResultados((actuales) =>
        actuales && {
          ...actuales,
          noticias: actuales.noticias.map((n) => (n.id === noticia.id ? { ...n, en_validacion: true } : n)),
        },
      );
      setAviso({ tipo: 'ok', texto: `"${noticia.titular}" se envió a Validación.` });
    } catch (err) {
      setAviso({ tipo: 'error', texto: err instanceof Error ? err.message : 'Error al enviar a validación.' });
    } finally {
      setValidandoId(null);
    }
  };

  const total = resultados ? resultados.noticias.length + resultados.historial.length : 0;

  return (
    <div className="busqueda-view">
      <div className="busqueda-header">
        <h1>Búsqueda</h1>
        <p>
          Rastrea un tema o rumor por palabras clave en el feed de las últimas 24 h y en lo que SIVAT ya
          evaluó. No importan las mayúsculas ni las tildes.
        </p>
      </div>

      <form className="busqueda-form" onSubmit={handleSubmit} role="search">
        <input
          type="search"
          value={consulta}
          onChange={(e) => setConsulta(e.target.value)}
          placeholder="Ej.: vacancia presidencial, bono, vacuna…"
          aria-label="Palabras clave"
          autoFocus
        />
        <button type="submit" disabled={buscando}>
          {buscando ? 'Buscando…' : 'Buscar'}
        </button>
      </form>

      <div className="busqueda-filtros" role="group" aria-label="Panel de noticias">
        {FILTROS_PANEL.map((f) => (
          <button
            key={f.label}
            type="button"
            className={panel === f.id ? 'is-activo' : ''}
            aria-pressed={panel === f.id}
            onClick={() => cambiarPanel(f.id)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && <p className="busqueda-error">{error}</p>}

      {aviso && (
        <div className={`panel-feed-aviso is-${aviso.tipo}`} role="status">
          <span>{aviso.texto}</span>
          {aviso.tipo === 'ok' && (
            <button type="button" onClick={onIrAValidacion}>
              Ir a Validación →
            </button>
          )}
        </div>
      )}

      {resultados && !buscando && (
        <p className="busqueda-resumen" role="status">
          {total === 0
            ? `Sin resultados para «${resultados.consulta}». Prueba con menos palabras.`
            : `${total} resultado(s) para «${resultados.consulta}».`}
        </p>
      )}

      {resultados && resultados.noticias.length > 0 && (
        <section className="busqueda-seccion">
          <h2>
            Noticias del feed <span>{resultados.noticias.length}</span>
          </h2>
          <p className="busqueda-seccion-nota">Capturadas en las últimas 24 h. Envíalas a Validación desde la tarjeta.</p>
          <div className="panel-feed-grid">
            {resultados.noticias.map((noticia) => (
              <NewsCard
                key={noticia.id}
                noticia={noticia}
                validando={validandoId === noticia.id}
                onValidar={handleValidar}
              />
            ))}
          </div>
        </section>
      )}

      {resultados && resultados.historial.length > 0 && (
        <section className="busqueda-seccion">
          <h2>
            Ya evaluado en SIVAT <span>{resultados.historial.length}</span>
          </h2>
          <p className="busqueda-seccion-nota">Afirmaciones que pasaron por Validación, con la decisión del periodista.</p>
          <ul className="busqueda-lista">
            {resultados.historial.map((h) => (
              <li key={h.afirmacion_id}>
                <div>
                  <span className="busqueda-titulo">{h.titular}</span>
                  <span className="busqueda-meta">
                    {h.fuente_origen ?? 'Ingreso manual'} · evaluada {formatearFecha(h.fecha_evaluacion)}
                    {h.url_original && (
                      <>
                        {' · '}
                        <a href={h.url_original} target="_blank" rel="noopener noreferrer">
                          Ver fuente ↗
                        </a>
                      </>
                    )}
                  </span>
                </div>
                <span className={`busqueda-decision ${h.decision ? `decision-${h.decision.toLowerCase()}` : ''}`}>
                  {h.decision ? `${h.decision} · ${formatearFecha(h.fecha_decision)}` : 'Pendiente de validación'}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
