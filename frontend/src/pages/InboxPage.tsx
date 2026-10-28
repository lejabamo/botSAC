import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchInbox, fetchArchivedInbox, approveRadicado, triggerWatchdog, triggerBatchProcess } from '../services/api';
import type { InboxResponse, InboxItem } from '../types';
import { InboxCard } from '../components/InboxCard';

import { useAuth } from '../contexts/AuthContext';

export const InboxPage: React.FC = () => {
  const [data, setData] = useState<InboxResponse | null>(null);
  const [archivedData, setArchivedData] = useState<InboxResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [runningWatchdog, setRunningWatchdog] = useState<boolean>(false);
  const [watchdogFeedback, setWatchdogFeedback] = useState<string | null>(null);
  const [runningBatch, setRunningBatch] = useState<boolean>(false);
  const [batchFeedback, setBatchFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Dynamic filter states
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedMuni, setSelectedMuni] = useState<string>('ALL');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [selectedDateMonth, setSelectedDateMonth] = useState<string>('ALL');
  const [selectedEtapa, setSelectedEtapa] = useState<string>('ALL');
  const [appliedFeedback, setAppliedFeedback] = useState<boolean>(false);

  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleRunBatch = async (batchSize = 3) => {
    try {
      setRunningBatch(true);
      setBatchFeedback(null);
      const res = await triggerBatchProcess(batchSize);
      await loadData(true);
      setBatchFeedback(
        `⚡ Bloque procesado exitosamente: ${res.processed_count} radicados poblados en Oracle con respuestas del funcionario y sedes. Restantes en cola: ${res.remaining_pending}.`
      );
      setTimeout(() => setBatchFeedback(null), 8000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error al procesar bloque de radicados.');
    } finally {
      setRunningBatch(false);
    }
  };

  const handleRunWatchdog = async () => {
    try {
      setRunningWatchdog(true);
      setWatchdogFeedback(null);
      const res = await triggerWatchdog();
      await loadData(true);
      setWatchdogFeedback(
        `🛡️ Watchdog: ${res.active_por_aprobar_count} activos por aprobar. Se reconciliaron ${res.tramitados_count} como tramitados.`
      );
      setTimeout(() => setWatchdogFeedback(null), 7000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error al ejecutar Watchdog SAC.');
    } finally {
      setRunningWatchdog(false);
    }
  };

  const handleApproveFromCard = async (radicadoId: string) => {
    if (!window.confirm(`¿Aprobar y despachar oficialmente el radicado ${radicadoId}?\nEl expediente será archivado y saldrá de la bandeja de trabajo activa.`)) {
      return;
    }
    try {
      await approveRadicado(radicadoId);
      await loadData(true);
      setWatchdogFeedback(`✅ Radicado ${radicadoId} aprobado exitosamente. Se ha trasladado al cajón de Tramitados.`);
      setTimeout(() => setWatchdogFeedback(null), 6000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al aprobar radicado');
    }
  };

  const handleLogout = () => {
    setData(null);
    logout();
    navigate('/login');
  };

  const loadData = async (isManualRefresh = false) => {
    if (!user?.username) {
      setData(null);
      setLoading(false);
      return;
    }
    try {
      if (isManualRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);
      const [res, archRes] = await Promise.all([
        fetchInbox(user?.username),
        fetchArchivedInbox().catch(() => null)
      ]);
      setData(res);
      setArchivedData(archRes);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Ocurrió un error inesperado al conectar con el servidor.');
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (user?.username) {
      loadData();
    } else {
      setData(null);
    }
  }, [user?.username]);

  // Auto-refresco agéntico: Si hay radicados en cola o en preparación, sincronizar automáticamente
  // para que el líder vea cómo los expedientes procesados suben a la cabecera en tiempo real
  useEffect(() => {
    if (!user?.username || !data?.items) return;
    const hasPendingExtraction = data.items.some(
      (i) => i.estado_botsac === 'PREPARANDO' || i.estado_botsac === 'PENDIENTE'
    );
    if (!hasPendingExtraction) return;

    const interval = setInterval(() => {
      loadData(true);
    }, 20000);

    return () => clearInterval(interval);
  }, [user?.username, data?.items]);

  // Compute unique filter options from active and archived items
  const allAvailableItems = useMemo(() => {
    return [...(data?.items || []), ...(archivedData?.items || [])];
  }, [data, archivedData]);

  const uniqueMunicipios = useMemo(() => {
    const set = new Set<string>();
    allAvailableItems.forEach((item) => {
      if (item.municipio) {
        item.municipio.split(',').forEach((m) => {
          const trimmed = m.trim();
          if (trimmed && trimmed !== 'No disponible' && trimmed !== 'Pendiente') {
            set.add(trimmed);
          }
        });
      }
    });
    return Array.from(set).sort();
  }, [allAvailableItems]);

  const uniqueCategories = useMemo(() => {
    const set = new Set<string>();
    allAvailableItems.forEach((item) => {
      if (item.categoria) {
        set.add(item.categoria.trim());
      }
    });
    return Array.from(set).sort();
  }, [allAvailableItems]);

  const uniqueMonths = useMemo(() => {
    const set = new Set<string>();
    allAvailableItems.forEach((item) => {
      const parts = item.fecha_creacion.split('/');
      if (parts.length === 3) {
        const monthNum = parts[1];
        const year = parts[2];
        const monthNames: Record<string, string> = {
          '01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril',
          '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
          '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
        };
        const label = `${monthNames[monthNum] || monthNum} ${year}`;
        set.add(label);
      }
    });
    return Array.from(set);
  }, [allAvailableItems]);

  // Counts for workflow stage tabs
  const countFaltaAprobacion = useMemo(() => {
    return data?.items?.filter((i) => i.etapa_tramite === 'FALTA_APROBACION').length || 0;
  }, [data]);

  const countPorGestionar = useMemo(() => {
    return data?.items?.filter((i) => i.etapa_tramite === 'POR_GESTIONAR').length || 0;
  }, [data]);

  // Filter items
  const filteredItems = useMemo(() => {
    const sourceList = selectedEtapa === 'TRAMITADO'
      ? (archivedData?.items || [])
      : (data?.items || []);

    return sourceList.filter((item: InboxItem) => {
      // Search query filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchesRad = item.radicado.toLowerCase().includes(q);
        const matchesAsunto = item.asunto.toLowerCase().includes(q);
        const matchesMuni = item.municipio.toLowerCase().includes(q);
        const matchesFunc = item.funcionario.toLowerCase().includes(q);
        const matchesRem = (item.remitente || '').toLowerCase().includes(q);
        const matchesSum = item.resumen_preview.toLowerCase().includes(q);
        const matchesCat = (item.categoria || '').toLowerCase().includes(q);

        if (!matchesRad && !matchesAsunto && !matchesMuni && !matchesFunc && !matchesRem && !matchesSum && !matchesCat) {
          return false;
        }
      }

      // Workflow Stage (Etapa Tramite) filter
      if (selectedEtapa !== 'ALL' && selectedEtapa !== 'TRAMITADO') {
        if (item.etapa_tramite !== selectedEtapa) {
          return false;
        }
      }

      // Municipality filter
      if (selectedMuni !== 'ALL') {
        if (!item.municipio.toLowerCase().includes(selectedMuni.toLowerCase())) {
          return false;
        }
      }

      // Category filter
      if (selectedCategory !== 'ALL') {
        if (item.categoria !== selectedCategory) {
          return false;
        }
      }

      // Status filter
      if (selectedStatus !== 'ALL') {
        if (selectedStatus === 'VENCIDOS') {
          if (!item.is_vencido) return false;
        } else if (selectedStatus === 'LISTO') {
          if (item.estado_botsac !== 'LISTO') return false;
        } else if (selectedStatus === 'PREPARANDO') {
          if (item.estado_botsac !== 'PREPARANDO') return false;
        }
      }

      // Date month filter
      if (selectedDateMonth !== 'ALL') {
        const parts = item.fecha_creacion.split('/');
        if (parts.length === 3) {
          const monthNum = parts[1];
          const year = parts[2];
          const monthNames: Record<string, string> = {
            '01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril',
            '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
            '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
          };
          const label = `${monthNames[monthNum] || monthNum} ${year}`;
          if (label !== selectedDateMonth) return false;
        } else {
          return false;
        }
      }

      return true;
    }).sort((a: InboxItem, b: InboxItem) => {
      // Orden inteligente de gestión:
      // 1. LISTO primero (con documentos adjuntos y expediente listo para revisión)
      // 2. PREPARANDO en segundo lugar (extracción en curso)
      // 3. EN COLA SAC / PENDIENTE al final (solo metadatos, esperando turno)
      const getPriority = (item: InboxItem) => {
        if (item.estado_botsac === 'LISTO') return 0;
        if (item.estado_botsac === 'PREPARANDO') return 1;
        if (item.estado_botsac === 'ERROR') return 3;
        return 2; // PENDIENTE / EN COLA SAC
      };

      const prioA = getPriority(a);
      const prioB = getPriority(b);
      if (prioA !== prioB) {
        return prioA - prioB;
      }

      // Desempate por fecha de creación más reciente (DD/MM/YYYY)
      const parseDate = (dStr: string) => {
        const parts = (dStr || '').split('/');
        if (parts.length === 3) {
          return new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0])).getTime();
        }
        return 0;
      };

      return parseDate(b.fecha_creacion) - parseDate(a.fecha_creacion);
    });
  }, [data, archivedData, searchQuery, selectedEtapa, selectedMuni, selectedCategory, selectedStatus, selectedDateMonth]);

  const hasActiveFilters = searchQuery !== '' || selectedEtapa !== 'ALL' || selectedMuni !== 'ALL' || selectedCategory !== 'ALL' || selectedStatus !== 'ALL' || selectedDateMonth !== 'ALL';

  const clearFilters = () => {
    setSearchQuery('');
    setSelectedEtapa('ALL');
    setSelectedMuni('ALL');
    setSelectedCategory('ALL');
    setSelectedStatus('ALL');
    setSelectedDateMonth('ALL');
  };

  return (
    <div className="app-container">
      {/* Top Header */}
      <div className="app-header">
        <div className="app-header-left">
          <h1 className="app-title">Bandeja de trabajo</h1>
          <div className="app-subtitle">
            Sub-Dependencia: <strong>Infraestructura Educativa</strong> · Gobernación del Cauca · Última actualización: {data ? data.updated_at : '...'}
          </div>
        </div>

        <div className="app-header-right" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {user && (
            <div className="user-profile-badge">
              <div className="user-avatar">{user.name.charAt(0)}</div>
              <div className="user-info">
                <span className="user-name">{user.name}</span>
                <span className="user-role">{user.role}</span>
              </div>
              <button className="btn-logout" onClick={handleLogout} title="Cerrar sesión">✕</button>
            </div>
          )}
          {user?.rol_principal === 'LIDER_OFICINA' && (
            <>
              <button
                className="btn-refresh"
                style={{ background: '#2563eb', borderColor: '#1d4ed8', color: '#ffffff' }}
                onClick={() => handleRunBatch(3)}
                disabled={runningBatch || runningWatchdog || refreshing || loading}
                title="Procesar progresivamente por bloques de 3 radicados poblando Oracle con respuestas del funcionario y sedes"
              >
                <span className={runningBatch ? 'spin-icon' : ''}>{runningBatch ? '⏳' : '⚡'}</span>
                {runningBatch ? 'Procesando bloque...' : 'Procesar Bloque (3)'}
              </button>
              <button
                className="btn-refresh"
                style={{ background: '#0f766e', borderColor: '#0d9488' }}
                onClick={handleRunWatchdog}
                disabled={runningWatchdog || runningBatch || refreshing || loading}
                title="Ejecutar Watchdog para verificar y reconciliar con SAC en tiempo real"
              >
                <span className={runningWatchdog ? 'spin-icon' : ''}>🛡️</span>
                {runningWatchdog ? 'Verificando SAC...' : 'Watchdog SAC'}
              </button>
            </>
          )}
          <button
            className="btn-refresh"
            onClick={() => loadData(true)}
            disabled={loading || refreshing || runningWatchdog || runningBatch}
            aria-label="Actualizar bandeja"
          >
            <span className={refreshing ? 'spin-icon' : ''}>🔄</span>
            {refreshing ? 'Sincronizando...' : 'Actualizar bandeja'}
          </button>
        </div>
      </div>

      {/* Batch Feedback Toast */}
      {batchFeedback && (
        <div style={{
          padding: '12px 18px',
          background: '#eff6ff',
          border: '1px solid #3b82f6',
          borderRadius: '8px',
          color: '#1e40af',
          fontSize: '0.9rem',
          fontWeight: 600,
          marginBottom: '12px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          animation: 'fadeIn 0.3s'
        }}>
          <span>⚡</span>
          <span>{batchFeedback}</span>
        </div>
      )}

      {/* Watchdog Feedback Toast */}
      {watchdogFeedback && (
        <div style={{
          padding: '10px 16px',
          background: '#ecfdf5',
          border: '1px solid #10b981',
          borderRadius: '8px',
          color: '#065f46',
          fontSize: '0.9rem',
          fontWeight: 600,
          marginBottom: '12px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          animation: 'fadeIn 0.3s'
        }}>
          <span>✓</span>
          <span>{watchdogFeedback}</span>
        </div>
      )}

      {/* Metrics Strip */}
      {data && (
        <div className="metrics-strip">
          <div className="metric-pill">
            <span className="metric-num">{data.summary.pending_sac}</span>
            <span className="metric-label">Pendientes de Gestión</span>
          </div>
          <span className="metric-divider">|</span>
          <div className="metric-pill">
            <span className="metric-num" style={{ color: '#d97706' }}>{countFaltaAprobacion}</span>
            <span className="metric-label">Por Aprobar ✍️</span>
          </div>
          <span className="metric-divider">|</span>
          <div className="metric-pill">
            <span className="metric-num" style={{ color: '#0284c7' }}>{countPorGestionar}</span>
            <span className="metric-label">No Diligenciados ⏳</span>
          </div>
          <span className="metric-divider">|</span>
          <div className="metric-pill metric-pill-ready">
            <span className="metric-num">{data.summary.ready}</span>
            <span className="metric-label">Listos (IA) ✓</span>
          </div>
          <span className="metric-divider">|</span>
          <div
            className={`metric-pill ${selectedEtapa === 'TRAMITADO' ? 'metric-pill-active' : ''}`}
            style={{ cursor: 'pointer' }}
            onClick={() => setSelectedEtapa(selectedEtapa === 'TRAMITADO' ? 'ALL' : 'TRAMITADO')}
            title="Ver expedientes tramitados y archivados"
          >
            <span className="metric-num" style={{ color: '#059669' }}>{archivedData?.items?.length || 0}</span>
            <span className="metric-label">Tramitados 📁</span>
          </div>
        </div>
      )}

      {/* SAC WORKFLOW PANEL: Semáforo Oficial y Pendientes de Revisar - Aprobar */}
      {data && (
        <div className="sac-dashboard-strip">
          <div className="sac-panel-card">
            <div className="sac-panel-title">
              <span>🚦 SEMÁFORO SAC (INFRAESTRUCTURA EDUCATIVA)</span>
              <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Clic para filtrar</span>
            </div>
            <div className="sac-semaforo-row">
              <div
                className={`sac-dot-pill dot-vencido ${selectedStatus === 'VENCIDOS' ? 'active-dot' : ''}`}
                onClick={() => setSelectedStatus(selectedStatus === 'VENCIDOS' ? 'ALL' : 'VENCIDOS')}
                title="Filtrar radicados vencidos en SAC"
              >
                <span className="dot-circle red-dot"></span>
                <span className="dot-label">Vencidos:</span>
                <span className="dot-count">{data.items.filter((i) => i.is_vencido).length}</span>
              </div>
              <div
                className="sac-dot-pill"
                title="A tiempo en SAC"
              >
                <span className="dot-circle green-dot"></span>
                <span className="dot-label">A Tiempo:</span>
                <span className="dot-count">0</span>
              </div>
              <div
                className="sac-dot-pill"
                title="Por vencer en SAC"
              >
                <span className="dot-circle yellow-dot"></span>
                <span className="dot-label">Por Vencer:</span>
                <span className="dot-count">0</span>
              </div>
            </div>
          </div>

          <div className="sac-panel-card">
            <div className="sac-panel-title">
              <span>✍️ PENDIENTES DE REVISAR - APROBAR</span>
              <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Filtro rápido</span>
            </div>
            <div className="sac-aprobar-row">
              <div
                className={`sac-aprobar-item ${selectedEtapa === 'FALTA_APROBACION' ? 'active-aprobar' : ''}`}
                onClick={() => setSelectedEtapa(selectedEtapa === 'FALTA_APROBACION' ? 'ALL' : 'FALTA_APROBACION')}
                title="Clic para ver los que esperan visto bueno del líder"
              >
                <span className="aprobar-type">RESPUESTAS</span>
                <span className="aprobar-badge red-badge">{countFaltaAprobacion} POR APROBAR</span>
              </div>
              <div className="sac-aprobar-item" title="Correspondencia interna pendiente de aprobar">
                <span className="aprobar-type">CORRESPONDENCIA</span>
                <span className="aprobar-badge muted-badge">0 POR APROBAR</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* QUICK WORKFLOW TABS */}
      <div className="quick-filter-tabs">
        <button
          className={`quick-tab-btn ${selectedEtapa === 'ALL' ? 'active' : ''}`}
          onClick={() => setSelectedEtapa('ALL')}
          title="Ver todos los radicados pendientes de trabajo"
        >
          📂 Todos los pendientes <span className="tab-badge">{data?.items?.length || 0}</span>
        </button>
        <button
          className={`quick-tab-btn ${selectedEtapa === 'FALTA_APROBACION' ? 'active-approval' : ''}`}
          onClick={() => setSelectedEtapa('FALTA_APROBACION')}
          title="Filtrar radicados que ya tienen propuesta o respuesta técnica y esperan visto bueno o aprobación"
        >
          ✍️ Por Aprobar ({countFaltaAprobacion})
        </button>
        <button
          className={`quick-tab-btn ${selectedEtapa === 'POR_GESTIONAR' ? 'active' : ''}`}
          onClick={() => setSelectedEtapa('POR_GESTIONAR')}
          title="Filtrar radicados pendientes por diligenciar o sin respuesta proyectada"
        >
          ⏳ No Diligenciados ({countPorGestionar})
        </button>
        <button
          className={`quick-tab-btn ${selectedEtapa === 'TRAMITADO' ? 'active-archive' : ''}`}
          onClick={() => setSelectedEtapa('TRAMITADO')}
          title="Cajón de archivo con radicados aprobados y tramitados oficialmente"
        >
          📁 Tramitados ({archivedData?.items?.length || 0})
        </button>
      </div>

      {/* DYNAMIC FILTER BAR */}
      <div className="filters-card">
        {/* Search bar */}
        <div className="search-bar-row">
          <div className="search-input-wrapper">
            <span className="search-icon" aria-hidden="true">🔍</span>
            <input
              type="text"
              className="search-input"
              placeholder="Buscar por radicado, asunto, municipio, sede o institución..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button className="search-clear-btn" onClick={() => setSearchQuery('')}>✕</button>
            )}
          </div>
        </div>

        {/* Filter dropdowns row */}
        <div className="filter-controls-row">
          {/* Trámite / Aprobación */}
          <div className="filter-group">
            <label className="filter-label">✍️ Trámite / Estado:</label>
            <select
              className="filter-select"
              value={selectedEtapa}
              onChange={(e) => setSelectedEtapa(e.target.value)}
            >
              <option value="ALL">Todos los pendientes</option>
              <option value="FALTA_APROBACION">✍️ Por Aprobar (Falta aprobación)</option>
              <option value="POR_GESTIONAR">⏳ No Diligenciados (Por Gestionar)</option>
              <option value="TRAMITADO">📁 Tramitados / Archivados ({archivedData?.items?.length || 0})</option>
            </select>
          </div>

          {/* Municipio */}
          <div className="filter-group">
            <label className="filter-label">📍 Municipio:</label>
            <select
              className="filter-select"
              value={selectedMuni}
              onChange={(e) => setSelectedMuni(e.target.value)}
            >
              <option value="ALL">Todos los municipios ({uniqueMunicipios.length})</option>
              {uniqueMunicipios.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>

          {/* Categoría */}
          <div className="filter-group">
            <label className="filter-label">🏷️ Categoría:</label>
            <select
              className="filter-select"
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
            >
              <option value="ALL">Todas las categorías</option>
              {uniqueCategories.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          {/* Estado */}
          <div className="filter-group">
            <label className="filter-label">⚡ Estado:</label>
            <select
              className="filter-select"
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
            >
              <option value="ALL">Todos los estados</option>
              <option value="VENCIDOS">🔴 Solo Vencidos</option>
              <option value="LISTO">✓ Solo Listos</option>
              <option value="PREPARANDO">⏳ Solo en Preparación</option>
            </select>
          </div>

          {/* Fecha / Mes */}
          <div className="filter-group">
            <label className="filter-label">📅 Periodo:</label>
            <select
              className="filter-select"
              value={selectedDateMonth}
              onChange={(e) => setSelectedDateMonth(e.target.value)}
            >
              <option value="ALL">Todos los periodos</option>
              {uniqueMonths.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>

          {/* Action Buttons: Filtrar / Aplicar & Limpiar */}
          <div className="filter-group" style={{ alignSelf: 'flex-end', display: 'flex', flexDirection: 'row', gap: '8px', alignItems: 'center' }}>
            <button
              className="btn-apply-filters"
              onClick={() => {
                setAppliedFeedback(true);
                setTimeout(() => setAppliedFeedback(false), 1500);
              }}
              title="El filtrado se aplica en tiempo real automáticamente. Este botón confirma y enfoca los resultados."
            >
              {appliedFeedback ? '✓ ¡Filtrado Activo!' : '🔍 Filtrar / Aplicar'}
            </button>
            {hasActiveFilters && (
              <button className="btn-clear-filters" onClick={clearFilters}>
                ✕ Limpiar
              </button>
            )}
          </div>
        </div>

        {/* Results Counter / Active Filters Summary */}
        <div className="filter-results-bar">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <span>
              Mostrando <strong>{filteredItems.length}</strong> de <strong>{selectedEtapa === 'TRAMITADO' ? (archivedData?.items?.length || 0) : (data?.items?.length || 0)}</strong> radicados {selectedEtapa === 'TRAMITADO' ? 'tramitados' : 'pendientes'}
            </span>
            <div className="live-filter-indicator">
              <span className="pulse-dot"></span>
              {selectedEtapa === 'TRAMITADO' ? 'Cajón de archivo oficial' : 'Filtrado en tiempo real activo'}
            </div>
            {hasActiveFilters && (
              <span className="active-filters-hint">
                (Filtros activos aplicados)
              </span>
            )}
          </div>
        </div>
      </div>

      {/* FRIENDLY LOADING SKELETON */}
      {(loading || refreshing) && (
        <div className="skeleton-container" aria-live="polite">
          <div className="friendly-loading-banner">
            <div className="spinner-small"></div>
            <span>
              {refreshing ? 'Sincronizando radicados y extrayendo sedes con IA en segundo plano...' : 'Cargando y consolidando análisis de la bandeja...'}
            </span>
          </div>
          {[1, 2, 3].map((n) => (
            <div key={n} className="inbox-card-skeleton">
              <div className="skeleton-col-a">
                <div className="skeleton-line skeleton-title"></div>
                <div className="skeleton-line skeleton-sub"></div>
                <div className="skeleton-line skeleton-sub"></div>
              </div>
              <div className="skeleton-col-b">
                <div className="skeleton-line skeleton-badge"></div>
                <div className="skeleton-line skeleton-subject"></div>
                <div className="skeleton-line skeleton-body"></div>
                <div className="skeleton-line skeleton-body" style={{ width: '80%' }}></div>
              </div>
              <div className="skeleton-col-c">
                <div className="skeleton-line skeleton-status"></div>
                <div className="skeleton-line skeleton-meta"></div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ERROR STATE */}
      {error && !loading && (
        <div className="error-box">
          <div style={{ fontSize: '2rem', marginBottom: '8px' }}>⚠️</div>
          <p style={{ color: 'var(--danger)', fontWeight: 700, fontSize: '1.1rem', marginBottom: '6px' }}>
            No fue posible cargar la bandeja.
          </p>
          <p style={{ fontSize: '0.9rem', color: '#64748b', marginBottom: '16px' }}>{error}</p>
          <button className="btn-primary" onClick={() => loadData(false)}>
            🔄 Reintentar conexión
          </button>
        </div>
      )}

      {/* ITEMS LIST */}
      {!loading && !refreshing && filteredItems.length > 0 && (
        <div className="inbox-list">
          {filteredItems.map((item) => {
            const navState = {
              filteredRadicados: filteredItems.map((i) => i.radicado),
              filterLabel: selectedEtapa === 'TRAMITADO'
                ? 'Expedientes Tramitados'
                : selectedEtapa === 'FALTA_APROBACION'
                ? 'Contestados (Falta aprobación)'
                : selectedEtapa === 'POR_GESTIONAR'
                ? 'Por gestionar'
                : selectedCategory !== 'ALL'
                ? selectedCategory
                : selectedMuni !== 'ALL'
                ? selectedMuni
                : undefined
            };

            return (
              <InboxCard
                key={item.radicado}
                item={item}
                onClick={() => navigate(`/radicado/${encodeURIComponent(item.radicado)}`, { state: navState })}
                onApprove={handleApproveFromCard}
              />
            );
          })}
        </div>
      )}

      {/* EMPTY RESULTS: INBOX ZERO (Todos tramitados / Escritorio despejado) */}
      {!loading && !refreshing && data && data.items.length === 0 && selectedEtapa !== 'TRAMITADO' && (
        <div className="empty-results-box" style={{ padding: '48px 24px', background: '#ffffff', borderRadius: '12px', border: '1px solid #bbf7d0', textAlign: 'center', maxWidth: '640px', margin: '30px auto', boxShadow: '0 4px 12px rgba(16, 185, 129, 0.08)' }}>
          <div style={{ fontSize: '3.5rem', marginBottom: '12px' }}>🎉</div>
          <div style={{ fontWeight: 800, fontSize: '1.35rem', color: '#166534', marginBottom: '8px' }}>
            ¡Bandeja de trabajo al día! (Escritorio Despejado)
          </div>
          <p style={{ color: '#374151', fontSize: '0.95rem', lineHeight: '1.6', marginBottom: '20px' }}>
            No tienes radicados pendientes de gestión ni por aprobar en este momento. Todos los requerimientos asignados han sido revisados y archivados exitosamente.
          </p>
          {(archivedData?.items?.length || 0) > 0 && (
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
              <button
                className="btn-primary"
                style={{ background: '#059669', borderColor: '#047857' }}
                onClick={() => setSelectedEtapa('TRAMITADO')}
              >
                📁 Ver cajón de tramitados ({archivedData?.items?.length})
              </button>
            </div>
          )}
        </div>
      )}

      {/* EMPTY RESULTS: CAJÓN DE ARCHIVO VACÍO */}
      {!loading && !refreshing && selectedEtapa === 'TRAMITADO' && filteredItems.length === 0 && (
        <div className="empty-results-box" style={{ padding: '48px 24px', background: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', textAlign: 'center', maxWidth: '640px', margin: '30px auto' }}>
          <div style={{ fontSize: '3rem', marginBottom: '12px' }}>📁</div>
          <div style={{ fontWeight: 700, fontSize: '1.25rem', color: '#1e293b', marginBottom: '8px' }}>
            Cajón de tramitados vacío
          </div>
          <p style={{ color: '#64748b', fontSize: '0.95rem', lineHeight: '1.5', marginBottom: '20px' }}>
            Aún no hay radicados aprobados o archivados que coincidan con la búsqueda. Al aprobar los radicados en tu bandeja, se trasladarán aquí automáticamente para su auditoría y custodia.
          </p>
          <button className="btn-primary" onClick={() => setSelectedEtapa('ALL')}>
            Volver a la bandeja activa
          </button>
        </div>
      )}

      {/* EMPTY RESULTS: FILTRO SIN COINCIDENCIAS EN BANDEJA ACTIVA */}
      {!loading && !refreshing && data && data.items.length > 0 && selectedEtapa !== 'TRAMITADO' && filteredItems.length === 0 && (
        <div className="empty-results-box">
          <div style={{ fontSize: '2.5rem', marginBottom: '10px' }}>🔍</div>
          <div style={{ fontWeight: 700, fontSize: '1.1rem', color: '#334155', marginBottom: '6px' }}>
            No se encontraron radicados
          </div>
          <p style={{ color: '#64748b', fontSize: '0.9rem', marginBottom: '16px' }}>
            No hay radicados que coincidan con los criterios de búsqueda o filtros seleccionados.
          </p>
          {hasActiveFilters && (
            <button className="btn-primary" onClick={clearFilters}>
              Restablecer todos los filtros
            </button>
          )}
        </div>
      )}
    </div>
  );
};
