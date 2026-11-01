import React, { useState } from 'react';
import { Bookmark, Plus, History } from 'lucide-react';
import type { Hito, Partido, SimulationResult } from '../types';
import { createHito } from '../api/client';
import { sounds } from '../utils/audio';

interface SnapshotTableProps {
  partido: Partido;
  hitos: Hito[];
  simulation?: Partial<SimulationResult> | null;
  onHitoCreated?: () => void;
}

export const SnapshotTable: React.FC<SnapshotTableProps> = ({
  partido,
  hitos,
  simulation,
  onHitoCreated,
}) => {
  const [nombreHito, setNombreHito] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSaveHito = async () => {
    if (!simulation || !simulation.total_mean) {
      alert('Debes ejecutar una simulación primero');
      return;
    }

    const hitoName = nombreHito.trim() || `Fin Q${partido.cuarto_actual}`;
    setSaving(true);
    try {
      const qDuration = (partido.torneo || '').includes('12') ? 12 : 10;
      const elapsedMins = (partido.cuarto_actual - 1) * qDuration + (qDuration - partido.min_restantes);

      await createHito(partido.id, {
        nombre_hito: hitoName,
        cuarto_snapshot: partido.cuarto_actual,
        minutos_jugados: Math.max(0, elapsedMins),
        pts_local_actual: partido.total_local || 0,
        pts_visitante_actual: partido.total_visitante || 0,
        total_mean: simulation.total_mean,
        total_median: simulation.total_median || simulation.total_mean,
        total_p05: simulation.total_p05 || 0,
        total_p95: simulation.total_p95 || 0,
        total_std: simulation.total_std || 0,
        team_a_mean: simulation.team_a_mean || 0,
        team_b_mean: simulation.team_b_mean || 0,
        win_prob_a: simulation.win_prob_a || 0.5,
        overtime_prob: simulation.overtime_prob || 0.05,
        observed_pace_per_min: simulation.observed_pace_per_min || 0,
        prior_pace_per_min: simulation.prior_pace_per_min || 0,
        linea_apuesta: simulation.linea_apuesta,
        prob_over: simulation.prob_over,
        prob_under: simulation.prob_under,
      });

      sounds.playScoreTick();
      setNombreHito('');
      if (onHitoCreated) onHitoCreated();
    } catch (err: any) {
      alert(`Error al registrar hito: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const finalTotal = (partido.pts_local_final || 0) + (partido.pts_visitante_final || 0);

  return (
    <div className="glass-card" style={{ padding: '22px' }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '16px',
        flexWrap: 'wrap',
        gap: '12px'
      }}>
        <h3 style={{ fontSize: '1.15rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Bookmark size={18} color="var(--accent-orange)" />
          Hitos Formales de Predicción (Checkpoints de Auditoría)
        </h3>

        {/* Quick save button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <input
            type="text"
            placeholder="Ej: Pre-Partido, Descanso..."
            value={nombreHito}
            onChange={(e) => setNombreHito(e.target.value)}
            style={{
              background: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-subtle)',
              color: '#fff',
              padding: '6px 12px',
              borderRadius: '6px',
              fontSize: '0.85rem'
            }}
          />
          <button
            type="button"
            onClick={handleSaveHito}
            disabled={saving || !simulation?.total_mean}
            className="btn-primary"
            style={{ padding: '6px 14px', fontSize: '0.85rem' }}
          >
            <Plus size={16} />
            {saving ? 'Guardando...' : 'Guardar Hito'}
          </button>
        </div>
      </div>

      {hitos.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
          <History size={24} style={{ display: 'block', margin: '0 auto 8px', opacity: 0.5 }} />
          No hay hitos guardados para este partido aún. Guarda un hito para auditar la proyección frente al resultado final.
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1.5px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
                <th style={{ padding: '10px 12px' }}>Hito</th>
                <th style={{ padding: '10px 12px' }}>Momento</th>
                <th style={{ padding: '10px 12px' }}>Marcador</th>
                <th style={{ padding: '10px 12px' }}>Proy. Total</th>
                <th style={{ padding: '10px 12px' }}>Banda IC 90%</th>
                <th style={{ padding: '10px 12px' }}>Prob. Local</th>
                {partido.estado === 'finalizado' && <th style={{ padding: '10px 12px' }}>Error vs Final</th>}
              </tr>
            </thead>
            <tbody>
              {hitos.map((h, i) => {
                const error = partido.estado === 'finalizado' && finalTotal > 0
                  ? (h.total_proyectado - finalTotal).toFixed(1)
                  : null;

                return (
                  <tr
                    key={h.id || i}
                    style={{
                      borderBottom: '1px solid var(--border-subtle)',
                      background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)'
                    }}
                  >
                    <td style={{ padding: '10px 12px', fontWeight: 700, color: 'var(--accent-orange)' }}>
                      {h.nombre_hito || `Checkpoint #${i + 1}`}
                    </td>
                    <td style={{ padding: '10px 12px', color: 'var(--text-secondary)' }}>
                      Q{h.cuarto_snapshot} ({h.minutos_jugados?.toFixed(0)}m)
                    </td>
                    <td style={{ padding: '10px 12px', fontFamily: 'JetBrains Mono' }}>
                      {h.pts_local_actual} - {h.pts_visitante_actual} ({h.total_actual} pts)
                    </td>
                    <td style={{ padding: '10px 12px', fontWeight: 800, color: '#fff', fontFamily: 'JetBrains Mono' }}>
                      {h.total_proyectado?.toFixed(1)} pts
                    </td>
                    <td style={{ padding: '10px 12px', color: 'var(--text-secondary)', fontFamily: 'JetBrains Mono' }}>
                      [{h.total_p05?.toFixed(0)} - {h.total_p95?.toFixed(0)}]
                    </td>
                    <td style={{ padding: '10px 12px', color: '#10b981', fontWeight: 700 }}>
                      {((h.prob_victoria_local || 0.5) * 100).toFixed(1)}%
                    </td>
                    {partido.estado === 'finalizado' && (
                      <td style={{ padding: '10px 12px', fontWeight: 700, color: Number(error) > 0 ? '#f43f5e' : '#10b981' }}>
                        {Number(error) > 0 ? `+${error}` : error} pts
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
