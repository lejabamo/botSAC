import React from 'react';
import './index.css';

export function ReportTable({ data, onRowClick }) {
  if (!data || data.length === 0) {
    return <div className="empty-state">No se encontraron datos de radicados.</div>;
  }

  return (
    <div className="card">
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Fecha Ingreso del SAC</th>
              <th>Municipio</th>
              <th>Institución Educativa o centro educativo</th>
              <th>Sede</th>
              <th>Número de Ingreso - SAC</th>
              <th>Descripción de la necesidad</th>
            </tr>
          </thead>
          <tbody>
            {data.map((item, index) => (
              <tr key={index} onClick={() => onRowClick(item)}>
                <td>{item['Fecha Ingreso del SAC']}</td>
                <td>{item['Municipio']}</td>
                <td>{item['Institución Educativa o centro educativo']}</td>
                <td>{item['Sede']}</td>
                <td>
                  <strong>{item['Número de Ingreso - SAC']}</strong>
                  {item.documentos && item.documentos.length > 0 && (
                    <div className="tag">{item.documentos.length} doc(s)</div>
                  )}
                </td>
                <td>{item['Descripción de la necesidad']}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
