import React, { useState, useEffect } from 'react';
import { PlusCircle, ArrowLeft, Trophy, Zap, CheckCircle2, AlertCircle } from 'lucide-react';
import type { Tournament } from '../types';
import { getTorneos, createPartido, extraerAposta, crearDesdeAposta } from '../api/client';
import { sounds } from '../utils/audio';

interface NuevoPartidoProps {
  onMatchCreated: (partidoId: number) => void;
  onCancel: () => void;
}

export const NuevoPartido: React.FC<NuevoPartidoProps> = ({ onMatchCreated, onCancel }) => {
  const [torneos, setTorneos] = useState<Tournament[]>([]);
  const [torneoNombre, setTorneoNombre] = useState('NBA (12 min/cuarto)');
  const [equipoLocal, setEquipoLocal] = useState('');
  const [equipoVisitante, setEquipoVisitante] = useState('');
  const [cuartoActual, setCuartoActual] = useState(1);
  const [minRestantes, setMinRestantes] = useState(12);
  const [segRestantes, setSegRestantes] = useState(0);
  const [notas, setNotas] = useState('');
  const [creating, setCreating] = useState(false);

  // Aposta.la auto-import state
  const [apostaUrl, setApostaUrl] = useState('');
  const [extracting, setExtracting] = useState(false);
  const [extractedData, setExtractedData] = useState<any | null>(null);
  const [extractError, setExtractError] = useState<string | null>(null);

  useEffect(() => {
    getTorneos().then((data) => {
      setTorneos(data);
      if (data.length > 0) {
        setTorneoNombre(data[0].name);
        setMinRestantes(data[0].quarter_duration);
      }
    }).catch(console.error);
  }, []);

  const handleTorneoChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setTorneoNombre(val);
    const found = torneos.find((t) => t.name === val);
    if (found) {
      setMinRestantes(found.quarter_duration);
    }
  };

  // 1. Extraer y crear directamente con un solo clic
  const handleAutoImportAndCreate = async () => {
    if (!apostaUrl.trim()) {
      alert('Pega el enlace del partido de Aposta.la o el ID numérico');
      return;
    }

    setExtracting(true);
    setExtractError(null);
    try {
      const res = await crearDesdeAposta(apostaUrl.trim(), 'Importado en vivo desde Aposta.la');
      sounds.playValueAlert();
      onMatchCreated(res.id);
    } catch (err: any) {
      setExtractError(err.message || 'No se pudieron extraer los datos');
      sounds.playWarning();
    } finally {
      setExtracting(false);
    }
  };

  // 2. Extraer para pre-llenar los campos en el formulario
  const handlePreviewExtract = async () => {
    if (!apostaUrl.trim()) return;

    setExtracting(true);
    setExtractError(null);
    try {
      const data = await extraerAposta(apostaUrl.trim());
      setExtractedData(data);
      setEquipoLocal(data.team_home);
      setEquipoVisitante(data.team_away);
      setCuartoActual(data.quarter);
      setMinRestantes(data.clock_min);
      setSegRestantes(data.clock_sec);

      if (data.tournament_key === 'NBA' || data.quarter_duration === 12) {
        setTorneoNombre('NBA (12 min/cuarto)');
      } else if (data.tournament_key === 'NBL') {
        setTorneoNombre('NBL Australia (10 min/cuarto)');
      } else {
        setTorneoNombre('FIBA / Euroliga / Ligas Locales (10 min/cuarto)');
      }

      sounds.playScoreTick();
    } catch (err: any) {
      setExtractError(err.message || 'Error al conectar con Aposta.la');
      sounds.playWarning();
    } finally {
      setExtracting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!equipoLocal.trim() || !equipoVisitante.trim()) {
      alert('Debes ingresar los nombres de ambos equipos');
      return;
    }

    setCreating(true);
    try {
      const res = await createPartido({
        equipo_local: equipoLocal.trim(),
        equipo_visitante: equipoVisitante.trim(),
        torneo_nombre: torneoNombre,
        cuarto_actual: cuartoActual,
        min_restantes: minRestantes,
        seg_restantes: segRestantes,
        quarters_data: extractedData?.quarter_scores || [
          [0, 0],
          [0, 0],
          [0, 0],
          [0, 0],
        ],
        notas: apostaUrl ? `${notas} | URL: ${apostaUrl}` : notas.trim(),
      });
      sounds.playValueAlert();
      onMatchCreated(res.id);
    } catch (err: any) {
      alert(`Error al crear partido: ${err.message}`);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div style={{ maxWidth: '780px', margin: '0 auto', padding: '24px' }}>
      <button
        onClick={onCancel}
        className="btn-secondary"
        style={{ marginBottom: '20px', padding: '6px 14px', fontSize: '0.85rem' }}
      >
        <ArrowLeft size={16} />
        Volver a Partidos
      </button>

      {/* ─── TARJETA DESTACADA: IMPORTACIÓN AUTOMÁTICA DESDE APOSTA.LA ──────── */}
      <div className="glass-card glass-card-orange" style={{ padding: '26px', marginBottom: '28px', position: 'relative' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '8px',
            background: 'var(--accent-orange)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <Zap size={20} color="#fff" />
          </div>
          <div>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--accent-orange)' }}>
              Importación Automática desde Aposta.la
            </h3>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              Pega el enlace del partido en vivo y el sistema extraerá automáticamente equipos, marcador, reloj y cuotas.
            </p>
          </div>
        </div>

        <div style={{ marginTop: '16px' }}>
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <input
              type="text"
              placeholder="Ej: https://aposta.la/sports-book/event/live/1021987... o solo el ID del evento"
              value={apostaUrl}
              onChange={(e) => setApostaUrl(e.target.value)}
              style={{
                flex: 1,
                minWidth: '280px',
                background: 'var(--bg-surface-elevated)',
                border: '1.5px solid var(--border-subtle)',
                color: '#fff',
                padding: '12px 16px',
                borderRadius: '8px',
                fontSize: '0.92rem',
                outline: 'none'
              }}
            />
            <button
              type="button"
              onClick={handleAutoImportAndCreate}
              disabled={extracting || !apostaUrl.trim()}
              className="btn-primary"
              style={{ padding: '12px 20px', fontSize: '0.92rem', whiteSpace: 'nowrap' }}
            >
              <Zap size={18} />
              {extracting ? 'Extrayendo...' : '1-Clic: Importar y Abrir'}
            </button>
            <button
              type="button"
              onClick={handlePreviewExtract}
              disabled={extracting || !apostaUrl.trim()}
              className="btn-secondary"
              style={{ padding: '12px 16px', fontSize: '0.88rem' }}
            >
              Cargar al Formulario
            </button>
          </div>

          {extractError && (
            <div style={{
              marginTop: '12px',
              padding: '10px 14px',
              borderRadius: '8px',
              background: 'rgba(244, 63, 94, 0.15)',
              border: '1px solid #f43f5e',
              color: '#f43f5e',
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <AlertCircle size={16} />
              {extractError}
            </div>
          )}

          {extractedData && !extractError && (
            <div style={{
              marginTop: '16px',
              padding: '14px',
              borderRadius: '10px',
              background: 'rgba(16, 185, 129, 0.12)',
              border: '1px solid #10b981',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckCircle2 size={18} color="#10b981" />
                <div>
                  <div style={{ fontWeight: 800, fontSize: '0.95rem', color: '#fff' }}>
                    {extractedData.team_home} ({extractedData.score_home}) – ({extractedData.score_away}) {extractedData.team_away}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                    Q{extractedData.quarter} · {extractedData.clock_min}:{extractedData.clock_sec?.toString().padStart(2, '0')} restante | {extractedData.league_name || 'Baloncesto'}
                  </div>
                </div>
              </div>

              {extractedData.odds_line && (
                <div style={{ background: 'var(--bg-surface-elevated)', padding: '6px 12px', borderRadius: '6px', fontSize: '0.85rem', fontWeight: 700, color: 'var(--accent-orange)' }}>
                  Línea en Vivo: {extractedData.odds_line} pts
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ─── FORMULARIO MANUAL O VERIFICACIÓN ────────────────────────────── */}
      <div className="glass-card" style={{ padding: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
          <div style={{
            width: '40px',
            height: '40px',
            borderRadius: '10px',
            background: 'var(--bg-surface-elevated)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: '1px solid var(--border-subtle)'
          }}>
            <Trophy size={20} color="var(--accent-orange)" />
          </div>
          <div>
            <h2 style={{ fontSize: '1.3rem', fontWeight: 800 }}>Configuración de Partido</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
              Verifica los parámetros o ingresa manualmente los datos del encuentro.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          {/* Torneo select */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, marginBottom: '6px', color: 'var(--text-secondary)' }}>
              Torneo / Reglamentación
            </label>
            <select
              value={torneoNombre}
              onChange={handleTorneoChange}
              style={{
                width: '100%',
                background: 'var(--bg-surface-elevated)',
                border: '1px solid var(--border-subtle)',
                color: '#fff',
                padding: '12px 14px',
                borderRadius: '8px',
                fontSize: '0.95rem',
                fontWeight: 600,
                outline: 'none'
              }}
            >
              {torneos.map((t) => (
                <option key={t.key} value={t.name}>
                  {t.name} ({t.quarter_duration} min/cuarto - Ritmo ~{t.league_pace} pos)
                </option>
              ))}
            </select>
          </div>

          {/* Teams grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, marginBottom: '6px', color: 'var(--text-secondary)' }}>
                Equipo Local
              </label>
              <input
                type="text"
                placeholder="Ej. Boston Celtics"
                value={equipoLocal}
                onChange={(e) => setEquipoLocal(e.target.value)}
                style={{
                  width: '100%',
                  background: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-subtle)',
                  color: '#fff',
                  padding: '12px 14px',
                  borderRadius: '8px',
                  fontSize: '0.95rem',
                  outline: 'none'
                }}
                required
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, marginBottom: '6px', color: 'var(--text-secondary)' }}>
                Equipo Visitante
              </label>
              <input
                type="text"
                placeholder="Ej. Golden State Warriors"
                value={equipoVisitante}
                onChange={(e) => setEquipoVisitante(e.target.value)}
                style={{
                  width: '100%',
                  background: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-subtle)',
                  color: '#fff',
                  padding: '12px 14px',
                  borderRadius: '8px',
                  fontSize: '0.95rem',
                  outline: 'none'
                }}
                required
              />
            </div>
          </div>

          {/* Initial Timing */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '14px', marginBottom: '20px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, marginBottom: '6px', color: 'var(--text-secondary)' }}>
                Cuarto Actual
              </label>
              <select
                value={cuartoActual}
                onChange={(e) => setCuartoActual(Number(e.target.value))}
                style={{
                  width: '100%',
                  background: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-subtle)',
                  color: '#fff',
                  padding: '10px',
                  borderRadius: '8px',
                  outline: 'none'
                }}
              >
                <option value={1}>1º Cuarto</option>
                <option value={2}>2º Cuarto</option>
                <option value={3}>3º Cuarto</option>
                <option value={4}>4º Cuarto</option>
                <option value={5}>Prórroga (OT)</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, marginBottom: '6px', color: 'var(--text-secondary)' }}>
                Minutos Restantes
              </label>
              <input
                type="number"
                min={0}
                max={20}
                value={minRestantes}
                onChange={(e) => setMinRestantes(Number(e.target.value))}
                style={{
                  width: '100%',
                  background: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-subtle)',
                  color: '#fff',
                  padding: '10px',
                  borderRadius: '8px',
                  fontFamily: 'JetBrains Mono',
                  outline: 'none'
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, marginBottom: '6px', color: 'var(--text-secondary)' }}>
                Segundos Restantes
              </label>
              <input
                type="number"
                min={0}
                max={59}
                value={segRestantes}
                onChange={(e) => setSegRestantes(Number(e.target.value))}
                style={{
                  width: '100%',
                  background: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-subtle)',
                  color: '#fff',
                  padding: '10px',
                  borderRadius: '8px',
                  fontFamily: 'JetBrains Mono',
                  outline: 'none'
                }}
              />
            </div>
          </div>

          {/* Notes */}
          <div style={{ marginBottom: '24px' }}>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, marginBottom: '6px', color: 'var(--text-secondary)' }}>
              Notas (opcional)
            </label>
            <input
              type="text"
              placeholder="Detalles tácticos, ausencias o contexto..."
              value={notas}
              onChange={(e) => setNotas(e.target.value)}
              style={{
                width: '100%',
                background: 'var(--bg-surface-elevated)',
                border: '1px solid var(--border-subtle)',
                color: '#fff',
                padding: '10px 14px',
                borderRadius: '8px',
                fontSize: '0.9rem',
                outline: 'none'
              }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
            <button type="button" onClick={onCancel} className="btn-secondary">
              Cancelar
            </button>
            <button type="submit" disabled={creating} className="btn-primary" style={{ padding: '12px 28px' }}>
              <PlusCircle size={18} />
              {creating ? 'Creando...' : 'Iniciar Mesa de Control'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
