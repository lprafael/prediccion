import type {
  Partido,
  Tournament,
  SimulationResult,
  Apuesta,
  ResumenApuestas,
  Hito,
  Jugador,
  ForebetCruceResponse
} from '../types';


const API_BASE = import.meta.env.VITE_API_URL || '/api';

function getApiKey(): string {
  if (typeof window !== 'undefined') {
    const params = new URLSearchParams(window.location.search);
    const keyFromUrl = params.get('api_key') || params.get('key');
    if (keyFromUrl) {
      localStorage.setItem('poliverso_api_key', keyFromUrl);
    }
    const saved = localStorage.getItem('poliverso_api_key');
    if (saved) return saved;
  }
  return (import.meta.env.VITE_API_KEY as string) || '';
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const apiKey = getApiKey();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(apiKey ? { 'X-API-Key': apiKey } : {}),
    ...(options?.headers as Record<string, string> || {}),
  };

  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401 && typeof window !== 'undefined') {
      const prompted = window.prompt("Se requiere la clave de acceso de Poliverso (API Key):");
      if (prompted) {
        localStorage.setItem('poliverso_api_key', prompted.trim());
        return fetchJson<T>(url, options);
      }
    }
    let errorDetail = response.statusText;
    try {
      const errObj = await response.json();
      errorDetail = errObj.detail || errorDetail;
    } catch {
      // Ignorar error al parsear JSON
    }
    throw new Error(errorDetail || `Error ${response.status}`);
  }

  return response.json();
}

// ─── Torneos ────────────────────────────────────────────────────────────────
export async function getTorneos(): Promise<Tournament[]> {
  return fetchJson<Tournament[]>('/torneos');
}

// ─── Partidos ───────────────────────────────────────────────────────────────
export async function getPartidos(limit = 100): Promise<Partido[]> {
  return fetchJson<Partido[]>(`/partidos?limit=${limit}`);
}

export async function getPartido(id: number): Promise<Partido> {
  return fetchJson<Partido>(`/partidos/${id}`);
}

