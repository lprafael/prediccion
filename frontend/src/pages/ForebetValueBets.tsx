import React, { useState, useEffect } from 'react';
import { 
  Flame, 
  RefreshCw, 
  Search, 
  TrendingUp, 
  AlertTriangle, 
  ShieldCheck, 
  Sparkles, 
  Percent, 
  Calendar,
  Info
} from 'lucide-react';
import { getForebetCruce, escanearForebetCruce } from '../api/client';
import type { ForebetCruceItem, ForebetCruceResponse } from '../types';


export const ForebetValueBets: React.FC = () => {
  const [data, setData] = useState<ForebetCruceResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [scanning, setScanning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Filtros
  const [soloValor, setSoloValor] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedLeague, setSelectedLeague] = useState<string>('all');
  const [minEv, setMinEv] = useState<number>(0);

  const fetchData = async (refresh = false) => {
    try {
      if (refresh) setScanning(true);
      else setLoading(true);
      setError(null);

      const res = await getForebetCruce({ refresh });
      setData(res);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Error al obtener datos del cruce Forebet vs Aposta.la');
    } finally {
      setLoading(false);
      setScanning(false);
    }
  };

  const handleForzarEscaneo = async () => {
    try {
      setScanning(true);
      setError(null);
      await escanearForebetCruce();
      await fetchData(false);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Error al forzar el escaneo');
      setScanning(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Filtrado de items en memoria
  const filteredItems = (data?.items || []).filter((item: ForebetCruceItem) => {
    if (soloValor && !item.has_value) return false;
    if (minEv > 0 && (!item.best_pick || item.best_pick.ev_pct < minEv)) return false;

    if (selectedLeague !== 'all') {
      const tour = (item.forebet.tournament || '').toLowerCase();
      const league = (item.aposta.league || '').toLowerCase();
      if (!tour.includes(selectedLeague.toLowerCase()) && !league.includes(selectedLeague.toLowerCase())) {
        return false;
      }
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const h1 = item.forebet.home.toLowerCase();
      const a1 = item.forebet.away.toLowerCase();
      const h2 = item.aposta.home.toLowerCase();
      const a2 = item.aposta.away.toLowerCase();
      if (!h1.includes(q) && !a1.includes(q) && !h2.includes(q) && !a2.includes(q)) {
        return false;
      }
    }

    return true;
  });

  // Extraer lista única de ligas
  const leagues = Array.from(
    new Set(
      (data?.items || [])
        .map((i) => i.aposta.league || i.forebet.tournament)
        .filter(Boolean)
    )
  );

  const formatLastUpdated = (ts?: number) => {
    if (!ts) return 'No disponible';
    const date = new Date(ts * 1000);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '24px 20px' }}>
      {/* ─── Hero Header ──────────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        flexWrap: 'wrap',
        gap: '20px',
        marginBottom: '28px',
        background: 'linear-gradient(135deg, rgba(20, 29, 47, 0.7) 0%, rgba(13, 19, 33, 0.9) 100%)',
        border: '1px solid rgba(0, 230, 153, 0.2)',
        borderRadius: '16px',
        padding: '24px 28px',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.37)'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              background: 'rgba(0, 230, 153, 0.15)',
              color: '#00e699',
              padding: '4px 12px',
              borderRadius: '20px',
              fontSize: '0.75rem',
              fontWeight: 700,
              letterSpacing: '0.5px',
              textTransform: 'uppercase'
            }}>
              <Sparkles size={14} /> Value Betting Cuantitativo
            </span>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              background: 'rgba(255, 119, 0, 0.15)',
              color: '#ff8800',
              padding: '4px 12px',
              borderRadius: '20px',
              fontSize: '0.75rem',
              fontWeight: 700,
              textTransform: 'uppercase'
            }}>
              <Flame size={14} /> Aposta.la + Forebet
            </span>
          </div>
          <h2 style={{ fontSize: '1.85rem', fontWeight: 800, margin: 0, letterSpacing: '-0.5px' }}>
            Radar de Apuestas con Valor <span style={{ color: '#00e699' }}>+EV</span>
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', marginTop: '6px', maxWidth: '720px' }}>
            Cruce algorítmico entre las probabilidades de <strong>Forebet</strong> y las cuotas de <strong>Aposta.la (Kambi)</strong>. 
            Identifica ineficiencias matemáticas donde la casa paga más de lo probabilísticamente justo.
          </p>
        </div>

        {/* Acciones superiores */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ textAlign: 'right', marginRight: '6px' }}>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)', display: 'block' }}>
              Último escaneo
            </span>
            <span style={{ fontSize: '0.86rem', fontWeight: 600, color: '#e0e6ed' }}>
              {formatLastUpdated(data?.last_updated)}
            </span>
          </div>

          <button
            onClick={handleForzarEscaneo}
            disabled={scanning || loading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              background: 'linear-gradient(135deg, #00c853 0%, #009624 100%)',
              color: '#fff',
              border: 'none',
              borderRadius: '10px',
              padding: '12px 18px',
              fontSize: '0.88rem',
              fontWeight: 700,
              cursor: scanning ? 'not-allowed' : 'pointer',
              boxShadow: '0 4px 16px rgba(0, 200, 83, 0.4)',
              transition: 'all 0.2s ease',
              opacity: scanning ? 0.75 : 1
            }}
          >
            <RefreshCw size={17} className={scanning ? 'spin-animation' : ''} />
            {scanning ? 'Escaneando en Vivo...' : 'Escanear Ahora'}
          </button>
        </div>
      </div>

      {/* ─── KPIs Cards ──────────────────────────────────────────────────────── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
        gap: '16px',
        marginBottom: '28px'
      }}>
        {/* Card 1: Partidos Cruzados */}
        <div style={{
          background: 'rgba(16, 22, 36, 0.8)',
          border: '1px solid var(--border-subtle)',
          borderRadius: '12px',
          padding: '18px 20px',
          display: 'flex',
          alignItems: 'center',
          gap: '16px'
        }}>
          <div style={{
            width: '46px',
            height: '46px',
            borderRadius: '10px',
            background: 'rgba(56, 189, 248, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#38bdf8'
          }}>
            <ShieldCheck size={24} />
          </div>
          <div>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
              Partidos Cruzados
            </span>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#f1f5f9' }}>
              {data?.summary?.total_matched || 0}
            </div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              de {data?.summary?.aposta_events_available || 0} eventos en Aposta.la
            </span>
          </div>
        </div>

        {/* Card 2: Apuestas con Valor */}
        <div style={{
          background: 'rgba(16, 22, 36, 0.8)',
          border: '1px solid rgba(0, 230, 153, 0.3)',
          borderRadius: '12px',
          padding: '18px 20px',
          display: 'flex',
          alignItems: 'center',
          gap: '16px'
        }}>
          <div style={{
            width: '46px',
            height: '46px',
            borderRadius: '10px',
            background: 'rgba(0, 230, 153, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#00e699'
          }}>
            <TrendingUp size={24} />
          </div>
          <div>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
              Oportunidades +EV
            </span>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#00e699' }}>
              {data?.summary?.total_value_bets || 0}
            </div>
            <span style={{ fontSize: '0.75rem', color: '#00e699' }}>
              {data?.summary?.high_value_bets || 0} de muy alto valor
            </span>
          </div>
        </div>

        {/* Card 3: Mejor Retorno Proyectado */}
        <div style={{
          background: 'rgba(16, 22, 36, 0.8)',
          border: '1px solid rgba(255, 119, 0, 0.3)',
          borderRadius: '12px',
          padding: '18px 20px',
          display: 'flex',
          alignItems: 'center',
          gap: '16px'
        }}>
          <div style={{
            width: '46px',
            height: '46px',
            borderRadius: '10px',
            background: 'rgba(255, 119, 0, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#ff8800'
          }}>
            <Percent size={24} />
          </div>
          <div>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
              Máximo Retorno (+EV)
            </span>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#ff8800' }}>
              {data?.summary?.best_ev ? `+${data.summary.best_ev}%` : 'N/A'}
            </div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              {data?.summary?.best_opportunity || 'Calculando...'}
            </span>
          </div>
        </div>
      </div>

      {/* ─── Barra de Filtros ─────────────────────────────────────────────────── */}
      <div style={{
        background: 'rgba(16, 22, 36, 0.6)',
        border: '1px solid var(--border-subtle)',
        borderRadius: '12px',
        padding: '14px 20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '14px',
        marginBottom: '24px'
      }}>
        {/* Buscador */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: '1 1 240px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: 'rgba(9, 13, 22, 0.8)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '8px',
            padding: '8px 12px',
            width: '100%',
            maxWidth: '320px'
          }}>
            <Search size={16} color="var(--text-muted)" />
            <input
              type="text"
              placeholder="Buscar por equipo..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#fff',
                fontSize: '0.85rem',
                outline: 'none',
                width: '100%'
              }}
            />
          </div>
        </div>

        {/* Filtros rápidos */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          {/* Selector de Liga */}
          <select
            value={selectedLeague}
            onChange={(e) => setSelectedLeague(e.target.value)}
            style={{
              background: 'rgba(9, 13, 22, 0.8)',
              border: '1px solid var(--border-subtle)',
              color: '#e0e6ed',
              borderRadius: '8px',
              padding: '8px 12px',
              fontSize: '0.84rem',
              outline: 'none',
              cursor: 'pointer'
            }}
          >
            <option value="all">Todas las Competiciones</option>
            {leagues.map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>

          {/* Selector de Min EV */}
          <select
            value={minEv}
            onChange={(e) => setMinEv(Number(e.target.value))}
            style={{
              background: 'rgba(9, 13, 22, 0.8)',
              border: '1px solid var(--border-subtle)',
              color: '#e0e6ed',
              borderRadius: '8px',
              padding: '8px 12px',
              fontSize: '0.84rem',
              outline: 'none',
              cursor: 'pointer'
            }}
          >
            <option value={0}>Todos los Retornos (+EV)</option>
            <option value={5}>Min +5% EV</option>
            <option value={15}>Min +15% EV</option>
            <option value={30}>Min +30% EV (Alto Impacto)</option>
          </select>


          {/* Toggle Solo +EV */}
          <button
            onClick={() => setSoloValor(!soloValor)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: soloValor ? 'rgba(0, 230, 153, 0.15)' : 'rgba(9, 13, 22, 0.8)',
              border: soloValor ? '1px solid #00e699' : '1px solid var(--border-subtle)',
              color: soloValor ? '#00e699' : 'var(--text-muted)',
              borderRadius: '8px',
              padding: '8px 14px',
              fontSize: '0.84rem',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.2s ease'
            }}
          >
            <TrendingUp size={15} />
            Solo Oportunidades +EV
          </button>
        </div>
      </div>

      {/* ─── Estado de Carga / Error ─────────────────────────────────────────── */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '60px 20px' }}>
          <div className="spin-animation" style={{
            width: '40px',
            height: '40px',
            border: '3px solid rgba(0, 230, 153, 0.2)',
            borderTopColor: '#00e699',
            borderRadius: '50%',
            margin: '0 auto 16px'
          }} />
          <h4 style={{ fontWeight: 700, margin: '0 0 6px' }}>Analizando y Cruzando Mercados en Vivo</h4>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Obteniendo predicciones de Forebet y cuotas de Aposta.la...
          </p>
        </div>
      )}

      {error && (
        <div style={{
          background: 'rgba(239, 68, 68, 0.12)',
          border: '1px solid rgba(239, 68, 68, 0.4)',
          borderRadius: '10px',
          padding: '16px 20px',
          marginBottom: '20px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          color: '#f87171'
        }}>
          <AlertTriangle size={20} />
          <span>{error}</span>
        </div>
      )}

      {/* ─── Lista de Partidos Cruzados ───────────────────────────────────────── */}
      {!loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {filteredItems.length === 0 ? (
            <div style={{
              textAlign: 'center',
              padding: '50px 20px',
              background: 'rgba(16, 22, 36, 0.5)',
              border: '1px dashed var(--border-subtle)',
              borderRadius: '12px'
            }}>
              <Info size={32} color="var(--text-muted)" style={{ margin: '0 auto 10px' }} />
              <h4 style={{ fontWeight: 700, margin: '0 0 6px' }}>No se encontraron partidos con los filtros actuales</h4>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.84rem' }}>
                Prueba desactivando "Solo Oportunidades +EV" o cambiando la liga seleccionada.
              </p>
            </div>
          ) : (
            filteredItems.map((item: ForebetCruceItem, idx: number) => {
              const fb = item.forebet;
              const ap = item.aposta;
              const best = item.best_pick;

              return (
                <div
                  key={`${fb.home}-${fb.away}-${idx}`}
                  style={{
                    background: 'rgba(16, 22, 36, 0.75)',
                    border: item.is_high_value 
                      ? '1px solid rgba(0, 230, 153, 0.4)' 
                      : (item.has_value ? '1px solid rgba(0, 230, 153, 0.2)' : '1px solid var(--border-subtle)'),
                    borderRadius: '14px',
                    padding: '20px 24px',
                    boxShadow: item.is_high_value ? '0 0 20px rgba(0, 230, 153, 0.08)' : 'none',
                    transition: 'all 0.2s ease'
                  }}
                >
                  {/* Fila superior: Torneo, Fecha y Badges */}
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '10px',
                    borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
                    paddingBottom: '12px',
                    marginBottom: '16px'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{
                        background: 'rgba(56, 189, 248, 0.15)',
                        color: '#38bdf8',
                        padding: '3px 10px',
                        borderRadius: '6px',
                        fontSize: '0.74rem',
                        fontWeight: 700,
                        textTransform: 'uppercase'
                      }}>
                        {fb.tournament || ap.league || 'Fútbol'}
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '5px', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
                        <Calendar size={13} /> {fb.dateTime || ap.start}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      {item.is_high_value && (
                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '5px',
                          background: 'rgba(0, 230, 153, 0.2)',
                          color: '#00e699',
                          padding: '4px 10px',
                          borderRadius: '8px',
                          fontSize: '0.75rem',
                          fontWeight: 700
                        }}>
                          <Flame size={14} /> VALOR ALTO (+EV)
                        </span>
                      )}

                      {item.trap_favorite && (
                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '5px',
                          background: 'rgba(239, 68, 68, 0.15)',
                          color: '#f87171',
                          padding: '4px 10px',
                          borderRadius: '8px',
                          fontSize: '0.75rem',
                          fontWeight: 700
                        }}>
                          <AlertTriangle size={14} /> CUOTA TRAMPA EN FAVORITO
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Cuerpo: Equipos, Marcador y Comparación */}
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                    gap: '20px',
                    alignItems: 'center'
                  }}>
                    {/* Bloque Equipos y Forebet */}
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                        <h3 style={{ fontSize: '1.25rem', fontWeight: 800, margin: 0, color: '#f8fafc' }}>
                          {fb.home} <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>vs</span> {fb.away}
                        </h3>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap', marginTop: '6px' }}>
                        {fb.pred && (
                          <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                            Pronóstico Forebet: <strong style={{ color: '#38bdf8' }}>[{fb.pred}]</strong>
                          </div>
                        )}
                        {fb.exactScore && (
                          <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                            Marcador Proyectado: <strong style={{ color: '#00e699' }}>{fb.exactScore}</strong>
                          </div>
                        )}
                        {fb.avgGoals && (
                          <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                            Promedio Goles: <strong>{fb.avgGoals}</strong>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Tabla de Mercados 1X2 con Cuotas Aposta.la vs Forebet */}
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(3, 1fr)',
                      gap: '10px'
                    }}>
                      {item.evaluations.map((ev) => {
                        const isBest = best && best.pick === ev.pick && ev.is_value;
                        const labelName = ev.pick === '1' ? '1 (Local)' : (ev.pick === 'X' ? 'X (Empate)' : '2 (Visita)');

                        return (
                          <div
                            key={ev.pick}
                            style={{
                              background: isBest 
                                ? 'linear-gradient(135deg, rgba(0, 230, 153, 0.15) 0%, rgba(0, 168, 112, 0.08) 100%)' 
                                : 'rgba(9, 13, 22, 0.7)',
                              border: isBest 
                                ? '1px solid #00e699' 
                                : '1px solid rgba(255, 255, 255, 0.08)',
                              borderRadius: '10px',
                              padding: '10px 12px',
                              textAlign: 'center',
                              position: 'relative'
                            }}
                          >
                            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700, display: 'block' }}>
                              {labelName}
                            </span>
                            <div style={{ fontSize: '1.25rem', fontWeight: 800, color: isBest ? '#00e699' : '#fff', margin: '2px 0' }}>
                              {ev.cuota_aposta}
                            </div>
                            <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                              Forebet: <strong>{ev.prob_fb_pct}%</strong>
                            </div>
                            <div style={{
                              fontSize: '0.74rem',
                              fontWeight: 700,
                              color: ev.ev_pct > 0 ? '#00e699' : '#f87171',
                              marginTop: '4px'
                            }}>
                              EV: {ev.ev_pct > 0 ? `+${ev.ev_pct}%` : `${ev.ev_pct}%`}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Bloque Recomendación Destacada */}
                  {best && (
                    <div style={{
                      marginTop: '16px',
                      background: best.is_value 
                        ? 'rgba(0, 230, 153, 0.06)' 
                        : 'rgba(255, 255, 255, 0.03)',
                      borderLeft: best.is_value ? '4px solid #00e699' : '4px solid var(--border-subtle)',
                      borderRadius: '0 8px 8px 0',
                      padding: '12px 16px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '12px'
                    }}>
                      <div>
                        <span style={{ fontSize: '0.76rem', color: best.is_value ? '#00e699' : 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
                          {best.is_value ? '💡 Selección Recomendada de Valor' : 'Evaluación del Partido'}
                        </span>
                        <div style={{ fontSize: '0.92rem', color: '#e2e8f0', marginTop: '2px' }}>
                          Apostar a <strong style={{ color: '#fff' }}>[{best.pick === '1' ? fb.home : (best.pick === 'X' ? 'Empate' : fb.away)}]</strong> en Aposta.la a cuota <strong style={{ color: '#00e699' }}>{best.cuota_aposta}</strong>
                          {best.is_value ? (
                            <span> (Ventaja del <strong style={{ color: '#00e699' }}>+{best.edge_pct}%</strong> frente a la probabilidad implícita de la casa).</span>
                          ) : (
                            <span> (Sin margen positivo frente a la casa).</span>
                          )}
                        </div>
                      </div>

                      {best.is_value && best.kelly_pct > 0 && (
                        <div style={{
                          background: 'rgba(0, 230, 153, 0.12)',
                          padding: '6px 12px',
                          borderRadius: '6px',
                          textAlign: 'right'
                        }}>
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block' }}>
                            Stake 1/4 Kelly
                          </span>
                          <span style={{ fontSize: '0.95rem', fontWeight: 800, color: '#00e699' }}>
                            {best.kelly_pct}% del bank
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};
