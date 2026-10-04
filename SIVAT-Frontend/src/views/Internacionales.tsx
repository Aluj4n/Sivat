import { useCallback, useEffect, useRef, useState } from 'react';
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
  nivel_confianza: string | null;
}

const API_BASE = '/api/v1';
const MAX_NOTICIAS_EN_PANTALLA = 60;

export default function Internacionales() {
  const [noticias, setNoticias] = useState<NoticiaInternacional[]>([]);
  const [cargando, setCargando] = useState(true);
  const [actualizando, setActualizando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enVivo, setEnVivo] = useState(false);
  const idsConocidos = useRef<Set<number>>(new Set());

  const cargarNoticias = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/noticias/internacionales`);
      if (!response.ok) throw new Error('No se pudo obtener las noticias internacionales');
      const data: NoticiaInternacional[] = await response.json();
      idsConocidos.current = new Set(data.map((n) => n.id));
      setNoticias(data);
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

  // Conexión en tiempo real: cada rumor/noticia nueva ingerida desde GDELT, X o
  // YouTube llega aquí apenas se guarda en el backend y se coloca primero,
  // sin importar si luego se confirma como verdadera o falsa (eso lo valida el periodista después).
  useEffect(() => {
    const source = new EventSource(`${API_BASE}/noticias/internacionales/stream`);

    source.onopen = () => setEnVivo(true);
    source.onerror = () => setEnVivo(false);

    source.onmessage = (event) => {
      const nueva: NoticiaInternacional = JSON.parse(event.data);
      if (idsConocidos.current.has(nueva.id)) return;
      idsConocidos.current.add(nueva.id);
      setNoticias((actuales) => [nueva, ...actuales].slice(0, MAX_NOTICIAS_EN_PANTALLA));
    };

    return () => source.close();
  }, []);

  const handleActualizar = async () => {
    setActualizando(true);
    try {
      // Fuerza un ciclo de ingesta inmediato; el ciclo automático en el
      // backend ya hace esto solo cada minuto, esto solo lo adelanta.
      await Promise.allSettled([
        fetch(`${API_BASE}/ingesta/internacional/gdelt`),
        fetch(`${API_BASE}/ingesta/internacional/x`),
        fetch(`${API_BASE}/ingesta/internacional/youtube`),
      ]);
    } finally {
      setActualizando(false);
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
          <p>Rumores y noticias captados en tiempo real desde GDELT Project, X y YouTube.</p>
        </div>
        <button
          className="internacionales-refresh"
          onClick={handleActualizar}
          disabled={actualizando}
        >
          {actualizando ? 'Consultando fuentes…' : 'Forzar actualización'}
        </button>
      </div>

      {cargando && <p className="internacionales-estado">Cargando noticias…</p>}
      {!cargando && error && <p className="internacionales-estado internacionales-error">{error}</p>}
      {!cargando && !error && noticias.length === 0 && (
        <p className="internacionales-estado">
          Aún no hay noticias internacionales ingeridas. Aparecerán aquí automáticamente
          en cuanto el sistema detecte una nueva.
        </p>
      )}

      <div className="internacionales-grid">
        {noticias.map((noticia) => (
          <NewsCard key={noticia.id} noticia={noticia} />
        ))}
      </div>
    </div>
  );
}
