import type { Evidencia } from '../components/EvidenciaPanel/EvidenciaPanel';

/** Validar -> "Ya validadas"; Observar -> "En observación". Descartar borra la afirmación. */
export type Decision = 'Validado' | 'Observado';

/** Conclusión del periodista al validar: el veredicto es humano, nunca de la IA (RNF-08). */
export const CONCLUSIONES = ['Verdadera', 'Falsa', 'Engañosa', 'Sin evidencia suficiente'] as const;
export type Conclusion = (typeof CONCLUSIONES)[number];

export interface DecisionInfo {
  decision_periodista: Decision;
  conclusion: Conclusion | null;
  comentarios: string | null;
  fecha_decision: string;
}

export interface Evaluacion {
  afirmacion_id: number;
  texto: string;
  probabilidad_desinformacion: number;
  confianza_modelo: number | null;
  texto_suficiente: boolean;
  palabras_analizadas: number;
  senal: string;
  recomendacion_sistema: string;
  version_modelo: string;
  fuente_origen: string | null;
  url_original: string | null;
  evidencia_buscada: boolean;
  nivel_evidencia_disponible: string | null;
  fuentes_coincidentes: number | null;
  fuentes_contradictorias: number | null;
  fuente_oficial_encontrada: boolean | null;
  cobertura_evidencia: string | null;
  explicacion: string[];
  evidencias: Evidencia[];
  fecha_evaluacion?: string;
  decision?: DecisionInfo | null;
}
