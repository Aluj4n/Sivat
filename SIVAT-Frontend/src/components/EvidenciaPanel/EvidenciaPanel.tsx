import './EvidenciaPanel.css';

export interface Evidencia {
  tipo: 'verificacion' | 'medio';
  origen: string | null;
  titulo: string | null;
  url: string | null;
  /** Calificación del verificador (de ellos, no de SIVAT). */
  calificacion: string | null;
  similitud: number;
  fecha_publicacion: string | null;
}

interface Props {
  evidenciaBuscada: boolean;
  nivel: string | null;
  coincidentes: number | null;
  contradictorias: number | null;
  explicacion: string[];
  evidencias: Evidencia[];
  buscando: boolean;
  onBuscar: () => void;
}

// Opción D: el "por qué" debajo del medidor. Las razones vienen de las reglas
// del backend; aquí solo se muestran, siempre atribuidas a su fuente.
export default function EvidenciaPanel({
  evidenciaBuscada,
  nivel,
  coincidentes,
  contradictorias,
  explicacion,
  evidencias,
  buscando,
  onBuscar,
}: Props) {
  if (!evidenciaBuscada) {
    return (
      <div className="evidencia evidencia-vacia">
        <span>Aún no se buscó evidencia para esta afirmación.</span>
        <button type="button" onClick={onBuscar} disabled={buscando}>
          {buscando ? 'Buscando…' : 'Buscar evidencia'}
        </button>
      </div>
    );
  }

  const verificaciones = evidencias.filter((e) => e.tipo === 'verificacion');
  const medios = evidencias.filter((e) => e.tipo === 'medio');

  return (
    <div className="evidencia">
      <div className="evidencia-cabecera">
        <span className="evidencia-titulo">Por qué</span>
        <div className="evidencia-chips">
          <span className="evidencia-chip">Evidencia: {nivel}</span>
          <span className="evidencia-chip">{coincidentes ?? 0} coincidentes</span>
          <span className="evidencia-chip">{contradictorias ?? 0} contradictorias</span>
        </div>
      </div>

      <ul className="evidencia-razones">
        {explicacion.map((razon) => (
          <li key={razon}>{razon}</li>
        ))}
      </ul>

      {evidencias.length > 0 && (
        <details className="evidencia-detalle">
          <summary>Ver evidencia ({evidencias.length})</summary>
          {verificaciones.length > 0 && (
            <ListaEvidencia titulo="Verificaciones similares" items={verificaciones} />
          )}
          {medios.length > 0 && <ListaEvidencia titulo="Medios que publicaron algo similar" items={medios} />}
        </details>
      )}

      <div className="evidencia-pie">
        <span>Similitud de texto (TF-IDF); la coincidencia de tema no confirma los hechos.</span>
        <button type="button" onClick={onBuscar} disabled={buscando}>
          {buscando ? 'Buscando…' : 'Actualizar evidencia'}
        </button>
      </div>
    </div>
  );
}

function ListaEvidencia({ titulo, items }: { titulo: string; items: Evidencia[] }) {
  return (
    <div className="evidencia-grupo">
      <span className="evidencia-grupo-titulo">{titulo}</span>
      <ul>
        {items.map((e) => (
          <li key={`${e.tipo}-${e.url ?? e.titulo}`}>
            <div className="evidencia-item-meta">
              <span className="evidencia-origen">{e.origen}</span>
              {e.calificacion && (
                <span className="evidencia-calificacion" title={`Calificación publicada por ${e.origen}`}>
                  Calificación del verificador: {e.calificacion}
                </span>
              )}
              <span className="evidencia-similitud">{Math.round(e.similitud * 100)}% similar</span>
            </div>
            {e.url ? (
              <a href={e.url} target="_blank" rel="noopener noreferrer">
                {e.titulo} ↗
              </a>
            ) : (
              <span>{e.titulo}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
