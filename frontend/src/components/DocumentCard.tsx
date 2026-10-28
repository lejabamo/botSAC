import React from 'react';
import type { DocumentItem } from '../types';

interface DocumentCardProps {
  document: DocumentItem;
  onClick: () => void;
}

export const DocumentCard: React.FC<DocumentCardProps> = ({ document, onClick }) => {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick();
    }
  };

  const isWord = document.document_type.toLowerCase().includes('word') || 
                 document.filename.endsWith('.doc') || 
                 document.filename.endsWith('.docx');

  const isIncoming = document.document_type === 'PETICION_INICIAL' || 
                     document.document_type === 'ANEXO_PETICIONARIO' ||
                     document.document_type === 'SOLICITUD';
  const isResponse = document.document_type === 'RESPUESTA_OFICIAL';

  const badgeClass = isResponse ? 'doc-badge-type doc-badge-response' :
                     isIncoming ? 'doc-badge-type doc-badge-incoming' :
                     'doc-badge-type';

  const badgeLabel = isResponse ? '📤 Respuesta Oficial' :
                     isIncoming ? '📥 Petición Ciudadano' :
                     document.document_type;

  return (
    <div
      className={`document-card ${isResponse ? 'document-card-response' : 'document-card-incoming'}`}
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      aria-label={`Ver documento ${document.filename}`}
    >
      <div className="doc-header-row">
        <div className="doc-name">
          <span className="doc-icon" aria-hidden="true">{isResponse ? '🏛️' : isWord ? '📝' : '📄'}</span>
          <span className="doc-filename-text">{document.filename}</span>
        </div>
        <span className={badgeClass}>{badgeLabel}</span>
      </div>

      <div className="doc-meta">
        <span>{isWord ? 'Word (.doc/docx)' : 'PDF'}</span>
        <span>·</span>
        <span>{document.pages} {document.pages === 1 ? 'página' : 'páginas'}</span>
        <span>·</span>
        <span className="doc-badge-ready">✓ Preparado</span>
      </div>

      {document.summary && (
        <div className="doc-summary-box">
          {document.summary}
        </div>
      )}
    </div>
  );
};
