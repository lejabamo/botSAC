import React from 'react';
import type { InboxItem } from '../types';

interface ApprovalCardProps {
  item: InboxItem;
  onClick: () => void;
  onApprove?: (radicado: string) => void;
}

export const ApprovalCard: React.FC<ApprovalCardProps> = ({ item, onClick, onApprove }) => {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick();
    }
  };

  return (
    <div
      className="inbox-card approval-card"
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      aria-label={`Aprobar respuesta para radicado ${item.radicado}`}
    >
      <div className="card-col-a">
        <div className="card-radicado">{item.radicado}</div>
        <div className="card-sac-status">{item.estado_sac}</div>
        <div className="card-meta-line">{item.fecha_creacion}</div>
        <div className="card-meta-line" style={{ fontWeight: 500 }}>👤 {item.funcionario}</div>
        <div className="card-location" style={{ marginTop: '12px' }}>
          <span>📍 {item.municipio}</span>
        </div>
      </div>

      <div className="card-col-b" style={{ flex: '1 1 50%' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '8px' }}>
          <span className={`etapa-badge ${item.etapa_tramite === 'EN_PROCESO' ? 'etapa-badge-proceso' : 'etapa-badge-aprobacion'}`}>
            {item.etapa_tramite === 'EN_PROCESO' ? '⏳ BotSAC Extrayendo...' : '✍️ Pendiente de Aprobación'}
          </span>
          {item.categoria && (
            <span className="categoria-badge-sm">
              {item.categoria}
            </span>
          )}
        </div>
        
        <div className="card-subject">{item.asunto}</div>
        <div className="card-summary" style={{ marginBottom: '16px' }}>
          <strong style={{ color: '#475569' }}>Resumen (Ciudadano): </strong> {item.resumen_preview}
        </div>
        
        {item.etapa_tramite === 'EN_PROCESO' ? (
          <div className="respuesta-formal-container" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px 20px', background: '#f8fafc', border: '1px dashed #cbd5e1' }}>
             <div className="spinner-small" style={{ width: '32px', height: '32px', marginBottom: '16px' }}></div>
             <div style={{ color: '#3b82f6', fontWeight: 600, fontSize: '1.1rem', marginBottom: '8px' }}>Extrayendo Respuesta...</div>
             <p style={{ color: '#64748b', fontSize: '0.9rem', textAlign: 'center', margin: 0 }}>
               BotSAC está navegando en el portal oficial y extrayendo el borrador actual para {item.radicado}.
             </p>
          </div>
        ) : (
          <div className="respuesta-formal-container">
            <div className="respuesta-formal-header">
               <span>📄 Vista Previa de Respuesta</span>
               <span className="verify-label">Pendiente de Aprobar</span>
            </div>
            <div className="respuesta-formal-document">
               <div className="doc-top-right">{item.radicado}</div>
               <div className="doc-date">Popayán, {new Date().toLocaleDateString('es-CO', {day: '2-digit', month: 'long', year: 'numeric'})}</div>
               <div className="doc-addressee">
                 <strong>{item.remitente || 'CIUDADANO'}</strong><br/>
                 {item.municipio}
               </div>
               <div className="doc-subject">
                 <strong>ASUNTO:</strong> Respuesta a la comunicación sobre {item.asunto}
               </div>
               <div className="doc-body">
                 {item.respuesta_actual ? (
                   <div dangerouslySetInnerHTML={{ __html: item.respuesta_actual.replace(/\n/g, '<br/>') }} />
                 ) : (
                   <>
                    Cordial saludo,<br/><br/>
                    Atendiendo a su comunicación radicada bajo el sistema SAC número {item.radicado}, mediante la cual expone la situación actual relacionada con <strong>{item.asunto}</strong>, nos permitimos presentar el respectivo pronunciamiento.<br/><br/>
                    En su escrito, esta Secretaría ha tomado atenta nota sobre el panorama operativo. El equipo del área correspondiente se pondrá en contacto para proyectar las alternativas viables que garanticen una solución adecuada de acuerdo a la normatividad vigente.<br/><br/>
                    Agradecemos su constante compromiso, liderazgo y vocación.<br/><br/>
                    Atentamente,
                   </>
                 )}
               </div>
               <div className="doc-firma">FIRMA<br/><br/><span style={{fontFamily: 'sans-serif', fontSize: '0.75rem', color: '#64748b'}}>{item.funcionario}</span></div>
            </div>
          </div>
        )}
      </div>

      <div className="card-col-c" style={{ justifyContent: 'space-between' }}>
         <div style={{ display: 'flex', justifyContent: 'flex-end', width: '100%' }}>
            {item.is_vencido && <span className="badge-vencido">🔴 VENCIDO</span>}
         </div>
         <div className="approval-actions">
            {item.etapa_tramite === 'EN_PROCESO' ? (
              <button className="btn-approve" disabled style={{ opacity: 0.6, cursor: 'not-allowed', background: '#94a3b8' }}>⏳ Procesando...</button>
            ) : item.etapa_tramite === 'TRAMITADO' ? (
              <span style={{ background: '#dcfce7', color: '#166534', padding: '6px 12px', borderRadius: '4px', fontWeight: 700, fontSize: '0.85rem' }}>✅ TRAMITADO</span>
            ) : (
              <>
                <button
                  className="btn-approve"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (onApprove) {
                      onApprove(item.radicado);
                    }
                  }}
                  title="Aprobar y despachar formalmente este expediente"
                >
                  ✅ Aprobar y Despachar
                </button>
              </>
            )}
         </div>
      </div>
    </div>
  );
};
