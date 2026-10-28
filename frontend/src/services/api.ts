import type { InboxResponse, RadicadoDetail, DocumentItem } from '../types';

const API_BASE = '/api';

export function getActiveToken(): string {
  try {
    const saved = localStorage.getItem('botsac_user');
    if (saved) {
      const u = JSON.parse(saved);
      if (u && u.token) {
        return u.token;
      }
    }
  } catch (e) {
    console.warn('Error leyendo token de localStorage', e);
  }
  return '';
}

export function getActiveUser(): string {
  try {
    const saved = localStorage.getItem('botsac_user');
    if (saved) {
      const u = JSON.parse(saved);
      if (u && u.username) {
        return u.username.trim().toLowerCase();
      }
    }
  } catch (e) {
    console.warn('Error leyendo botsac_user de localStorage', e);
  }
  return '';
}

function getAuthHeaders(): Record<string, string> {
  const token = getActiveToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

async function handleApiResponse(response: Response, defaultErrorMsg: string): Promise<any> {
  if (!response.ok) {
    let msg = defaultErrorMsg;
    try {
      const err = await response.json();
      if (err && err.detail) msg = err.detail;
    } catch {
      // Keep default msg
    }
    if (response.status === 401) {
      localStorage.removeItem('botsac_user');
      window.location.href = '/login';
    }
    throw new Error(msg);
  }
  return response.json();
}

export async function fetchInbox(_user?: string): Promise<InboxResponse> {
  const response = await fetch(`${API_BASE}/inbox`, {
    headers: getAuthHeaders()
  });
  return handleApiResponse(response, 'No fue posible cargar la bandeja.');
}

export async function fetchRadicadoDetail(radicado: string): Promise<RadicadoDetail> {
  const response = await fetch(`${API_BASE}/radicados/${encodeURIComponent(radicado)}`, {
    headers: getAuthHeaders()
  });
  return handleApiResponse(response, 'No fue posible cargar el radicado.');
}

export async function fetchDocumentMeta(radicado: string, documentId: string): Promise<DocumentItem> {
  const response = await fetch(`${API_BASE}/radicados/${encodeURIComponent(radicado)}/documents/${encodeURIComponent(documentId)}`, {
    headers: getAuthHeaders()
  });
  return handleApiResponse(response, 'No se encontró la información del documento.');
}

export function getDocumentViewUrl(radicado: string, documentId: string): string {
  const token = getActiveToken();
  return `${API_BASE}/radicados/${encodeURIComponent(radicado)}/documents/${encodeURIComponent(documentId)}/view?token=${encodeURIComponent(token)}`;
}

export async function triggerWatchdog(): Promise<any> {
  const response = await fetch(`${API_BASE}/watchdog/run`, {
    method: 'POST',
    headers: getAuthHeaders()
  });
  return handleApiResponse(response, 'Error al ejecutar Watchdog SAC.');
}

export async function triggerBatchProcess(batchSize: number = 3): Promise<any> {
  const response = await fetch(`${API_BASE}/batch/process?batch_size=${batchSize}`, {
    method: 'POST',
    headers: getAuthHeaders()
  });
  return handleApiResponse(response, 'Error al procesar bloque de radicados.');
}

export async function triggerSyncLightweight(maxPages: number = 3): Promise<any> {
  const response = await fetch(`${API_BASE}/sync/lightweight?pages=${maxPages}`, {
    method: 'POST',
    headers: getAuthHeaders()
  });
  return handleApiResponse(response, 'Error al sincronizar bandeja desde SAC.');
}

export async function approveRadicado(radicado: string, notes?: string): Promise<any> {
  const response = await fetch(`${API_BASE}/radicados/${encodeURIComponent(radicado)}/approve`, {
    method: 'POST',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ notes: notes || '' })
  });
  return handleApiResponse(response, `No fue posible aprobar el radicado ${radicado}.`);
}

export async function fetchArchivedInbox(): Promise<InboxResponse> {
  const response = await fetch(`${API_BASE}/inbox/archived`, {
    headers: getAuthHeaders()
  });
  return handleApiResponse(response, 'No fue posible cargar el archivo histórico.');
}
