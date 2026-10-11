import { useCallback, useEffect, useState } from 'react';
import NewsCard from '../components/NewsCard/NewsCard';
import './Internacionales.css';

export interface NoticiaInternacional {
  id: number;
  titular: string;
  imagen_url: string | null;
  url_original: string | null;
  fuente_origen: string;
  pais: string | null;
  categoria: string;
  fecha_publicacion: string | null;
  en_validacion: boolean;
  afirmacion_id: number | null;
}

interface Props {
  onIrAValidacion: () => void;
}

const API_BASE = '/api/v1/noticias/internacionales';
const MAX_NOTICIAS_EN_PANTALLA = 100;

export default function Internacionales({ onIrAValidacion }: Props) {
  const [noticias, setNoticias] = useState<NoticiaInternacional[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [enVivo, setEnVivo] = useState(false);
  const [validandoId, setValidandoId] = useState<number | null>(null);
  const [aviso, setAviso] = useState<{ tipo: 'ok' | 'error'; texto: string } | null>(null);

  const cargarNoticias = useCallback(async () => {
    try {
      const response = await fetch(API_BASE);
      if (!response.ok) throw new Error('No se pudo obtener las noticias internacionales');
      setNoticias(await response.json());
      setError(null);
    } catch (err) {
      console.error('Error al cargar noticias internacionales', err);
      setError('No se pudieron cargar las noticias internacionales.');
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargarNoticias();
  }, [cargarNoticias]);

  // El backend empuja por SSE tanto noticias nuevas como cambios de estado
  // (p. ej. otra persona la envió a validación): nueva -> arriba, conocida -> se reemplaza.
  useEffect(() => {
    const source = new EventSource(`${API_BASE}/stream`);
    source.onopen = () => setEnVivo(true);
    source.onerror = () => setEnVivo(false);
    source.onmessage = (event) => {
      const recibida: NoticiaInternacional = JSON.parse(event.data);
      setNoticias((actuales) => {
        if (actuales.some((n) => n.id === recibida.id)) {
          return actuales.map((n) => (n.id === recibida.id ? recibida : n));
        }
        return [recibida, ...actuales].slice(0, MAX_NOTICIAS_EN_PANTALLA);
      });
    };
    return () => source.close();
  }, []);

  const handleValidar = async (noticia: NoticiaInternacional) => {
    setValidandoId(noticia.id);
    setAviso(null);
    try {
      const response = await fetch(`${API_BASE}/${noticia.id}/validar`, { method: 'POST' });
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
    <div className="internacionales-view">
      <div className="internacionales-header">
        <div>
          <h1>
            Internacionales
            <span className={`internacionales-live ${enVivo ? 'is-on' : ''}`}>
              <span className="internacionales-live-dot" />
              {enVivo ? 'EN VIVO' : 'CONECTANDO…'}
            </span>
          </h1>
          <p>
            Noticias y rumores internacionales de GDELT, medios en español (RSS), Bluesky, Reddit y YouTube.
            Se actualiza solo y lo no validado se descarta a las 24 h.
          </p>
        </div>
      </div>

      {aviso && (
        <div className={`internacionales-aviso is-${aviso.tipo}`} role="status">
          <span>{aviso.texto}</span>
          {aviso.tipo === 'ok' && (
            <button type="button" onClick={onIrAValidacion}>
              Ir a Validación →
            </button>
          )}
        </div>
      )}

      {cargando && <p className="internacionales-estado">Cargando noticias…</p>}
      {!cargando && error && <p className="internacionales-estado internacionales-error">{error}</p>}
      {!cargando && !error && noticias.length === 0 && (
        <p className="internacionales-estado">
          Aún no hay noticias en el feed. Aparecerán aquí automáticamente en el próximo ciclo de captura.
        </p>
      )}

      <div className="internacionales-grid">
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
