export interface InboxSummary {
  pending_sac: number;
  ready: number;
  preparing: number;
  error: number;
  falta_aprobacion?: number;
  por_gestionar?: number;
  tramitados?: number;
}

export interface ItemStats {
  docs_count: number;
  hallazgos_count: number;
  alerts_count: number;
}

export type BotSacStatus = 'LISTO' | 'PREPARANDO' | 'PENDIENTE' | 'ERROR';

export interface InstitucionSede {
  institucion: string;
  municipio: string;
  sedes: string[];
}

export type EtapaTramite = 'FALTA_APROBACION' | 'POR_GESTIONAR' | 'TRAMITADO' | 'FINALIZADO' | 'EN_PROCESO';

export interface InboxItem {
  radicado: string;
  asunto: string;
  municipio: string;
  funcionario: string;
  remitente?: string;
  categoria: string;
  fecha_creacion: string;
  dias_plazo: string;
  estado_sac: string;
  estado_botsac: BotSacStatus;
  is_vencido: boolean;
  resumen_preview: string;
  respuesta_actual?: string;
  sedes_count?: number;
  etapa_tramite?: EtapaTramite;
  etapa_label?: string;
  stats: ItemStats;
}

export interface InboxResponse {
  updated_at: string;
  summary: InboxSummary;
  items: InboxItem[];
}

export interface DocumentItem {
  id: string;
  filename: string;
  document_type: string;
  summary?: string;
  key_facts?: string[];
  pages: number;
  sha256: string;
  is_ready: boolean;
}

export interface Finding {
  fact: string;
  source_doc: string;
}

export interface Alert {
  type: string;
  detail?: string;
  source?: string;
  severity?: string;
}

export interface TraceabilityItem {
  source_type: string;
  detail: string;
  timestamp?: string;
}

export interface KeyData {
  municipality: string;
  requester: string;
}

export interface RadicadoDetail {
  radicado: string;
  asunto: string;
  municipio: string;
  funcionario: string;
  fecha_creacion: string;
  dias_plazo: string;
  estado_sac: string;
  estado_botsac: BotSacStatus;
  is_vencido: boolean;
  categoria: string;
  etapa_tramite?: EtapaTramite;
  etapa_label?: string;
  summary: string;
  requests: string[];
  respuesta_actual?: string;
  estado_respuesta?: string;
  instituciones_sedes: InstitucionSede[];
  key_data: KeyData;
  findings: Finding[];
  alerts: Alert[];
  documents: DocumentItem[];
  traceability: TraceabilityItem[];
  raw_metadata: string;
}
