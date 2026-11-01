import React, { useState, useEffect } from 'react';
import { 
  PlusCircle, 
  Trash2, 
  Trophy, 
  ArrowRight,
  Zap
} from 'lucide-react';
import type { Partido } from '../types';
import { getPartidos, deletePartido, crearDesdeAposta } from '../api/client';

interface DashboardProps {
  onSelectMatch: (id: number) => void;
  onNavigateNew: () => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ onSelectMatch, onNavigateNew }) => {
  const [partidos, setPartidos] = useState<Partido[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'en_curso' | 'finalizado'>('all');
  const [apostaUrl, setApostaUrl] = useState('');
  const [importingAposta, setImportingAposta] = useState(false);
  const [apostaError, setApostaError] = useState<string | null>(null);

  const loadPartidos = async () => {
    setLoading(true);
    try {
      const data = await getPartidos();
      setPartidos(data);
    } catch (err: any) {
      console.error('Error al cargar partidos:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPartidos();
  }, []);

  const handleImportAposta = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apostaUrl.trim()) return;
    setImportingAposta(true);
    setApostaError(null);
    try {
      const res = await crearDesdeAposta(apostaUrl.trim());
      onSelectMatch(res.id);
    } catch (err: any) {
      setApostaError(err.message || 'Error al importar partido desde Aposta.la');
    } finally {
      setImportingAposta(false);
    }
  };

  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`¿Eliminar definitivamente el partido ID ${id}?`)) return;
    try {
      await deletePartido(id);
      loadPartidos();
    } catch (err: any) {
      alert(`Error al eliminar: ${err.message}`);
    }
  };

  const filtered = partidos.filter((p) => {
    if (filter === 'en_curso') return p.estado === 'en_curso';
    if (filter === 'finalizado') return p.estado === 'finalizado';
    return true;
  });

  return (
    <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '24px' }}>
      {/* Quick Aposta.la 1-Click Import Bar */}
      <div className="glass-card" style={{
        padding: '16px 20px',
        marginBottom: '28px',
        background: 'linear-gradient(135deg, rgba(255, 119, 0, 0.1) 0%, rgba(20, 20, 32, 0.7) 100%)',
        border: '1px solid rgba(255, 119, 0, 0.35)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '16px',
        flexWrap: 'wrap'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: '280px' }}>
          <div style={{
            width: '40px',
            height: '40px',
            borderRadius: '10px',
            background: 'rgba(255, 119, 0, 0.2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--accent-orange)'
          }}>
            <Zap size={22} />
          </div>
          <div>
            <h3 style={{ fontSize: '0.98rem', fontWeight: 800, margin: 0, color: '#fff' }}>
              Importación Directa desde Aposta.la
            </h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '2px 0 0' }}>
              Pegá el link del partido en vivo y el sistema estira equipos, reloj, cuartos y cuotas automáticamente.
            </p>
          </div>
        </div>

        <form onSubmit={handleImportAposta} style={{ display: 'flex', gap: '10px', flex: 1, minWidth: '320px', maxWidth: '650px' }}>
          <input
            type="text"
            placeholder="Pegá el link de Aposta.la aquí (ej: https://www.aposta.la/apuestas-deportivas/#event/...)"
            value={apostaUrl}
            onChange={(e) => setApostaUrl(e.target.value)}
            disabled={importingAposta}
            className="form-input"
            style={{ flex: 1, fontSize: '0.88rem' }}
          />
          <button
            type="submit"
            disabled={importingAposta || !apostaUrl.trim()}
            className="btn-primary"
            style={{
              whiteSpace: 'nowrap',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontWeight: 700,
              padding: '8px 16px'
            }}
          >
            <Zap size={16} />
            {importingAposta ? 'Estirando datos...' : '⚡ 1-Clic: Abrir en Vivo'}
          </button>
        </form>
      </div>

      {apostaError && (
        <div style={{
          background: 'rgba(239, 68, 68, 0.15)',
          border: '1px solid rgba(239, 68, 68, 0.4)',
          color: '#f87171',
          padding: '10px 16px',
          borderRadius: '8px',
          fontSize: '0.88rem',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <span>❌ {apostaError}</span>
        </div>
      )}

      {/* Top Banner & Actions */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        marginBottom: '28px'
      }}>
        <div>
          <h2 style={{ fontSize: '1.8rem', fontWeight: 800, letterSpacing: '-0.5px' }}>
            Panel de Partidos & Predicciones
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', marginTop: '4px' }}>
            Selecciona un partido en curso para conectar la transmisión WebSocket y simulación en vivo.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Filters */}
          <div style={{ display: 'flex', background: 'var(--bg-surface)', padding: '4px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
            <button
              onClick={() => setFilter('all')}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer',
                fontSize: '0.82rem',
                fontWeight: 600,
                background: filter === 'all' ? 'var(--bg-surface-elevated)' : 'transparent',
                color: filter === 'all' ? '#fff' : 'var(--text-muted)'
              }}
            >
              Todos ({partidos.length})
            </button>
            <button
              onClick={() => setFilter('en_curso')}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer',
                fontSize: '0.82rem',
                fontWeight: 600,
                background: filter === 'en_curso' ? 'rgba(16, 185, 129, 0.2)' : 'transparent',
                color: filter === 'en_curso' ? '#10b981' : 'var(--text-muted)'
              }}
            >
              En Vivo
            </button>
            <button
              onClick={() => setFilter('finalizado')}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer',
                fontSize: '0.82rem',
                fontWeight: 600,
                background: filter === 'finalizado' ? 'var(--bg-surface-elevated)' : 'transparent',
                color: filter === 'finalizado' ? '#fff' : 'var(--text-muted)'
              }}
            >
              Finalizados
            </button>
          </div>

          <button onClick={onNavigateNew} className="btn-primary">
            <PlusCircle size={18} />
            Nuevo Partido
          </button>
        </div>
      </div>

      {/* Matches Grid */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-secondary)' }}>
          Cargando partidos desde la base de datos...
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass-card" style={{ padding: '48px', textAlign: 'center' }}>
          <Trophy size={48} color="var(--accent-orange)" style={{ margin: '0 auto 16px', opacity: 0.6 }} />
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '8px' }}>No hay partidos registrados</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '20px' }}>
            Comienza creando un nuevo partido de baloncesto para calcular predicciones probabilísticas.
          </p>
          <button onClick={onNavigateNew} className="btn-primary">
            <PlusCircle size={18} />
            Crear Partido
          </button>
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
          gap: '20px'
        }}>
          {filtered.map((p) => {
            const isLive = p.estado === 'en_curso';
            return (
              <div
                key={p.id}
                onClick={() => onSelectMatch(p.id)}
                className="glass-card"
                style={{
                  padding: '20px',
                  cursor: 'pointer',
                  position: 'relative',
                  borderTop: isLive ? '3px solid var(--accent-orange)' : '1px solid var(--border-subtle)',
                }}
              >
                {/* Header: Tournament & Status */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                  <span style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    color: 'var(--accent-orange)',
                    background: 'rgba(255, 119, 0, 0.12)',
                    padding: '3px 8px',
                    borderRadius: '6px'
                  }}>
                    {p.torneo}
                  </span>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '5px',
                      fontSize: '0.78rem',
                      fontWeight: 700,
                      color: isLive ? '#10b981' : 'var(--text-muted)'
                    }}>
                      {isLive && <span className="live-pulse" style={{ width: '8px', height: '8px' }} />}
                      {isLive ? `Q${p.cuarto_actual} · ${p.min_restantes}m` : 'FINAL'}
                    </span>

                    <button
                      type="button"
                      onClick={(e) => handleDelete(p.id, e)}
                      title="Eliminar partido"
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--text-muted)',
                        cursor: 'pointer',
                        padding: '4px',
                        display: 'flex',
                        alignItems: 'center'
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = '#f43f5e')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>

                {/* Teams & Score */}
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <span style={{ fontSize: '1.15rem', fontWeight: 700, color: '#fff' }}>{p.equipo_local}</span>
                    <span style={{ fontFamily: 'JetBrains Mono', fontSize: '1.4rem', fontWeight: 800, color: '#fff' }}>
                      {p.total_local}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '1.15rem', fontWeight: 700, color: '#fff' }}>{p.equipo_visitante}</span>
                    <span style={{ fontFamily: 'JetBrains Mono', fontSize: '1.4rem', fontWeight: 800, color: '#fff' }}>
                      {p.total_visitante}
                    </span>
                  </div>
                </div>

                {/* Footer: Combined score & action */}
                <div style={{
                  borderTop: '1px solid var(--border-subtle)',
                  paddingTop: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '0.82rem',
                  color: 'var(--text-secondary)'
                }}>
                  <span>Total actual: <strong style={{ color: '#fff' }}>{(p.total_local || 0) + (p.total_visitante || 0)} pts</strong></span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--accent-orange)', fontWeight: 700 }}>
                    <span>{isLive ? 'Mesa en vivo' : 'Ver análisis'}</span>
                    <ArrowRight size={14} />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
