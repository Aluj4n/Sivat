import React from 'react';
import './NewsCard.css';
import type { NoticiaFeed } from '../PanelFeed/PanelFeed';

interface Props {
  noticia: NoticiaFeed;
  validando: boolean;
  onValidar: (noticia: NoticiaFeed) => void;
}

// En el panel Perú el país sobra; en Internacionales "INTL" no dice nada
const PAISES_SIN_ETIQUETA = new Set(['intl', 'peru', 'perú', 'pe']);

function tiempoRelativo(iso: string | null): string {
  if (!iso) return '';
  const minutos = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutos < 1) return 'ahora';
  if (minutos < 60) return `hace ${minutos} min`;
  const horas = Math.round(minutos / 60);
  return horas < 24 ? `hace ${horas} h` : `hace ${Math.round(horas / 24)} d`;
}

const NewsCard: React.FC<Props> = ({ noticia, validando, onValidar }) => {
  return (
    <article className={`news-card ${noticia.en_validacion ? 'is-en-validacion' : ''}`}>
      {/* Sin imagen (o si falla al cargar) queda el fondo gris de la tarjeta */}
      {noticia.imagen_url && (
        <img
          src={noticia.imagen_url}
          alt=""
          className="news-card-img"
          onError={(e) => {
            e.currentTarget.style.display = 'none';
          }}
        />
      )}
      <div className="news-card-overlay" />

      <div className="news-card-body">
        <div className="news-card-tags">
          <span className="news-card-tag">
            {noticia.fuente_origen}
            {noticia.pais && !PAISES_SIN_ETIQUETA.has(noticia.pais.toLowerCase()) ? ` · ${noticia.pais}` : ''}
          </span>
          {/* El periodista ve de inmediato si el propio canal ya cubrió el tema */}
          {noticia.fuente_origen === 'Canal N' && <span className="news-card-canal-n">Cobertura Canal N</span>}
          {noticia.en_validacion && <span className="news-card-estado">En validación</span>}
        </div>
        <h2 className="news-card-titular">{noticia.titular}</h2>
        <span className="news-card-fecha">{tiempoRelativo(noticia.fecha_publicacion)}</span>
      </div>

      {/* Visible al pasar el mouse, con foco de teclado y siempre en pantallas táctiles */}
      <div className="news-card-acciones">
        {noticia.en_validacion ? (
          <span className="news-card-accion-hecha">✓ Enviada a validación</span>
        ) : (
          <button
            type="button"
            className="news-card-validar"
            disabled={validando}
            onClick={() => onValidar(noticia)}
          >
            {validando ? 'Enviando…' : 'Validar'}
          </button>
        )}
        {noticia.url_original && (
          <a
            href={noticia.url_original}
            target="_blank"
            rel="noopener noreferrer"
            className="news-card-fuente"
          >
            Ver fuente ↗
          </a>
        )}
      </div>
    </article>
  );
};

export default NewsCard;
