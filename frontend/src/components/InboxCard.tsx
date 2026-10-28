import React from 'react';
import type { InboxItem } from '../types';

interface InboxCardProps {
  item: InboxItem;
  onClick: () => void;
  onApprove?: (radicado: string) => void;
}

export const InboxCard: React.FC<InboxCardProps> = ({ item, onClick, onApprove }) => {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick();
    }
  };

  const getStatusBadge = () => {
    if (item.estado_sac === 'TRAMITADO' || item.estado_sac === 'APROBADO') {
      return <span className="status-badge" style={{ background: '#ecfdf5', color: '#047857', border: '1px solid #10b981' }}>✓ TRAMITADO</span>;
    }
    switch (item.estado_botsac) {
      case 'LISTO':
        return <span className="status-badge status-badge-ready">✓ LISTO</span>;
      case 'ERROR':
        return <span className="status-badge status-badge-error">✕ ERROR</span>;
      case 'PREPARANDO':
        return <span className="status-badge status-badge-prep">⏳ PREPARANDO</span>;
      default:
        return <span className="status-badge status-badge-pending" style={{ background: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1' }}>📋 EN COLA SAC</span>;
    }
  };

  return (
    <div
      className="inbox-card"
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      aria-label={`Radicado ${item.radicado} - ${item.asunto}`}
    >
      {/* COLUMN A: Radicado, SAC status, Date, Official */}
      <div className="card-col-a">
        <div className="card-radicado">{item.radicado}</div>
        <div className="card-sac-status">{item.estado_sac}</div>
        <div className="card-meta-line">{item.fecha_creacion}</div>
        <div className="card-meta-line" style={{ fontWeight: 500 }}>{item.funcionario}</div>
      </div>

      {/* COLUMN B: Subject, Category, Summary, Location & Sedes */}
      <div className="card-col-b">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          {item.etapa_tramite === 'FALTA_APROBACION' && (
            <span className="etapa-badge etapa-badge-aprobacion">
              ✍️ Por Aprobar
            </span>
          )}
          {(item.estado_sac === 'TRAMITADO' || item.estado_sac === 'APROBADO') && (
            <span className="etapa-badge" style={{ background: '#ecfdf5', color: '#047857', border: '1px solid #10b981' }}>
              📁 Tramitado y Archivado
            </span>
          )}
          {item.etapa_tramite === 'EN_PROCESO' && (
            <span className="etapa-badge etapa-badge-proceso">
              <span className="spin-icon" style={{marginRight:'4px', display:'inline-block'}}>⏳</span> BotSAC Extrayendo...
            </span>
          )}
          {item.etapa_tramite === 'POR_GESTIONAR' && (
            <span className="etapa-badge etapa-badge-gestionar">
              ⏳ No Diligenciado
            </span>
          )}
          {item.categoria && (
            <span className="categoria-badge-sm">
              {item.categoria}
            </span>
          )}
          {item.sedes_count !== undefined && item.sedes_count > 0 && (
            <span className="sedes-counter-pill">
              🏫 {item.sedes_count} {item.sedes_count === 1 ? 'sede' : 'sedes'}
            </span>
          )}
        </div>
        
        <div className="card-subject">{item.asunto}</div>
        <div className="card-summary">
          {item.etapa_tramite === 'EN_PROCESO' ? 'BotSAC está extrayendo y consolidando la respuesta de este radicado en segundo plano...' : item.resumen_preview}
        </div>
        {item.respuesta_actual && item.respuesta_actual.trim() && (
          <div className="card-response-preview-box">
            <span className="card-response-label">✍️ Respuesta:</span>
            <span className="card-response-snippet">
              {item.respuesta_actual.length > 150 ? item.respuesta_actual.slice(0, 150) + '...' : item.respuesta_actual}
            </span>
          </div>
        )}
        <div className="card-location">
          <span>📍 {item.municipio}</span>
          {item.remitente && (
            <>
              <span>·</span>
              <span className="card-remitente">👤 {item.remitente}</span>
            </>
          )}
        </div>
      </div>

      {/* COLUMN C: BotSAC status, Vencido, Stats indicators, Action indicator */}
      <div className="card-col-c">
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          {item.is_vencido && <span className="badge-vencido">🔴 VENCIDO</span>}
          {getStatusBadge()}
        </div>
        <div className="card-stats">
          {item.stats.docs_count > 0
            ? `${item.stats.docs_count} docs · ${item.stats.hallazgos_count} hallazgos · ${item.stats.alerts_count} alertas`
            : (item.estado_botsac === 'LISTO'
                ? 'Expediente analizado · 0 anexos adicionales'
                : 'Metadatos en Oracle · Pendiente extracción documental')}
        </div>
        {item.etapa_tramite === 'FALTA_APROBACION' && item.estado_sac !== 'TRAMITADO' && (
          item.estado_botsac === 'LISTO' ? (
            onApprove && (
              <button
                className="btn-primary"
                style={{
                  background: '#16a34a',
                  borderColor: '#15803d',
                  color: '#ffffff',
                  padding: '5px 12px',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  borderRadius: '6px',
                  cursor: 'pointer',
                  marginTop: '4px'
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  onApprove(item.radicado);
                }}
                title="Aprobar y despachar directamente este radicado listo con documentos verificados"
              >
                ✅ Aprobar y Archivar
              </button>
            )
          ) : (
            <div style={{ fontSize: '0.75rem', color: '#64748b', fontStyle: 'italic', marginTop: '6px', textAlign: 'right' }}>
              ⏳ Esperando extracción para revisión
            </div>
          )
        )}
        <div className="card-arrow" aria-hidden="true">→</div>
      </div>
    </div>
  );
};