export async function createPartido(data: {
  equipo_local: string;
  equipo_visitante: string;
  torneo_nombre: string;
  cuarto_actual: number;
  min_restantes: number;
  seg_restantes: number;
  quarters_data: [number, number][];
  notas?: string;
}): Promise<{ id: number; message: string }> {
  return fetchJson<{ id: number; message: string }>('/partidos', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updatePartido(
  id: number,
  data: {
    cuarto_actual: number;
    min_restantes: number;
    seg_restantes: number;
    quarters_data: [number, number][];
    notas?: string;
  }
): Promise<{ message: string }> {
  return fetchJson<{ message: string }>(`/partidos/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deletePartido(id: number): Promise<{ message: string }> {
  return fetchJson<{ message: string }>(`/partidos/${id}`, {
    method: 'DELETE',
  });
}

export async function finalizarPartido(
  id: number,
  data: {
    pts_local_final: number;
    pts_visitante_final: number;
    quarters_data?: [number, number][];
    notas?: string;
  }
): Promise<any> {
  return fetchJson<any>(`/partidos/${id}/finalizar`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// ─── Simulación ─────────────────────────────────────────────────────────────
export async function runSimulacion(data: {
  torneo_key: string;
  current_quarter: number;
  elapsed_seconds_in_quarter: number;
  quarters_data: [number, number][];
  n_simulations?: number;
  actual_total_scores?: [number, number];
  linea_apuesta?: number;
  use_deep_learning?: boolean;
}): Promise<SimulationResult> {
  return fetchJson<SimulationResult>('/simular', {
    method: 'POST',
    body: JSON.stringify({
      n_simulations: 5000,
      use_deep_learning: true,
      ...data,
    }),
  });
}

export async function getBaseline(torneoKey = 'NBA'): Promise<{
  tournament_key: string;
  tournament_name: string;
  quarter_duration: number;
  timeline: any[];
}> {
  return fetchJson(`/baseline?torneo_key=${encodeURIComponent(torneoKey)}`);
}

// ─── Apuestas ───────────────────────────────────────────────────────────────
export async function getApuestasPartido(partidoId: number): Promise<Apuesta[]> {
  return fetchJson<Apuesta[]>(`/partidos/${partidoId}/apuestas`);
}

export async function getAllApuestas(limit = 200): Promise<Apuesta[]> {
  return fetchJson<Apuesta[]>(`/apuestas?limit=${limit}`);
}

export async function createApuesta(
  partidoId: number,
  data: {
    partido_id?: number;
    tipo_apuesta: string;
    linea: number;
    cuota: number;
    monto: number;
    prob_modelo?: number;
    ev_estimado?: number;
    kelly_sugerido?: number;
    momento_cuarto?: number;
    minuto_partido?: number;
    marcador_momento?: string;
    es_ficticia?: boolean;
    notas?: string;
    grado_apuesta?: string;
    spread_edge?: number;
    equipo_apostado?: string;
    linea_cierre_casa?: number;
    cuota_cierre_casa?: number;
  }
): Promise<{ id: number; message: string }> {
  return fetchJson<{ id: number; message: string }>(`/partidos/${partidoId}/apuestas`, {
    method: 'POST',
    body: JSON.stringify({ partido_id: partidoId, ...data }),
  });
}


export async function updateApuestaResultado(
  apuestaId: number,
  resultado: 'GANADA' | 'PERDIDA' | 'PUSH',
  gananciaNeta?: number
): Promise<{ message: string }> {
  return fetchJson<{ message: string }>(`/apuestas/${apuestaId}/resultado`, {
    method: 'PUT',
    body: JSON.stringify({ resultado, ganancia_neta: gananciaNeta }),
  });
}

export async function deleteApuesta(apuestaId: number): Promise<{ message: string }> {
  return fetchJson<{ message: string }>(`/apuestas/${apuestaId}`, {
    method: 'DELETE',
  });
}

export async function updateApuesta(
  apuestaId: number,
  data: {
    monto?: number;
    cuota?: number;
    linea?: number;
    tipo_apuesta?: string;
    resultado?: string;
    ganancia_neta?: number;
    notas?: string;
  }
): Promise<{ message: string }> {
  return fetchJson<{ message: string }>(`/apuestas/${apuestaId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function getResumenApuestas(): Promise<ResumenApuestas> {
  return fetchJson<ResumenApuestas>('/apuestas/resumen');
}

export async function getMetricasApuestas(): Promise<any> {
  return fetchJson<any>('/apuestas/metricas');
}

// ─── Hitos & Snapshots ──────────────────────────────────────────────────────
export async function getHitos(partidoId?: number): Promise<Hito[]> {
  if (partidoId) {
    return fetchJson<Hito[]>(`/partidos/${partidoId}/hitos`);
  }
  return fetchJson<Hito[]>('/hitos');
}

export async function createHito(
  partidoId: number,
  data: any
): Promise<{ id: number; message: string }> {
  return fetchJson<{ id: number; message: string }>(`/partidos/${partidoId}/hitos`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// ─── Calibración ────────────────────────────────────────────────────────────
export async function getCalibracionActiva(): Promise<any> {
  return fetchJson<any>('/calibracion/activa');
}

export async function entrenarCalibracion(): Promise<any> {
  return fetchJson<any>('/calibracion/entrenar', {
    method: 'POST',
  });
}

export async function getCotejoHitos(partidoId: number): Promise<any> {
  return fetchJson<any>(`/partidos/${partidoId}/cotejo`);
}

export async function getEstadoDeepLearning(): Promise<any> {
  return fetchJson<any>('/calibracion/estado-dl');
}

export async function entrenarDeepLearning(params?: {
  epochs?: number;
  batch_size?: number;
  learning_rate?: number;
}): Promise<any> {
  return fetchJson<any>('/calibracion/entrenar-dl', {
    method: 'POST',
    body: JSON.stringify(params || {}),
  });
}

// ─── Scraper Aposta.la ──────────────────────────────────────────────────────
export async function extraerAposta(url: string): Promise<any> {
  return fetchJson<any>('/scraper/extraer', {
    method: 'POST',
    body: JSON.stringify({ url }),
  });
}

export async function crearDesdeAposta(url: string, notas?: string): Promise<{ id: number; message: string; extracted_data: any }> {
  return fetchJson<{ id: number; message: string; extracted_data: any }>('/partidos/crear-desde-aposta', {
    method: 'POST',
    body: JSON.stringify({ url, notas }),
  });
}

export async function syncPartidoAposta(partidoId: number, url: string): Promise<any> {
  return fetchJson<any>(`/partidos/${partidoId}/sync-aposta`, {
    method: 'POST',
    body: JSON.stringify({ url }),
  });
}

/**
 * Ciclo de predicción live todo-en-uno:
 * Lee jugadas de BD → Monte Carlo+DL → Señales play-by-play → Veredicto apuesta.
 * Diseñado para ejecutarse cada 15s en el auto-sync.
 */
export async function simularLive(
  partidoId: number,
  params?: {
    linea_apuesta?: number;
    cuota_over?: number;
    cuota_under?: number;
    n_simulations?: number;
    lineup_local?: number[];
    lineup_visitante?: number[];
    fouls_local?: number;
    fouls_visitante?: number;
  }
): Promise<any> {
  return fetchJson<any>(`/partidos/${partidoId}/simular-live`, {
    method: 'POST',
    body: JSON.stringify(params || {}),
  });
}

// ─── Jugadores, Lineups & CLV ───────────────────────────────────────────────
export async function getJugadores(equipo?: string): Promise<Jugador[]> {
  const query = equipo ? `?equipo=${encodeURIComponent(equipo)}` : '';
  return fetchJson<Jugador[]>(`/jugadores${query}`);
}

export async function getLineups(partidoId: number): Promise<{
  partido_id: number;
  equipo_local: string;
  equipo_visitante: string;
  lineup_local: number[];
  lineup_visitante: number[];
  fouls_local: number;
  fouls_visitante: number;
  jugadores_local: Jugador[];
  jugadores_visitante: Jugador[];
}> {
  return fetchJson(`/partidos/${partidoId}/lineups`);
}

export async function updateLineups(
  partidoId: number,
  data: {
    lineup_local?: number[];
    lineup_visitante?: number[];
    fouls_local?: number;
    fouls_visitante?: number;
  }
): Promise<{
  message: string;
  lineup_local: number[];
  lineup_visitante: number[];
  fouls_local: number;
  fouls_visitante: number;
}> {
  return fetchJson(`/partidos/${partidoId}/lineups`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function updateApuestaCLV(
  id: number,
  data: {
    linea_cierre_casa?: number;
    cuota_cierre_casa?: number;
  }
): Promise<any> {
  return fetchJson(`/apuestas/${id}/clv`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

// ─── Integración WNBA y NBA Data Ingestion ──────────────────────────────────
export interface WNBATeam {
  id: number;
  full_name: string;
  abbreviation: string;
  nickname: string;
  city: string;
  state: string;
  year_founded: number;
}

export async function getWNBATeams(): Promise<WNBATeam[]> {
  return fetchJson<WNBATeam[]>('/torneos/wnba/equipos');
}

export async function ingestarWNBA(params?: {
  num_partidos?: number;
  temporada?: string;
  poblar_estrellas?: boolean;
}): Promise<any> {
  return fetchJson<any>('/calibracion/ingestar-wnba', {
    method: 'POST',
    body: JSON.stringify(params || {}),
  });
}

export async function ingestarNBA(params?: {
  num_partidos?: number;
  temporada?: string;
  poblar_estrellas?: boolean;
}): Promise<any> {
  return fetchJson<any>('/calibracion/ingestar-nba', {
    method: 'POST',
    body: JSON.stringify(params || {}),
  });
}

// ─── Forebet vs Aposta.la Value Betting ─────────────────────────────────────
export async function getForebetCruce(params?: {
  refresh?: boolean;
  solo_valor?: boolean;
  min_ev?: number;
  liga?: string;
  q?: string;
}): Promise<ForebetCruceResponse> {
  const query = new URLSearchParams();
  if (params?.refresh) query.append('refresh', 'true');
  if (params?.solo_valor) query.append('solo_valor', 'true');
  if (params?.min_ev !== undefined && params.min_ev > 0) query.append('min_ev', params.min_ev.toString());
  if (params?.liga) query.append('liga', params.liga);
  if (params?.q) query.append('q', params.q);

  const qs = query.toString();
  return fetchJson<ForebetCruceResponse>(`/forebet-cruce${qs ? `?${qs}` : ''}`);
}

export async function escanearForebetCruce(): Promise<{
  message: string;
  last_updated: number;
  summary: any;
  total_matched: number;
}> {
  return fetchJson('/forebet-cruce/escanear', {
    method: 'POST',
  });
}


