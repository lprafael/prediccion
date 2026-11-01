import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  ArrowLeft, 
  RefreshCw, 
  CheckCircle,
  Zap,
  Users,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import type { Partido, SimulationResult, Hito, Jugador } from '../types';
import { getPartido, updatePartido, finalizarPartido, runSimulacion, getHitos, syncPartidoAposta, simularLive, getLineups, updateLineups } from '../api/client';
import { useLiveMatchSocket } from '../api/websocket';
import { ScoreBoard } from '../components/ScoreBoard';
import { QuarterInput } from '../components/QuarterInput';
import { MonteCarloChart } from '../components/MonteCarloChart';
import { TimelineChart } from '../components/TimelineChart';
import { LiveBettingPanel } from '../components/LiveBettingPanel';
import { SnapshotTable } from '../components/SnapshotTable';
import { ApuestasTable } from '../components/ApuestasTable';
import { sounds } from '../utils/audio';

interface PartidoLiveProps {
  matchId: number;
  onBack: () => void;
}

export const PartidoLive: React.FC<PartidoLiveProps> = ({ matchId, onBack }) => {
  const [localMatch, setLocalMatch] = useState<Partido | null>(null);
  const [fullSimulation, setFullSimulation] = useState<SimulationResult | null>(null);
  const [hitos, setHitos] = useState<Hito[]>([]);
  const [simulating, setSimulating] = useState(false);
  const [showFinalizarModal, setShowFinalizarModal] = useState(false);
  const [ptsFinalLocal, setPtsFinalLocal] = useState<number>(0);
  const [ptsFinalVisitante, setPtsFinalVisitante] = useState<number>(0);

  // Aposta.la Sync State
  const [apostaUrl, setApostaUrl] = useState<string>('');
  const [syncing, setSyncing] = useState<boolean>(false);
  const [autoSync, setAutoSync] = useState<boolean>(false);
  const [autoSyncInterval, setAutoSyncInterval] = useState<number>(15);
  const [lastSyncTime, setLastSyncTime] = useState<string | null>(null);
  const [syncNotice, setSyncNotice] = useState<string | null>(null);
  const [liveOddsScraped, setLiveOddsScraped] = useState<{ line?: number; over?: number; under?: number } | null>(null);
  // Resultado del ciclo predictivo completo (jugadas → DL → señales → veredicto)
  const [liveAnalysis, setLiveAnalysis] = useState<any>(null);

  // Lineup Stints & Fouls State
  const [showLineups, setShowLineups] = useState<boolean>(false);
  const [lineupData, setLineupData] = useState<{
    partido_id: number;
    equipo_local: string;
    equipo_visitante: string;
    lineup_local: number[];
    lineup_visitante: number[];
    fouls_local: number;
    fouls_visitante: number;
    jugadores_local: Jugador[];
    jugadores_visitante: Jugador[];
  } | null>(null);
  const [savingLineups, setSavingLineups] = useState<boolean>(false);

  const apostaUrlRef = useRef(apostaUrl);
  apostaUrlRef.current = apostaUrl;
  const liveOddsRef = useRef(liveOddsScraped);
  liveOddsRef.current = liveOddsScraped;
  const syncingRef = useRef(false);

  // WebSocket Live Hook
  const { connected, match: wsMatch, simulation: wsSim, liveOdds: wsOdds, sendScoreUpdate } = useLiveMatchSocket(matchId);

  // Active match data priority: WebSocket > Local state
  const activeMatch = wsMatch || localMatch;
  const activeOdds = liveOddsScraped || wsOdds;

  // Fetch match details & initial simulation via REST
  const refreshData = async () => {
    try {
      const p = await getPartido(matchId);
      setLocalMatch(p);
      setPtsFinalLocal(p.pts_local_final || p.total_local || 0);
      setPtsFinalVisitante(p.pts_visitante_final || p.total_visitante || 0);

      // Extract URL from notes if present
      if (p.notas && p.notas.includes('URL:')) {
        const matchUrl = p.notas.split('URL:')[1]?.trim();
        if (matchUrl && !apostaUrl) {
          setApostaUrl(matchUrl);
          // Si el partido está en curso y tiene URL, activar auto-sincronización automáticamente
          if (p.estado === 'en_curso') {
            setAutoSync(true);
          }
        }
      }

      const h = await getHitos(matchId);
      setHitos(h);

      try {
        const ld = await getLineups(matchId);
        setLineupData(ld);
      } catch (e) {
        console.warn('No se pudieron cargar lineups:', e);
      }

      // Trigger full REST simulation for rich timeline & histogram
      await triggerFullSimulation(p);
    } catch (err: any) {
      console.error('Error al cargar partido en vivo:', err);
    }
  };

  const handleTogglePlayer = (team: 'local' | 'visitante', playerId: number) => {
    if (!lineupData) return;
    const current = team === 'local' ? [...lineupData.lineup_local] : [...lineupData.lineup_visitante];
    const idx = current.indexOf(playerId);
    let updatedList: number[];
    if (idx >= 0) {
      updatedList = current.filter(id => id !== playerId);
    } else {
      if (current.length >= 5) {
        alert('Solo puede haber hasta 5 jugadores en cancha para este quinteto.');
        return;
      }
      updatedList = [...current, playerId];
    }

    setLineupData({
      ...lineupData,
      [team === 'local' ? 'lineup_local' : 'lineup_visitante']: updatedList
    });
  };

  const handleUpdateFouls = (team: 'local' | 'visitante', delta: number) => {
    if (!lineupData) return;
    const field = team === 'local' ? 'fouls_local' : 'fouls_visitante';
    const current = lineupData[field] || 0;
    const nextVal = Math.max(0, current + delta);
    setLineupData({
      ...lineupData,
      [field]: nextVal
    });
  };

  const handleSaveLineupChanges = async () => {
    if (!lineupData) return;
    setSavingLineups(true);
    try {
      const res = await updateLineups(matchId, {
        lineup_local: lineupData.lineup_local,
        lineup_visitante: lineupData.lineup_visitante,
        fouls_local: lineupData.fouls_local,
        fouls_visitante: lineupData.fouls_visitante,
      });
      setLocalMatch((prev: any) => prev ? {
        ...prev,
        fouls_local: res.fouls_local,
        fouls_visitante: res.fouls_visitante,
        lineup_local: res.lineup_local,
        lineup_visitante: res.lineup_visitante
      } : null);

      // Trigger quick live simulation with new lineup and fouls
      const analysis = await simularLive(matchId, {
        linea_apuesta: liveOddsScraped?.line ?? fullSimulation?.linea_apuesta,
        cuota_over: liveOddsScraped?.over,
        cuota_under: liveOddsScraped?.under,
        lineup_local: res.lineup_local,
        lineup_visitante: res.lineup_visitante,
        fouls_local: res.fouls_local,
        fouls_visitante: res.fouls_visitante,
      });
      setLiveAnalysis(analysis);
    } catch (err: any) {
      alert(`Error al guardar quinteto: ${err.message}`);
    } finally {
      setSavingLineups(false);
    }
  };

  useEffect(() => {
    refreshData();
  }, [matchId]);

  const triggerFullSimulation = async (matchData?: Partido, targetLine?: number) => {
    const p = matchData || activeMatch;
    if (!p) return;

    setSimulating(true);
    try {
      const torneoStr = (p.torneo || '').toUpperCase();
      const isWNBA = torneoStr.includes('WNBA');
      const qDuration = (!isWNBA && (torneoStr.includes('12') || (torneoStr.includes('NBA') && !isWNBA))) ? 12 : 10;
      const elapsedSec = Math.max(0, (qDuration * 60) - (p.min_restantes * 60 + p.seg_restantes));

      const quarters: [number, number][] = [[0, 0], [0, 0], [0, 0], [0, 0]];
      if (p.marcadores && p.marcadores.length > 0) {
        p.marcadores.forEach((m) => {
          if (m.cuarto >= 1 && m.cuarto <= 4) {
            quarters[m.cuarto - 1] = [m.pts_local, m.pts_visitante];
          }
        });
      }

      let torneoKey = 'NBA';
      if (isWNBA) torneoKey = 'WNBA';
      else if (torneoStr.includes('FIBA') || torneoStr.includes('EUROLIGA')) torneoKey = 'FIBA';
      else if (torneoStr.includes('NBL')) torneoKey = 'NBL';
      else if (torneoStr.includes('NCAA')) torneoKey = 'NCAA_FEMENIL';

      const actualScores: [number, number] | undefined =
        p.total_local !== undefined && p.total_visitante !== undefined
          ? [p.total_local, p.total_visitante]
          : undefined;

      const lineToSim = targetLine ?? liveOddsScraped?.line ?? fullSimulation?.linea_apuesta;

      const simRes = await runSimulacion({
        torneo_key: torneoKey,
        current_quarter: p.cuarto_actual,
        elapsed_seconds_in_quarter: elapsedSec,
        quarters_data: quarters,
        actual_total_scores: actualScores,
        linea_apuesta: lineToSim,
      });

      setFullSimulation(simRes);
    } catch (err: any) {
      console.error('Error en simulación completa:', err);
    } finally {
      setSimulating(false);
    }
  };

  // ─── APOSTA.LA MANUAL / AUTO SYNC ──────────────────────────────────────────
  const handleSyncAposta = useCallback(async () => {
    const url = apostaUrlRef.current?.trim();
    if (!url) {
      return;
    }
    if (syncingRef.current) return;

    syncingRef.current = true;
    setSyncing(true);
    try {
      // 1. Scrape Aposta.la — obtiene marcador, cuotas y jugadas
      const res = await syncPartidoAposta(matchId, url);
      if (res.success === false) {
        if (res.event_finished) {
          setAutoSync(false);
          setSyncNotice('🏁 El evento ha finalizado en Aposta.la. Sincronización automática detenida.');
        } else {
          setSyncNotice(res.message || 'No se encontraron datos en vivo en Aposta.la.');
        }
        return;
      }
      setSyncNotice(null);

      if (res.partido) {
        setLocalMatch(res.partido);
        sounds.playScoreTick();
      }
      if (res.live_odds && res.live_odds.line !== null && res.live_odds.line !== undefined) {
        setLiveOddsScraped(res.live_odds);
      }
      const now = new Date();
      setLastSyncTime(now.toLocaleTimeString());

      // 2. Ciclo predictivo completo: lee jugadas BD → Monte Carlo+DL → señales → veredicto
      //    Esto es lo que hace el sistema inteligente cada 15s: analiza TODAS las jugadas
      //    acumuladas y produce una predicción con contexto play-by-play real.
      const odds = res.live_odds || liveOddsRef.current;
      const analysis = await simularLive(matchId, {
        linea_apuesta: odds?.line,
        cuota_over: odds?.over,
        cuota_under: odds?.under,
        lineup_local: lineupData?.lineup_local,
        lineup_visitante: lineupData?.lineup_visitante,
        fouls_local: lineupData?.fouls_local,
        fouls_visitante: lineupData?.fouls_visitante,
      });
      setLiveAnalysis(analysis);
      // Merge Monte Carlo result into full simulation display
      if (analysis) {
        setFullSimulation((prev: any) => ({
          ...prev,
          total_mean: analysis.total_mean,
          total_median: analysis.total_median,
          total_std: analysis.total_std,
          team_a_mean: analysis.team_a_mean,
          team_b_mean: analysis.team_b_mean,
          win_prob_a: analysis.win_prob_a,
          win_prob_b: analysis.win_prob_b,
          overtime_prob: analysis.overtime_prob,
          prior_pace_per_min: analysis.prior_pace_per_min,
          observed_pace_per_min: analysis.observed_pace_per_min,
          posterior_pace_per_min: analysis.posterior_pace_per_min,
          dl_active: analysis.dl_active,
          dl_delta_pace: analysis.dl_delta_pace,
          dl_pace_multiplier: analysis.dl_pace_multiplier,
          dl_uncertainty_pts: analysis.dl_uncertainty_pts,
          dl_win_prob: analysis.dl_win_prob,
          dl_momentum_label: analysis.dl_momentum_label,
          prob_over: analysis.prob_over,
          prob_under: analysis.prob_under,
          spread_mean: analysis.spread_mean,
          spread_std: analysis.spread_std,
          dl_spread_margin: analysis.dl_spread_margin,
          dl_spread_std: analysis.dl_spread_std,
          dl_xai_factors: analysis.dl_xai_factors,
          betting_recommendation: analysis.betting_recommendation,
          signals: analysis.signals,
          linea_apuesta: analysis.linea_apuesta,
          histogram_totals: analysis.histogram_totals ?? prev?.histogram_totals,
          timeline: analysis.timeline?.length > 0 ? analysis.timeline : prev?.timeline,
        }));
      }
    } catch (err: any) {
      console.warn('Sync Aposta.la:', err.message);
      setSyncNotice(err.message || 'Error de conexión con Aposta.la');
    } finally {
      syncingRef.current = false;
      setSyncing(false);
    }
  }, [matchId, lineupData]);

  // Auto-sync Interval Loop
  useEffect(() => {
    if (autoSync && apostaUrl && activeMatch?.estado !== 'finalizado') {
      // Execute immediately on enable
      handleSyncAposta();

      const timer = window.setInterval(() => {
        handleSyncAposta();
      }, autoSyncInterval * 1000);

      return () => {
        clearInterval(timer);
      };
    }
  }, [autoSync, apostaUrl, autoSyncInterval, handleSyncAposta, activeMatch?.estado]);

  const handleQuarterUpdate = async (data: {
    cuarto_actual: number;
    min_restantes: number;
    seg_restantes: number;
    quarters_data: [number, number][];
    notas?: string;
  }) => {
    if (connected) {
      sendScoreUpdate(data);
    } else {
      await updatePartido(matchId, data);
      await refreshData();
    }
    setTimeout(() => triggerFullSimulation(), 300);
  };

  const handleFinalizarPartido = async () => {
    try {
      await finalizarPartido(matchId, {
        pts_local_final: ptsFinalLocal,
        pts_visitante_final: ptsFinalVisitante,
      });
      setShowFinalizarModal(false);
      refreshData();
    } catch (err: any) {
      alert(`Error al finalizar partido: ${err.message}`);
    }
  };

  if (!activeMatch) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 0', color: 'var(--text-secondary)' }}>
        Cargando mesa de control en vivo...
      </div>
    );
  }

  // Merged simulation data — prioridad: WebSocket > liveAnalysis (ciclo 15s) > REST inicial
  const simDisplay = {
    ...fullSimulation,
    ...(wsSim || {}),
    ...(liveAnalysis ? {
      total_mean: liveAnalysis.total_mean,
      total_median: liveAnalysis.total_median,
      total_std: liveAnalysis.total_std,
      team_a_mean: liveAnalysis.team_a_mean,
      team_b_mean: liveAnalysis.team_b_mean,
      win_prob_a: liveAnalysis.win_prob_a,
      win_prob_b: liveAnalysis.win_prob_b,
      overtime_prob: liveAnalysis.overtime_prob,
      dl_active: liveAnalysis.dl_active,
      dl_delta_pace: liveAnalysis.dl_delta_pace,
      dl_pace_multiplier: liveAnalysis.dl_pace_multiplier,
      dl_uncertainty_pts: liveAnalysis.dl_uncertainty_pts,
      dl_win_prob: liveAnalysis.dl_win_prob,
      dl_momentum_label: liveAnalysis.dl_momentum_label,
      prob_over: liveAnalysis.prob_over,
      prob_under: liveAnalysis.prob_under,
      spread_mean: liveAnalysis.spread_mean,
      spread_std: liveAnalysis.spread_std,
      dl_spread_margin: liveAnalysis.dl_spread_margin,
      dl_spread_std: liveAnalysis.dl_spread_std,
      dl_xai_factors: liveAnalysis.dl_xai_factors,
      betting_recommendation: liveAnalysis.betting_recommendation,
      signals: liveAnalysis.signals,
    } : {}),
    linea_apuesta: liveOddsScraped?.line ?? liveAnalysis?.linea_apuesta ?? fullSimulation?.linea_apuesta,
  };

  // Veredicto del último ciclo predictivo (jugadas → DL → apuesta)
  const liveRec = liveAnalysis?.betting_recommendation;
  const liveSig = liveAnalysis?.signals;

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '24px' }}>
      {/* ─── TOP BAR: NAVEGACIÓN Y ACCIONES GENERALES ───────────────────────── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '16px',
        flexWrap: 'wrap',
        gap: '12px'
      }}>
        <button onClick={onBack} className="btn-secondary" style={{ padding: '6px 14px', fontSize: '0.85rem' }}>
          <ArrowLeft size={16} />
          Volver al Panel
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={() => triggerFullSimulation()}
            disabled={simulating}
            className="btn-secondary"
            style={{ padding: '8px 16px', fontSize: '0.88rem' }}
          >
            <RefreshCw size={16} className={simulating ? 'spin-animation' : ''} />
            {simulating ? 'Simulando...' : 'Re-simular Monte Carlo'}
          </button>

          {activeMatch.estado === 'en_curso' && (
            <button
              onClick={() => setShowFinalizarModal(true)}
              className="btn-secondary"
              style={{
                padding: '8px 16px',
                fontSize: '0.88rem',
                borderColor: '#10b981',
                color: '#10b981',
                background: 'rgba(16, 185, 129, 0.1)'
              }}
            >
              <CheckCircle size={16} />
              Finalizar y Liquidar
            </button>
          )}
        </div>
      </div>

      {/* ─── BARRA DE SINCRONIZACIÓN EN VIVO CON APOSTA.LA (DESTACADA) ────────── */}
      <div className="glass-card" style={{
        padding: '14px 20px',
        marginBottom: '20px',
        background: 'linear-gradient(135deg, rgba(255, 119, 0, 0.08) 0%, rgba(15, 22, 38, 0.95) 100%)',
        border: '1.5px solid var(--accent-orange)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '14px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, minWidth: '320px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '8px',
            background: 'var(--accent-orange)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0
          }}>
            <Zap size={18} color="#fff" />
          </div>

          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '0.82rem', fontWeight: 800, color: 'var(--accent-orange)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>ENLACE APOSTA.LA (SINCRONIZACIÓN EN VIVO)</span>
              {lastSyncTime && (
                <span style={{ fontSize: '0.72rem', color: '#10b981', fontWeight: 600 }}>
                  · Sincronizado a las {lastSyncTime}
                </span>
              )}
            </div>
            <input
              type="text"
              placeholder="Pega el enlace live de aposta.la o ID del evento para auto-llenar marcador y cuotas"
              value={apostaUrl}
              onChange={(e) => setApostaUrl(e.target.value)}
              style={{
                width: '100%',
                background: 'rgba(0, 0, 0, 0.4)',
                border: '1px solid var(--border-subtle)',
                color: '#fff',
                padding: '6px 10px',
                borderRadius: '6px',
                fontSize: '0.85rem',
                marginTop: '4px',
                outline: 'none'
              }}
            />
            {syncNotice && (
              <div style={{
                marginTop: '6px',
                fontSize: '0.78rem',
                fontWeight: 600,
                color: syncNotice?.includes('finalizado') ? '#f59e0b' : '#f87171',
                background: 'rgba(0, 0, 0, 0.3)',
                padding: '4px 8px',
                borderRadius: '4px',
                borderLeft: `3px solid ${syncNotice?.includes('finalizado') ? '#f59e0b' : '#ef4444'}`
              }}>
                {syncNotice}
              </div>
            )}
          </div>
        </div>

        {/* Sync Actions & Auto-Sync Switch */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={handleSyncAposta}
            disabled={syncing || !apostaUrl.trim()}
            className="btn-primary"
            style={{ padding: '8px 16px', fontSize: '0.85rem' }}
          >
            <Zap size={16} />
            {syncing ? 'Estirando...' : 'Sincronizar Ahora'}
          </button>

          {/* Auto-sync toggle */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: 'var(--bg-surface-elevated)',
            padding: '6px 12px',
            borderRadius: '8px',
            border: '1px solid var(--border-subtle)'
          }}>
            <button
              type="button"
              onClick={() => setAutoSync(!autoSync)}
              style={{
                background: autoSync ? '#10b981' : 'transparent',
                color: autoSync ? '#fff' : 'var(--text-muted)',
                border: `1px solid ${autoSync ? '#10b981' : 'var(--border-subtle)'}`,
                padding: '4px 10px',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '0.78rem',
                fontWeight: 800,
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              {autoSync && <span className="live-pulse" style={{ width: '6px', height: '6px', background: '#fff' }} />}
              {autoSync ? 'AUTO-SYNC ACTIVO' : 'AUTO-SYNC OFF'}
            </button>

            {autoSync && (
              <select
                value={autoSyncInterval}
                onChange={(e) => setAutoSyncInterval(Number(e.target.value))}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#fff',
                  fontSize: '0.78rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  outline: 'none'
                }}
              >
                <option value={10} style={{ background: '#0f1626' }}>c/ 10s</option>
                <option value={15} style={{ background: '#0f1626' }}>c/ 15s</option>
                <option value={30} style={{ background: '#0f1626' }}>c/ 30s</option>
                <option value={60} style={{ background: '#0f1626' }}>c/ 60s</option>
              </select>
            )}
          </div>
        </div>
      </div>

      {/* Main Scoreboard Display */}
      <div style={{ marginBottom: '16px' }}>
        <ScoreBoard
          match={activeMatch}
          simulation={simDisplay}
          isAutoSyncActive={autoSync}
          autoSyncInterval={autoSyncInterval}
          lastSyncTime={lastSyncTime}
          isSyncing={syncing}
        />
      </div>

      {/* ─── TIRA DE ANÁLISIS EN VIVO (jugadas → DL → señales) ─────────────── */}
      {(liveAnalysis || liveSig) && (
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '8px',
          marginBottom: '20px',
          padding: '10px 16px',
          background: 'rgba(0,0,0,0.35)',
          border: '1px solid var(--border-subtle)',
          borderRadius: '10px',
          alignItems: 'center',
          fontSize: '0.78rem',
        }}>
          <span style={{ color: 'var(--text-muted)', fontWeight: 700, marginRight: '4px' }}>
            🧠 Análisis Live ({liveAnalysis?.total_jugadas_analizadas ?? 0} jugadas):
          </span>
          {liveSig?.total_plays > 0 && (
            <>
              <span className="badge-tag badge-blue">
                Ritmo obs: {liveSig.pace_observed_per_min != null ? Number(liveSig.pace_observed_per_min).toFixed(1) : '--'} pts/min → {liveSig.pace_projected_total != null ? Number(liveSig.pace_projected_total).toFixed(0) : '--'} pts proyectados
              </span>
              <span className="badge-tag" style={{
                background: Math.abs(liveSig.momentum_score) > 2 ? 'rgba(251,191,36,0.15)' : 'rgba(255,255,255,0.05)',
                color: Math.abs(liveSig.momentum_score) > 2 ? '#fbbf24' : 'var(--text-secondary)',
                border: `1px solid ${Math.abs(liveSig.momentum_score) > 2 ? '#fbbf24' : 'var(--border-subtle)'}`,
              }}>
                Momentum: {liveSig.momentum_label}
              </span>
              {liveSig.run_pts >= 5 && (
                <span className="badge-tag badge-red">
                  🔥 Racha: {liveSig.run_pts} pts {liveSig.run_team}
                </span>
              )}
              {liveSig.recent_heat >= 8 && (
                <span className="badge-tag badge-red">🌡 Calor reciente: {liveSig.recent_heat} pts</span>
              )}
            </>
          )}
          {liveAnalysis?.dl_active && (
            <span className="badge-tag" style={{ background: 'rgba(139,92,246,0.15)', color: '#a78bfa', border: '1px solid rgba(139,92,246,0.3)' }}>
              🤖 DL: {liveAnalysis.dl_momentum_label} ({liveAnalysis.dl_delta_pace != null && Number(liveAnalysis.dl_delta_pace) > 0 ? '+' : ''}{liveAnalysis.dl_delta_pace != null ? Number(liveAnalysis.dl_delta_pace).toFixed(2) : '0.00'} pts/min)
            </span>
          )}
          {liveRec?.bet_grade && liveRec.bet_grade !== 'SIN EDGE / EVITAR' && (
            <span className="badge-tag" style={{
              background: liveRec.bet_grade?.includes('A+') ? 'rgba(16,185,129,0.2)' : liveRec.bet_grade?.includes('GRADO A') ? 'rgba(34,197,94,0.15)' : 'rgba(234,179,8,0.15)',
              color: liveRec.bet_grade?.includes('A+') ? '#10b981' : liveRec.bet_grade?.includes('GRADO A') ? '#22c55e' : '#eab308',
              border: `1px solid ${liveRec.bet_grade?.includes('A+') ? '#10b981' : liveRec.bet_grade?.includes('GRADO A') ? '#22c55e' : '#eab308'}`,
              fontWeight: 900,
            }}>
              🎯 {liveRec.bet_grade} — {liveRec.direction} {liveRec.confidence_pct != null ? Number(liveRec.confidence_pct).toFixed(1) : ''}%
            </span>
          )}
        </div>
      )}

      {/* ─── MONITOR DE QUINTETOS EN PISTA (LINEUPS) Y FALTAS COLECTIVAS ─── */}
      <div className="glass-card" style={{ marginBottom: '20px', padding: '14px 20px', border: '1px solid var(--border-subtle)' }}>
        <div 
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
          onClick={() => setShowLineups(!showLineups)}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '30px', height: '30px', borderRadius: '6px', background: 'rgba(56, 189, 248, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Users size={16} color="#38bdf8" />
            </div>
            <div>
              <span style={{ fontSize: '0.88rem', fontWeight: 800, color: '#f8fafc' }}>
                Quintetos en Pista (Lineup Stints) & Faltas Colectivas
              </span>
              <span style={{ marginLeft: '10px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {lineupData ? `(${lineupData.lineup_local.length}/5 local vs ${lineupData.lineup_visitante.length}/5 visitante)` : 'Cargando quintetos...'}
              </span>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{showLineups ? 'Ocultar' : 'Alinear / Faltas'}</span>
            {showLineups ? <ChevronUp size={18} color="var(--text-muted)" /> : <ChevronDown size={18} color="var(--text-muted)" />}
          </div>
        </div>

        {showLineups && lineupData && (
          <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '18px' }}>
              {/* Local Lineup & Fouls */}
              <div style={{ background: 'rgba(0,0,0,0.25)', padding: '14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <span style={{ fontWeight: 800, fontSize: '0.85rem', color: 'var(--accent-orange)' }}>
                    {activeMatch.equipo_local} (Local)
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Faltas:</span>
                    <button type="button" onClick={() => handleUpdateFouls('local', -1)} style={{ padding: '2px 8px', borderRadius: '4px', background: 'var(--bg-surface-elevated)', color: '#fff', border: '1px solid var(--border-subtle)', cursor: 'pointer' }}>-</button>
                    <strong style={{ fontFamily: 'JetBrains Mono', color: (lineupData.fouls_local || 0) >= 5 ? '#ef4444' : '#fff' }}>{lineupData.fouls_local || 0}</strong>
                    <button type="button" onClick={() => handleUpdateFouls('local', 1)} style={{ padding: '2px 8px', borderRadius: '4px', background: 'var(--bg-surface-elevated)', color: '#fff', border: '1px solid var(--border-subtle)', cursor: 'pointer' }}>+</button>
                    {(lineupData.fouls_local || 0) >= 5 && <span style={{ background: '#ef4444', color: '#fff', fontSize: '0.65rem', padding: '1px 5px', borderRadius: '4px', fontWeight: 800 }}>BONUS</span>}
                  </div>
                </div>
                <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
                  Selecciona 5 jugadores activos en pista:
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '200px', overflowY: 'auto' }}>
                  {lineupData.jugadores_local.map((j) => {
                    const active = lineupData.lineup_local.includes(j.id);
                    return (
                      <div key={j.id} onClick={() => handleTogglePlayer('local', j.id)} style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '6px 10px',
                        borderRadius: '6px',
                        background: active ? 'rgba(255, 119, 0, 0.15)' : 'rgba(255,255,255,0.03)',
                        border: `1px solid ${active ? 'var(--accent-orange)' : 'var(--border-subtle)'}`,
                        cursor: 'pointer',
                        fontSize: '0.78rem'
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <input type="checkbox" checked={active} onChange={() => {}} style={{ cursor: 'pointer' }} />
                          <span style={{ fontWeight: active ? 700 : 500, color: active ? '#fff' : 'var(--text-secondary)' }}>
                            #{j.dorsal || '--'} {j.nombre} ({j.posicion})
                          </span>
                        </div>
                        <div style={{ display: 'flex', gap: '8px', fontFamily: 'JetBrains Mono', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                          <span>BPM: <strong style={{ color: (j.bpm ?? 0) >= 0 ? '#10b981' : '#ef4444' }}>{(j.bpm ?? 0) > 0 ? `+${j.bpm}` : j.bpm ?? 0}</strong></span>
                          <span>TS%: {j.ts_pct ?? j.true_shooting_pct ?? 0}%</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Visitante Lineup & Fouls */}
              <div style={{ background: 'rgba(0,0,0,0.25)', padding: '14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <span style={{ fontWeight: 800, fontSize: '0.85rem', color: '#38bdf8' }}>
                    {activeMatch.equipo_visitante} (Visitante)
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Faltas:</span>
                    <button type="button" onClick={() => handleUpdateFouls('visitante', -1)} style={{ padding: '2px 8px', borderRadius: '4px', background: 'var(--bg-surface-elevated)', color: '#fff', border: '1px solid var(--border-subtle)', cursor: 'pointer' }}>-</button>
                    <strong style={{ fontFamily: 'JetBrains Mono', color: (lineupData.fouls_visitante || 0) >= 5 ? '#ef4444' : '#fff' }}>{lineupData.fouls_visitante || 0}</strong>
                    <button type="button" onClick={() => handleUpdateFouls('visitante', 1)} style={{ padding: '2px 8px', borderRadius: '4px', background: 'var(--bg-surface-elevated)', color: '#fff', border: '1px solid var(--border-subtle)', cursor: 'pointer' }}>+</button>
                    {(lineupData.fouls_visitante || 0) >= 5 && <span style={{ background: '#ef4444', color: '#fff', fontSize: '0.65rem', padding: '1px 5px', borderRadius: '4px', fontWeight: 800 }}>BONUS</span>}
                  </div>
                </div>
                <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
                  Selecciona 5 jugadores activos en pista:
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '200px', overflowY: 'auto' }}>
                  {lineupData.jugadores_visitante.map((j) => {
                    const active = lineupData.lineup_visitante.includes(j.id);
                    return (
                      <div key={j.id} onClick={() => handleTogglePlayer('visitante', j.id)} style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '6px 10px',
                        borderRadius: '6px',
                        background: active ? 'rgba(56, 189, 248, 0.15)' : 'rgba(255,255,255,0.03)',
                        border: `1px solid ${active ? '#38bdf8' : 'var(--border-subtle)'}`,
                        cursor: 'pointer',
                        fontSize: '0.78rem'
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <input type="checkbox" checked={active} onChange={() => {}} style={{ cursor: 'pointer' }} />
                          <span style={{ fontWeight: active ? 700 : 500, color: active ? '#fff' : 'var(--text-secondary)' }}>
                            #{j.dorsal || '--'} {j.nombre} ({j.posicion})
                          </span>
                        </div>
                        <div style={{ display: 'flex', gap: '8px', fontFamily: 'JetBrains Mono', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                          <span>BPM: <strong style={{ color: (j.bpm ?? 0) >= 0 ? '#10b981' : '#ef4444' }}>{(j.bpm ?? 0) > 0 ? `+${j.bpm}` : j.bpm ?? 0}</strong></span>
                          <span>TS%: {j.ts_pct ?? j.true_shooting_pct ?? 0}%</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <div style={{ marginTop: '14px', display: 'flex', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={handleSaveLineupChanges}
                disabled={savingLineups}
                className="btn-primary"
                style={{ padding: '6px 14px', fontSize: '0.8rem' }}
              >
                {savingLineups ? 'Guardando...' : 'Aplicar Quintetos y Recalcular DL'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Main 2-Column Responsive Layout */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))',
        gap: '24px'
      }}>
        {/* Left Column: Quarter Inputs & Live Betting Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <QuarterInput
            match={activeMatch}
            onUpdate={handleQuarterUpdate}
            loading={simulating}
          />

          <LiveBettingPanel
            partidoId={matchId}
            simulation={simDisplay}
            liveOdds={activeOdds}
            currentQuarter={activeMatch.cuarto_actual}
            elapsedMinutes={(activeMatch.cuarto_actual - 1) * 10 + (10 - activeMatch.min_restantes)}
            onBetRegistered={refreshData}
          />
        </div>

        {/* Right Column: Charts & Snapshots */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <MonteCarloChart
            simulation={simDisplay}
            betLine={simDisplay.linea_apuesta}
          />

          <TimelineChart
            timeline={fullSimulation?.timeline}
            currentTotal={(activeMatch.total_local || 0) + (activeMatch.total_visitante || 0)}
          />

          <SnapshotTable
            partido={activeMatch}
            hitos={hitos}
            simulation={simDisplay}
            onHitoCreated={refreshData}
          />
        </div>
      </div>

      {/* Historial de Apuestas Registradas para este Partido (con edición y eliminación) */}
      <div style={{ marginTop: '24px' }}>
        <ApuestasTable partidoId={matchId} onChanged={refreshData} />
      </div>

      {/* Finalizar Partido Modal */}
      {showFinalizarModal && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 100,
          padding: '20px'
        }}>
          <div className="glass-card" style={{ maxWidth: '480px', width: '100%', padding: '28px' }}>
            <h3 style={{ fontSize: '1.3rem', fontWeight: 800, marginBottom: '10px' }}>
              Finalizar Partido y Liquidar Apuestas
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginBottom: '20px' }}>
              Registra el tanteador definitivo para liquidar automáticamente todas las apuestas asociadas (reales y simuladas).
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '20px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  {activeMatch.equipo_local}
                </label>
                <input
                  type="number"
                  value={ptsFinalLocal}
                  onChange={(e) => setPtsFinalLocal(Number(e.target.value))}
                  style={{
                    width: '100%',
                    background: 'var(--bg-surface-elevated)',
                    border: '1px solid var(--border-subtle)',
                    color: '#fff',
                    padding: '10px',
                    borderRadius: '8px',
                    fontSize: '1.2rem',
                    fontFamily: 'JetBrains Mono',
                    textAlign: 'center'
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  {activeMatch.equipo_visitante}
                </label>
                <input
                  type="number"
                  value={ptsFinalVisitante}
                  onChange={(e) => setPtsFinalVisitante(Number(e.target.value))}
                  style={{
                    width: '100%',
                    background: 'var(--bg-surface-elevated)',
                    border: '1px solid var(--border-subtle)',
                    color: '#fff',
                    padding: '10px',
                    borderRadius: '8px',
                    fontSize: '1.2rem',
                    fontFamily: 'JetBrains Mono',
                    textAlign: 'center'
                  }}
                />
              </div>
            </div>

            <div style={{ textAlign: 'center', marginBottom: '24px', fontSize: '0.95rem', color: 'var(--accent-orange)' }}>
              Total Final: <strong>{ptsFinalLocal + ptsFinalVisitante} puntos</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                type="button"
                onClick={() => setShowFinalizarModal(false)}
                className="btn-secondary"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleFinalizarPartido}
                className="btn-primary"
              >
                Confirmar y Liquidar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
