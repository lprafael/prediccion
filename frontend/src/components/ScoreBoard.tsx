import React from 'react';
import { Clock, Zap, Activity } from 'lucide-react';
import type { Partido, SimulationResult } from '../types';

interface ScoreBoardProps {
  match: Partido;
  simulation?: Partial<SimulationResult> | null;
  isAutoSyncActive?: boolean;
  autoSyncInterval?: number;
  lastSyncTime?: string | null;
  isSyncing?: boolean;
}

export const ScoreBoard: React.FC<ScoreBoardProps> = ({
  match,
  simulation,
  isAutoSyncActive,
  autoSyncInterval = 15,
  lastSyncTime,
  isSyncing = false
}) => {
  const padZero = (n: number) => n.toString().padStart(2, '0');

  // Format quarter title
  const getQuarterText = (q: number) => {
    if (q === 1) return '1º CUARTO';
    if (q === 2) return '2º CUARTO';
    if (q === 3) return '3º CUARTO';
    if (q === 4) return '4º CUARTO';
    if (q > 4) return match.estado === 'finalizado' ? 'FINALIZADO' : 'PRÓRROGA (OT)';
    return `CUARTO ${q}`;
  };

  // Cálculo seguro de totales con fallback a suma de marcadores_cuarto
  const totalLocal = (match.total_local !== undefined && match.total_local !== null)
    ? match.total_local
    : (match.marcadores ? match.marcadores.reduce((acc, m) => acc + (Number(m.pts_local) || 0), 0) : 0);

  const totalVisitante = (match.total_visitante !== undefined && match.total_visitante !== null)
    ? match.total_visitante
    : (match.marcadores ? match.marcadores.reduce((acc, m) => acc + (Number(m.pts_visitante) || 0), 0) : 0);

  const totalPoints = totalLocal + totalVisitante;

  return (
    <div className="glass-card" style={{ padding: '24px', position: 'relative', overflow: 'hidden' }}>
      {/* Background glow lines */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: '3px',
        background: 'linear-gradient(90deg, #ff7700 0%, #38bdf8 50%, #10b981 100%)'
      }} />

      {/* Top Header: Tournament, Status, Quarter & Clock */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px',
        marginBottom: '20px',
        borderBottom: '1px solid var(--border-subtle)',
        paddingBottom: '14px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <span style={{
            background: 'var(--bg-surface-elevated)',
            padding: '4px 10px',
            borderRadius: '6px',
            fontSize: '0.78rem',
            fontWeight: 700,
            color: 'var(--accent-orange)'
          }}>
            {match.torneo}
          </span>
          <span style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.8rem',
            fontWeight: 700,
            color: match.estado === 'en_curso' ? '#10b981' : '#94a3b8'
          }}>
            {match.estado === 'en_curso' && <span className="live-pulse" />}
            {match.estado === 'en_curso' ? 'PARTIDO EN VIVO' : 'FINALIZADO'}
          </span>

          {/* Badge indicador de auto-sync en vivo */}
          {isAutoSyncActive && (
            <span style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.75rem',
              fontWeight: 700,
              color: isSyncing ? '#fbbf24' : '#10b981',
              background: isSyncing ? 'rgba(251, 191, 36, 0.12)' : 'rgba(16, 185, 129, 0.12)',
              border: `1px solid ${isSyncing ? 'rgba(251, 191, 36, 0.3)' : 'rgba(16, 185, 129, 0.3)'}`,
              padding: '3px 8px',
              borderRadius: '6px'
            }}>
              <span className="live-pulse" style={{ width: '6px', height: '6px', background: isSyncing ? '#fbbf24' : '#10b981' }} />
              {isSyncing ? 'SINCRONIZANDO...' : `AUTO-SYNC (${autoSyncInterval}s)`}
              {lastSyncTime && <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>· {lastSyncTime}</span>}
            </span>
          )}
        </div>

        {/* Digital Period & Game Clock */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '14px',
          background: 'rgba(0, 0, 0, 0.4)',
          padding: '6px 16px',
          borderRadius: '12px',
          border: '1px solid var(--border-subtle)'
        }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '0.5px' }}>
            {getQuarterText(match.cuarto_actual)}
          </span>
          <div style={{ width: '1px', height: '18px', background: 'var(--border-subtle)' }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#ff9800', fontFamily: 'JetBrains Mono', fontWeight: 700, fontSize: '1.1rem' }}>
            <Clock size={16} />
            <span>{padZero(match.min_restantes)}:{padZero(match.seg_restantes)}</span>
          </div>
        </div>
      </div>

      {/* Main Scoreboard: Home vs Away */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr auto 1fr',
        alignItems: 'center',
        gap: '20px',
        textAlign: 'center'
      }}>
        {/* Local Team */}
        <div style={{ textAlign: 'right', paddingRight: '10px' }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#f8fafc', marginBottom: '6px' }}>
            {match.equipo_local}
          </h2>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>
            LOCAL
          </div>
          {match.fouls_local !== undefined && (
            <div style={{ marginTop: '4px', fontSize: '0.76rem', color: (match.fouls_local ?? 0) >= 5 ? '#ef4444' : 'var(--text-muted)' }}>
              Faltas: <strong style={{ color: (match.fouls_local ?? 0) >= 5 ? '#ef4444' : '#e2e8f0' }}>{match.fouls_local ?? 0}</strong>{' '}
              {(match.fouls_local ?? 0) >= 5 && (
                <span style={{ background: 'rgba(239, 68, 68, 0.2)', border: '1px solid #ef4444', color: '#ef4444', padding: '1px 5px', borderRadius: '4px', fontSize: '0.68rem', fontWeight: 800 }}>
                  BONUS
                </span>
              )}
            </div>
          )}
          {simulation?.win_prob_a != null && (
            <div style={{ marginTop: '8px', fontSize: '0.85rem', color: '#10b981', fontWeight: 700 }}>
              {(Number(simulation.win_prob_a) * 100).toFixed(1)}% victoria
            </div>
          )}
        </div>

        {/* Digital Scores Center */}
        <div style={{
          background: 'radial-gradient(circle, rgba(255, 119, 0, 0.12) 0%, rgba(15, 22, 38, 0.8) 100%)',
          border: '1.5px solid var(--border-subtle)',
          borderRadius: '16px',
          padding: '12px 30px',
          display: 'flex',
          alignItems: 'center',
          gap: '20px',
          boxShadow: 'inset 0 0 20px rgba(0,0,0,0.5)'
        }}>
          <span style={{
            fontFamily: 'JetBrains Mono',
            fontSize: '3.2rem',
            fontWeight: 800,
            color: '#fff',
            textShadow: '0 0 20px rgba(255, 255, 255, 0.4)'
          }}>
            {totalLocal}
          </span>
          <span style={{ fontSize: '2rem', color: 'var(--text-muted)', fontWeight: 300 }}>:</span>
          <span style={{
            fontFamily: 'JetBrains Mono',
            fontSize: '3.2rem',
            fontWeight: 800,
            color: '#fff',
            textShadow: '0 0 20px rgba(255, 255, 255, 0.4)'
          }}>
            {totalVisitante}
          </span>
        </div>

        {/* Visitor Team */}
        <div style={{ textAlign: 'left', paddingLeft: '10px' }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#f8fafc', marginBottom: '6px' }}>
            {match.equipo_visitante}
          </h2>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>
            VISITANTE
          </div>
          {match.fouls_visitante !== undefined && (
            <div style={{ marginTop: '4px', fontSize: '0.76rem', color: (match.fouls_visitante ?? 0) >= 5 ? '#ef4444' : 'var(--text-muted)' }}>
              Faltas: <strong style={{ color: (match.fouls_visitante ?? 0) >= 5 ? '#ef4444' : '#e2e8f0' }}>{match.fouls_visitante ?? 0}</strong>{' '}
              {(match.fouls_visitante ?? 0) >= 5 && (
                <span style={{ background: 'rgba(239, 68, 68, 0.2)', border: '1px solid #ef4444', color: '#ef4444', padding: '1px 5px', borderRadius: '4px', fontSize: '0.68rem', fontWeight: 800 }}>
                  BONUS
                </span>
              )}
            </div>
          )}
          {simulation?.win_prob_b != null && (
            <div style={{ marginTop: '8px', fontSize: '0.85rem', color: '#38bdf8', fontWeight: 700 }}>
              {(Number(simulation.win_prob_b) * 100).toFixed(1)}% victoria
            </div>
          )}
        </div>
      </div>

      {/* Quarter Breakdown Mini-Table */}
      {match.marcadores && match.marcadores.length > 0 && (
        <div style={{
          marginTop: '18px',
          display: 'flex',
          justifyContent: 'center',
          overflowX: 'auto',
        }}>
          <table style={{
            borderCollapse: 'collapse',
            fontSize: '0.82rem',
            fontFamily: 'JetBrains Mono, monospace',
            textAlign: 'center',
            background: 'rgba(0, 0, 0, 0.35)',
            borderRadius: '8px',
            overflow: 'hidden',
            border: '1px solid var(--border-subtle)'
          }}>
            <thead>
              <tr style={{ background: 'rgba(255, 255, 255, 0.04)', color: 'var(--text-muted)' }}>
                <th style={{ padding: '6px 14px', textAlign: 'left', fontWeight: 600 }}>EQUIPO</th>
                <th style={{ padding: '6px 12px' }}>1Q</th>
                <th style={{ padding: '6px 12px' }}>2Q</th>
                <th style={{ padding: '6px 12px' }}>3Q</th>
                <th style={{ padding: '6px 12px' }}>4Q</th>
                <th style={{ padding: '6px 14px', color: 'var(--accent-orange)' }}>TOT</th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderTop: '1px solid var(--border-subtle)' }}>
                <td style={{ padding: '6px 14px', textAlign: 'left', fontWeight: 700, color: '#f8fafc' }}>
                  {match.equipo_local}
                </td>
                {[1, 2, 3, 4].map(q => {
                  const m = match.marcadores?.find(item => item.cuarto === q);
                  const isCurrent = match.cuarto_actual === q && match.estado === 'en_curso';
                  return (
                    <td key={q} style={{
                      padding: '6px 12px',
                      color: isCurrent ? '#ff9933' : 'var(--text-secondary)',
                      fontWeight: isCurrent ? 800 : 500
                    }}>
                      {m ? m.pts_local : '-'}
                    </td>
                  );
                })}
                <td style={{ padding: '6px 14px', fontWeight: 800, color: '#fff' }}>{totalLocal}</td>
              </tr>
              <tr style={{ borderTop: '1px solid var(--border-subtle)' }}>
                <td style={{ padding: '6px 14px', textAlign: 'left', fontWeight: 700, color: '#f8fafc' }}>
                  {match.equipo_visitante}
                </td>
                {[1, 2, 3, 4].map(q => {
                  const m = match.marcadores?.find(item => item.cuarto === q);
                  const isCurrent = match.cuarto_actual === q && match.estado === 'en_curso';
                  return (
                    <td key={q} style={{
                      padding: '6px 12px',
                      color: isCurrent ? '#ff9933' : 'var(--text-secondary)',
                      fontWeight: isCurrent ? 800 : 500
                    }}>
                      {m ? m.pts_visitante : '-'}
                    </td>
                  );
                })}
                <td style={{ padding: '6px 14px', fontWeight: 800, color: '#fff' }}>{totalVisitante}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {/* Bottom Summary Bar: Total Actual, Ritmo Obs vs Base, Deep Learning Tag */}
      <div style={{
        marginTop: '22px',
        paddingTop: '16px',
        borderTop: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px',
        fontSize: '0.84rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)' }}>
          <Activity size={16} color="var(--accent-orange)" />
          <span>Total acumulado: <strong style={{ color: '#fff' }}>{totalPoints} pts</strong></span>
        </div>

        {simulation?.observed_pace_per_min != null && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)' }}>
            <span>Ritmo en pista: <strong style={{ color: '#ff9933' }}>{Number(simulation.observed_pace_per_min).toFixed(1)} pts/min</strong></span>
            <span style={{ color: 'var(--text-muted)' }}>(Base: {simulation.prior_pace_per_min != null ? Number(simulation.prior_pace_per_min).toFixed(1) : '--'})</span>
          </div>
        )}

        {simulation?.spread_mean != null && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)' }}>
            <span>Margen Proyectado: <strong style={{ color: Number(simulation.spread_mean) >= 0 ? '#10b981' : '#38bdf8' }}>
              {Number(simulation.spread_mean) > 0 ? `+${Number(simulation.spread_mean).toFixed(1)}` : Number(simulation.spread_mean).toFixed(1)} pts ({Number(simulation.spread_mean) >= 0 ? match.equipo_local : match.equipo_visitante})
            </strong></span>
          </div>
        )}

        {simulation?.dl_momentum_label && (
          <div className="badge-tag badge-gold" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Zap size={14} />
            <span>
              DEEP LEARNING: {simulation.dl_momentum_label}
              {simulation.dl_spread_margin != null ? ` (Spread DL: ${Number(simulation.dl_spread_margin) > 0 ? '+' : ''}${Number(simulation.dl_spread_margin).toFixed(1)})` : ''}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
