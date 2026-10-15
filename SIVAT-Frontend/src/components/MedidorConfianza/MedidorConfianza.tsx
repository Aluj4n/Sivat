import './MedidorConfianza.css';

interface Props {
  /**
   * 0-100: 100 - probabilidad de desinformación del clasificador (lo calcula el backend).
   * null cuando el texto es muy corto para el modelo: no se muestra un porcentaje engañoso.
   */
  confianza: number | null;
  /** Palabras que recibió el modelo, para explicar por qué no hay porcentaje. */
  palabras?: number;
  compacto?: boolean;
}

// Opción C acordada: porcentaje visual con escala explícita y aclaración de
// qué mide. Evolucionará a la opción D (el "por qué" y la evidencia del RAG
// debajo del medidor) sin reemplazar este componente.
export default function MedidorConfianza({ confianza, palabras, compacto = false }: Props) {
  if (confianza === null) {
    return (
      <div className={`medidor is-insuficiente ${compacto ? 'is-compacto' : ''}`}>
        <div className="medidor-cabecera">
          <span className="medidor-titulo">Confianza del modelo</span>
          <span className="medidor-valor">—</span>
        </div>
        <span className="medidor-aviso">
          Texto insuficiente para el modelo{palabras !== undefined ? ` (${palabras} palabras)` : ''}
        </span>
        {!compacto && <span className="medidor-nota">Sin contenido completo · Decidir con la evidencia</span>}
      </div>
    );
  }

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
