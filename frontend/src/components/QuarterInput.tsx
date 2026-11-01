import React, { useState, useEffect } from 'react';
import { Save, Clock } from 'lucide-react';
import type { Partido } from '../types';

interface QuarterInputProps {
  match: Partido;
  onUpdate: (data: {
    cuarto_actual: number;
    min_restantes: number;
    seg_restantes: number;
    quarters_data: [number, number][];
    notas?: string;
  }) => void;
  loading?: boolean;
}

export const QuarterInput: React.FC<QuarterInputProps> = ({ match, onUpdate, loading }) => {
  const [cuartoActual, setCuartoActual] = useState(match.cuarto_actual || 1);
  const [minRestantes, setMinRestantes] = useState(match.min_restantes || 10);
  const [segRestantes, setSegRestantes] = useState(match.seg_restantes || 0);
  
  const [quarters, setQuarters] = useState<[number, number][]>([
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
  ]);

  // Sync state with match data
  useEffect(() => {
    setCuartoActual(match.cuarto_actual);
    setMinRestantes(match.min_restantes);
    setSegRestantes(match.seg_restantes);

    const initialQuarters: [number, number][] = [[0, 0], [0, 0], [0, 0], [0, 0]];
    if (match.marcadores && match.marcadores.length > 0) {
      match.marcadores.forEach((m) => {
        if (m.cuarto >= 1 && m.cuarto <= 4) {
          initialQuarters[m.cuarto - 1] = [m.pts_local, m.pts_visitante];
        }
      });
    }
    setQuarters(initialQuarters);
  }, [match]);

  const handleQuarterChange = (qIndex: number, teamIndex: 0 | 1, value: number) => {
    const val = Math.max(0, isNaN(value) ? 0 : value);
    const updated = [...quarters] as [number, number][];
    updated[qIndex] = teamIndex === 0 
      ? [val, updated[qIndex][1]] 
      : [updated[qIndex][0], val];
    setQuarters(updated);
  };

  const addPoints = (qIndex: number, teamIndex: 0 | 1, delta: number) => {
    const current = quarters[qIndex][teamIndex];
    handleQuarterChange(qIndex, teamIndex, current + delta);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onUpdate({
      cuarto_actual: cuartoActual,
      min_restantes: minRestantes,
      seg_restantes: segRestantes,
      quarters_data: quarters,
      notas: match.notas,
    });
  };

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
          <Clock size={18} color="var(--accent-orange)" />
          Control de Tiempo y Marcador por Cuarto
        </h3>

        {/* Quarter selector & time inputs */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Cuarto:</label>
          <select
            value={cuartoActual}
            onChange={(e) => setCuartoActual(Number(e.target.value))}
            style={{
              background: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-subtle)',
              color: '#fff',
              padding: '6px 10px',
              borderRadius: '6px',
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            <option value={1}>1º Cuarto</option>
            <option value={2}>2º Cuarto</option>
            <option value={3}>3º Cuarto</option>
            <option value={4}>4º Cuarto</option>
            <option value={5}>Prórroga (OT)</option>
          </select>

          <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginLeft: '6px' }}>Min Rest:</label>
          <input
            type="number"
            min={0}
            max={20}
            value={minRestantes}
            onChange={(e) => setMinRestantes(Number(e.target.value))}
            style={{
              width: '56px',
              background: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-subtle)',
              color: '#fff',
              padding: '6px 8px',
              borderRadius: '6px',
              textAlign: 'center',
              fontWeight: 700,
              fontFamily: 'JetBrains Mono'
            }}
          />
          <span style={{ color: 'var(--text-muted)' }}>:</span>
          <input
            type="number"
            min={0}
            max={59}
            value={segRestantes}
            onChange={(e) => setSegRestantes(Number(e.target.value))}
            style={{
              width: '56px',
              background: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-subtle)',
              color: '#fff',
              padding: '6px 8px',
              borderRadius: '6px',
              textAlign: 'center',
              fontWeight: 700,
              fontFamily: 'JetBrains Mono'
            }}
          />
        </div>
      </div>

      {/* Grid of 4 Quarters */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
        gap: '14px',
        marginBottom: '18px'
      }}>
        {[0, 1, 2, 3].map((qIdx) => {
          const isCurrentQ = (cuartoActual === qIdx + 1);
          return (
            <div
              key={qIdx}
              style={{
                background: isCurrentQ ? 'rgba(255, 119, 0, 0.08)' : 'var(--bg-surface-elevated)',
                border: `1.5px solid ${isCurrentQ ? 'var(--accent-orange)' : 'var(--border-subtle)'}`,
                borderRadius: '12px',
                padding: '14px',
                transition: 'all 0.2s ease'
              }}
            >
              <div style={{
                fontSize: '0.85rem',
                fontWeight: 800,
                color: isCurrentQ ? 'var(--accent-orange)' : 'var(--text-secondary)',
                marginBottom: '10px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}>
                <span>CUARTO {qIdx + 1}</span>
                {isCurrentQ && <span style={{ fontSize: '0.72rem', background: 'var(--accent-orange)', color: '#fff', padding: '2px 6px', borderRadius: '4px' }}>ACTIVO</span>}
              </div>

              {/* Local points */}
              <div style={{ marginBottom: '10px' }}>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  {match.equipo_local} (Local)
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <input
                    type="number"
                    min={0}
                    value={quarters[qIdx][0]}
                    onChange={(e) => handleQuarterChange(qIdx, 0, Number(e.target.value))}
                    style={{
                      width: '60px',
                      background: 'rgba(0,0,0,0.3)',
                      border: '1px solid var(--border-subtle)',
                      color: '#fff',
                      padding: '6px 8px',
                      borderRadius: '6px',
                      textAlign: 'center',
                      fontWeight: 700,
                      fontFamily: 'JetBrains Mono'
                    }}
                  />
                  <button type="button" onClick={() => addPoints(qIdx, 0, 1)} className="btn-secondary" style={{ padding: '4px 8px', fontSize: '0.75rem' }}>+1</button>
                  <button type="button" onClick={() => addPoints(qIdx, 0, 2)} className="btn-secondary" style={{ padding: '4px 8px', fontSize: '0.75rem' }}>+2</button>
                  <button type="button" onClick={() => addPoints(qIdx, 0, 3)} className="btn-secondary" style={{ padding: '4px 8px', fontSize: '0.75rem' }}>+3</button>
                </div>
              </div>

              {/* Visitor points */}
              <div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  {match.equipo_visitante} (Visitante)
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <input
                    type="number"
                    min={0}
                    value={quarters[qIdx][1]}
                    onChange={(e) => handleQuarterChange(qIdx, 1, Number(e.target.value))}
                    style={{
                      width: '60px',
                      background: 'rgba(0,0,0,0.3)',
                      border: '1px solid var(--border-subtle)',
                      color: '#fff',
                      padding: '6px 8px',
                      borderRadius: '6px',
                      textAlign: 'center',
                      fontWeight: 700,
                      fontFamily: 'JetBrains Mono'
                    }}
                  />
                  <button type="button" onClick={() => addPoints(qIdx, 1, 1)} className="btn-secondary" style={{ padding: '4px 8px', fontSize: '0.75rem' }}>+1</button>
                  <button type="button" onClick={() => addPoints(qIdx, 1, 2)} className="btn-secondary" style={{ padding: '4px 8px', fontSize: '0.75rem' }}>+2</button>
                  <button type="button" onClick={() => addPoints(qIdx, 1, 3)} className="btn-secondary" style={{ padding: '4px 8px', fontSize: '0.75rem' }}>+3</button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Action button */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={loading}
          className="btn-primary"
          style={{ width: '100%', justifyContent: 'center', fontSize: '1rem', padding: '12px 24px' }}
        >
          <Save size={18} />
          {loading ? 'Sincronizando...' : 'Actualizar Marcador y Re-simular Monte Carlo'}
        </button>
      </div>
    </div>
  );
};
