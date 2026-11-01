import React, { useState, useEffect } from 'react';
import { Cpu, RefreshCw, CheckCircle2, Sliders, Brain, Zap, Database, Clock, DownloadCloud } from 'lucide-react';
import {
  getCalibracionActiva,
  entrenarCalibracion,
  getEstadoDeepLearning,
  entrenarDeepLearning,
  ingestarWNBA,
  ingestarNBA,
} from '../api/client';

export const Calibracion: React.FC = () => {
  const [calib, setCalib] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [training, setTraining] = useState(false);
  const [trainResult, setTrainResult] = useState<any>(null);

  // Deep Learning state
  const [dlStatus, setDlStatus] = useState<any>(null);
  const [dlLoading, setDlLoading] = useState(true);
  const [dlTraining, setDlTraining] = useState(false);
  const [dlResult, setDlResult] = useState<any>(null);
  const [dlEpochs, setDlEpochs] = useState(35);
  const [dlBatchSize, setDlBatchSize] = useState(16);
  const [dlLr, setDlLr] = useState(0.001);

  // Ingesta Oficial WNBA & NBA
  const [ingestLeague, setIngestLeague] = useState<'WNBA' | 'NBA'>('WNBA');
  const [ingestCount, setIngestCount] = useState(3);
  const [ingestSeason, setIngestSeason] = useState('2024');
  const [ingestStars, setIngestStars] = useState(true);
  const [ingesting, setIngesting] = useState(false);
  const [ingestResult, setIngestResult] = useState<any>(null);

  // Test calibrator
  const [testProb, setTestProb] = useState<number>(0.65);

  const loadCalib = async () => {
    setLoading(true);
    try {
      const data = await getCalibracionActiva();
      setCalib(data);
    } catch (err: any) {
      console.error('Error al cargar calibración:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadDlStatus = async () => {
    setDlLoading(true);
    try {
      const data = await getEstadoDeepLearning();
      setDlStatus(data);
    } catch (err: any) {
      console.error('Error al obtener estado DL:', err);
    } finally {
      setDlLoading(false);
    }
  };

  useEffect(() => {
    loadCalib();
    loadDlStatus();
  }, []);

  const handleTrain = async () => {
    setTraining(true);
    setTrainResult(null);
    try {
      const res = await entrenarCalibracion();
      setTrainResult(res);
      await loadCalib();
    } catch (err: any) {
      alert(`Error al entrenar: ${err.message}`);
    } finally {
      setTraining(false);
    }
  };

  const handleTrainDL = async () => {
    setDlTraining(true);
    setDlResult(null);
    try {
      const res = await entrenarDeepLearning({
        epochs: dlEpochs,
        batch_size: dlBatchSize,
        learning_rate: dlLr,
      });
      setDlResult(res);
      await loadDlStatus();
    } catch (err: any) {
      alert(`Error al entrenar red neuronal: ${err.message}`);
    } finally {
      setDlTraining(false);
    }
  };

  const handleIngestar = async () => {
    setIngesting(true);
    setIngestResult(null);
    try {
      let res;
      if (ingestLeague === 'WNBA') {
        res = await ingestarWNBA({
          num_partidos: ingestCount,
          temporada: ingestSeason,
          poblar_estrellas: ingestStars,
        });
      } else {
        res = await ingestarNBA({
          num_partidos: ingestCount,
          temporada: ingestSeason,
          poblar_estrellas: ingestStars,
        });
      }
      setIngestResult(res);
      await loadCalib();
      await loadDlStatus();
    } catch (err: any) {
      alert(`Error al ingestar datos: ${err.message}`);
    } finally {
      setIngesting(false);
    }
  };

  // Platt scaling calculation preview
  const a = calib?.platt_a || 1.0;
  const b = calib?.platt_b || 0.0;
  const logit = Math.log(testProb / (1.0 - testProb));
  const z = a * logit + b;
  const calibratedProb = 1.0 / (1.0 + Math.exp(-z));

  const dlActive = dlStatus?.modelo_activo_en_memoria;
  const dlOnDisk = dlStatus?.modelo_en_disco;

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '24px' }}>
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.8rem', fontWeight: 800, letterSpacing: '-0.5px' }}>
          Calibración Probabilística &amp; Auto-Aprendizaje
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', marginTop: '4px' }}>
          Platt Scaling estadístico + Red Neuronal Residual (DeepMomentumResidualNet). El sistema aprende de cada partido cargado a la BD.
        </p>
      </div>

      {/* ─── INGESTA OFICIAL WNBA & NBA DATA WAREHOUSE ─── */}
      <div className="glass-card" style={{
        padding: '24px',
        marginBottom: '24px',
        border: '1.5px solid rgba(249, 115, 22, 0.4)',
        background: 'linear-gradient(135deg, rgba(249, 115, 22, 0.05) 0%, rgba(10, 10, 25, 0.95) 100%)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '42px', height: '42px', borderRadius: '10px',
              background: 'rgba(249, 115, 22, 0.18)',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <DownloadCloud size={22} color="#f97316" />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#fff' }}>
                  Ingesta Oficial de Datos &amp; Play-by-Play
                </h3>
                <span style={{
                  fontSize: '0.72rem', fontWeight: 800, padding: '2px 8px', borderRadius: '4px',
                  background: 'rgba(249, 115, 22, 0.2)', color: '#f97316', border: '1px solid rgba(249, 115, 22, 0.4)'
                }}>
                  WNBA + NBA LIVE API
                </span>
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                Descarga partidos oficiales con play-by-play detallado e inyecta estadísticas de jugadoras/jugadores estrella para entrenar los modelos.
              </p>
            </div>
          </div>
        </div>

        {/* League Selector & Parameters */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginTop: '16px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '6px', fontWeight: 700 }}>
              LIGA
            </label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                type="button"
                onClick={() => { setIngestLeague('WNBA'); setIngestSeason('2024'); }}
                style={{
                  flex: 1,
                  padding: '9px 14px',
                  borderRadius: '8px',
                  border: ingestLeague === 'WNBA' ? '2px solid #f97316' : '1px solid var(--border-subtle)',
                  background: ingestLeague === 'WNBA' ? 'rgba(249, 115, 22, 0.2)' : 'var(--bg-surface-elevated)',
                  color: ingestLeague === 'WNBA' ? '#f97316' : 'var(--text-secondary)',
                  fontWeight: 700,
                  fontSize: '0.88rem',
                  cursor: 'pointer'
                }}
              >
                🏀 WNBA (10 min)
              </button>
              <button
                type="button"
                onClick={() => { setIngestLeague('NBA'); setIngestSeason('2023-24'); }}
                style={{
                  flex: 1,
                  padding: '9px 14px',
                  borderRadius: '8px',
                  border: ingestLeague === 'NBA' ? '2px solid #3b82f6' : '1px solid var(--border-subtle)',
                  background: ingestLeague === 'NBA' ? 'rgba(59, 130, 246, 0.2)' : 'var(--bg-surface-elevated)',
                  color: ingestLeague === 'NBA' ? '#60a5fa' : 'var(--text-secondary)',
                  fontWeight: 700,
                  fontSize: '0.88rem',
                  cursor: 'pointer'
                }}
              >
                🏀 NBA (12 min)
              </button>
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '6px', fontWeight: 700 }}>
              PARTIDOS A DESCARGAR (1 - 10)
            </label>
            <input
              type="number"
              min={1}
              max={10}
              value={ingestCount}
              onChange={(e) => setIngestCount(Math.max(1, Math.min(10, parseInt(e.target.value) || 1)))}
              style={{
                width: '100%',
                background: 'var(--bg-surface-elevated)',
                border: '1px solid var(--border-subtle)',
                color: '#fff',
                padding: '9px 12px',
                borderRadius: '8px',
                fontSize: '0.9rem',
                outline: 'none'
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '6px', fontWeight: 700 }}>
              TEMPORADA
            </label>
            <input
              type="text"
              value={ingestSeason}
              onChange={(e) => setIngestSeason(e.target.value)}
              placeholder={ingestLeague === 'WNBA' ? '2024' : '2023-24'}
              style={{
                width: '100%',
                background: 'var(--bg-surface-elevated)',
                border: '1px solid var(--border-subtle)',
                color: '#fff',
                padding: '9px 12px',
                borderRadius: '8px',
                fontSize: '0.9rem',
                outline: 'none'
              }}
            />
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '18px', flexWrap: 'wrap', gap: '12px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            <input
              type="checkbox"
              checked={ingestStars}
              onChange={(e) => setIngestStars(e.target.checked)}
              style={{ accentColor: '#f97316', cursor: 'pointer' }}
            />
            <span>Poblar/actualizar métricas analíticas de estrellas ({ingestLeague === 'WNBA' ? 'Caitlin Clark, A\'ja Wilson, Stewart...' : 'Tatum, Luka, LeBron...'})</span>
          </label>

          <button
            onClick={handleIngestar}
            disabled={ingesting}
            className="btn-primary"
            style={{
              padding: '10px 22px',
              fontSize: '0.9rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              background: ingestLeague === 'WNBA' ? 'linear-gradient(135deg, #ea580c 0%, #f97316 100%)' : undefined
            }}
          >
            <DownloadCloud size={17} />
            {ingesting ? `Descargando ${ingestLeague}...` : `Ingestar Partidos ${ingestLeague}`}
          </button>
        </div>

        {ingestResult && (
          <div style={{
            marginTop: '16px',
            padding: '14px',
            borderRadius: '8px',
            background: 'rgba(249, 115, 22, 0.12)',
            border: '1px solid rgba(249, 115, 22, 0.4)',
            color: '#fff',
            fontSize: '0.85rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 800, color: '#f97316', marginBottom: '6px' }}>
              <CheckCircle2 size={18} />
              {ingestResult.mensaje || 'Ingesta completada'}
            </div>
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
              <span>Partidos almacenados: <strong style={{ color: '#fff' }}>{ingestResult.partidos_ingestados}</strong></span>
              <span>Jugadas Play-by-Play procesadas: <strong style={{ color: '#fff' }}>{ingestResult.total_jugadas}</strong></span>
              {ingestResult.jugadoras_estrellas_registradas !== undefined && (
                <span>Jugadoras WNBA sembradas: <strong style={{ color: '#fff' }}>{ingestResult.jugadoras_estrellas_registradas}</strong></span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ─── Deep Learning Section ─── */}
      <div className="glass-card" style={{
        padding: '24px',
        marginBottom: '24px',
        border: dlActive
          ? '1.5px solid rgba(139, 92, 246, 0.5)'
          : '1.5px solid var(--border-subtle)',
        background: dlActive
          ? 'linear-gradient(135deg, rgba(139,92,246,0.08) 0%, rgba(6,6,20,0.95) 100%)'
          : undefined
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '42px', height: '42px', borderRadius: '10px',
              background: dlActive ? 'rgba(139,92,246,0.2)' : 'rgba(255,255,255,0.05)',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <Brain size={22} color={dlActive ? '#8b5cf6' : '#94a3b8'} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 800 }}>
                Red Neuronal Deep Learning
                <span style={{
                  marginLeft: '10px',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  padding: '3px 10px',
                  borderRadius: '6px',
                  background: dlActive ? 'rgba(139,92,246,0.25)' : 'rgba(255,255,255,0.06)',
                  color: dlActive ? '#a78bfa' : '#64748b',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px'
                }}>
                  {dlLoading ? '...' : dlActive ? '🟢 ACTIVA' : dlOnDisk ? '🟡 EN DISCO' : '🔴 NO ENTRENADA'}
                </span>
              </h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', marginTop: '2px' }}>
                DeepMomentumResidualNet · GRU Bidireccional + MLP Contextual · Multi-tarea
              </p>
            </div>
          </div>
        </div>

        {/* DL Status Grid */}
        {!dlLoading && dlStatus && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '12px',
            marginBottom: '20px'
          }}>
            <div style={{ background: 'var(--bg-surface-elevated)', padding: '14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Cpu size={12} /> ESTADO PYTORCH
              </div>
              <div style={{ fontWeight: 800, color: dlStatus.torch_disponible ? '#10b981' : '#f43f5e' }}>
                {dlStatus.torch_disponible ? 'Disponible ✓' : 'No disponible ✗'}
              </div>
            </div>

            <div style={{ background: 'var(--bg-surface-elevated)', padding: '14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Database size={12} /> MODELO EN DISCO
              </div>
              <div style={{ fontWeight: 800, color: dlOnDisk ? '#38bdf8' : '#94a3b8' }}>
                {dlOnDisk ? `${dlStatus.tamano_kb} KB ✓` : 'No encontrado'}
              </div>
            </div>

            <div style={{ background: 'var(--bg-surface-elevated)', padding: '14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Clock size={12} /> ÚLTIMO ENTRENAMIENTO
              </div>
              <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#e2e8f0' }}>
                {dlStatus.ultima_modificacion
                  ? new Date(dlStatus.ultima_modificacion).toLocaleString('es-PY')
                  : '—'}
              </div>
            </div>

            <div style={{ background: 'var(--bg-surface-elevated)', padding: '14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Zap size={12} /> EN MEMORIA (CACHE)
              </div>
              <div style={{ fontWeight: 800, color: dlActive ? '#8b5cf6' : '#64748b' }}>
                {dlActive ? 'Cargada y activa ✓' : 'No cargada'}
              </div>
            </div>
          </div>
        )}

        {/* DL Training Controls */}
        <div style={{
          background: 'rgba(0,0,0,0.3)',
          border: '1px solid var(--border-subtle)',
          borderRadius: '12px',
          padding: '18px',
          marginBottom: '16px'
        }}>
          <div style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '14px' }}>
            Hiperparámetros de Entrenamiento
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', marginBottom: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                ÉPOCAS: <strong style={{ color: '#a78bfa' }}>{dlEpochs}</strong>
              </label>
              <input
                type="range" min={5} max={150} step={5} value={dlEpochs}
                onChange={(e) => setDlEpochs(Number(e.target.value))}
                style={{ width: '100%', accentColor: '#8b5cf6', cursor: 'pointer' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                BATCH SIZE: <strong style={{ color: '#a78bfa' }}>{dlBatchSize}</strong>
              </label>
              <input
                type="range" min={4} max={64} step={4} value={dlBatchSize}
                onChange={(e) => setDlBatchSize(Number(e.target.value))}
                style={{ width: '100%', accentColor: '#8b5cf6', cursor: 'pointer' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                LEARNING RATE: <strong style={{ color: '#a78bfa' }}>{dlLr}</strong>
              </label>
              <select
                value={dlLr}
                onChange={(e) => setDlLr(Number(e.target.value))}
                style={{
                  width: '100%', background: 'var(--bg-surface)', color: '#fff',
                  border: '1px solid var(--border-subtle)', borderRadius: '6px',
                  padding: '6px 8px', fontSize: '0.85rem'
                }}
              >
                <option value={0.01}>0.01 (Rápido)</option>
                <option value={0.001}>0.001 (Estándar)</option>
                <option value={0.0003}>0.0003 (Fino)</option>
                <option value={0.0001}>0.0001 (Muy fino)</option>
              </select>
            </div>
          </div>

          <button
            onClick={handleTrainDL}
            disabled={dlTraining || !dlStatus?.torch_disponible}
            className="btn-primary"
            style={{
              background: dlTraining
                ? 'rgba(139,92,246,0.4)'
                : 'linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%)',
              boxShadow: dlTraining ? 'none' : '0 4px 20px rgba(139,92,246,0.4)',
              fontSize: '0.92rem',
              fontWeight: 800,
              padding: '10px 24px',
              width: '100%',
              justifyContent: 'center',
              opacity: !dlStatus?.torch_disponible ? 0.5 : 1,
            }}
          >
            <Brain size={18} className={dlTraining ? 'spin-animation' : ''} />
            {dlTraining
              ? `🧠 Entrenando red neuronal (${dlEpochs} épocas, puede tardar 30–90s)...`
              : '🧠 Iniciar Re-Entrenamiento Deep Learning desde BD'}
          </button>

          {!dlStatus?.torch_disponible && (
            <p style={{ fontSize: '0.78rem', color: '#f87171', marginTop: '8px', textAlign: 'center' }}>
              ⚠️ PyTorch no está disponible en el contenedor. Verificar que torch esté instalado en el entorno.
            </p>
          )}
        </div>

        {/* What does auto-learning do? */}
        <div style={{
          background: 'rgba(139,92,246,0.06)',
          border: '1px solid rgba(139,92,246,0.2)',
          borderRadius: '10px',
          padding: '14px 16px',
          fontSize: '0.82rem',
          color: 'var(--text-secondary)',
          lineHeight: 1.6
        }}>
          <strong style={{ color: '#a78bfa' }}>🤖 Cómo funciona el auto-aprendizaje:</strong> La red extrae secuencias de jugadas y contextos macro de todos los partidos guardados en la BD. Con cada reentrenamiento, la red ajusta sus pesos para predecir con mayor precisión el <strong>delta de ritmo</strong>, los <strong>puntos restantes</strong> y la <strong>probabilidad de victoria</strong>. El modelo guardado se carga automáticamente en las siguientes simulaciones en vivo.
        </div>

        {/* DL Training Result */}
        {dlResult && (
          <div style={{
            marginTop: '16px',
            padding: '14px',
            borderRadius: '8px',
            background: dlResult.exito ? 'rgba(139,92,246,0.15)' : 'rgba(244,63,94,0.15)',
            border: `1px solid ${dlResult.exito ? '#8b5cf6' : '#f43f5e'}`,
            fontSize: '0.88rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, marginBottom: '8px', color: dlResult.exito ? '#a78bfa' : '#f87171' }}>
              {dlResult.exito ? <CheckCircle2 size={18} /> : '⚠️'}
              {dlResult.exito ? 'Red neuronal entrenada con éxito' : 'Error en entrenamiento'}
            </div>
            {dlResult.exito && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '10px', marginBottom: '10px' }}>
                <div style={{ background: 'rgba(0,0,0,0.3)', padding: '10px', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>ÉPOCAS</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, fontFamily: 'JetBrains Mono', color: '#a78bfa' }}>{dlResult.epochs}</div>
                </div>
                <div style={{ background: 'rgba(0,0,0,0.3)', padding: '10px', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>MUESTRAS</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, fontFamily: 'JetBrains Mono', color: '#38bdf8' }}>{dlResult.total_muestras}</div>
                </div>
                <div style={{ background: 'rgba(0,0,0,0.3)', padding: '10px', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>PÉRDIDA FINAL</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, fontFamily: 'JetBrains Mono', color: '#10b981' }}>{dlResult.perdida_final}</div>
                </div>
                <div style={{ background: 'rgba(0,0,0,0.3)', padding: '10px', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>MAE RITMO</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, fontFamily: 'JetBrains Mono', color: '#f59e0b' }}>{dlResult.mae_pace_final}</div>
                </div>
              </div>
            )}
            {!dlResult.exito && (
              <div style={{ color: '#f87171' }}>{dlResult.error}</div>
            )}
          </div>
        )}
      </div>

      {/* ─── Platt Scaling Section ─── */}
      <div className="glass-card" style={{ padding: '24px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Cpu size={22} color="var(--accent-orange)" />
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>Parámetros de Calibración Estadística (Platt Scaling)</h3>
          </div>

          <button
            onClick={handleTrain}
            disabled={training}
            className="btn-primary"
            style={{ padding: '8px 18px', fontSize: '0.88rem' }}
          >
            <RefreshCw size={16} className={training ? 'spin-animation' : ''} />
            {training ? 'Entrenando sobre DB...' : 'Re-Entrenar Platt Scaling'}
          </button>
        </div>

        {loading ? (
          <div style={{ color: 'var(--text-muted)' }}>Cargando calibración...</div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '16px'
          }}>
            <div style={{ background: 'var(--bg-surface-elevated)', padding: '16px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>PENDIENTE (PLATT A)</div>
              <div style={{ fontSize: '1.6rem', fontWeight: 800, fontFamily: 'JetBrains Mono', color: 'var(--accent-orange)' }}>
                {a.toFixed(4)}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                Sensibilidad / Escala sigmoide
              </div>
            </div>

            <div style={{ background: 'var(--bg-surface-elevated)', padding: '16px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>SESGO (PLATT B)</div>
              <div style={{ fontSize: '1.6rem', fontWeight: 800, fontFamily: 'JetBrains Mono', color: '#38bdf8' }}>
                {b.toFixed(4)}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                Desplazamiento a favor del Over/Under
              </div>
            </div>

            <div style={{ background: 'var(--bg-surface-elevated)', padding: '16px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>MUESTRA HISTÓRICA</div>
              <div style={{ fontSize: '1.6rem', fontWeight: 800, fontFamily: 'JetBrains Mono', color: '#10b981' }}>
                {calib?.n_muestras || calib?.n_partidos || 0}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                Partidos / Hitos cotejados
              </div>
            </div>
          </div>
        )}

        {trainResult && (
          <div style={{
            marginTop: '20px',
            padding: '14px',
            borderRadius: '8px',
            background: 'rgba(16, 185, 129, 0.15)',
            border: '1px solid #10b981',
            color: '#10b981',
            fontSize: '0.88rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, marginBottom: '6px' }}>
              <CheckCircle2 size={18} />
              Auto-entrenamiento estadístico completado con éxito
            </div>
            <pre style={{ fontFamily: 'JetBrains Mono', fontSize: '0.78rem', color: '#cbd5e0', whiteSpace: 'pre-wrap' }}>
              {JSON.stringify(trainResult, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Interactive Simulator of Platt Transform */}
      <div className="glass-card" style={{ padding: '24px' }}>
        <h3 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sliders size={18} color="var(--accent-orange)" />
          Simulador Interactivo de Platt Scaling
        </h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '18px' }}>
          Prueba cómo la curva sigmoide aprendida transforma una probabilidad cruda de Monte Carlo en una probabilidad empíricamente calibrada:
        </p>

        <div style={{ display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '240px' }}>
            <label style={{ display: 'block', fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
              PROBABILIDAD CRUDA DE MONTE CARLO: <strong>{(testProb * 100).toFixed(1)}%</strong>
            </label>
            <input
              type="range"
              min={0.01}
              max={0.99}
              step={0.01}
              value={testProb}
              onChange={(e) => setTestProb(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--accent-orange)', cursor: 'pointer' }}
            />
          </div>

          <div style={{
            background: 'var(--bg-surface-elevated)',
            padding: '14px 24px',
            borderRadius: '12px',
            border: '1px solid var(--border-subtle)',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '2px' }}>PROBABILIDAD CALIBRADA</div>
            <div style={{ fontSize: '1.8rem', fontWeight: 800, fontFamily: 'JetBrains Mono', color: '#10b981' }}>
              {(calibratedProb * 100).toFixed(1)}%
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              Ajuste: {((calibratedProb - testProb) * 100).toFixed(1)}%
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
