import React, { useState, useEffect } from 'react';
import { ReportTable } from './components/ReportTable';
import { DocumentViewer } from './components/DocumentViewer';

function App() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState(null);

  useEffect(() => {
    // En producción esto llamaría a un backend. 
    // Aquí leemos el JSON estático generado por el bot (copiado a /public)
    fetch('/report.json')
      .then(res => res.json())
      .then(json => {
        setData(json);
        setLoading(false);
      })
      .catch(err => {
        console.error('Error cargando los datos:', err);
        setLoading(false);
      });
  }, []);

  return (
    <div className="dashboard-container">
      <header>
        <div>
          <h1>Dashboard botSAC</h1>
          <p style={{color: 'var(--text-secondary)', marginTop: '0.25rem'}}>
            Revisión Rápida de Infraestructura
          </p>
        </div>
      </header>

      <main>
        {loading ? (
          <div className="empty-state">Cargando radicados...</div>
        ) : (
          <ReportTable 
            data={data} 
            onRowClick={(item) => setSelectedItem(item)} 
          />
        )}
      </main>

      {selectedItem && (
        <DocumentViewer 
          selectedItem={selectedItem} 
          onClose={() => setSelectedItem(null)} 
        />
      )}
    </div>
  );
}

export default App;
