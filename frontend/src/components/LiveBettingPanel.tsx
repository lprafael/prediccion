import React, { useState, useEffect, useRef } from 'react';
import { Target, TrendingUp, TrendingDown, DollarSign, CheckCircle2, Award, PenLine, ChevronDown, ChevronUp, Brain, Activity, Scale } from 'lucide-react';
import type { SimulationResult } from '../types';
import { createApuesta } from '../api/client';
import { sounds } from '../utils/audio';

interface LiveBettingPanelProps {
  partidoId: number;
  simulation?: Partial<SimulationResult> | null;
  liveOdds?: { line?: number; over?: number; under?: number } | null;
  currentQuarter?: number;
  elapsedMinutes?: number;
  onBetRegistered?: () => void;
}

export const LiveBettingPanel: React.FC<LiveBettingPanelProps> = ({
  partidoId,
  simulation,
  liveOdds,
  currentQuarter = 1,
  elapsedMinutes = 0,
  onBetRegistered,
}) => {
  // ─── Pestañas de Mercado ─────────────────────────────────────────────────────
  const [activeMarket, setActiveMarket] = useState<'TOTALS' | 'SPREAD' | 'MONEYLINE' | 'XAI'>('TOTALS');

  // ─── Mercado: Totales (Over/Under) ───────────────────────────────────────────
  const [linea, setLinea] = useState<number>(() => liveOdds?.line ?? simulation?.linea_apuesta ?? 215.5);
  const [cuotaOver, setCuotaOver] = useState<number>(() => liveOdds?.over ?? 1.90);
  const [cuotaUnder, setCuotaUnder] = useState<number>(() => liveOdds?.under ?? 1.90);

  // ─── Mercado: Spread / Hándicap ──────────────────────────────────────────────
  const [spreadLine, setSpreadLine] = useState<number>(() => simulation?.spread_line ?? -4.5);
  const [cuotaSpreadHome, setCuotaSpreadHome] = useState<number>(1.90);
  const [cuotaSpreadAway, setCuotaSpreadAway] = useState<number>(1.90);

  // ─── Mercado: Moneyline ──────────────────────────────────────────────────────
  const [cuotaMlHome, setCuotaMlHome] = useState<number>(1.85);
  const [cuotaMlAway, setCuotaMlAway] = useState<number>(1.95);

  const [bankroll, setBankroll] = useState<number>(1000000);
  const [esFicticia, setEsFicticia] = useState<boolean>(true);
  const [registering, setRegistering] = useState<boolean>(false);
  const [registeredMsg, setRegisteredMsg] = useState<string | null>(null);

  // ─── Formulario Manual de Registro ───────────────────────────────────────────
  const [showManualForm, setShowManualForm] = useState<boolean>(false);
  const [manualTipo, setManualTipo] = useState<'OVER' | 'UNDER' | 'SPREAD' | 'MONEYLINE'>('OVER');
  const [manualEquipo, setManualEquipo] = useState<'LOCAL' | 'VISITANTE'>('LOCAL');
  const [manualLinea, setManualLinea] = useState<number>(215.5);
  const [manualCuota, setManualCuota] = useState<number>(1.90);
  const [manualMonto, setManualMonto] = useState<number>(100000);
  const [manualEsFicticia, setManualEsFicticia] = useState<boolean>(true);
  const [manualNotas, setManualNotas] = useState<string>('');
  const [manualRegistering, setManualRegistering] = useState<boolean>(false);
  const [manualMsg, setManualMsg] = useState<string | null>(null);

  // Sincronizar automáticamente la Línea y Cuotas cuando lleguen valores de la casa desde Aposta.la
  useEffect(() => {
    if (liveOdds?.line !== undefined && liveOdds.line !== null) {
      setLinea(liveOdds.line);
    } else if (simulation?.linea_apuesta !== undefined && simulation.linea_apuesta !== null) {
      setLinea(simulation.linea_apuesta);
    } else if (simulation?.total_mean && (linea === 215.5 || !linea)) {
      setLinea(Math.round(simulation.total_mean * 2) / 2);
    }
  }, [liveOdds?.line, simulation?.linea_apuesta, simulation?.total_mean]);

  useEffect(() => {
    if (liveOdds?.over !== undefined && liveOdds.over !== null) {
      setCuotaOver(liveOdds.over);
    }
  }, [liveOdds?.over]);

  useEffect(() => {
    if (liveOdds?.under !== undefined && liveOdds.under !== null) {
      setCuotaUnder(liveOdds.under);
    }
  }, [liveOdds?.under]);

  // ─── Métricas de Totales (Over/Under) ─────────────────────────────────────────
  const probOver = simulation?.prob_over !== undefined
    ? simulation.prob_over
    : (simulation?.total_mean ? (simulation.total_mean > linea ? 0.58 : 0.42) : 0.50);
  
  const probUnder = 1.0 - probOver;
  const fairOddsOver = probOver > 0.01 ? (1.0 / probOver).toFixed(2) : '--';
  const fairOddsUnder = probUnder > 0.01 ? (1.0 / probUnder).toFixed(2) : '--';
  const evOver = ((probOver * cuotaOver) - 1.0) * 100;
  const evUnder = ((probUnder * cuotaUnder) - 1.0) * 100;
  const bestBet = evOver > evUnder ? 'OVER' : 'UNDER';
  const bestEv = Math.max(evOver, evUnder);
  const bestProb = bestBet === 'OVER' ? probOver : probUnder;
  const bestCuota = bestBet === 'OVER' ? cuotaOver : cuotaUnder;

  const spreadPts = simulation?.total_mean !== undefined ? Number((simulation.total_mean - linea).toFixed(1)) : 0;
  const absSpread = Math.abs(spreadPts);
  const maxProb = Math.max(probOver, probUnder);
  const favSide = probOver >= probUnder ? 'OVER' : 'UNDER';

  // ─── Clasificación Profesional de Totales ──────────────────────────────────
  let calcGrade = 'SIN EDGE (LÍNEA AJUSTADA / 50-50)';
  let calcBadgeColor = '#94a3b8';
  let calcUnits = '0.0 U (NO ENTRAR)';
  let isActionable = false;

  if (absSpread >= 4.0 && (maxProb >= 0.65 || bestEv >= 5.0)) {
    calcGrade = 'GRADO A+ (MÁXIMO VALOR)';
    calcBadgeColor = '#10b981';
    calcUnits = '2.5 – 3.0 U';
    isActionable = true;
  } else if (absSpread >= 2.5 && (maxProb >= 0.60 || bestEv >= 3.0)) {
    calcGrade = 'GRADO A (VENTAJA SÓLIDA)';
    calcBadgeColor = '#22c55e';
    calcUnits = '1.5 – 2.0 U';
    isActionable = true;
  } else if (absSpread >= 1.5 && (maxProb >= 0.55 || bestEv >= 1.5)) {
    calcGrade = 'GRADO B (MODERADO)';
    calcBadgeColor = '#eab308';
    calcUnits = '0.5 – 1.0 U';
    isActionable = true;
  }



  // Criterio de Kelly (fracción recomendada al 25%)
  const b = bestCuota - 1.0;
  const p = bestProb;
  const q = 1.0 - p;
  const rawKelly = b > 0 ? (b * p - q) / b : 0;
  const kellyFraction = Math.max(0, rawKelly * 0.25);
  const suggestedStake = Math.round(bankroll * kellyFraction);

  // ─── Métricas de Hándicap (Point Spread) ─────────────────────────────────────
  const simMargin = simulation?.spread_mean != null
    ? simulation.spread_mean
    : (simulation?.team_a_mean != null && simulation?.team_b_mean != null
        ? simulation.team_a_mean - simulation.team_b_mean
        : 0);
  const probSpreadHome = simulation?.prob_spread_home != null
    ? simulation.prob_spread_home
    : (Number(simMargin) + spreadLine > 0 ? 0.56 : 0.44);
  const probSpreadAway = simulation?.prob_spread_away != null
    ? simulation.prob_spread_away
    : (1.0 - probSpreadHome);

  const evSpreadHome = ((probSpreadHome * cuotaSpreadHome) - 1.0) * 100;
  const evSpreadAway = ((probSpreadAway * cuotaSpreadAway) - 1.0) * 100;
  const spreadEdgeHome = Number(((Number(simMargin) || 0) - (-spreadLine)).toFixed(1));

  // ─── Métricas de Moneyline ───────────────────────────────────────────────────
  const probMlHome = simulation?.win_prob_a ?? 0.50;
  const probMlAway = simulation?.win_prob_b ?? (1.0 - probMlHome);
  const evMlHome = ((probMlHome * cuotaMlHome) - 1.0) * 100;
  const evMlAway = ((probMlAway * cuotaMlAway) - 1.0) * 100;
  const fairOddsMlHome = probMlHome > 0.01 ? (1.0 / probMlHome).toFixed(2) : '--';
  const fairOddsMlAway = probMlAway > 0.01 ? (1.0 / probMlAway).toFixed(2) : '--';

  // ─── Factores XAI ────────────────────────────────────────────────────────────
  const xaiFactors = simulation?.dl_xai_factors || {
    atencion_momentum: 0.35,
    impacto_alineaciones: 0.28,
    varianza_triples: 0.22,
    factor_tiempo_restante: 0.15
  };

  // ─── ALERTA SONORA: Campana (> 90%) o Chime Cuantitativo (Grado A/A+) ────────
  const prevHighProbKeyRef = useRef<string>('');
  const prevGradeRef = useRef<string>('');

  useEffect(() => {
    // Detectar si alguna probabilidad de los mercados supera o iguala el 90% (0.90)
    let currentHighKey = '';
    if (probOver >= 0.90) currentHighKey = `OVER_${linea}_${(probOver * 100).toFixed(0)}`;
    else if (probUnder >= 0.90) currentHighKey = `UNDER_${linea}_${(probUnder * 100).toFixed(0)}`;
    else if (probSpreadHome >= 0.90) currentHighKey = `SPREAD_HOME_${spreadLine}_${(probSpreadHome * 100).toFixed(0)}`;
    else if (probSpreadAway >= 0.90) currentHighKey = `SPREAD_AWAY_${spreadLine}_${(probSpreadAway * 100).toFixed(0)}`;
    else if (probMlHome >= 0.90) currentHighKey = `ML_HOME_${(probMlHome * 100).toFixed(0)}`;
    else if (probMlAway >= 0.90) currentHighKey = `ML_AWAY_${(probMlAway * 100).toFixed(0)}`;

    if (currentHighKey && currentHighKey !== prevHighProbKeyRef.current) {
      // 🔔 Probabilidad mayor al 90%: emitir sonido de campana
      sounds.playBellAlert();
    } else if (
      !currentHighKey &&
      (calcGrade?.includes('GRADO A+') || calcGrade?.includes('GRADO A')) &&
      !prevGradeRef.current?.includes('GRADO A')
    ) {
      sounds.playValueAlert();
    }

    prevHighProbKeyRef.current = currentHighKey;
    prevGradeRef.current = calcGrade;
  }, [probOver, probUnder, probSpreadHome, probSpreadAway, probMlHome, probMlAway, linea, spreadLine, calcGrade]);

  // ─── Handler registro general ────────────────────────────────────────────────
  const handleRegisterBet = async (
    tipo: 'OVER' | 'UNDER' | 'SPREAD' | 'MONEYLINE',
    customLinea?: number,
    customCuota?: number,
    customEv?: number,
    customProb?: number,
    customGrade?: string,
    equipoApostado?: string
  ) => {
    setRegistering(true);
    try {
      const validProb = customProb ?? (tipo === 'OVER' ? probOver : (tipo === 'UNDER' ? probUnder : (tipo === 'SPREAD' ? probSpreadHome : probMlHome)));
      const rawCuota = customCuota ?? (tipo === 'OVER' ? cuotaOver : (tipo === 'UNDER' ? cuotaUnder : (tipo === 'SPREAD' ? cuotaSpreadHome : cuotaMlHome)));
      const validCuota = (rawCuota && rawCuota > 1.0) ? Number(rawCuota) : 1.90;
      const validEv = customEv ?? (tipo === 'OVER' ? evOver : (tipo === 'UNDER' ? evUnder : (tipo === 'SPREAD' ? evSpreadHome : evMlHome)));
      const stake = suggestedStake > 0 ? suggestedStake : 100000;
      const validLinea = customLinea ?? (tipo === 'SPREAD' ? spreadLine : (tipo === 'MONEYLINE' ? 0.0 : ((linea !== undefined && !isNaN(linea)) ? Number(linea) : 215.5)));
      const grade = customGrade ?? calcGrade;

      await createApuesta(partidoId, {
        partido_id: partidoId,
        tipo_apuesta: tipo,
        linea: validLinea,
        cuota: validCuota,
        monto: Number(stake),
        prob_modelo: validProb ? Number(validProb.toFixed(4)) : 0.50,
        ev_estimado: validEv ? Number(validEv.toFixed(2)) : 0.0,
        kelly_sugerido: kellyFraction ? Number(kellyFraction.toFixed(4)) : 0.0,
        momento_cuarto: currentQuarter || 1,
        minuto_partido: elapsedMinutes || 0,
        es_ficticia: esFicticia,
        grado_apuesta: grade,
        spread_edge: tipo === 'SPREAD' ? spreadEdgeHome : spreadPts,
        equipo_apostado: equipoApostado,
        notas: `Veredicto ${grade} | ${tipo} ${validLinea} | EV: ${validEv.toFixed(1)}%`
      });

      sounds.playValueAlert();
      setRegisteredMsg(`✅ Apuesta ${tipo} ${validLinea !== 0 ? validLinea : ''} [${grade}] registrada (${esFicticia ? 'Simulada' : 'Real'})`);
      if (onBetRegistered) onBetRegistered();
      setTimeout(() => setRegisteredMsg(null), 4000);
    } catch (err: any) {
      alert(`Error al registrar apuesta: ${err.message}`);
    } finally {
      setRegistering(false);
    }
  };

  // ─── Handler registro manual ─────────────────────────────────────────────────
  const handleManualBet = async () => {
    if (manualMonto <= 0) { setManualMsg('❌ El monto debe ser mayor a 0'); return; }
    if (manualCuota <= 1.0) { setManualMsg('❌ La cuota debe ser mayor a 1.0'); return; }

    setManualRegistering(true);
    setManualMsg(null);
    try {
      const modelProb = manualTipo === 'OVER'
        ? (probOver > 0.01 ? probOver : 0.50)
        : (manualTipo === 'UNDER' ? probUnder : (manualTipo === 'SPREAD' ? probSpreadHome : probMlHome));

      await createApuesta(partidoId, {
        partido_id: partidoId,
        tipo_apuesta: manualTipo,
        linea: manualTipo === 'MONEYLINE' ? 0.0 : manualLinea,
        cuota: manualCuota,
        monto: manualMonto,
        prob_modelo: Number(modelProb.toFixed(4)),
        ev_estimado: Number((((modelProb * manualCuota) - 1.0) * 100).toFixed(2)),
        kelly_sugerido: 0.05,
        momento_cuarto: currentQuarter || 1,
        minuto_partido: elapsedMinutes || 0,
        es_ficticia: manualEsFicticia,
        grado_apuesta: 'MANUAL',
        spread_edge: manualTipo === 'SPREAD' ? spreadEdgeHome : spreadPts,
        equipo_apostado: (manualTipo === 'SPREAD' || manualTipo === 'MONEYLINE') ? manualEquipo : undefined,
        notas: manualNotas
          ? `[MANUAL] ${manualNotas} | Cuota: ${manualCuota}`
          : `[MANUAL] ${manualTipo} ${manualLinea} | Cuota: ${manualCuota}`
      });

      sounds.playValueAlert();
      setManualMsg(`✅ Apuesta manual ${manualTipo} registrada (${manualEsFicticia ? 'Ficticia' : 'Real'})`);
      if (onBetRegistered) onBetRegistered();
      setTimeout(() => setManualMsg(null), 5000);
    } catch (err: any) {
      setManualMsg(`❌ Error: ${err.message}`);
    } finally {
      setManualRegistering(false);
    }
  };

  return (
    <div className="glass-card glass-card-orange" style={{ padding: '22px' }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '16px',
        flexWrap: 'wrap',
        gap: '12px'
      }}>
        <div>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--accent-orange)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Target size={20} />
            Módulo Predictivo Multimercado & Veredicto Cuantitativo
          </h3>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
            Totales (O/U), Hándicap en Vivo, Moneyline, Parada Óptima y Explicabilidad XAI.
          </p>
        </div>

        {/* Real vs Sim switch */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'var(--bg-surface-elevated)', padding: '4px 8px', borderRadius: '8px' }}>
          <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Modo:</label>
          <button
            type="button"
            onClick={() => setEsFicticia(true)}
            style={{
              padding: '4px 10px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.78rem',
              fontWeight: 700,
              background: esFicticia ? 'var(--accent-orange)' : 'transparent',
              color: esFicticia ? '#fff' : 'var(--text-muted)'
            }}
          >
            Ficticia (Test)
          </button>
          <button
            type="button"
            onClick={() => setEsFicticia(false)}
            style={{
              padding: '4px 10px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.78rem',
              fontWeight: 700,
              background: !esFicticia ? '#10b981' : 'transparent',
              color: !esFicticia ? '#fff' : 'var(--text-muted)'
            }}
          >
            Real
          </button>
        </div>
      </div>

      {/* ─── Banner de Política de Parada Óptima & Sobre-reacción ─── */}
      {simulation?.optimal_stopping_action && (
        <div style={{
          background: simulation.optimal_stopping_action === 'ENTRAR_AHORA'
            ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(5, 150, 105, 0.08) 100%)'
            : (simulation.optimal_stopping_action === 'ESPERAR_MEJOR_LINEA'
              ? 'linear-gradient(135deg, rgba(234, 179, 8, 0.2) 0%, rgba(180, 83, 9, 0.08) 100%)'
              : 'rgba(148, 163, 184, 0.08)'),
          border: `1.5px solid ${
            simulation.optimal_stopping_action === 'ENTRAR_AHORA'
              ? '#10b981'
              : (simulation.optimal_stopping_action === 'ESPERAR_MEJOR_LINEA' ? '#eab308' : '#64748b')
          }`,
          borderRadius: '12px',
          padding: '12px 18px',
          marginBottom: '18px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          boxShadow: simulation.optimal_stopping_action === 'ENTRAR_AHORA' ? '0 0 20px rgba(16, 185, 129, 0.2)' : 'none'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '1.4rem' }}>
              {simulation.optimal_stopping_action === 'ENTRAR_AHORA' ? '🚀' : (simulation.optimal_stopping_action === 'ESPERAR_MEJOR_LINEA' ? '⏳' : '⏸️')}
            </span>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{
                  fontWeight: 900,
                  fontSize: '0.92rem',
                  letterSpacing: '0.3px',
                  color: simulation.optimal_stopping_action === 'ENTRAR_AHORA' ? '#10b981' : (simulation.optimal_stopping_action === 'ESPERAR_MEJOR_LINEA' ? '#fbbf24' : '#94a3b8')
                }}>
                  POLÍTICA ÓPTIMA: {simulation.optimal_stopping_action.replace(/_/g, ' ')}
                </span>
                {simulation.overreaction_detected && (
                  <span style={{ background: '#f59e0b', color: '#000', fontWeight: 900, fontSize: '0.7rem', padding: '2px 8px', borderRadius: '4px' }}>
                    🔥 SOBRE-REACCIÓN DETECTADA
                  </span>
                )}
              </div>
              <div style={{ fontSize: '0.78rem', color: '#cbd5e1', marginTop: '3px' }}>
                {simulation.optimal_stopping_action === 'ENTRAR_AHORA'
                  ? 'Discrepancia estadística máxima identificada. El modelo recomienda ejecutar la apuesta antes del ajuste de la casa.'
                  : (simulation.optimal_stopping_action === 'ESPERAR_MEJOR_LINEA'
                    ? 'Racha anotadora en progreso. Esperar el pico máximo de la sobre-reacción de la línea en directo.'
                    : 'Mercado eficiente sin desvío analítico suficiente. Mantener cautela.')}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ─── Pestañas de Navegación de Mercado ─── */}
      <div style={{
        display: 'flex',
        gap: '8px',
        marginBottom: '20px',
        borderBottom: '1px solid var(--border-subtle)',
        paddingBottom: '10px',
        overflowX: 'auto'
      }}>
        <button
          type="button"
          onClick={() => setActiveMarket('TOTALS')}
          style={{
            padding: '8px 16px',
            borderRadius: '8px',
            border: 'none',
            cursor: 'pointer',
            fontWeight: 800,
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: activeMarket === 'TOTALS' ? 'var(--accent-orange)' : 'rgba(255,255,255,0.05)',
            color: activeMarket === 'TOTALS' ? '#fff' : 'var(--text-secondary)'
          }}
        >
          <Activity size={15} /> Totales (Over/Under)
        </button>
        <button
          type="button"
          onClick={() => setActiveMarket('SPREAD')}
          style={{
            padding: '8px 16px',
            borderRadius: '8px',
            border: 'none',
            cursor: 'pointer',
            fontWeight: 800,
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: activeMarket === 'SPREAD' ? 'var(--accent-orange)' : 'rgba(255,255,255,0.05)',
            color: activeMarket === 'SPREAD' ? '#fff' : 'var(--text-secondary)'
          }}
        >
          <Scale size={15} /> Hándicap (Spread)
        </button>
        <button
          type="button"
          onClick={() => setActiveMarket('MONEYLINE')}
          style={{
            padding: '8px 16px',
            borderRadius: '8px',
            border: 'none',
            cursor: 'pointer',
            fontWeight: 800,
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: activeMarket === 'MONEYLINE' ? 'var(--accent-orange)' : 'rgba(255,255,255,0.05)',
            color: activeMarket === 'MONEYLINE' ? '#fff' : 'var(--text-secondary)'
          }}
        >
          <Award size={15} /> Moneyline (Ganador)
        </button>
        <button
          type="button"
          onClick={() => setActiveMarket('XAI')}
          style={{
            padding: '8px 16px',
            borderRadius: '8px',
            border: 'none',
            cursor: 'pointer',
            fontWeight: 800,
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: activeMarket === 'XAI' ? 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)' : 'rgba(255,255,255,0.05)',
            color: '#fff'
          }}
        >
          <Brain size={15} /> Explicabilidad XAI
        </button>

        <button
          type="button"
          onClick={() => sounds.playBellAlert()}
          title="Prueba el sonido especial de campana cuando la probabilidad supera el 90%"
          style={{
            marginLeft: 'auto',
            padding: '7px 14px',
            borderRadius: '8px',
            border: '1px solid rgba(251, 191, 36, 0.4)',
            cursor: 'pointer',
            fontWeight: 800,
            fontSize: '0.8rem',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: 'rgba(251, 191, 36, 0.12)',
            color: '#fbbf24',
            transition: 'all 0.2s ease'
          }}
        >
          🔔 Probar Campana (&gt;90%)
        </button>
      </div>

      {/* ─── CONTENIDO: MERCADO DE TOTALES (O/U) ─── */}
      {activeMarket === 'TOTALS' && (
        <>
          {isActionable ? (
            <div style={{
              background: favSide === 'OVER' ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.18) 0%, rgba(5, 150, 105, 0.08) 100%)' : 'linear-gradient(135deg, rgba(244, 63, 94, 0.18) 0%, rgba(225, 29, 72, 0.08) 100%)',
              border: `2px solid ${favSide === 'OVER' ? '#10b981' : '#f43f5e'}`,
              borderRadius: '12px',
              padding: '16px 20px',
              marginBottom: '22px',
              boxShadow: favSide === 'OVER' ? '0 0 25px rgba(16, 185, 129, 0.25)' : '0 0 25px rgba(244, 63, 94, 0.25)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '14px' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', flex: 1, minWidth: '280px' }}>
                  <div style={{
                    width: '42px',
                    height: '42px',
                    borderRadius: '10px',
                    background: favSide === 'OVER' ? 'rgba(16, 185, 129, 0.25)' : 'rgba(244, 63, 94, 0.25)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0
                  }}>
                    <Award size={24} color={favSide === 'OVER' ? '#10b981' : '#f43f5e'} />
                  </div>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '1.12rem', fontWeight: 900, color: favSide === 'OVER' ? '#10b981' : '#f43f5e' }}>
                        🎯 MOMENTO DE APUESTA: {favSide === 'OVER' ? `MÁS DE ${linea} (OVER)` : `MENOS DE ${linea} (UNDER)`}
                      </span>
                      <span style={{ background: calcBadgeColor, color: '#000', fontWeight: 900, fontSize: '0.78rem', padding: '3px 10px', borderRadius: '6px' }}>
                        {calcGrade}
                      </span>
                    </div>
                    <div style={{ marginTop: '6px', fontSize: '0.86rem', color: '#e2e8f0', lineHeight: 1.45 }}>
                      El modelo proyecta una media de <strong style={{ color: '#fff' }}>{simulation?.total_mean?.toFixed(1)} pts</strong> ({spreadPts > 0 ? `+${spreadPts}` : spreadPts} pts de ventaja sobre la línea de {linea}).
                      <br />
                      Probabilidad estimada: <strong style={{ color: favSide === 'OVER' ? '#10b981' : '#f43f5e' }}>+{(maxProb * 100).toFixed(1)}%</strong> | Stake sugerido: <strong style={{ color: 'var(--accent-gold)' }}>{calcUnits}</strong> (Kelly: Gs. {suggestedStake.toLocaleString('es-PY')}).
                    </div>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => handleRegisterBet(favSide as 'OVER' | 'UNDER')}
                  disabled={registering}
                  className="btn-primary"
                  style={{
                    background: favSide === 'OVER' ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)' : 'linear-gradient(135deg, #f43f5e 0%, #e11d48 100%)',
                    fontWeight: 900,
                    fontSize: '0.92rem',
                    padding: '10px 22px',
                    whiteSpace: 'nowrap'
                  }}
                >
                  {registering ? 'Registrando...' : `⚡ Apostar ${favSide} Ahora`}
                </button>
              </div>
            </div>
          ) : (
            <div style={{
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '10px',
              padding: '12px 18px',
              marginBottom: '22px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '1.2rem' }}>⚖️</span>
                <span style={{ fontWeight: 700, color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
                  Línea de mercado equilibrada / Sin ventaja suficiente ({calcGrade})
                </span>
              </div>
              <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                Proyección modelo: <strong style={{ color: '#fff' }}>{simulation?.total_mean?.toFixed(1) || '--'} pts</strong> vs Línea casa: <strong style={{ color: '#fff' }}>{linea}</strong>
              </span>
            </div>
          )}

          {/* Input controls Totales */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '14px', marginBottom: '20px' }}>
            <div style={{ background: 'var(--bg-surface-elevated)', padding: '10px 14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>LÍNEA TOTAL (CASA)</label>
              <input type="number" step="0.5" value={linea} onChange={(e) => setLinea(Number(e.target.value))} style={{ width: '100%', background: 'transparent', border: 'none', color: '#fff', fontSize: '1.2rem', fontWeight: 800, fontFamily: 'JetBrains Mono', outline: 'none' }} />
            </div>
            <div style={{ background: 'var(--bg-surface-elevated)', padding: '10px 14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>CUOTA OVER (+)</label>
              <input type="number" step="0.05" value={cuotaOver} onChange={(e) => setCuotaOver(Number(e.target.value))} style={{ width: '100%', background: 'transparent', border: 'none', color: '#10b981', fontSize: '1.2rem', fontWeight: 800, fontFamily: 'JetBrains Mono', outline: 'none' }} />
            </div>
            <div style={{ background: 'var(--bg-surface-elevated)', padding: '10px 14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>CUOTA UNDER (-)</label>
              <input type="number" step="0.05" value={cuotaUnder} onChange={(e) => setCuotaUnder(Number(e.target.value))} style={{ width: '100%', background: 'transparent', border: 'none', color: '#f43f5e', fontSize: '1.2rem', fontWeight: 800, fontFamily: 'JetBrains Mono', outline: 'none' }} />
            </div>
            <div style={{ background: 'var(--bg-surface-elevated)', padding: '10px 14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>BANKROLL (Gs.)</label>
              <input type="number" step="50000" value={bankroll} onChange={(e) => setBankroll(Number(e.target.value))} style={{ width: '100%', background: 'transparent', border: 'none', color: 'var(--accent-orange)', fontSize: '1.2rem', fontWeight: 800, fontFamily: 'JetBrains Mono', outline: 'none' }} />
            </div>
          </div>

          {/* Comparison Cards: OVER vs UNDER */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
            <div style={{
              background: probOver >= 0.90 ? 'rgba(251, 191, 36, 0.12)' : (evOver > 0 ? 'rgba(16, 185, 129, 0.08)' : 'var(--bg-surface-elevated)'),
              border: probOver >= 0.90 ? '2px solid #fbbf24' : `1.5px solid ${evOver > 0 ? '#10b981' : 'var(--border-subtle)'}`,
              borderRadius: '12px',
              padding: '16px',
              textAlign: 'center',
              boxShadow: probOver >= 0.90 ? '0 0 24px rgba(251, 191, 36, 0.25)' : undefined,
              position: 'relative'
            }}>
              {probOver >= 0.90 && (
                <div style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '5px',
                  background: 'rgba(251, 191, 36, 0.2)',
                  color: '#fbbf24',
                  border: '1px solid #fbbf24',
                  borderRadius: '6px',
                  padding: '3px 10px',
                  fontSize: '0.72rem',
                  fontWeight: 900,
                  marginBottom: '8px',
                  letterSpacing: '0.3px'
                }}>
                  🔔 ALTA PROBABILIDAD (&gt; 90%)
                </div>
              )}
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#10b981', marginBottom: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
                <TrendingUp size={16} /> MÁS DE {linea} (OVER)
              </div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: probOver >= 0.90 ? '#fbbf24' : '#fff', fontFamily: 'JetBrains Mono' }}>{(probOver * 100).toFixed(1)}%</div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: '4px 0' }}>Cuota Justa: <strong>{fairOddsOver}</strong> | Casa: <strong>{cuotaOver}</strong></div>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: evOver >= 0 ? '#10b981' : '#f43f5e', marginTop: '8px' }}>EV: {evOver >= 0 ? `+${evOver.toFixed(1)}%` : `${evOver.toFixed(1)}%`}</div>
              <button type="button" onClick={() => handleRegisterBet('OVER')} disabled={registering} className="btn-primary" style={{ marginTop: '12px', width: '100%', justifyContent: 'center', background: probOver >= 0.90 ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)' : (evOver > 0 ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)' : 'var(--bg-surface)'), fontSize: '0.88rem' }}>Apostar OVER</button>
            </div>

            <div style={{
              background: probUnder >= 0.90 ? 'rgba(251, 191, 36, 0.12)' : (evUnder > 0 ? 'rgba(244, 63, 94, 0.08)' : 'var(--bg-surface-elevated)'),
              border: probUnder >= 0.90 ? '2px solid #fbbf24' : `1.5px solid ${evUnder > 0 ? '#f43f5e' : 'var(--border-subtle)'}`,
              borderRadius: '12px',
              padding: '16px',
              textAlign: 'center',
              boxShadow: probUnder >= 0.90 ? '0 0 24px rgba(251, 191, 36, 0.25)' : undefined,
              position: 'relative'
            }}>
              {probUnder >= 0.90 && (
                <div style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '5px',
                  background: 'rgba(251, 191, 36, 0.2)',
                  color: '#fbbf24',
                  border: '1px solid #fbbf24',
                  borderRadius: '6px',
                  padding: '3px 10px',
                  fontSize: '0.72rem',
                  fontWeight: 900,
                  marginBottom: '8px',
                  letterSpacing: '0.3px'
                }}>
                  🔔 ALTA PROBABILIDAD (&gt; 90%)
                </div>
              )}
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#f43f5e', marginBottom: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
                <TrendingDown size={16} /> MENOS DE {linea} (UNDER)
              </div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: probUnder >= 0.90 ? '#fbbf24' : '#fff', fontFamily: 'JetBrains Mono' }}>{(probUnder * 100).toFixed(1)}%</div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: '4px 0' }}>Cuota Justa: <strong>{fairOddsUnder}</strong> | Casa: <strong>{cuotaUnder}</strong></div>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: evUnder >= 0 ? '#10b981' : '#f43f5e', marginTop: '8px' }}>EV: {evUnder >= 0 ? `+${evUnder.toFixed(1)}%` : `${evUnder.toFixed(1)}%`}</div>
              <button type="button" onClick={() => handleRegisterBet('UNDER')} disabled={registering} className="btn-primary" style={{ marginTop: '12px', width: '100%', justifyContent: 'center', background: probUnder >= 0.90 ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)' : (evUnder > 0 ? 'linear-gradient(135deg, #f43f5e 0%, #e11d48 100%)' : 'var(--bg-surface)'), fontSize: '0.88rem' }}>Apostar UNDER</button>
            </div>
          </div>
        </>
      )}

      {/* ─── CONTENIDO: MERCADO DE HÁNDICAP (SPREAD) ─── */}
      {activeMarket === 'SPREAD' && (
        <>
          <div style={{
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '10px',
            padding: '14px 18px',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '12px'
          }}>
            <div>
              <span style={{ fontWeight: 800, color: '#38bdf8', fontSize: '0.9rem' }}>
                Margen Final Proyectado por Monte Carlo: {Number(simMargin) > 0 ? `+${Number(simMargin).toFixed(1)}` : Number(simMargin || 0).toFixed(1)} pts
              </span>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                Ventaja sobre el Spread de la Casa: <strong style={{ color: spreadEdgeHome > 0 ? '#10b981' : '#f43f5e' }}>{spreadEdgeHome > 0 ? `+${spreadEdgeHome}` : spreadEdgeHome} pts</strong>
              </div>
            </div>
            <span className="badge-tag badge-blue" style={{ fontSize: '0.78rem' }}>
              {Math.abs(spreadEdgeHome) >= 2.5 ? 'VENTAJA DE SPREAD DETECTADA' : 'LÍNEA AJUSTADA'}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '14px', marginBottom: '20px' }}>
            <div style={{ background: 'var(--bg-surface-elevated)', padding: '10px 14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>HÁNDICAP LOCAL</label>
              <input type="number" step="0.5" value={spreadLine} onChange={(e) => setSpreadLine(Number(e.target.value))} style={{ width: '100%', background: 'transparent', border: 'none', color: '#fff', fontSize: '1.2rem', fontWeight: 800, fontFamily: 'JetBrains Mono', outline: 'none' }} />
            </div>
            <div style={{ background: 'var(--bg-surface-elevated)', padding: '10px 14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>CUOTA LOCAL CUBRE</label>
              <input type="number" step="0.05" value={cuotaSpreadHome} onChange={(e) => setCuotaSpreadHome(Number(e.target.value))} style={{ width: '100%', background: 'transparent', border: 'none', color: '#38bdf8', fontSize: '1.2rem', fontWeight: 800, fontFamily: 'JetBrains Mono', outline: 'none' }} />
            </div>
            <div style={{ background: 'var(--bg-surface-elevated)', padding: '10px 14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>CUOTA VIS. CUBRE</label>
              <input type="number" step="0.05" value={cuotaSpreadAway} onChange={(e) => setCuotaSpreadAway(Number(e.target.value))} style={{ width: '100%', background: 'transparent', border: 'none', color: '#a78bfa', fontSize: '1.2rem', fontWeight: 800, fontFamily: 'JetBrains Mono', outline: 'none' }} />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
            {/* Local Cubre */}
            <div style={{ background: evSpreadHome > 0 ? 'rgba(56, 189, 248, 0.08)' : 'var(--bg-surface-elevated)', border: `1.5px solid ${evSpreadHome > 0 ? '#38bdf8' : 'var(--border-subtle)'}`, borderRadius: '12px', padding: '16px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#38bdf8', marginBottom: '4px' }}>
                LOCAL ({spreadLine > 0 ? `+${spreadLine}` : spreadLine})
              </div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fff', fontFamily: 'JetBrains Mono' }}>{(probSpreadHome * 100).toFixed(1)}%</div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: '4px 0' }}>Cuota Justa: <strong>{(1 / probSpreadHome).toFixed(2)}</strong> | Casa: <strong>{cuotaSpreadHome}</strong></div>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: evSpreadHome >= 0 ? '#10b981' : '#f43f5e', marginTop: '8px' }}>EV: {evSpreadHome >= 0 ? `+${evSpreadHome.toFixed(1)}%` : `${evSpreadHome.toFixed(1)}%`}</div>
              <button type="button" onClick={() => handleRegisterBet('SPREAD', spreadLine, cuotaSpreadHome, evSpreadHome, probSpreadHome, 'SPREAD LOCAL', 'LOCAL')} disabled={registering} className="btn-primary" style={{ marginTop: '12px', width: '100%', justifyContent: 'center', background: evSpreadHome > 0 ? 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)' : 'var(--bg-surface)', fontSize: '0.88rem' }}>Apostar Local Cubre</button>
            </div>

            {/* Visitante Cubre */}
            <div style={{ background: evSpreadAway > 0 ? 'rgba(167, 139, 250, 0.08)' : 'var(--bg-surface-elevated)', border: `1.5px solid ${evSpreadAway > 0 ? '#a78bfa' : 'var(--border-subtle)'}`, borderRadius: '12px', padding: '16px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#a78bfa', marginBottom: '4px' }}>
                VISITANTE ({-spreadLine > 0 ? `+${-spreadLine}` : -spreadLine})
              </div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fff', fontFamily: 'JetBrains Mono' }}>{(probSpreadAway * 100).toFixed(1)}%</div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: '4px 0' }}>Cuota Justa: <strong>{(1 / probSpreadAway).toFixed(2)}</strong> | Casa: <strong>{cuotaSpreadAway}</strong></div>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: evSpreadAway >= 0 ? '#10b981' : '#f43f5e', marginTop: '8px' }}>EV: {evSpreadAway >= 0 ? `+${evSpreadAway.toFixed(1)}%` : `${evSpreadAway.toFixed(1)}%`}</div>
              <button type="button" onClick={() => handleRegisterBet('SPREAD', -spreadLine, cuotaSpreadAway, evSpreadAway, probSpreadAway, 'SPREAD VISITANTE', 'VISITANTE')} disabled={registering} className="btn-primary" style={{ marginTop: '12px', width: '100%', justifyContent: 'center', background: evSpreadAway > 0 ? 'linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%)' : 'var(--bg-surface)', fontSize: '0.88rem' }}>Apostar Visitante Cubre</button>
            </div>
          </div>
        </>
      )}

      {/* ─── CONTENIDO: MERCADO DE MONEYLINE (GANADOR DIRECTO) ─── */}
      {activeMarket === 'MONEYLINE' && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '20px' }}>
            <div style={{ background: 'var(--bg-surface-elevated)', padding: '10px 14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>CUOTA GANADOR LOCAL (ML)</label>
              <input type="number" step="0.05" value={cuotaMlHome} onChange={(e) => setCuotaMlHome(Number(e.target.value))} style={{ width: '100%', background: 'transparent', border: 'none', color: '#10b981', fontSize: '1.2rem', fontWeight: 800, fontFamily: 'JetBrains Mono', outline: 'none' }} />
            </div>
            <div style={{ background: 'var(--bg-surface-elevated)', padding: '10px 14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>CUOTA GANADOR VISITANTE (ML)</label>
              <input type="number" step="0.05" value={cuotaMlAway} onChange={(e) => setCuotaMlAway(Number(e.target.value))} style={{ width: '100%', background: 'transparent', border: 'none', color: '#f43f5e', fontSize: '1.2rem', fontWeight: 800, fontFamily: 'JetBrains Mono', outline: 'none' }} />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
            {/* Local ML */}
            <div style={{ background: evMlHome > 0 ? 'rgba(16, 185, 129, 0.08)' : 'var(--bg-surface-elevated)', border: `1.5px solid ${evMlHome > 0 ? '#10b981' : 'var(--border-subtle)'}`, borderRadius: '12px', padding: '16px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#10b981', marginBottom: '4px' }}>VICTORIA LOCAL</div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fff', fontFamily: 'JetBrains Mono' }}>{(probMlHome * 100).toFixed(1)}%</div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: '4px 0' }}>Cuota Justa: <strong>{fairOddsMlHome}</strong> | Casa: <strong>{cuotaMlHome}</strong></div>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: evMlHome >= 0 ? '#10b981' : '#f43f5e', marginTop: '8px' }}>EV: {evMlHome >= 0 ? `+${evMlHome.toFixed(1)}%` : `${evMlHome.toFixed(1)}%`}</div>
              <button type="button" onClick={() => handleRegisterBet('MONEYLINE', 0.0, cuotaMlHome, evMlHome, probMlHome, 'ML LOCAL', 'LOCAL')} disabled={registering} className="btn-primary" style={{ marginTop: '12px', width: '100%', justifyContent: 'center', background: evMlHome > 0 ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)' : 'var(--bg-surface)', fontSize: '0.88rem' }}>Apostar Local ML</button>
            </div>

            {/* Visitante ML */}
            <div style={{ background: evMlAway > 0 ? 'rgba(244, 63, 94, 0.08)' : 'var(--bg-surface-elevated)', border: `1.5px solid ${evMlAway > 0 ? '#f43f5e' : 'var(--border-subtle)'}`, borderRadius: '12px', padding: '16px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#f43f5e', marginBottom: '4px' }}>VICTORIA VISITANTE</div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fff', fontFamily: 'JetBrains Mono' }}>{(probMlAway * 100).toFixed(1)}%</div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: '4px 0' }}>Cuota Justa: <strong>{fairOddsMlAway}</strong> | Casa: <strong>{cuotaMlAway}</strong></div>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: evMlAway >= 0 ? '#10b981' : '#f43f5e', marginTop: '8px' }}>EV: {evMlAway >= 0 ? `+${evMlAway.toFixed(1)}%` : `${evMlAway.toFixed(1)}%`}</div>
              <button type="button" onClick={() => handleRegisterBet('MONEYLINE', 0.0, cuotaMlAway, evMlAway, probMlAway, 'ML VISITANTE', 'VISITANTE')} disabled={registering} className="btn-primary" style={{ marginTop: '12px', width: '100%', justifyContent: 'center', background: evMlAway > 0 ? 'linear-gradient(135deg, #f43f5e 0%, #e11d48 100%)' : 'var(--bg-surface)', fontSize: '0.88rem' }}>Apostar Visitante ML</button>
            </div>
          </div>
        </>
      )}

      {/* ─── CONTENIDO: EXPLICABILIDAD XAI (DEEP LEARNING ATTENTION) ─── */}
      {activeMarket === 'XAI' && (
        <div style={{
          background: 'rgba(99, 102, 241, 0.06)',
          border: '1px solid rgba(99, 102, 241, 0.3)',
          borderRadius: '12px',
          padding: '20px',
          marginBottom: '20px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Brain size={22} color="#818cf8" />
              <span style={{ fontWeight: 800, fontSize: '1rem', color: '#c7d2fe' }}>
                Pesos de Atención Transformer & Interpretabilidad
              </span>
            </div>
            <span style={{ fontSize: '0.75rem', background: 'rgba(99, 102, 241, 0.25)', color: '#818cf8', fontWeight: 800, padding: '3px 10px', borderRadius: '6px' }}>
              BasketballTransformerNet v2
            </span>
          </div>

          <p style={{ fontSize: '0.82rem', color: '#94a3b8', marginBottom: '16px', lineHeight: 1.5 }}>
            La red neuronal procesa el play-by-play secuencialmente y asigna atención a los factores clave que modulan el ritmo y el spread.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {/* Factor 1: Momentum */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: '4px' }}>
                <span style={{ color: '#e2e8f0', fontWeight: 600 }}>⚡ Atención a Momentum & Rachas Recientes</span>
                <span style={{ color: '#818cf8', fontWeight: 800 }}>{((xaiFactors.atencion_momentum || 0.35) * 100).toFixed(0)}%</span>
              </div>
              <div style={{ height: '8px', background: 'rgba(255,255,255,0.08)', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ width: `${Math.min(100, (xaiFactors.atencion_momentum || 0.35) * 100)}%`, height: '100%', background: 'linear-gradient(90deg, #6366f1, #818cf8)', borderRadius: '4px' }} />
              </div>
            </div>

            {/* Factor 2: Lineup */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: '4px' }}>
                <span style={{ color: '#e2e8f0', fontWeight: 600 }}>🏀 Impacto de Quinteto & Calidad de Jugadores</span>
                <span style={{ color: '#38bdf8', fontWeight: 800 }}>{((xaiFactors.impacto_alineaciones || 0.28) * 100).toFixed(0)}%</span>
              </div>
              <div style={{ height: '8px', background: 'rgba(255,255,255,0.08)', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ width: `${Math.min(100, (xaiFactors.impacto_alineaciones || 0.28) * 100)}%`, height: '100%', background: 'linear-gradient(90deg, #0284c7, #38bdf8)', borderRadius: '4px' }} />
              </div>
            </div>

            {/* Factor 3: 3PT Variance */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: '4px' }}>
                <span style={{ color: '#e2e8f0', fontWeight: 600 }}>🎯 Varianza de Tiro Exterior (Triples)</span>
                <span style={{ color: '#ec4899', fontWeight: 800 }}>{((xaiFactors.varianza_triples || 0.22) * 100).toFixed(0)}%</span>
              </div>
              <div style={{ height: '8px', background: 'rgba(255,255,255,0.08)', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ width: `${Math.min(100, (xaiFactors.varianza_triples || 0.22) * 100)}%`, height: '100%', background: 'linear-gradient(90deg, #db2777, #ec4899)', borderRadius: '4px' }} />
              </div>
            </div>

            {/* Factor 4: Time Remaining */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: '4px' }}>
                <span style={{ color: '#e2e8f0', fontWeight: 600 }}>⏳ Factor de Desgaste & Tiempo Restante</span>
                <span style={{ color: '#10b981', fontWeight: 800 }}>{((xaiFactors.factor_tiempo_restante || 0.15) * 100).toFixed(0)}%</span>
              </div>
              <div style={{ height: '8px', background: 'rgba(255,255,255,0.08)', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ width: `${Math.min(100, (xaiFactors.factor_tiempo_restante || 0.15) * 100)}%`, height: '100%', background: 'linear-gradient(90deg, #059669, #10b981)', borderRadius: '4px' }} />
              </div>
            </div>
          </div>

          <div style={{
            marginTop: '18px',
            paddingTop: '14px',
            borderTop: '1px solid rgba(255,255,255,0.1)',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: '12px',
            fontSize: '0.8rem'
          }}>
            <div>
              <span style={{ color: '#94a3b8' }}>Multiplicador Ritmo DL:</span>
              <div style={{ fontWeight: 800, color: '#fff', fontSize: '0.95rem' }}>{simulation?.dl_pace_multiplier?.toFixed(3) || '1.000'}x</div>
            </div>
            <div>
              <span style={{ color: '#94a3b8' }}>Delta Ritmo:</span>
              <div style={{ fontWeight: 800, color: '#38bdf8', fontSize: '0.95rem' }}>{simulation?.dl_delta_pace ? `${simulation.dl_delta_pace > 0 ? '+' : ''}${simulation.dl_delta_pace.toFixed(2)} pts/min` : '0.00 pts/min'}</div>
            </div>
            <div>
              <span style={{ color: '#94a3b8' }}>Incertidumbre Epistémica:</span>
              <div style={{ fontWeight: 800, color: '#f59e0b', fontSize: '0.95rem' }}>±{simulation?.dl_uncertainty_pts?.toFixed(1) || '0.0'} pts</div>
            </div>
          </div>
        </div>
      )}

      {/* Kelly Stake Footer Banner */}
      <div style={{
        background: 'rgba(0, 0, 0, 0.4)',
        border: '1px solid var(--border-subtle)',
        borderRadius: '10px',
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '10px',
        fontSize: '0.85rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <DollarSign size={18} color="var(--accent-gold)" />
          <span>
            Recomendación Criterio de Kelly (1/4): <strong style={{ color: 'var(--accent-gold)' }}>Gs. {suggestedStake.toLocaleString('es-PY')}</strong> ({(kellyFraction * 100).toFixed(1)}% del bankroll)
          </span>
        </div>

        {bestEv > 0 ? (
          <span className="badge-tag badge-green">
            VENTAJA DETECTADA: {bestBet} (+{bestEv.toFixed(1)}% EV)
          </span>
        ) : (
          <span className="badge-tag badge-gold">
            SIN VALOR SUFICIENTE EN ESTA LÍNEA
          </span>
        )}
      </div>

      {registeredMsg && (
        <div style={{
          marginTop: '12px',
          padding: '10px',
          borderRadius: '8px',
          background: 'rgba(16, 185, 129, 0.15)',
          border: '1px solid #10b981',
          color: '#10b981',
          fontWeight: 700,
          textAlign: 'center',
          fontSize: '0.88rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px'
        }}>
          <CheckCircle2 size={16} />
          {registeredMsg}
        </div>
      )}

      {/* ─── Formulario Manual de Registro de Apuesta ─────────────────────── */}
      <div style={{
        marginTop: '20px',
        borderTop: '1px solid var(--border-subtle)',
        paddingTop: '16px'
      }}>
        <button
          type="button"
          onClick={() => setShowManualForm(v => !v)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '8px',
            padding: '8px 14px',
            cursor: 'pointer',
            color: 'var(--text-secondary)',
            fontSize: '0.85rem',
            fontWeight: 700,
            width: '100%',
            justifyContent: 'space-between'
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <PenLine size={15} />
            Registrar Apuesta Manualmente (Multimercado)
          </span>
          {showManualForm ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>

        {showManualForm && (
          <div style={{
            marginTop: '14px',
            background: 'rgba(0,0,0,0.3)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '10px',
            padding: '18px'
          }}>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '14px', lineHeight: 1.5 }}>
              Ingresá tu apuesta para auditoría CLV y cálculo automático de liquidación al finalizar el partido.
            </p>

            {/* Tipo Selector */}
            <div style={{ marginBottom: '14px' }}>
              <label style={{ fontSize: '0.73rem', color: 'var(--text-muted)', fontWeight: 700, display: 'block', marginBottom: '6px' }}>TIPO DE MERCADO</label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
                {(['OVER', 'UNDER', 'SPREAD', 'MONEYLINE'] as const).map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setManualTipo(t)}
                    style={{
                      padding: '8px',
                      borderRadius: '8px',
                      border: `1.5px solid ${manualTipo === t ? 'var(--accent-orange)' : 'var(--border-subtle)'}`,
                      background: manualTipo === t ? 'rgba(255, 119, 0, 0.15)' : 'transparent',
                      color: manualTipo === t ? 'var(--accent-orange)' : 'var(--text-muted)',
                      fontWeight: 800,
                      fontSize: '0.78rem',
                      cursor: 'pointer'
                    }}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            {/* Equipo Selector si es Spread o Moneyline */}
            {(manualTipo === 'SPREAD' || manualTipo === 'MONEYLINE') && (
              <div style={{ marginBottom: '14px' }}>
                <label style={{ fontSize: '0.73rem', color: 'var(--text-muted)', fontWeight: 700, display: 'block', marginBottom: '6px' }}>EQUIPO APOSTADO</label>
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button
                    type="button"
                    onClick={() => setManualEquipo('LOCAL')}
                    style={{
                      flex: 1, padding: '8px', borderRadius: '8px', border: `1.5px solid ${manualEquipo === 'LOCAL' ? '#38bdf8' : 'var(--border-subtle)'}`,
                      background: manualEquipo === 'LOCAL' ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
                      color: manualEquipo === 'LOCAL' ? '#38bdf8' : 'var(--text-muted)',
                      fontWeight: 800, fontSize: '0.82rem', cursor: 'pointer'
                    }}
                  >
                    LOCAL
                  </button>
                  <button
                    type="button"
                    onClick={() => setManualEquipo('VISITANTE')}
                    style={{
                      flex: 1, padding: '8px', borderRadius: '8px', border: `1.5px solid ${manualEquipo === 'VISITANTE' ? '#a78bfa' : 'var(--border-subtle)'}`,
                      background: manualEquipo === 'VISITANTE' ? 'rgba(167, 139, 250, 0.15)' : 'transparent',
                      color: manualEquipo === 'VISITANTE' ? '#a78bfa' : 'var(--text-muted)',
                      fontWeight: 800, fontSize: '0.82rem', cursor: 'pointer'
                    }}
                  >
                    VISITANTE
                  </button>
                </div>
              </div>
            )}

            {/* Grid: Línea / Cuota / Monto */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '14px' }}>
              <div style={{ background: 'var(--bg-surface-elevated)', padding: '10px 12px', borderRadius: '8px' }}>
                <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 700, display: 'block', marginBottom: '4px' }}>
                  {manualTipo === 'MONEYLINE' ? 'LÍNEA (N/A)' : 'LÍNEA'}
                </label>
                <input
                  type="number" step="0.5" value={manualLinea}
                  disabled={manualTipo === 'MONEYLINE'}
                  onChange={e => setManualLinea(Number(e.target.value))}
                  style={{ width: '100%', background: 'transparent', border: 'none', color: '#fff', fontSize: '1.1rem', fontWeight: 800, outline: 'none', fontFamily: 'JetBrains Mono' }}
                />
              </div>
              <div style={{ background: 'var(--bg-surface-elevated)', padding: '10px 12px', borderRadius: '8px' }}>
                <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 700, display: 'block', marginBottom: '4px' }}>CUOTA (ODDS)</label>
                <input
                  type="number" step="0.01" value={manualCuota}
                  onChange={e => setManualCuota(Number(e.target.value))}
                  style={{ width: '100%', background: 'transparent', border: 'none', color: 'var(--accent-gold)', fontSize: '1.1rem', fontWeight: 800, outline: 'none', fontFamily: 'JetBrains Mono' }}
                />
              </div>
              <div style={{ background: 'var(--bg-surface-elevated)', padding: '10px 12px', borderRadius: '8px' }}>
                <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 700, display: 'block', marginBottom: '4px' }}>MONTO (Gs.)</label>
                <input
                  type="number" step="10000" value={manualMonto}
                  onChange={e => setManualMonto(Number(e.target.value))}
                  style={{ width: '100%', background: 'transparent', border: 'none', color: 'var(--accent-orange)', fontSize: '1.1rem', fontWeight: 800, outline: 'none', fontFamily: 'JetBrains Mono' }}
                />
              </div>
            </div>

            {/* Notas opcionales */}
            <div style={{ marginBottom: '14px' }}>
              <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 700, display: 'block', marginBottom: '4px' }}>NOTAS (opcional)</label>
              <input
                type="text" placeholder="Ej: Disparo de cuota en Q3 por racha 10-0..."
                value={manualNotas} onChange={e => setManualNotas(e.target.value)}
                style={{
                  width: '100%', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-subtle)',
                  borderRadius: '6px', color: '#fff', padding: '7px 10px', fontSize: '0.82rem', outline: 'none'
                }}
              />
            </div>

            {/* Real vs Ficticia */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 700 }}>MODO:</label>
              <button
                type="button" onClick={() => setManualEsFicticia(true)}
                style={{
                  padding: '5px 14px', borderRadius: '6px', border: 'none', cursor: 'pointer', fontSize: '0.78rem', fontWeight: 700,
                  background: manualEsFicticia ? 'var(--accent-orange)' : 'rgba(255,255,255,0.06)',
                  color: manualEsFicticia ? '#fff' : 'var(--text-muted)'
                }}
              >📝 Ficticia (Test)</button>
              <button
                type="button" onClick={() => setManualEsFicticia(false)}
                style={{
                  padding: '5px 14px', borderRadius: '6px', border: 'none', cursor: 'pointer', fontSize: '0.78rem', fontWeight: 700,
                  background: !manualEsFicticia ? '#10b981' : 'rgba(255,255,255,0.06)',
                  color: !manualEsFicticia ? '#fff' : 'var(--text-muted)'
                }}
              >💵 Real</button>
              <span style={{ marginLeft: 'auto', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                Ganancia potencial: <strong style={{ color: 'var(--accent-gold)' }}>Gs. {((manualMonto * manualCuota) - manualMonto).toLocaleString('es-PY', { maximumFractionDigits: 0 })}</strong>
              </span>
            </div>

            {/* Botón Registrar */}
            <button
              type="button"
              onClick={handleManualBet}
              disabled={manualRegistering}
              className="btn-primary"
              style={{
                width: '100%',
                justifyContent: 'center',
                background: 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)',
                padding: '10px',
                fontWeight: 900,
                fontSize: '0.92rem'
              }}
            >
              {manualRegistering ? 'Registrando...' : `💾 Registrar ${manualTipo} · Gs. ${manualMonto.toLocaleString('es-PY')}`}
            </button>

            {manualMsg && (
              <div style={{
                marginTop: '10px', padding: '9px 12px', borderRadius: '8px', fontWeight: 700, fontSize: '0.84rem', textAlign: 'center',
                background: manualMsg.startsWith('✅') ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.12)',
                border: `1px solid ${manualMsg.startsWith('✅') ? '#10b981' : '#ef4444'}`,
                color: manualMsg.startsWith('✅') ? '#10b981' : '#f87171'
              }}>
                {manualMsg}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
