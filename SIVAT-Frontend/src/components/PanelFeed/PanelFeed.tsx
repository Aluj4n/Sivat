import { useCallback, useEffect, useState } from 'react';
import NewsCard from '../NewsCard/NewsCard';
import './PanelFeed.css';

export type PanelNoticias = 'peru' | 'internacional';

export interface NoticiaFeed {
  id: number;
  titular: string;
  imagen_url: string | null;
  url_original: string | null;
  fuente_origen: string;
  pais: string | null;
  categoria: string;
  panel: PanelNoticias;
  fecha_publicacion: string | null;
  en_validacion: boolean;
  afirmacion_id: number | null;
}

interface Props {
  panel: PanelNoticias;
  titulo: string;
  descripcion: string;
  onIrAValidacion: () => void;
}

const API_NOTICIAS = '/api/v1/noticias';
const RUTA_PANEL: Record<PanelNoticias, string> = { peru: 'peru', internacional: 'internacionales' };
const MAX_NOTICIAS_EN_PANTALLA = 100;

/**
 * Feed temporal en vivo de un panel (Perú o Internacionales). Ambos comparten
 * el mismo feed del backend: el país de cada noticia decide en qué panel sale.
 */
export default function PanelFeed({ panel, titulo, descripcion, onIrAValidacion }: Props) {
  const [noticias, setNoticias] = useState<NoticiaFeed[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [enVivo, setEnVivo] = useState(false);
  const [validandoId, setValidandoId] = useState<number | null>(null);
  const [aviso, setAviso] = useState<{ tipo: 'ok' | 'error'; texto: string } | null>(null);

  const cargarNoticias = useCallback(async () => {
    try {
      const response = await fetch(`${API_NOTICIAS}/${RUTA_PANEL[panel]}`);
      if (!response.ok) throw new Error('No se pudo obtener las noticias');
      setNoticias(await response.json());
      setError(null);
    } catch (err) {
      console.error(`Error al cargar el panel ${panel}`, err);
      setError('No se pudieron cargar las noticias.');
    } finally {
      setCargando(false);
    }
  }, [panel]);

  useEffect(() => {
    cargarNoticias();
  }, [cargarNoticias]);

  // El backend empuja por SSE tanto noticias nuevas como cambios de estado
  // (p. ej. otra persona la envió a validación) de los dos paneles; cada
  // panel se queda con lo suyo: nueva -> arriba, conocida -> se reemplaza.
  useEffect(() => {
    const source = new EventSource(`${API_NOTICIAS}/feed/stream`);
    source.onopen = () => setEnVivo(true);
    source.onerror = () => setEnVivo(false);
    source.onmessage = (event) => {
      const recibida: NoticiaFeed = JSON.parse(event.data);
      if (recibida.panel !== panel) return;
      setNoticias((actuales) => {
        if (actuales.some((n) => n.id === recibida.id)) {
          return actuales.map((n) => (n.id === recibida.id ? recibida : n));
        }
        return [recibida, ...actuales].slice(0, MAX_NOTICIAS_EN_PANTALLA);
      });
    };
    return () => source.close();
  }, [panel]);

  const handleValidar = async (noticia: NoticiaFeed) => {
    setValidandoId(noticia.id);
    setAviso(null);
    try {
      const response = await fetch(`${API_NOTICIAS}/feed/${noticia.id}/validar`, { method: 'POST' });
      if (!response.ok) {
        const detalle = await response.json().catch(() => null);
        throw new Error(detalle?.detail || 'No se pudo enviar a validación.');
      }
      setNoticias((actuales) =>
        actuales.map((n) => (n.id === noticia.id ? { ...n, en_validacion: true } : n)),
      );
      setAviso({ tipo: 'ok', texto: `"${noticia.titular}" se envió a Validación.` });
    } catch (err) {
      setAviso({ tipo: 'error', texto: err instanceof Error ? err.message : 'Error al enviar a validación.' });
    } finally {
      setValidandoId(null);
    }
  };

  return (
    <div className="panel-feed">
      <div className="panel-feed-header">
        <div>
          <h1>
            {titulo}
            <span className={`panel-feed-live ${enVivo ? 'is-on' : ''}`}>
              <span className="panel-feed-live-dot" />
              {enVivo ? 'EN VIVO' : 'CONECTANDO…'}
            </span>
          </h1>
          <p>{descripcion}</p>
        </div>
      </div>

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

      {cargando && <p className="panel-feed-estado">Cargando noticias…</p>}
      {!cargando && error && <p className="panel-feed-estado panel-feed-error">{error}</p>}
      {!cargando && !error && noticias.length === 0 && (
        <p className="panel-feed-estado">
          Aún no hay noticias en el feed. Aparecerán aquí automáticamente en el próximo ciclo de captura.
        </p>
      )}

      <div className="panel-feed-grid">
        {noticias.map((noticia) => (
          <NewsCard
            key={noticia.id}
            noticia={noticia}
            validando={validandoId === noticia.id}
            onValidar={handleValidar}
          />
        ))}
      </div>
    </div>
  );
}
