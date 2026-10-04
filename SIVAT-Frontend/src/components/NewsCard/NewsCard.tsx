import React from 'react';
import './NewsCard.css';
import type { NoticiaInternacional } from '../../views/Internacionales';

interface Props {
  noticia: NoticiaInternacional;
}

const NewsCard: React.FC<Props> = ({ noticia }) => {
  const contenido = (
    <>
      <img
        src={noticia.imagen_url || '/placeholder.jpg'}
        alt={noticia.titular}
        className="news-card-img"
        onError={(e) => {
          (e.currentTarget as HTMLImageElement).src = '/placeholder.jpg';
        }}
      />
      <div className="news-card-overlay" />
      <div className="news-card-body">
        <div className="news-card-tags">
          <span className="news-card-tag">
            {noticia.categoria} · {noticia.fuente_origen}
          </span>
          {noticia.nivel_confianza && (
            <span className="news-card-confianza">Confianza: {noticia.nivel_confianza}</span>
          )}
        </div>
        <h2 className="news-card-titular">{noticia.titular}</h2>
      </div>
    </>
  );

  if (noticia.url_original) {
    return (
      <a
        href={noticia.url_original}
        target="_blank"
        rel="noopener noreferrer"
        className="news-card"
      >
        {contenido}
      </a>
    );
  }

  return <div className="news-card">{contenido}</div>;
};

export default NewsCard;
