import React, { useState, useEffect } from 'react';
import { 
  CircleDollarSign, 
  TrendingUp, 
  TrendingDown, 
  Trash2, 
  Edit3, 
  Percent, 
  Wallet, 
  Save, 
  X, 
  RefreshCw,
  Target
} from 'lucide-react';
import type { Apuesta, ResumenApuestas } from '../types';
import { getAllApuestas, getResumenApuestas, updateApuestaResultado, updateApuesta, deleteApuesta, updateApuestaCLV } from '../api/client';

export const Apuestas: React.FC = () => {
  const [apuestas, setApuestas] = useState<Apuesta[]>([]);
  const [resumen, setResumen] = useState<ResumenApuestas | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState<'all' | 'real' | 'ficticia'>('all');
  const [marketFilter, setMarketFilter] = useState<'ALL' | 'TOTALS' | 'SPREAD' | 'MONEYLINE'>('ALL');

  // Edit Modal State
  const [editingApuesta, setEditingApuesta] = useState<Apuesta | null>(null);
  const [editTipo, setEditTipo] = useState<string>('OVER');
  const [editLinea, setEditLinea] = useState<number>(215.5);
  const [editCuota, setEditCuota] = useState<number>(1.90);
  const [editMonto, setEditMonto] = useState<number>(100000);
  const [editNotas, setEditNotas] = useState<string>('');
  const [editResultado, setEditResultado] = useState<string>('PENDIENTE');
  const [editSaving, setEditSaving] = useState<boolean>(false);
  const [editMsg, setEditMsg] = useState<{ text: string; ok: boolean } | null>(null);

  // CLV Audit Modal State
  const [clvModalApuesta, setClvModalApuesta] = useState<Apuesta | null>(null);
  const [clvLineaCierre, setClvLineaCierre] = useState<number>(0);
  const [clvCuotaCierre, setClvCuotaCierre] = useState<number>(1.90);
  const [clvSaving, setClvSaving] = useState<boolean>(false);
  const [clvMsg, setClvMsg] = useState<{ text: string; ok: boolean } | null>(null);

  const openClvModal = (a: Apuesta) => {
    setClvModalApuesta(a);
    setClvLineaCierre(Number(a.linea_cierre_casa) || Number(a.linea) || 0);
    setClvCuotaCierre(Number(a.cuota_cierre_casa) || Number(a.cuota) || 1.90);
    setClvMsg(null);
  };

  const handleSaveCLV = async () => {
    if (!clvModalApuesta) return;
    setClvSaving(true);
    try {
      await updateApuestaCLV(clvModalApuesta.id, {
        linea_cierre_casa: clvLineaCierre,
        cuota_cierre_casa: clvCuotaCierre,
      });
      setClvMsg({ text: 'Auditoría CLV guardada con éxito', ok: true });
      setTimeout(() => {
        setClvModalApuesta(null);
        loadData();
      }, 700);
    } catch (err: any) {
      setClvMsg({ text: `Error: ${err.message}`, ok: false });
    } finally {
      setClvSaving(false);
    }
  };

  const loadData = async () => {
    setLoading(true);
    try {
      const [bets, summary] = await Promise.all([
        getAllApuestas(),
        getResumenApuestas(),
      ]);
      setApuestas(bets);
      setResumen(summary);
    } catch (err: any) {
      console.error('Error al cargar apuestas:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [filterType]);

  const handleUpdateResultado = async (id: number, resultado: 'GANADA' | 'PERDIDA' | 'PUSH', cuota: number, monto: number) => {
    let ganancia = 0;
    if (resultado === 'GANADA') ganancia = (cuota - 1) * monto;
    else if (resultado === 'PERDIDA') ganancia = -monto;
    else if (resultado === 'PUSH') ganancia = 0;

    try {
      await updateApuestaResultado(id, resultado, ganancia);
      loadData();
    } catch (err: any) {
      alert(`Error al actualizar resultado: ${err.message}`);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('¿Eliminar esta apuesta? Esta acción no se puede deshacer.')) return;
    try {
      await deleteApuesta(id);
      loadData();
    } catch (err: any) {
      alert(`Error al eliminar: ${err.message}`);
    }
  };

  const openEditModal = (a: Apuesta) => {
    setEditingApuesta(a);
    setEditTipo((a.tipo_apuesta || 'OVER').toUpperCase());
    setEditLinea(Number(a.linea) || 0);
    setEditCuota(Number(a.cuota) || 1.90);
    setEditMonto(Number(a.monto) || 100000);
    setEditNotas(a.notas || '');
    setEditResultado(a.resultado || 'PENDIENTE');
    setEditMsg(null);
  };

  const closeEditModal = () => {
    setEditingApuesta(null);
    setEditMsg(null);
  };

  const handleSaveEdit = async () => {
    if (!editingApuesta) return;
    if (editMonto <= 0) {
      setEditMsg({ text: 'El monto debe ser mayor a 0', ok: false });
      return;
    }
    if (editCuota <= 1.0) {
      setEditMsg({ text: 'La cuota debe ser mayor a 1.0', ok: false });
      return;
    }

    setEditSaving(true);
    try {
      let gananciaNeta: number | undefined = undefined;
      if (editResultado === 'GANADA') {
        gananciaNeta = (editCuota - 1) * editMonto;
      } else if (editResultado === 'PERDIDA') {
        gananciaNeta = -editMonto;
      } else if (editResultado === 'PUSH') {
        gananciaNeta = 0;
      }

      await updateApuesta(editingApuesta.id, {
        tipo_apuesta: editTipo,
        linea: editLinea,
        cuota: editCuota,
        monto: editMonto,
        notas: editNotas,
        resultado: editResultado,
        ganancia_neta: gananciaNeta,
      });

      setEditMsg({ text: 'Apuesta actualizada correctamente', ok: true });
      setTimeout(() => {
        closeEditModal();
        loadData();
      }, 700);
    } catch (err: any) {
      setEditMsg({ text: `Error: ${err.message}`, ok: false });
    } finally {
      setEditSaving(false);
    }
  };

  const filteredApuestas = apuestas.filter((a) => {
    // Filter by mode (Real vs Simulado)
    if (filterType === 'real' && a.es_ficticia) return false;
    if (filterType === 'ficticia' && !a.es_ficticia) return false;

    // Filter by market type
    const t = (a.tipo_apuesta || '').toUpperCase();
    if (marketFilter === 'TOTALS' && !(t.includes('OVER') || t.includes('UNDER') || t.includes('TOTAL'))) return false;
    if (marketFilter === 'SPREAD' && !(t.includes('SPREAD') || t.includes('HANDICAP'))) return false;
    if (marketFilter === 'MONEYLINE' && !(t.includes('MONEYLINE') || t.includes('ML') || t.includes('GANADOR'))) return false;

    return true;
  });

  return (
    <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h2 style={{ fontSize: '1.8rem', fontWeight: 800, letterSpacing: '-0.5px' }}>
            Gestión de Apuestas & Rendimiento (P&L / ROI)
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', marginTop: '4px' }}>
            Métricas cuantitativas auditables de todas las selecciones automáticas y manuales (Valores en Guaraníes - Gs.).
          </p>
        </div>
        <button
          onClick={loadData}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 16px',
            borderRadius: '8px',
            border: '1px solid var(--border-subtle)',
            background: 'var(--bg-surface-elevated)',
            color: 'var(--text-primary)',
            fontSize: '0.85rem',
            fontWeight: 700,
            cursor: 'pointer'
          }}
        >
          <RefreshCw size={15} />
          Actualizar
        </button>
      </div>

      {/* 4 Summary Stat Cards */}
      {resumen && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '16px',
          marginBottom: '28px'
        }}>
          {/* Card 1: P&L */}
          <div className="glass-card" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '0.82rem', marginBottom: '8px' }}>
              <CircleDollarSign size={16} color={resumen.beneficio_neto >= 0 ? '#10b981' : '#f43f5e'} />
              <span>BENEFICIO NETO (P&L)</span>
            </div>
            <div style={{
              fontSize: '1.8rem',
              fontWeight: 800,
              fontFamily: 'JetBrains Mono',
              color: resumen.beneficio_neto >= 0 ? '#10b981' : '#f43f5e'
            }}>
              {resumen.beneficio_neto >= 0 ? '+' : ''}Gs. {Math.round(resumen.beneficio_neto).toLocaleString('es-PY')}
            </div>
          </div>

          {/* Card 2: ROI */}
          <div className="glass-card" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '0.82rem', marginBottom: '8px' }}>
              <Percent size={16} color="var(--accent-orange)" />
              <span>RETORNO DE INVERSIÓN (ROI)</span>
            </div>
            <div style={{
              fontSize: '1.8rem',
              fontWeight: 800,
              fontFamily: 'JetBrains Mono',
              color: resumen.roi_porcentaje >= 0 ? '#10b981' : '#f43f5e'
            }}>
              {resumen.roi_porcentaje >= 0 ? `+${resumen.roi_porcentaje.toFixed(1)}%` : `${resumen.roi_porcentaje.toFixed(1)}%`}
            </div>
          </div>

          {/* Card 3: Win Rate */}
          <div className="glass-card" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '0.82rem', marginBottom: '8px' }}>
              <TrendingUp size={16} color="#38bdf8" />
              <span>TASA DE ACIERTO (WIN RATE)</span>
            </div>
            <div style={{
              fontSize: '1.8rem',
              fontWeight: 800,
              fontFamily: 'JetBrains Mono',
              color: '#38bdf8'
            }}>
              {resumen.win_rate.toFixed(1)}%
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              {resumen.ganadas}G - {resumen.perdidas}P - {resumen.pushes}Push
            </div>
          </div>

          {/* Card 4: Total Volume */}
          <div className="glass-card" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '0.82rem', marginBottom: '8px' }}>
              <Wallet size={16} color="var(--accent-gold)" />
              <span>VOLUMEN APOSTADO</span>
            </div>
            <div style={{
              fontSize: '1.8rem',
              fontWeight: 800,
              fontFamily: 'JetBrains Mono',
              color: '#fff'
            }}>
              Gs. {Math.round(resumen.total_apostado).toLocaleString('es-PY')}
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              {resumen.total_apuestas} apuestas registradas
            </div>
          </div>
        </div>
      )}

      {/* Filter tabs: Modalidad & Mercado */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
        {/* Modalidad tabs */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={() => setFilterType('all')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.82rem',
              fontWeight: 700,
              background: filterType === 'all' ? 'var(--accent-orange)' : 'var(--bg-surface-elevated)',
              color: filterType === 'all' ? '#fff' : 'var(--text-secondary)'
            }}
          >
            Todas
          </button>
          <button
            onClick={() => setFilterType('real')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.82rem',
              fontWeight: 700,
              background: filterType === 'real' ? '#10b981' : 'var(--bg-surface-elevated)',
              color: filterType === 'real' ? '#fff' : 'var(--text-secondary)'
            }}
          >
            Reales
          </button>
          <button
            onClick={() => setFilterType('ficticia')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.82rem',
              fontWeight: 700,
              background: filterType === 'ficticia' ? 'var(--bg-surface)' : 'var(--bg-surface-elevated)',
              color: filterType === 'ficticia' ? 'var(--accent-orange)' : 'var(--text-secondary)'
            }}
          >
            Simuladas (Test)
          </button>
        </div>

        {/* Market Filter tabs */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(0,0,0,0.3)', padding: '4px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
          <button
            onClick={() => setMarketFilter('ALL')}
            style={{
              padding: '4px 10px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.78rem',
              fontWeight: 700,
              background: marketFilter === 'ALL' ? 'var(--accent-orange)' : 'transparent',
              color: marketFilter === 'ALL' ? '#fff' : 'var(--text-muted)'
            }}
          >
            Todos Mercados
          </button>
          <button
            onClick={() => setMarketFilter('TOTALS')}
            style={{
              padding: '4px 10px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.78rem',
              fontWeight: 700,
              background: marketFilter === 'TOTALS' ? 'var(--accent-orange)' : 'transparent',
              color: marketFilter === 'TOTALS' ? '#fff' : 'var(--text-muted)'
            }}
          >
            Totales (O/U)
          </button>
          <button
            onClick={() => setMarketFilter('SPREAD')}
            style={{
              padding: '4px 10px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.78rem',
              fontWeight: 700,
              background: marketFilter === 'SPREAD' ? '#38bdf8' : 'transparent',
              color: marketFilter === 'SPREAD' ? '#000' : 'var(--text-muted)'
            }}
          >
            Hándicap (Spread)
          </button>
          <button
            onClick={() => setMarketFilter('MONEYLINE')}
            style={{
              padding: '4px 10px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.78rem',
              fontWeight: 700,
              background: marketFilter === 'MONEYLINE' ? '#a78bfa' : 'transparent',
              color: marketFilter === 'MONEYLINE' ? '#fff' : 'var(--text-muted)'
            }}
          >
            Moneyline
          </button>
        </div>
      </div>

      {/* Bets Table */}
      <div className="glass-card" style={{ padding: '20px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-secondary)' }}>
            Cargando historial de apuestas...
          </div>
        ) : filteredApuestas.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
            No hay apuestas registradas en esta categoría.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1.5px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
                  <th style={{ padding: '10px 12px' }}>Partido</th>
                  <th style={{ padding: '10px 12px' }}>Mercado / Selección</th>
                  <th style={{ padding: '10px 12px' }}>Grado DL</th>
                  <th style={{ padding: '10px 12px' }}>Línea</th>
                  <th style={{ padding: '10px 12px' }}>Cuota</th>
                  <th style={{ padding: '10px 12px' }}>Monto</th>
                  <th style={{ padding: '10px 12px' }}>EV / Prob</th>
                  <th style={{ padding: '10px 12px' }}>Auditoría CLV</th>
                  <th style={{ padding: '10px 12px' }}>Modalidad</th>
                  <th style={{ padding: '10px 12px' }}>Estado</th>
                  <th style={{ padding: '10px 12px', textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {filteredApuestas.map((a, idx) => {
                  const isPending = a.resultado === 'PENDIENTE';
                  const isWon = a.resultado === 'GANADA';
                  const isLost = a.resultado === 'PERDIDA';
                  const tUpper = (a.tipo_apuesta || '').toUpperCase();
                  const isOver = tUpper.includes('OVER');
                  const isUnder = tUpper.includes('UNDER');
                  const isSpread = tUpper.includes('SPREAD') || tUpper.includes('HANDICAP');
                  const isML = tUpper.includes('MONEYLINE') || tUpper.includes('ML');

                  let typeColor = '#fff';
                  if (isOver) typeColor = '#10b981';
                  else if (isUnder) typeColor = '#f43f5e';
                  else if (isSpread) typeColor = '#38bdf8';
                  else if (isML) typeColor = '#a78bfa';

                  return (
                    <tr
                      key={a.id || idx}
                      style={{
                        borderBottom: '1px solid var(--border-subtle)',
                        background: idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)'
                      }}
                    >
                      <td style={{ padding: '10px 12px', fontWeight: 600 }}>
                        {a.equipo_local ? `${a.equipo_local} vs ${a.equipo_visitante}` : `Partido #${a.partido_id}`}
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span style={{ fontWeight: 800, color: typeColor }}>
                            {a.tipo_apuesta || '--'}
                          </span>
                          {a.equipo_apostado && (
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>
                              ({a.equipo_apostado})
                            </span>
                          )}
                        </div>
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        {a.grado_apuesta ? (
                          <span className="badge-tag" style={{
                            background: a.grado_apuesta.includes('A+') ? 'rgba(16,185,129,0.2)' : a.grado_apuesta.includes('A') ? 'rgba(34,197,94,0.15)' : 'rgba(234,179,8,0.15)',
                            color: a.grado_apuesta.includes('A+') ? '#10b981' : a.grado_apuesta.includes('A') ? '#22c55e' : '#eab308',
                            border: `1px solid ${a.grado_apuesta.includes('A+') ? '#10b981' : a.grado_apuesta.includes('A') ? '#22c55e' : '#eab308'}`,
                            fontWeight: 800,
                            fontSize: '0.72rem'
                          }}>
                            {a.grado_apuesta}
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>--</span>
                        )}
                      </td>
                      <td style={{ padding: '10px 12px', fontFamily: 'JetBrains Mono', fontWeight: 700 }}>
                        {a.linea !== null && a.linea !== undefined ? `${a.linea > 0 && isSpread ? '+' : ''}${a.linea}` : '--'}
                      </td>
                      <td style={{ padding: '10px 12px', fontFamily: 'JetBrains Mono', fontWeight: 700, color: '#38bdf8' }}>
                        {(Number(a.cuota) || 0).toFixed(2)}
                      </td>
                      <td style={{ padding: '10px 12px', fontFamily: 'JetBrains Mono' }}>
                        Gs. {(Number(a.monto) || 0).toLocaleString('es-PY')}
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        {a.ev_estimado != null ? (
                          <span style={{ color: a.ev_estimado > 0 ? '#10b981' : '#f43f5e', fontWeight: 700 }}>
                            {a.ev_estimado > 0 ? `+${a.ev_estimado.toFixed(1)}%` : `${a.ev_estimado.toFixed(1)}%`}
                          </span>
                        ) : a.prob_modelo != null ? (
                          <span style={{ color: '#a78bfa', fontWeight: 700 }}>
                            {(a.prob_modelo * 100).toFixed(1)}%
                          </span>
                        ) : '--'}
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        {a.clv_beat_ratio !== undefined && a.clv_beat_ratio !== null ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                            <span className="badge-tag" style={{
                              background: a.clv_beat_ratio >= 1.0 ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
                              color: a.clv_beat_ratio >= 1.0 ? '#10b981' : '#f87171',
                              border: `1px solid ${a.clv_beat_ratio >= 1.0 ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
                              fontSize: '0.7rem',
                              fontWeight: 800
                            }}>
                              {a.clv_beat_ratio >= 1.0 ? 'BEAT: ' : 'LAG: '}{a.clv_beat_ratio.toFixed(2)}x
                            </span>
                            {a.clv_delta_pts !== null && a.clv_delta_pts !== undefined && (
                              <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono' }}>
                                Δ {a.clv_delta_pts > 0 ? `+${a.clv_delta_pts.toFixed(1)}` : a.clv_delta_pts.toFixed(1)} pts
                              </span>
                            )}
                          </div>
                        ) : (
                          <button
                            onClick={() => openClvModal(a)}
                            style={{
                              background: 'rgba(255,255,255,0.05)',
                              border: '1px solid var(--border-subtle)',
                              color: 'var(--text-muted)',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              fontSize: '0.7rem',
                              cursor: 'pointer'
                            }}
                            title="Auditar valor contra línea de cierre"
                          >
                            + Auditar CLV
                          </button>
                        )}
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        <span className={`badge-tag ${a.es_ficticia ? 'badge-gold' : 'badge-green'}`} style={{ fontSize: '0.72rem' }}>
                          {a.es_ficticia ? 'Simulada' : 'Real'}
                        </span>
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        {isPending && <span className="badge-tag" style={{ background: 'rgba(255,255,255,0.1)', color: '#fff' }}>PENDIENTE</span>}
                        {isWon && <span className="badge-tag badge-green">GANADA (+Gs. {Math.round(a.ganancia_neta || (a.cuota - 1) * a.monto).toLocaleString('es-PY')})</span>}
                        {isLost && <span className="badge-tag badge-red">PERDIDA (-Gs. {Math.abs(Math.round(a.ganancia_neta || a.monto)).toLocaleString('es-PY')})</span>}
                        {a.resultado === 'PUSH' && <span className="badge-tag badge-blue">PUSH</span>}
                      </td>
                      <td style={{ padding: '10px 12px', textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                          {/* Botones de liquidación rápida si está pendiente */}
                          {isPending && (
                            <>
                              <button
                                onClick={() => handleUpdateResultado(a.id, 'GANADA', a.cuota, a.monto)}
                                title="Marcar Ganada"
                                style={{ background: 'rgba(16, 185, 129, 0.2)', border: '1px solid #10b981', color: '#10b981', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 700 }}
                              >
                                G
                              </button>
                              <button
                                onClick={() => handleUpdateResultado(a.id, 'PERDIDA', a.cuota, a.monto)}
                                title="Marcar Perdida"
                                style={{ background: 'rgba(244, 63, 94, 0.2)', border: '1px solid #f43f5e', color: '#f43f5e', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 700 }}
                              >
                                P
                              </button>
                              <button
                                onClick={() => handleUpdateResultado(a.id, 'PUSH', a.cuota, a.monto)}
                                title="Marcar Push"
                                style={{ background: 'rgba(56, 189, 248, 0.2)', border: '1px solid #38bdf8', color: '#38bdf8', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 700 }}
                              >
                                =
                              </button>
                            </>
                          )}

                          {/* Botón Auditar CLV */}
                          <button
                            onClick={() => openClvModal(a)}
                            title="Auditar Closing Line Value (CLV)"
                            style={{
                              background: 'rgba(56, 189, 248, 0.12)',
                              border: '1px solid rgba(56, 189, 248, 0.3)',
                              color: '#38bdf8',
                              padding: '4px 7px',
                              borderRadius: '4px',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center'
                            }}
                          >
                            <Target size={13} />
                          </button>

                          {/* Botón Editar */}
                          <button
                            onClick={() => openEditModal(a)}
                            title="Editar detalles de la apuesta"
                            style={{
                              background: 'rgba(251, 191, 36, 0.15)',
                              border: '1px solid rgba(251, 191, 36, 0.4)',
                              color: '#fbbf24',
                              padding: '4px 7px',
                              borderRadius: '4px',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center'
                            }}
                          >
                            <Edit3 size={13} />
                          </button>

                          {/* Botón Eliminar */}
                          <button
                            onClick={() => handleDelete(a.id)}
                            title="Eliminar apuesta"
                            style={{
                              background: 'rgba(239, 68, 68, 0.12)',
                              border: '1px solid rgba(239, 68, 68, 0.3)',
                              color: '#f87171',
                              padding: '4px 7px',
                              borderRadius: '4px',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center'
                            }}
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal de Edición de Apuesta */}
      {editingApuesta && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '20px'
        }}>
          <div className="glass-card" style={{ maxWidth: '520px', width: '100%', padding: '26px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 800, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Edit3 size={18} color="var(--accent-gold)" />
                Editar Apuesta #{editingApuesta.id}
              </h3>
              <button
                onClick={closeEditModal}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            {editMsg && (
              <div style={{
                marginBottom: '14px',
                padding: '8px 12px',
                borderRadius: '6px',
                fontSize: '0.82rem',
                fontWeight: 700,
                background: editMsg.ok ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
                border: `1px solid ${editMsg.ok ? '#10b981' : '#ef4444'}`,
                color: editMsg.ok ? '#10b981' : '#f87171'
              }}>
                {editMsg.ok ? '✅' : '❌'} {editMsg.text}
              </div>
            )}

            {/* Tipo */}
            <div style={{ marginBottom: '14px' }}>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 700, marginBottom: '6px' }}>
                TIPO DE APUESTA
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
                <button
                  type="button"
                  onClick={() => setEditTipo('OVER')}
                  style={{
                    padding: '8px 4px',
                    borderRadius: '6px',
                    border: `2px solid ${editTipo === 'OVER' ? '#10b981' : 'var(--border-subtle)'}`,
                    background: editTipo === 'OVER' ? 'rgba(16,185,129,0.15)' : 'transparent',
                    color: editTipo === 'OVER' ? '#10b981' : 'var(--text-muted)',
                    fontWeight: 800,
                    fontSize: '0.75rem',
                    cursor: 'pointer'
                  }}
                >
                  <TrendingUp size={12} style={{ display: 'inline', marginRight: '2px' }} />
                  OVER
                </button>
                <button
                  type="button"
                  onClick={() => setEditTipo('UNDER')}
                  style={{
                    padding: '8px 4px',
                    borderRadius: '6px',
                    border: `2px solid ${editTipo === 'UNDER' ? '#f43f5e' : 'var(--border-subtle)'}`,
                    background: editTipo === 'UNDER' ? 'rgba(244,63,94,0.15)' : 'transparent',
                    color: editTipo === 'UNDER' ? '#f43f5e' : 'var(--text-muted)',
                    fontWeight: 800,
                    fontSize: '0.75rem',
                    cursor: 'pointer'
                  }}
                >
                  <TrendingDown size={12} style={{ display: 'inline', marginRight: '2px' }} />
                  UNDER
                </button>
                <button
                  type="button"
                  onClick={() => setEditTipo('SPREAD')}
                  style={{
                    padding: '8px 4px',
                    borderRadius: '6px',
                    border: `2px solid ${editTipo === 'SPREAD' ? '#38bdf8' : 'var(--border-subtle)'}`,
                    background: editTipo === 'SPREAD' ? 'rgba(56,189,248,0.15)' : 'transparent',
                    color: editTipo === 'SPREAD' ? '#38bdf8' : 'var(--text-muted)',
                    fontWeight: 800,
                    fontSize: '0.75rem',
                    cursor: 'pointer'
                  }}
                >
                  SPREAD
                </button>
                <button
                  type="button"
                  onClick={() => setEditTipo('MONEYLINE')}
                  style={{
                    padding: '8px 4px',
                    borderRadius: '6px',
                    border: `2px solid ${editTipo === 'MONEYLINE' ? '#a78bfa' : 'var(--border-subtle)'}`,
                    background: editTipo === 'MONEYLINE' ? 'rgba(167,139,250,0.15)' : 'transparent',
                    color: editTipo === 'MONEYLINE' ? '#a78bfa' : 'var(--text-muted)',
                    fontWeight: 800,
                    fontSize: '0.75rem',
                    cursor: 'pointer'
                  }}
                >
                  MONEYLINE
                </button>
              </div>
            </div>

            {/* Grid Línea / Cuota / Monto */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700, marginBottom: '4px' }}>
                  LÍNEA TOTAL
                </label>
                <input
                  type="number"
                  step="0.5"
                  value={editLinea}
                  onChange={e => setEditLinea(Number(e.target.value))}
                  style={{
                    width: '100%',
                    background: 'var(--bg-surface-elevated)',
                    border: '1px solid var(--border-subtle)',
                    color: '#fff',
                    padding: '8px 10px',
                    borderRadius: '6px',
                    fontSize: '1rem',
                    fontWeight: 800,
                    fontFamily: 'JetBrains Mono'
                  }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700, marginBottom: '4px' }}>
                  CUOTA (ODDS)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={editCuota}
                  onChange={e => setEditCuota(Number(e.target.value))}
                  style={{
                    width: '100%',
                    background: 'var(--bg-surface-elevated)',
                    border: '1px solid var(--border-subtle)',
                    color: '#38bdf8',
                    padding: '8px 10px',
                    borderRadius: '6px',
                    fontSize: '1rem',
                    fontWeight: 800,
                    fontFamily: 'JetBrains Mono'
                  }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700, marginBottom: '4px' }}>
                  MONTO (Gs.)
                </label>
                <input
                  type="number"
                  step="10000"
                  value={editMonto}
                  onChange={e => setEditMonto(Number(e.target.value))}
                  style={{
                    width: '100%',
                    background: 'var(--bg-surface-elevated)',
                    border: '1px solid var(--border-subtle)',
                    color: '#fff',
                    padding: '8px 10px',
                    borderRadius: '6px',
                    fontSize: '1rem',
                    fontWeight: 800,
                    fontFamily: 'JetBrains Mono'
                  }}
                />
              </div>
            </div>

            {/* Resultado */}
            <div style={{ marginBottom: '14px' }}>
              <label style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700, marginBottom: '4px' }}>
                RESULTADO / ESTADO
              </label>
              <select
                value={editResultado}
                onChange={e => setEditResultado(e.target.value)}
                style={{
                  width: '100%',
                  background: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-subtle)',
                  color: '#fff',
                  padding: '8px 10px',
                  borderRadius: '6px',
                  fontSize: '0.9rem',
                  fontWeight: 700
                }}
              >
                <option value="PENDIENTE">PENDIENTE (En curso)</option>
                <option value="GANADA">GANADA (Acertada)</option>
                <option value="PERDIDA">PERDIDA (Fallo)</option>
                <option value="PUSH">PUSH (Empate / Anulada)</option>
              </select>
            </div>

            {/* Notas */}
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700, marginBottom: '4px' }}>
                NOTAS / OBSERVACIONES
              </label>
              <input
                type="text"
                value={editNotas}
                onChange={e => setEditNotas(e.target.value)}
                placeholder="Observaciones de la apuesta..."
                style={{
                  width: '100%',
                  background: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-subtle)',
                  color: '#fff',
                  padding: '8px 10px',
                  borderRadius: '6px',
                  fontSize: '0.85rem'
                }}
              />
            </div>

            {/* Botones de acción */}
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={closeEditModal}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-subtle)',
                  background: 'transparent',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  fontWeight: 700,
                  fontSize: '0.85rem'
                }}
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleSaveEdit}
                disabled={editSaving}
                className="btn-primary"
                style={{
                  padding: '8px 20px',
                  borderRadius: '6px',
                  fontWeight: 800,
                  fontSize: '0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <Save size={15} />
                {editSaving ? 'Guardando...' : 'Guardar Cambios'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Auditoría CLV */}
      {clvModalApuesta && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '20px'
        }}>
          <div className="glass-card" style={{ maxWidth: '440px', width: '100%', padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 800, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Target size={18} color="#38bdf8" />
                Auditoría CLV (Closing Line Value)
              </h3>
              <button
                onClick={() => setClvModalApuesta(null)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '16px' }}>
              Compara la cuota y línea apostada con el cierre de la casa para verificar si lograste batir al mercado institucional.
            </p>

            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '12px', borderRadius: '8px', marginBottom: '16px', fontSize: '0.82rem' }}>
              <div>Apuesta: <strong style={{ color: '#fff' }}>{clvModalApuesta.tipo_apuesta} {clvModalApuesta.linea}</strong></div>
              <div>Cuota tomada: <strong style={{ color: '#10b981' }}>{clvModalApuesta.cuota}</strong></div>
            </div>

            {clvMsg && (
              <div style={{
                marginBottom: '14px',
                padding: '8px 12px',
                borderRadius: '6px',
                fontSize: '0.82rem',
                fontWeight: 700,
                background: clvMsg.ok ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
                border: `1px solid ${clvMsg.ok ? '#10b981' : '#ef4444'}`,
                color: clvMsg.ok ? '#10b981' : '#f87171'
              }}>
                {clvMsg.text}
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '20px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  Línea Cierre Casa
                </label>
                <input
                  type="number"
                  step="0.5"
                  value={clvLineaCierre}
                  onChange={(e) => setClvLineaCierre(Number(e.target.value))}
                  style={{
                    width: '100%',
                    background: 'var(--bg-surface-elevated)',
                    border: '1px solid var(--border-subtle)',
                    color: '#fff',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    fontSize: '0.95rem',
                    fontFamily: 'JetBrains Mono'
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  Cuota Cierre Casa
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={clvCuotaCierre}
                  onChange={(e) => setClvCuotaCierre(Number(e.target.value))}
                  style={{
                    width: '100%',
                    background: 'var(--bg-surface-elevated)',
                    border: '1px solid var(--border-subtle)',
                    color: '#fff',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    fontSize: '0.95rem',
                    fontFamily: 'JetBrains Mono'
                  }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                onClick={() => setClvModalApuesta(null)}
                className="btn-secondary"
                style={{ padding: '8px 16px', fontSize: '0.85rem' }}
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleSaveCLV}
                disabled={clvSaving}
                className="btn-primary"
                style={{ padding: '8px 16px', fontSize: '0.85rem' }}
              >
                {clvSaving ? 'Guardando...' : 'Calcular CLV'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
