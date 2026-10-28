import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { fetchRadicadoDetail, fetchInbox, approveRadicado } from '../services/api';
import type { RadicadoDetail, InboxItem, DocumentItem } from '../types';
import { DocumentCard } from '../components/DocumentCard';

export const DetailPage: React.FC = () => {
  const { radicado } = useParams<{ radicado: string }>();
  const navigate = useNavigate();
  const location = useLocation();

  const [detail, setDetail] = useState<RadicadoDetail | null>(null);
  const [inboxItems, setInboxItems] = useState<InboxItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [approving, setApproving] = useState<boolean>(false);
  const [approveSuccess, setApproveSuccess] = useState<string | null>(null);

  const filteredRadicados: string[] | undefined = location.state?.filteredRadicados;
  const filterLabel: string | undefined = location.state?.filterLabel;

  useEffect(() => {
    if (!radicado) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    Promise.all([
      fetchRadicadoDetail(radicado),
      fetchInbox().catch(() => null)
    ])
      .then(([detailRes, inboxRes]) => {
        if (!isMounted) return;
        setDetail(detailRes);
        if (inboxRes && inboxRes.items) {
          setInboxItems(inboxRes.items);
        }
      })
      .catch((err: unknown) => {
        if (!isMounted) return;
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('No fue posible cargar el radicado.');
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [radicado]);

  // Navigation handlers respecting active filters
  const listToNavigate = filteredRadicados && filteredRadicados.length > 0
    ? filteredRadicados
    : inboxItems.map((item) => item.radicado);

  const currentIndex = listToNavigate.indexOf(radicado || '');
  const prevRadicado = currentIndex > 0 ? listToNavigate[currentIndex - 1] : null;
  const nextRadicado = currentIndex >= 0 && currentIndex < listToNavigate.length - 1 ? listToNavigate[currentIndex + 1] : null;

  const handleApprove = async () => {
    if (!detail?.radicado) return;
    if (!window.confirm(`¿Aprobar y despachar formalmente el radicado ${detail.radicado}?\nEl expediente será archivado y saldrá de la bandeja de trabajo activa.`)) {
      return;
    }
    try {
      setApproving(true);
      setError(null);
      await approveRadicado(detail.radicado);
      setApproveSuccess(`✅ Radicado ${detail.radicado} aprobado exitosamente. Se ha trasladado al cajón de Tramitados.`);
      const updated = await fetchRadicadoDetail(detail.radicado);
      setDetail(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al aprobar radicado');
    } finally {
      setApproving(false);
    }
  };

  if (loading) {
    return (
      <div className="app-container">
        <div className="loading-box">
          <div className="spinner"></div>
          <div style={{ fontWeight: 600, color: '#334155' }}>Cargando expediente del radicado...</div>
          <div style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '6px' }}>
            Consolidando datos técnicos y análisis documental
          </div>
        </div>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="app-container">
        <div className="error-box">
          <p style={{ color: 'var(--danger)', fontWeight: 600, marginBottom: '8px' }}>
            No fue posible cargar el radicado.
          </p>
          <p style={{ fontSize: '0.875rem', color: '#64748b', marginBottom: '16px' }}>{error}</p>
          <button className="btn-primary" onClick={() => navigate('/')}>Volver a la Bandeja</button>
        </div>
      </div>
    );
  }

  const totalSedes = (detail.instituciones_sedes || []).reduce(
    (acc, curr) => acc + (curr.sedes ? curr.sedes.length : 1),
    0
  );

  return (
    <div className="app-container">
      {/* Top Navigation */}
      <div className="detail-nav">
        <div>
          <button
            className="btn-primary"
            onClick={() => prevRadicado && navigate(`/radicado/${encodeURIComponent(prevRadicado)}`, { state: location.state })}
            disabled={!prevRadicado}
            style={{ opacity: prevRadicado ? 1 : 0.4 }}
          >
            ← Anterior
          </button>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button className="btn-primary" onClick={() => navigate('/')}>
            🏠 Volver a Bandeja
          </button>
          {listToNavigate.length > 1 && (
            <span className="nav-filter-counter">
              {filterLabel ? `${filterLabel} · ` : ''} Radicado {currentIndex + 1} de {listToNavigate.length}
            </span>
          )}
        </div>
        <div>
          <button
            className="btn-primary"
            onClick={() => nextRadicado && navigate(`/radicado/${encodeURIComponent(nextRadicado)}`, { state: location.state })}
            disabled={!nextRadicado}
            style={{ opacity: nextRadicado ? 1 : 0.4 }}
          >
            Siguiente →
          </button>
        </div>
      </div>

      {/* Header */}
      <div className="detail-header">
        <div className="detail-header-left">
          <div className="detail-radicado">{detail.radicado}</div>
          <div className="detail-subject">{detail.asunto}</div>
        </div>
        <div className="detail-header-right">
          <div>Estado SAC: <strong>{detail.estado_sac}</strong></div>
          <div>Funcionario: {detail.funcionario}</div>
          <div>Fecha: {detail.fecha_creacion}</div>
          {detail.is_vencido && <div style={{ color: 'var(--danger)', fontWeight: 'bold' }}>Plazo: VENCIDO</div>}
        </div>
      </div>

      {/* Status Strip */}
      <div className="detail-status-strip">
        {detail.etapa_tramite === 'FALTA_APROBACION' && (
          <span className="etapa-badge etapa-badge-aprobacion" style={{ fontSize: '0.8rem', padding: '4px 10px' }}>
            ✍️ Contestado · Falta Aprobación
          </span>
        )}
        {detail.etapa_tramite === 'POR_GESTIONAR' && (
          <span className="etapa-badge etapa-badge-gestionar" style={{ fontSize: '0.8rem', padding: '4px 10px' }}>
            ⏳ Por Gestionar
          </span>
        )}
        {detail.categoria && (
          <span className="categoria-badge">
            📌 {detail.categoria}
          </span>
        )}
        {detail.is_vencido && <span style={{ color: 'var(--danger)', fontWeight: 800 }}>🔴 VENCIDO ·</span>}
        {detail.respuesta_actual && detail.respuesta_actual.trim() ? (
          <span style={{ color: '#059669', fontWeight: 700 }}>✅ CON BORRADOR DE RESPUESTA ·</span>
        ) : (
          <span style={{ color: 'var(--warning)', fontWeight: 700 }}>⚠️ PENDIENTE DE RESPUESTA ·</span>
        )}
        <span>{detail.documents.length} DOCUMENTOS</span>
        <span>·</span>
        <span>{detail.findings.length} HALLAZGOS</span>
        {totalSedes > 0 && (
          <>
            <span>·</span>
            <span style={{ color: 'var(--primary)', fontWeight: 700 }}>🏫 {totalSedes} SEDES REPORTADAS</span>
          </>
        )}
        {detail.alerts.map((alert, i) => (
          <React.Fragment key={i}>
            <span>·</span>
            <span style={{ color: 'var(--danger)', fontWeight: 700 }}>🚩 {alert.type}</span>
          </React.Fragment>
        ))}
      </div>

      {/* Central 2-Column Responsive Layout */}
      {(() => {
        const hasOfficialResponse = Boolean(
          detail.respuesta_actual &&
          detail.respuesta_actual.trim() &&
          detail.respuesta_actual.trim().toLowerCase() !== (detail.summary || '').trim().toLowerCase() &&
          (detail.etapa_tramite === 'FALTA_APROBACION' || detail.documents.some(d => d.document_type === 'RESPUESTA_OFICIAL' || d.document_type === 'RESPUESTA_PRELIMINAR'))
        );

        const isResponseDoc = (doc: DocumentItem) => {
          const t = (doc.document_type || '').toUpperCase();
          const f = (doc.filename || '').toUpperCase();
          return t.includes('RESPUESTA') || f.includes('RESPUESTA') || f.includes('OFICIO_RESPUESTA');
        };

        const petitionerDocs = detail.documents.filter(doc => !isResponseDoc(doc));
        const responseDocs = detail.documents.filter(doc => isResponseDoc(doc));

        return (
          <div className={`detail-grid ${hasOfficialResponse ? 'detail-grid-with-response' : 'detail-grid-no-response'}`}>
            {/* Columna Izquierda: Contexto de la Petición y Documentos del Solicitante (Entrada) */}
            <div className="panel-left">
              {/* Card 1: Resumen de la Solicitud */}
              <div className="detail-section-card">
                <div className="section-title">RESUMEN DE LA SOLICITUD (CONTEXTO PARA APROBACIÓN)</div>
                <p className="summary-text">{detail.summary}</p>
              </div>

              {/* Card 2: Datos Clave */}
              <div className="detail-section-card">
                <div className="section-title">DATOS CLAVE DEL RADICADO</div>
                <div className="key-data-grid">
                  <div className="bullet-item">
                    <span>📍</span>
                    <span>Municipio(s): <strong>{detail.key_data.municipality}</strong></span>
                  </div>
                  <div className="bullet-item">
                    <span>👤</span>
                    <span>Remitente: <strong>{detail.key_data.requester}</strong></span>
                  </div>
                  {detail.categoria && (
                    <div className="bullet-item">
                      <span>📌</span>
                      <span>Categoría: <strong>{detail.categoria}</strong></span>
                    </div>
                  )}
                  <div className="bullet-item">
                    <span>⏱️</span>
                    <span>Plazo legal: <strong>{detail.dias_plazo}</strong></span>
                  </div>
                </div>
              </div>

              {/* Card 3: Peticiones Concretas (si existen) */}
              {detail.requests && detail.requests.length > 0 && (
                <div className="detail-section-card">
                  <div className="section-title">PETICIONES CONCRETAS (SOLICITA)</div>
                  <div className="requests-list">
                    {detail.requests.map((req, i) => (
                      <div key={i} className="bullet-item">
                        <span style={{ color: 'var(--primary)', fontWeight: 'bold' }}>•</span>
                        <span>{req}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Card 4: Instituciones Educativas y Sedes Afectadas (si existen) */}
              {detail.instituciones_sedes && detail.instituciones_sedes.length > 0 && (
                <div className="instituciones-block">
                  <div className="section-title" style={{ color: '#0369a1' }}>
                    🏫 INSTITUCIONES EDUCATIVAS Y SEDES AFECTADAS ({totalSedes} sedes en {detail.instituciones_sedes.length} planteles)
                  </div>
                  <div className="instituciones-list">
                    {detail.instituciones_sedes.map((item, idx) => (
                      <div key={idx} className="institucion-card">
                        <div className="institucion-title-row">
                          <span className="institucion-name">🏛️ {item.institucion}</span>
                          {item.municipio && (
                            <span className="institucion-muni-pill">📍 {item.municipio}</span>
                          )}
                        </div>
                        <div className="sedes-tags-wrapper">
                          {item.sedes && item.sedes.map((sede, sIdx) => (
                            <span key={sIdx} className="sede-chip">
                              🏷️ {sede}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Card 5: Documentos del Solicitante (Anexos del Ciudadano) */}
              <div className="detail-section-card">
                <div className="section-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>DOCUMENTOS DEL SOLICITANTE ({petitionerDocs.length})</span>
                  {petitionerDocs.length > 0 && (
                    <span style={{ fontSize: '0.75rem', fontWeight: 500, color: '#64748b' }}>Clic para abrir visor</span>
                  )}
                </div>
                {petitionerDocs.length === 0 ? (
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                    No se registraron documentos anexos del peticionario en la radicación inicial.
                  </p>
                ) : (
                  <div className="documents-cards-container">
                    {petitionerDocs.map((doc) => (
                      <DocumentCard
                        key={doc.id}
                        document={doc}
                        onClick={() =>
                          navigate(`/radicado/${encodeURIComponent(detail.radicado)}/documento/${encodeURIComponent(doc.id)}`)
                        }
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Card 6: Hallazgos Clave Extraídos (si existen) */}
              {detail.findings && detail.findings.length > 0 && (
                <div className="detail-section-card">
                  <div className="section-title">HALLAZGOS CLAVE EXTRAÍDOS</div>
                  <div className="findings-list">
                    {detail.findings.map((f, i) => (
                      <div key={i} className="fact-item">
                        <span className="fact-diamond">◆</span>
                        <span>{f.fact}</span>
                        <span className="fact-source">({f.source_doc})</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Columna Derecha: Respuesta Oficial del Funcionario (Salida y Aprobación) */}
            <div className="panel-right">
              {/* Card 1: Respuesta Oficial Proyectada (Solo si existe borrador oficial proyectado) */}
              {hasOfficialResponse ? (
                <>
                  <div className="official-response-box">
                    <div className="official-response-header">
                      <div className="official-response-title-group">
                        <span className="official-response-badge">✍️ RESPUESTA PROYECTADA POR EL FUNCIONARIO</span>
                        <span className="official-response-tag">Listo para Aprobación</span>
                      </div>
                      <div className="official-response-meta">
                        Funcionario: <strong>{detail.funcionario}</strong>
                      </div>
                    </div>
                    <div className="official-response-body">
                      <div className="official-response-text">{detail.respuesta_actual}</div>
                    </div>
                    <div className="official-response-note">
                      ℹ️ Esta es la respuesta que el funcionario redactó y cargó en SAC. Evalúe el contenido técnico antes de firmar o devolver el radicado.
                    </div>
                  </div>

                  {/* Card 2: Documento Oficial de Respuesta */}
                  <div className="detail-section-card">
                    <div className="section-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>DOCUMENTO OFICIAL DE RESPUESTA ({responseDocs.length})</span>
                      {responseDocs.length > 0 && (
                        <span style={{ fontSize: '0.75rem', fontWeight: 500, color: '#64748b' }}>Clic para abrir visor</span>
                      )}
                    </div>
                    {responseDocs.length === 0 ? (
                      <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                        El funcionario redactó la pre-respuesta directamente en el formulario SAC.
                      </p>
                    ) : (
                      <div className="documents-cards-container">
                        {responseDocs.map((doc) => (
                          <DocumentCard
                            key={doc.id}
                            document={doc}
                            onClick={() =>
                              navigate(`/radicado/${encodeURIComponent(detail.radicado)}/documento/${encodeURIComponent(doc.id)}`)
                            }
                          />
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Card 3: Panel de Aprobación y Despacho del Líder */}
                  {detail.estado_sac === 'TRAMITADO' || detail.estado_sac === 'APROBADO' ? (
                    <div className="detail-section-card" style={{ background: '#f0fdf4', border: '1px solid #86efac', marginTop: '16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span style={{ fontSize: '1.8rem' }}>📁</span>
                        <div>
                          <div style={{ fontWeight: 700, color: '#166534', fontSize: '1.05rem' }}>Expediente Tramitado y Archivado</div>
                          <div style={{ fontSize: '0.85rem', color: '#15803d', marginTop: '2px' }}>
                            Este requerimiento ya fue aprobado y despachado oficialmente. Su constancia reposa en el Archivo Digital de BotSAC.
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="detail-section-card" style={{ background: '#f8fafc', border: '1px solid #cbd5e1', marginTop: '16px' }}>
                      <div className="section-title">ACCIONES DE DESPACHO OFICIAL (LÍDER DE OFICINA)</div>
                      <p style={{ fontSize: '0.875rem', color: '#475569', marginBottom: '14px', lineHeight: 1.5 }}>
                        Al aprobar este requerimiento, se registrará el visto bueno formal en la base institucional, el oficio se despachará y el expediente se archivará fuera de la bandeja de trabajo activa.
                      </p>
                      <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
                        <button
                          className="btn-primary"
                          style={{ background: '#16a34a', borderColor: '#15803d', color: '#ffffff', padding: '10px 22px', fontWeight: 700, fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '8px', cursor: approving ? 'wait' : 'pointer' }}
                          onClick={handleApprove}
                          disabled={approving}
                        >
                          <span>{approving ? '⏳' : '✅'}</span>
                          <span>{approving ? 'Despachando...' : 'Aprobar y Despachar'}</span>
                        </button>
                        {approveSuccess && (
                          <span style={{ color: '#15803d', fontWeight: 600, fontSize: '0.9rem' }}>
                            {approveSuccess}
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="detail-section-card" style={{ background: '#f8fafc', border: '1px dashed #cbd5e1' }}>
                  <div className="section-title" style={{ color: '#64748b' }}>GESTIÓN DE RESPUESTA INSTITUCIONAL</div>
                  <p style={{ color: '#475569', fontSize: '0.875rem', lineHeight: 1.5, marginTop: '8px' }}>
                    ⏳ Este radicado se encuentra <strong>{detail.etapa_label}</strong>. Aún no cuenta con borrador de respuesta proyectado por el funcionario asignado.
                  </p>
                </div>
              )}

              {/* Accordion: Trazabilidad */}
              {detail.traceability && detail.traceability.length > 0 && (
                <details className="accordion">
                  <summary>Evidencia y trazabilidad ▸</summary>
                  <div className="accordion-body">
                    {detail.traceability.map((t, i) => (
                      <div key={i} style={{ marginBottom: '6px' }}>
                        <strong>{t.source_type}</strong>: {t.detail}
                      </div>
                    ))}
                  </div>
                </details>
              )}

              {/* Accordion: Contenido original SAC */}
              {detail.raw_metadata && (
                <details className="accordion">
                  <summary>Contenido original SAC ▸</summary>
                  <div className="accordion-body">
                    <pre className="raw-json">{detail.raw_metadata}</pre>
                  </div>
                </details>
              )}
            </div>
          </div>
        );
      })()}
    </div>
  );
};
