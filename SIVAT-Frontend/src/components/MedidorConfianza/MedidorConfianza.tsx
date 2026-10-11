import './MedidorConfianza.css';

interface Props {
  /** 0-100: 100 - probabilidad de desinformación del clasificador (lo calcula el backend). */
  confianza: number;
  compacto?: boolean;
}

// Opción C acordada: porcentaje visual con escala explícita y aclaración de
// qué mide. Evolucionará a la opción D (el "por qué" y la evidencia del RAG
// debajo del medidor) sin reemplazar este componente.
export default function MedidorConfianza({ confianza, compacto = false }: Props) {
  const valor = Math.max(0, Math.min(100, Math.round(confianza)));

  return (
    <div className={`medidor ${compacto ? 'is-compacto' : ''}`}>
      <div className="medidor-cabecera">
        <span className="medidor-titulo">Confianza del modelo</span>
        <span className="medidor-valor">{valor}%</span>
      </div>
      <div
        className="medidor-pista"
        role="meter"
        aria-label="Confianza del modelo"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={valor}
        aria-valuetext={`${valor}% — basado en patrones de texto, requiere validación periodística`}
      >
        <div className="medidor-relleno" style={{ width: `${valor}%` }} />
      </div>
      <div className="medidor-escala">
        <span>Más probable desinformación</span>
        <span>Más probable confiable</span>
      </div>
      {!compacto && (
        <span className="medidor-nota">Basado en patrones de texto · Requiere validación periodística</span>
      )}
    </div>
  );
}
