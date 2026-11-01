"""
🏀 Módulo de Extracción de Secuencias y Características de Momentum para Deep Learning.
Transforma el flujo de jugadas (play-by-play) y los snapshots en:
1. Tensores de Secuencia Temporal [Window, Feat_Seq] para redes recurrentes (GRU/LSTM).
2. Vectores Macro de Contexto [Feat_Macro] para modelar la situación de partido.
3. Vectores Target para aprendizaje supervisado de residuos y ritmo.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import math

from model.database import (
    obtener_partido,
    listar_partidos,
    listar_jugadas,
    listar_snapshots,
)


class SequenceExtractor:
    """
    Extractor de tensores y características para alimentar la arquitectura de Deep Learning.
    
    Dimensiones estándar:
    - Seq_len (Ventana de jugadas W): 15 jugadas
    - Feat_seq (Características por jugada): 10
    - Feat_macro (Características contextuales macro): 16
    - Feat_lineup (Características de quintetos y jugadores en pista): 10
    """

    def __init__(self, window_size: int = 15):
        self.window_size = window_size
        self.num_seq_features = 10
        self.num_macro_features = 16
        self.num_lineup_features = 10

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Extracción de Secuencia Temporal (Play-by-Play Window)
    # ─────────────────────────────────────────────────────────────────────────

    def extraer_secuencia_jugadas(
        self,
        plays: List[dict],
        team_a: str = "",
        team_b: str = ""
    ) -> np.ndarray:
        """
        Extrae una matriz de forma (window_size, 10) correspondiente a las últimas
        `window_size` jugadas. Si hay menos jugadas, realiza zero-padding a la izquierda.
        
        Características por jugada:
        0: Puntos anotados normalizados (pts / 3.0)
        1: Indicador de quién anotó (+1.0 Local, -1.0 Visitante, 0.0 ninguno/fallo)
        2: Flag Tiro Libre (pts == 1)
        3: Flag Doble (pts == 2)
        4: Flag Triple (pts == 3)
        5: Margen de diferencia normalizado (diff / 20.0, acotado [-2, 2])
        6: Total de puntos en ese instante normalizado (total / 200.0)
        7: Posición relativa dentro de la ventana (idx / W)
        8: Momentum corto en las 3 jugadas previas (net_pts_3 / 9.0)
        9: Momentum medio en las 5 jugadas previas (net_pts_5 / 15.0)
        """
        matrix = np.zeros((self.window_size, self.num_seq_features), dtype=np.float32)

        if not plays:
            return matrix

        # Tomar hasta las últimas window_size jugadas
        recent_plays = plays[-self.window_size:]
        n_available = len(recent_plays)
        start_idx = self.window_size - n_available  # Left padding

        # Para calcular momentum acumulativo dentro de la ventana
        # Consideramos toda la lista disponible hasta la jugada evaluada
        all_plays_len = len(plays)
        offset = all_plays_len - n_available

        for i, p in enumerate(recent_plays):
            target_row = start_idx + i
            global_play_idx = offset + i

            pts = float(p.get("pts") or 0.0)
            who = str(p.get("who") or "").upper()
            team = str(p.get("team") or "")

            # Quién anotó
            if who == "HOME" or (team_a and team == team_a):
                scorer_sign = 1.0
            elif who == "AWAY" or (team_b and team == team_b):
                scorer_sign = -1.0
            else:
                scorer_sign = 1.0 if pts > 0 else 0.0

            s_home = float(p.get("score_home") or 0.0)
            s_away = float(p.get("score_away") or 0.0)
            tot_play = s_home + s_away
            diff_play = s_home - s_away

            # Momentum en 3 y 5 jugadas
            sub_window_3 = plays[max(0, global_play_idx - 2): global_play_idx + 1]
            sub_window_5 = plays[max(0, global_play_idx - 4): global_play_idx + 1]

            def _net_pts(sub_list: List[dict]) -> float:
                net = 0.0
                for sp in sub_list:
                    p_pts = float(sp.get("pts") or 0.0)
                    p_who = str(sp.get("who") or "").upper()
                    p_team = str(sp.get("team") or "")
                    if p_who == "HOME" or (team_a and p_team == team_a):
                        net += p_pts
                    elif p_who == "AWAY" or (team_b and p_team == team_b):
                        net -= p_pts
                return net

            net_3 = _net_pts(sub_window_3)
            net_5 = _net_pts(sub_window_5)

            # Llenar fila
            matrix[target_row, 0] = np.clip(pts / 3.0, 0.0, 1.0)
            matrix[target_row, 1] = scorer_sign
            matrix[target_row, 2] = 1.0 if pts == 1 else 0.0
            matrix[target_row, 3] = 1.0 if pts == 2 else 0.0
            matrix[target_row, 4] = 1.0 if pts == 3 else 0.0
            matrix[target_row, 5] = np.clip(diff_play / 20.0, -2.0, 2.0)
            matrix[target_row, 6] = np.clip(tot_play / 200.0, 0.0, 2.0)
            matrix[target_row, 7] = float(i) / max(1.0, float(self.window_size - 1))
            matrix[target_row, 8] = np.clip(net_3 / 9.0, -1.0, 1.0)
            matrix[target_row, 9] = np.clip(net_5 / 15.0, -1.0, 1.0)

        return matrix

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Extracción de Vector Macro de Contexto
    # ─────────────────────────────────────────────────────────────────────────

    def extraer_vector_macro(
        self,
        minutos_jugados: float,
        pts_local: float,
        pts_visitante: float,
        cuarto: int = 1,
        total_game_min: float = 40.0,
        ritmo_base: float = 4.0,
        ritmo_obs: Optional[float] = None,
        run_pts: float = 0.0,
        run_team_is_home: Optional[bool] = None,
        recent_heat: float = 0.0
    ) -> np.ndarray:
        """
        Genera un vector 1D de tamaño (16,) con la situación macro del partido.
        
        0: Fracción de tiempo jugado (t / T)
        1: Fracción de tiempo restante ((T - t) / T)
        2: Total actual normalizado (total / 200.0)
        3: Margen actual normalizado ((local - vis) / 20.0)
        4: Valor absoluto del margen (|margin| / 20.0)
        5: Ritmo observado actual normalizado (obs / 5.0)
        6: Ritmo base pre-partido normalizado (base / 5.0)
        7: Ratio de ritmo observado vs base (obs / base, centrado en 1.0)
        8: Flag Cuarto 1
        9: Flag Cuarto 2
        10: Flag Cuarto 3
        11: Flag Cuarto 4
        12: Probabilidad de Clutch (tiempo <= 5 min y |diff| <= 8)
        13: Probabilidad de Garbage Time (tiempo_restante <= 10 min y |diff| >= 20)
        14: Racha activa normalizada (run_pts / 15.0)
        15: Calor reciente normalizado (puntos en últimas jugadas / 18.0)
        """
        vec = np.zeros(self.num_macro_features, dtype=np.float32)

        t = max(0.0, float(minutos_jugados))
        T = max(10.0, float(total_game_min))
        t_rem = max(0.0, T - t)

        tot = float(pts_local + pts_visitante)
        margin = float(pts_local - pts_visitante)
        abs_margin = abs(margin)

        if ritmo_obs is None:
            ritmo_obs = tot / max(0.5, t) if t > 0.1 else ritmo_base

        pace_base_safe = max(0.5, float(ritmo_base))
        pace_ratio = float(ritmo_obs) / pace_base_safe

        is_clutch = 1.0 if (t_rem <= 5.0 and abs_margin <= 8.0) else 0.0
        is_garbage = 1.0 if (t >= 0.75 * T and abs_margin >= 20.0) else 0.0

        run_dir = 1.0 if run_team_is_home is True else (-1.0 if run_team_is_home is False else 0.0)
        run_feat = (run_pts / 15.0) * (run_dir if run_dir != 0.0 else 1.0)

        vec[0] = np.clip(t / T, 0.0, 1.0)
        vec[1] = np.clip(t_rem / T, 0.0, 1.0)
        vec[2] = np.clip(tot / 200.0, 0.0, 2.0)
        vec[3] = np.clip(margin / 20.0, -2.5, 2.5)
        vec[4] = np.clip(abs_margin / 20.0, 0.0, 2.5)
        vec[5] = np.clip(float(ritmo_obs) / 5.0, 0.0, 2.5)
        vec[6] = np.clip(pace_base_safe / 5.0, 0.0, 2.5)
        vec[7] = np.clip(pace_ratio, 0.2, 3.0)
        vec[8] = 1.0 if cuarto == 1 else 0.0
        vec[9] = 1.0 if cuarto == 2 else 0.0
        vec[10] = 1.0 if cuarto == 3 else 0.0
        vec[11] = 1.0 if cuarto >= 4 else 0.0
        vec[12] = is_clutch
        vec[13] = is_garbage
        vec[14] = np.clip(run_feat, -1.0, 1.0)
        vec[15] = np.clip(recent_heat / 18.0, 0.0, 2.0)

        return vec

    # ─────────────────────────────────────────────────────────────────────────
    # 2.1 Extracción de Vector de Quintetos y Jugadores en Pista (Lineup Context)
    # ─────────────────────────────────────────────────────────────────────────

    def extraer_vector_lineup(
        self,
        lineup_local: Optional[List[dict]] = None,
        lineup_visitante: Optional[List[dict]] = None,
        fouls_local: int = 0,
        fouls_visitante: int = 0
    ) -> np.ndarray:
        """
        Genera un vector 1D de tamaño (10,) con la situación de quintetos y jugadores:
        0: Net Rating estimado del quinteto local normalizado ((off - def) / 30.0)
        1: Net Rating estimado del quinteto visitante normalizado
        2: Diferencial de Net Rating entre ambos quintetos en cancha
        3: Usage Rate medio del quinteto local normalizado (usg / 25.0)
        4: Usage Rate medio del quinteto visitante normalizado
        5: True Shooting % medio local normalizado (ts / 0.60)
        6: True Shooting % medio visitante normalizado
        7: Jugadores locales en Foul Trouble (3+ faltas) normalizado (count / 5.0)
        8: Jugadores visitantes en Foul Trouble normalizado
        9: Diferencial de faltas de equipo en el cuarto (fouls_local - fouls_visitante) / 5.0
        """
        vec = np.zeros(self.num_lineup_features, dtype=np.float32)

        def _calc_quintet_metrics(l: Optional[List[dict]]):
            if not l:
                return 108.0, 108.0, 20.0, 0.55, 0
            off = float(np.mean([float(p.get("off_rating", 108.0)) for p in l]))
            defr = float(np.mean([float(p.get("def_rating", 108.0)) for p in l]))
            usg = float(np.mean([float(p.get("usage_rate", 20.0)) for p in l]))
            ts = float(np.mean([float(p.get("ts_pct", 0.55)) for p in l]))
            f_trouble = sum(1 for p in l if float(p.get("fouls", p.get("foul_rate", 0))) >= 3.0)
            return off, defr, usg, ts, f_trouble

        off_a, def_a, usg_a, ts_a, ft_a = _calc_quintet_metrics(lineup_local)
        off_b, def_b, usg_b, ts_b, ft_b = _calc_quintet_metrics(lineup_visitante)

        net_a = off_a - def_a
        net_b = off_b - def_b
        diff_net = net_a - net_b

        vec[0] = np.clip(net_a / 30.0, -1.5, 1.5)
        vec[1] = np.clip(net_b / 30.0, -1.5, 1.5)
        vec[2] = np.clip(diff_net / 30.0, -2.0, 2.0)
        vec[3] = np.clip(usg_a / 25.0, 0.5, 1.8)
        vec[4] = np.clip(usg_b / 25.0, 0.5, 1.8)
        vec[5] = np.clip(ts_a / 0.60, 0.5, 1.5)
        vec[6] = np.clip(ts_b / 0.60, 0.5, 1.5)
        vec[7] = np.clip(ft_a / 5.0, 0.0, 1.0)
        vec[8] = np.clip(ft_b / 5.0, 0.0, 1.0)
        vec[9] = np.clip((fouls_local - fouls_visitante) / 5.0, -1.0, 1.0)

        return vec

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Extracción Unificada para Inferencia en Vivo
    # ─────────────────────────────────────────────────────────────────────────

    def extraer_estado_en_vivo(
        self,
        plays: List[dict],
        team_a: str,
        team_b: str,
        minutos_jugados: float,
        pts_local: float,
        pts_visitante: float,
        cuarto: int,
        total_game_min: float = 40.0,
        ritmo_base: float = 4.0,
        ritmo_obs: Optional[float] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extrae directamente el par (X_seq, X_macro) listo para pasar por la red neuronal.
        Mantiene 100% compatibilidad con tests y llamadas legacy.
        """
        x_seq, x_macro, _ = self.extraer_estado_en_vivo_completo(
            plays=plays,
            team_a=team_a,
            team_b=team_b,
            minutos_jugados=minutos_jugados,
            pts_local=pts_local,
            pts_visitante=pts_visitante,
            cuarto=cuarto,
            total_game_min=total_game_min,
            ritmo_base=ritmo_base,
            ritmo_obs=ritmo_obs
        )
        return x_seq, x_macro

    def extraer_estado_en_vivo_completo(
        self,
        plays: List[dict],
        team_a: str,
        team_b: str,
        minutos_jugados: float,
        pts_local: float,
        pts_visitante: float,
        cuarto: int,
        total_game_min: float = 40.0,
        ritmo_base: float = 4.0,
        ritmo_obs: Optional[float] = None,
        lineup_local: Optional[List[dict]] = None,
        lineup_visitante: Optional[List[dict]] = None,
        fouls_local: int = 0,
        fouls_visitante: int = 0
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Extrae la tríada completa (X_seq, X_macro, X_lineup) para la red Transformer.
        """
        run_team_is_home = None
        run_pts = 0.0
        recent_heat = 0.0

        if plays:
            last_run_team = ""
            for p in reversed(plays):
                tm = str(p.get("team") or "")
                who = str(p.get("who") or "").upper()
                pts_p = float(p.get("pts") or 0.0)
                cur_team = team_a if (who == "HOME" or tm == team_a) else (team_b if (who == "AWAY" or tm == team_b) else tm)
                if not last_run_team:
                    last_run_team = cur_team
                    run_pts += pts_p
                elif cur_team == last_run_team:
                    run_pts += pts_p
                else:
                    break
            run_team_is_home = (last_run_team == team_a) if team_a else None
            recent_heat = float(sum(float(p.get("pts") or 0.0) for p in plays[-6:]))

        seq_mat = self.extraer_secuencia_jugadas(plays, team_a=team_a, team_b=team_b)
        macro_vec = self.extraer_vector_macro(
            minutos_jugados=minutos_jugados,
            pts_local=pts_local,
            pts_visitante=pts_visitante,
            cuarto=cuarto,
            total_game_min=total_game_min,
            ritmo_base=ritmo_base,
            ritmo_obs=ritmo_obs,
            run_pts=run_pts,
            run_team_is_home=run_team_is_home,
            recent_heat=recent_heat
        )
        lineup_vec = self.extraer_vector_lineup(
            lineup_local=lineup_local,
            lineup_visitante=lineup_visitante,
            fouls_local=fouls_local,
            fouls_visitante=fouls_visitante
        )

        return (
            np.expand_dims(seq_mat, axis=0),
            np.expand_dims(macro_vec, axis=0),
            np.expand_dims(lineup_vec, axis=0)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Construcción de Muestras de Entrenamiento desde PostgreSQL
    # ─────────────────────────────────────────────────────────────────────────

    def construir_dataset_desde_bd(self) -> List[Dict[str, Any]]:
        """
        Recorre todos los partidos finalizados en PostgreSQL y construye muestras de
        entrenamiento en cada snapshot o hito registrado.
        """
        partidos = listar_partidos(limit=500)
        partidos_fin = [p for p in partidos if p.get("estado") == "finalizado"]

        muestras = []

        for p in partidos_fin:
            pid = p["id"]
            team_a = p.get("equipo_local", "Local")
            team_b = p.get("equipo_visitante", "Visitante")

            t_fin = p.get("total_final")
            pts_loc_fin = p.get("pts_local_final")
            pts_vis_fin = p.get("pts_visitante_final")

            if t_fin is None or pts_loc_fin is None or pts_vis_fin is None:
                from model.database import _fetchall
                m_cuartos = _fetchall("SELECT pts_local, pts_visitante FROM marcadores_cuarto WHERE partido_id = %s", (pid,))
                if m_cuartos:
                    pts_loc_fin = sum(m["pts_local"] for m in m_cuartos)
                    pts_vis_fin = sum(m["pts_visitante"] for m in m_cuartos)
                    t_fin = pts_loc_fin + pts_vis_fin

            if not t_fin or t_fin <= 0:
                continue

            t_fin = float(t_fin)
            win_home = 1.0 if float(pts_loc_fin) > float(pts_vis_fin) else 0.0

            jugadas = listar_jugadas(pid)
            snapshots = listar_snapshots(pid)

            total_game_min = 40.0
            if "NBA" in str(p.get("torneo_id", "")):
                total_game_min = 48.0

            for s in snapshots:
                min_jug = float(s.get("minutos_jugados") or 0.0)
                if min_jug <= 0.5 or min_jug >= total_game_min - 0.5:
                    continue

                pts_loc_act = float(s.get("pts_local_actual") or 0.0)
                pts_vis_act = float(s.get("pts_visitante_actual") or 0.0)
                tot_act = pts_loc_act + pts_vis_act

                pts_rem_real = max(0.0, t_fin - tot_act)
                t_rem = max(0.5, total_game_min - min_jug)
                pace_rem_real = pts_rem_real / t_rem
                pace_base = float(s.get("ritmo_base") or 4.0)
                delta_pace = pace_rem_real - pace_base

                if jugadas:
                    fraction = min_jug / total_game_min
                    cutoff_idx = max(1, int(fraction * len(jugadas)))
                    plays_subset = jugadas[:cutoff_idx]
                else:
                    plays_subset = []

                seq_mat = self.extraer_secuencia_jugadas(plays_subset, team_a=team_a, team_b=team_b)
                macro_vec = self.extraer_vector_macro(
                    minutos_jugados=min_jug,
                    pts_local=pts_loc_act,
                    pts_visitante=pts_vis_act,
                    cuarto=int(s.get("cuarto_snapshot") or 1),
                    total_game_min=total_game_min,
                    ritmo_base=pace_base,
                    ritmo_obs=float(s.get("ritmo_obs") or (tot_act / min_jug))
                )

                from model.database import obtener_lineups_partido
                lineup_data = obtener_lineups_partido(pid)
                lineup_vec = self.extraer_vector_lineup(
                    lineup_local=lineup_data.get("lineup_local"),
                    lineup_visitante=lineup_data.get("lineup_visitante"),
                    fouls_local=lineup_data.get("fouls_local", 0),
                    fouls_visitante=lineup_data.get("fouls_visitante", 0)
                )
                spread_real = float(pts_loc_fin - pts_vis_fin)

                muestras.append({
                    "x_seq": seq_mat,
                    "x_macro": macro_vec,
                    "x_lineup": lineup_vec,
                    "y_pts_restantes": pts_rem_real,
                    "y_ritmo_restante": pace_rem_real,
                    "y_delta_pace": delta_pace,
                    "y_win_home": win_home,
                    "y_spread_margin": spread_real,
                    "partido_id": pid,
                    "minutos_jugados": min_jug
                })

        return muestras

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Generador Sintético Físico para Pre-Calibración (Evita Data Starvation)
    # ─────────────────────────────────────────────────────────────────────────

    def generar_dataset_sintetico_calibracion(
        self,
        num_partidos: int = 150,
        seed: int = 42
    ) -> List[Dict[str, Any]]:
        """
        Genera un dataset sintético fundamentado en la física de juego del motor Monte Carlo.
        Permite pre-entrenar la red neuronal para que aprenda las correlaciones básicas
        de momentum, clutch y variabilidad, incluso con pocos partidos en PostgreSQL.
        """
        np.random.seed(seed)
        muestras = []

        for p_idx in range(num_partidos):
            total_game_min = 40.0
            base_pace = float(np.random.uniform(3.6, 4.4))
            home_advantage = float(np.random.uniform(0.02, 0.08))

            cur_home = 0.0
            cur_away = 0.0
            simulated_plays = []

            total_poss = int(np.random.normal(150, 10))
            running_home = 0
            running_away = 0

            for seq in range(1, total_poss + 1):
                t_event = (seq / total_poss) * total_game_min
                is_home = np.random.rand() < (0.5 + home_advantage)
                roll = np.random.rand()
                if roll < 0.45:
                    pts = 0
                elif roll < 0.60:
                    pts = 1
                elif roll < 0.90:
                    pts = 2
                else:
                    pts = 3

                if is_home:
                    running_home += pts
                else:
                    running_away += pts

                simulated_plays.append({
                    "seq": seq,
                    "who": "HOME" if is_home else "AWAY",
                    "pts": pts,
                    "score_home": running_home,
                    "score_away": running_away,
                    "time": t_event
                })

            final_total = float(running_home + running_away)
            final_win_home = 1.0 if running_home > running_away else 0.0

            checkpoints = [6.0, 12.0, 20.0, 28.0, 34.0, 38.0]
            for t_chk in checkpoints:
                plays_up_to = [p for p in simulated_plays if p["time"] <= t_chk]
                if not plays_up_to:
                    continue

                last_p = plays_up_to[-1]
                h_now = float(last_p["score_home"])
                a_now = float(last_p["score_away"])
                tot_now = h_now + a_now

                t_rem = max(0.5, total_game_min - t_chk)
                pts_rem = max(0.0, final_total - tot_now)
                pace_rem = pts_rem / t_rem
                delta_pace = pace_rem - base_pace

                q_chk = min(4, int(t_chk // 10.0) + 1)

                seq_mat = self.extraer_secuencia_jugadas(plays_up_to, team_a="HOME", team_b="AWAY")
                macro_vec = self.extraer_vector_macro(
                    minutos_jugados=t_chk,
                    pts_local=h_now,
                    pts_visitante=a_now,
                    cuarto=q_chk,
                    total_game_min=total_game_min,
                    ritmo_base=base_pace,
                    ritmo_obs=tot_now / t_chk
                )

                final_margin = float(running_home - running_away)
                lineup_vec = self.extraer_vector_lineup()
                lineup_vec[2] = np.clip(home_advantage * 10.0, -1.0, 1.0)

                muestras.append({
                    "x_seq": seq_mat,
                    "x_macro": macro_vec,
                    "x_lineup": lineup_vec,
                    "y_pts_restantes": pts_rem,
                    "y_ritmo_restante": pace_rem,
                    "y_delta_pace": delta_pace,
                    "y_win_home": final_win_home,
                    "y_spread_margin": final_margin,
                    "partido_id": -p_idx,
                    "minutos_jugados": t_chk
                })

        return muestras
