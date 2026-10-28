import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchDocumentMeta, getDocumentViewUrl } from '../services/api';
import type { DocumentItem } from '../types';

export const DocumentViewerPage: React.FC = () => {
  const { radicado, documentId } = useParams<{ radicado: string; documentId: string }>();
  const navigate = useNavigate();

  const [docMeta, setDocMeta] = useState<DocumentItem | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!radicado || !documentId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    fetchDocumentMeta(radicado, documentId)
      .then((meta) => {
        if (isMounted) setDocMeta(meta);
      })
      .catch((err: unknown) => {
        if (isMounted) {
          if (err instanceof Error) {
            setError(err.message);
          } else {
            setError('No fue posible cargar los metadatos del documento.');
          }
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [radicado, documentId]);

  if (!radicado || !documentId) {
    return null;
  }

  const pdfUrl = getDocumentViewUrl(radicado, documentId);

  return (
    <div className="app-container">
      <div className="viewer-container">
        {/* Navigation / Header */}
        <div className="viewer-header">
          <button
            className="btn-primary"
            onClick={() => navigate(`/radicado/${encodeURIComponent(radicado)}`)}
          >
            ← Volver al Radicado ({radicado})
          </button>
          
          <div className="viewer-title">
            📄 {docMeta ? docMeta.filename : 'Cargando documento...'}
          </div>

          <div style={{ fontSize: '0.85rem', color: '#64748b' }}>
            {docMeta && (
              <span className="doc-badge-type">
                {docMeta.document_type} · {docMeta.pages} {docMeta.pages === 1 ? 'página' : 'páginas'}
              </span>
            )}
          </div>
        </div>

        {/* Document Micro-summary strip */}
        {docMeta && docMeta.summary && (
          <div className="doc-summary-box" style={{ marginBottom: '12px', fontSize: '0.875rem' }}>
            💡 <strong>Resumen del documento analizado:</strong> {docMeta.summary}
          </div>
        )}

        {/* Loading state */}
        {loading && !docMeta && (
          <div className="loading-box">
            <div className="spinner"></div>
            <div>Cargando información del documento...</div>
          </div>
        )}

        {/* Loading error */}
        {error && (
          <div className="error-box">
            <p style={{ color: 'var(--danger)', fontWeight: 600 }}>No fue posible cargar el documento.</p>
            <p style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '4px' }}>{error}</p>
          </div>
        )}

        {/* Embedded PDF Viewer */}
        <iframe
          src={pdfUrl}
          title={docMeta ? docMeta.filename : 'Visor PDF'}
          className="pdf-frame"
        />
      </div>
    </div>
  );
};
