import React from 'react';

export function DocumentViewer({ selectedItem, onClose }) {
  if (!selectedItem) return null;

  const docs = selectedItem.documentos || [];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Documentos: {selectedItem['Número de Ingreso - SAC']}</h2>
          <button className="close-btn" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          {docs.length === 0 ? (
            <div className="empty-state">
              <p>No hay documentos adjuntos para este SAC.</p>
            </div>
          ) : (
            <div className="doc-list">
              {docs.map((doc, idx) => {
                const isPdf = doc.toLowerCase().endsWith('.pdf');
                return (
                  <div key={idx} className="doc-item" onClick={() => alert('Abriendo visualizador para ' + doc)}>
                    <div className="doc-icon">
                      {isPdf ? '📄' : '🖼️'}
                    </div>
                    <span className="doc-name">{doc}</span>
                  </div>
                );
              })}
            </div>
          )}
          
          <div style={{marginTop: '2rem', padding: '1rem', backgroundColor: '#f8fafc', borderRadius: '0.5rem'}}>
            <h3 style={{fontSize: '0.875rem', marginBottom: '0.5rem', color: 'var(--text-secondary)'}}>Detalles de la necesidad:</h3>
            <p style={{fontSize: '0.875rem'}}>{selectedItem['Descripción de la necesidad']}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
