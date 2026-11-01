import { useEffect, useRef, useState, useCallback } from 'react';
import type { Partido, SimulationResult } from '../types';
import { sounds } from '../utils/audio';

const defaultWsProtocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const defaultWsHost = typeof window !== 'undefined' ? window.location.host : 'localhost:8000';
const WS_BASE = import.meta.env.VITE_WS_URL || `${defaultWsProtocol}//${defaultWsHost}/ws/live`;

interface UseLiveMatchSocketReturn {
  connected: boolean;
  match: Partido | null;
  simulation: Partial<SimulationResult> | null;
  liveOdds: { line?: number; over?: number; under?: number } | null;
  latestAlert: any | null;
  sendScoreUpdate: (payload: {
    cuarto_actual: number;
    min_restantes: number;
    seg_restantes: number;
    quarters_data: [number, number][];
    linea_apuesta?: number;
    notas?: string;
  }) => void;
  sendResimulate: (linea_apuesta?: number) => void;
  sendNewPlay: (play: any) => void;
}

export function useLiveMatchSocket(partidoId?: number): UseLiveMatchSocketReturn {
  const [connected, setConnected] = useState(false);
  const [match, setMatch] = useState<Partido | null>(null);
  const [simulation, setSimulation] = useState<Partial<SimulationResult> | null>(null);
  const [liveOdds, setLiveOdds] = useState<{ line?: number; over?: number; under?: number } | null>(null);
  const [latestAlert, setLatestAlert] = useState<any | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    if (!partidoId) return;

    const apiKey = typeof window !== 'undefined' ? (localStorage.getItem('poliverso_api_key') || '') : '';
    const query = apiKey ? `?api_key=${encodeURIComponent(apiKey)}` : '';
    const wsUrl = `${WS_BASE}/${partidoId}${query}`;
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      console.log(`[WS] Conectado al partido ${partidoId}`);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === 'init') {
          if (msg.partido) setMatch(msg.partido);
          if (msg.simulation) setSimulation(msg.simulation);
          if (msg.live_odds && msg.live_odds.line !== undefined && msg.live_odds.line !== null) {
            setLiveOdds(msg.live_odds);
          }
        } else if (msg.type === 'match_updated') {
          if (msg.partido) setMatch(msg.partido);
          if (msg.simulation) setSimulation(msg.simulation);
          if (msg.live_odds && msg.live_odds.line !== undefined && msg.live_odds.line !== null) {
            setLiveOdds(msg.live_odds);
          }
          sounds.playScoreTick();
        } else if (msg.type === 'simulation_update') {
          if (msg.simulation) setSimulation(msg.simulation);
        } else if (msg.type === 'bet_alert') {
          setLatestAlert(msg.alert);
          sounds.playValueAlert();
        }
      } catch (err) {
        console.error('[WS] Error al procesar mensaje:', err);
      }
    };

    ws.onclose = () => {
      setConnected(false);
      console.log('[WS] Conexión cerrada. Reintentando en 3s...');
      reconnectTimerRef.current = window.setTimeout(() => {
        connect();
      }, 3000);
    };

    ws.onerror = (err) => {
      console.error('[WS] Error de socket:', err);
      ws.close();
    };
  }, [partidoId]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [connect]);

  const sendScoreUpdate = useCallback(
    (payload: {
      cuarto_actual: number;
      min_restantes: number;
      seg_restantes: number;
      quarters_data: [number, number][];
      linea_apuesta?: number;
      notas?: string;
    }) => {
      if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
        socketRef.current.send(
          JSON.stringify({
            action: 'update_score',
            ...payload,
          })
        );
      }
    },
    []
  );

  const sendResimulate = useCallback((linea_apuesta?: number) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(
        JSON.stringify({
          action: 'resimulate',
          linea_apuesta,
        })
      );
    }
  }, []);

  const sendNewPlay = useCallback((play: any) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(
        JSON.stringify({
          action: 'new_play',
          play,
        })
      );
    }
  }, []);

  return {
    connected,
    match,
    simulation,
    liveOdds,
    latestAlert,
    sendScoreUpdate,
    sendResimulate,
    sendNewPlay,
  };
}
