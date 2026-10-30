import { useState } from 'react';
import { CONCLUSIONES, type Conclusion, type Decision } from '../../tipos/verificacion';
import './ControlesDecision.css';

interface Props {
  afirmacionId: number;
  /** En "En observación" ya está observada: solo se puede validar o descartar. */
  permitirObservar?: boolean;
  compacto?: boolean;
  /** Se llama tras registrar la decisión o descartar, para recargar la lista. */
  onHecho: () => void;
}

const API = '/api/v1/verificacion';

async function detalleError(respuesta: Response, porDefecto: string): Promise<string> {
  const cuerpo = await respuesta.json().catch(() => null);
  return typeof cuerpo?.detail === 'string' ? cuerpo.detail : porDefecto;
}

/**
 * Validar (con la conclusión del periodista), Observar (seguimiento) o
 * Descartar (borra la afirmación por completo, previa confirmación).
 */
export default function ControlesDecision({ afirmacionId, permitirObservar = true, compacto = false, onHecho }: Props) {
  const [validando, setValidando] = useState(false);
  const [conclusion, setConclusion] = useState<Conclusion | null>(null);
  const [comentario, setComentario] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const decidir = async (decision: Decision) => {
    setEnviando(true);
    setError(null);
    try {
      const respuesta = await fetch(`${API}/${afirmacionId}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision,
          conclusion: decision === 'Validado' ? conclusion : null,
          comentarios: decision === 'Validado' && comentario.trim() ? comentario.trim() : null,
        }),
      });
      if (!respuesta.ok) throw new Error(await detalleError(respuesta, 'No se pudo registrar la decisión.'));
      onHecho();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al registrar la decisión.');
    } finally {
      setEnviando(false);
    }
  };

  const descartar = async () => {
    if (!window.confirm('¿Descartar esta afirmación? Se eliminará por completo de SIVAT y no se puede deshacer.')) return;
    setEnviando(true);
    setError(null);
    try {
      const respuesta = await fetch(`${API}/${afirmacionId}`, { method: 'DELETE' });
      if (!respuesta.ok) throw new Error(await detalleError(respuesta, 'No se pudo descartar la afirmación.'));
      onHecho();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al descartar.');
    } finally {
      setEnviando(false);
    }
  };

  if (validando) {
    return (
      <div className={`decision-form ${compacto ? 'is-compacto' : ''}`}>
        <span className="decision-form-titulo">Conclusión del periodista</span>
        <div className="decision-conclusiones" role="radiogroup" aria-label="Conclusión del periodista">
          {CONCLUSIONES.map((c) => (
            <button
              key={c}
              type="button"
              role="radio"
              aria-checked={conclusion === c}
              className={conclusion === c ? 'is-elegida' : ''}
              onClick={() => setConclusion(c)}
            >
              {c}
            </button>
          ))}
        </div>
        <textarea
          value={comentario}
          onChange={(e) => setComentario(e.target.value)}
          placeholder="Comentario o fuente que respalda la conclusión (opcional)"
          rows={2}
          maxLength={1000}
        />
        {error && <span className="decision-error">{error}</span>}
        <div className="decision-botones">
          <button type="button" onClick={() => setValidando(false)} disabled={enviando}>
            Cancelar
          </button>
          <button
            type="button"
            className="is-principal"
            onClick={() => decidir('Validado')}
            disabled={enviando || conclusion === null}
          >
            {enviando ? 'Guardando…' : 'Confirmar validación'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="decision-controles">
      <div className="decision-botones">
        <button type="button" className="is-principal" onClick={() => setValidando(true)} disabled={enviando}>
          Validar
        </button>
        {permitirObservar && (
          <button type="button" onClick={() => decidir('Observado')} disabled={enviando}>
            Observar
          </button>
        )}
        <button type="button" className="is-peligro" onClick={descartar} disabled={enviando}>
          Descartar
        </button>
      </div>
      {error && <span className="decision-error">{error}</span>}
    </div>
  );
}
