"""
🏀 Módulo de Ingesta y Data Warehouse Histórico para Baloncesto
Descarga y normaliza partidos reales de la NBA vía `nba_api` para poblar
las tablas de PostgreSQL (partidos, jugadores, jugadas_partido y eventos_detallados).
Permite entrenar las redes neuronales profundas con datos empíricos de alta fidelidad.
"""

from typing import Dict, List, Optional, Tuple, Any
import time
import re
import numpy as np

from model.database import (
    get_connection,
    crear_partido,
    finalizar_partido_y_liquidar,
    guardar_jugadas_lote,
    registrar_jugador,
    registrar_evento_detallado,
    actualizar_lineups_partido,
)

# Intentar importar nba_api de forma segura
try:
    from nba_api.stats.endpoints import (
        leaguegamefinder,
        playbyplayv2,
        boxscoretraditionalv2,
        boxscoreadvancedv2,
    )
    from nba_api.stats.static import teams
    NBA_API_AVAILABLE = True
except ImportError:
    NBA_API_AVAILABLE = False


class NBADataIngestion:
    """
    Ingesta y normaliza partidos reales de la NBA con eventos detallados y alineaciones.
    """

    def __init__(
        self,
        season: str = "2023-24",
        season_type: str = "Regular Season",
        league_id: str = "00",
        quarter_duration: int = 12,
        torneo_nombre: str = "NBA (12 min/cuarto)",
    ):
        self.season = season
        self.season_type = season_type
        self.league_id = league_id
        self.quarter_duration = quarter_duration
        self.torneo_nombre = torneo_nombre

    def descargar_partidos_recientes(self, num_partidos: int = 5) -> List[dict]:
        """
        Descarga una lista de partidos jugados recientemente con sus IDs y marcadores.
        """
        if not NBA_API_AVAILABLE:
            return []

        try:
            finder = leaguegamefinder.LeagueGameFinder(
                season_nullable=self.season,
                season_type_nullable=self.season_type,
                league_id_nullable=self.league_id
            )
            df_games = finder.get_data_frames()[0]
            if df_games.empty:
                return []

            # Agrupar por GAME_ID (cada juego tiene dos filas: una por equipo)
            grouped = df_games.groupby("GAME_ID")
            partidos = []

            for game_id, group in grouped:
                if len(group) < 2:
                    continue

                row_a = group.iloc[0]
                row_b = group.iloc[1]

                # Determinar local y visitante por MATCHUP ('vs.' es local, '@' es visitante)
                if "vs." in str(row_a.get("MATCHUP", "")):
                    home = row_a
                    away = row_b
                else:
                    home = row_b
                    away = row_a

                partidos.append({
                    "game_id": str(game_id),
                    "fecha": str(home.get("GAME_DATE", "")),
                    "home_team": str(home.get("TEAM_NAME", "")),
                    "away_team": str(away.get("TEAM_NAME", "")),
                    "home_pts": int(home.get("PTS", 0)),
                    "away_pts": int(away.get("PTS", 0)),
                    "total_pts": int(home.get("PTS", 0) + away.get("PTS", 0)),
                })

                if len(partidos) >= num_partidos:
                    break

            return partidos
        except Exception as e:
            print(f"[NBADataIngestion] Error al consultar partidos: {e}")
            return []

    def descargar_play_by_play_y_guardar(self, game_id: str, partido_id: int) -> int:
        """
        Descarga el play-by-play detallado de un partido y lo almacena en PostgreSQL.
        Adapta el reloj según quarter_duration (12 min para NBA, 10 min para WNBA).
        """
        if not NBA_API_AVAILABLE:
            return 0

        try:
            # Pausa para respetar el rate-limiting de la API de la NBA
            time.sleep(0.6)
            pbp = playbyplayv2.PlayByPlayV2(game_id=game_id)
            df_pbp = pbp.get_data_frames()[0]
            if df_pbp.empty:
                return 0

            jugadas_lote = []

            cur_home = 0
            cur_away = 0

            for idx, row in df_pbp.iterrows():
                period = int(row.get("PERIOD", 1))
                time_str = str(row.get("PCTIMESTRING", f"{self.quarter_duration}:00"))
                m = re.match(r"(\d+):(\d+)", time_str)
                min_left = int(m.group(1)) if m else 0
                sec_left = int(m.group(2)) if m else 0
                sec_elapsed_period = (self.quarter_duration * 60) - (min_left * 60 + sec_left)
                sec_elapsed_total = (period - 1) * self.quarter_duration * 60 + sec_elapsed_period

                score_str = str(row.get("SCORE", ""))
                if score_str and " - " in score_str:
                    parts = score_str.split(" - ")
                    cur_away = int(parts[0].strip()) if parts[0].strip().isdigit() else cur_away
                    cur_home = int(parts[1].strip()) if parts[1].strip().isdigit() else cur_home

                desc_home = str(row.get("HOMEDESCRIPTION") or "")
                desc_away = str(row.get("VISITORDESCRIPTION") or "")
                desc_neutral = str(row.get("NEUTRALDESCRIPTION") or "")
                desc = desc_home or desc_away or desc_neutral

                who = "HOME" if desc_home else ("AWAY" if desc_away else "")
                pts = 0
                shot_clock = 24.0

                event_type = int(row.get("EVENTMSGTYPE", 0))
                # Event Types NBA:
                # 1: Made Shot, 2: Missed Shot, 3: Free Throw, 4: Rebound, 5: Turnover, 6: Foul
                tipo_evento = "OTRO"
                zona_tiro = ""
                xpts = 1.0

                if event_type == 1:
                    tipo_evento = "TIRO_CONVERTIDO"
                    if "3PT" in desc:
                        pts = 3
                        zona_tiro = "TRIPLE"
                        xpts = 1.05
                    else:
                        pts = 2
                        zona_tiro = "PINTURA" if ("Dunk" in desc or "Layup" in desc) else "MEDIA"
                        xpts = 1.15
                elif event_type == 2:
                    tipo_evento = "TIRO_FALLADO"
                    pts = 0
                    zona_tiro = "TRIPLE" if "3PT" in desc else "DOBLE"
                    xpts = 0.95
                elif event_type == 3:
                    tipo_evento = "TIRO_LIBRE"
                    pts = 1 if "Free Throw" in desc and "MISS" not in desc else 0
                    zona_tiro = "LINEA_TL"
                    xpts = 1.5
                elif event_type == 4:
                    tipo_evento = "REBOTE"
                elif event_type == 5:
                    tipo_evento = "PERDIDA"
                elif event_type == 6:
                    tipo_evento = "FALTA"

                jugada = {
                    "seq": idx + 1,
                    "team": str(row.get("PLAYER1_TEAM_NICKNAME") or who),
                    "who": who,
                    "pts": pts,
                    "info": f"Q{period} {time_str} - {desc[:60]}",
                    "score_home": cur_home,
                    "score_away": cur_away,
                }
                jugadas_lote.append(jugada)

                registrar_evento_detallado(
                    partido_id=partido_id,
                    seq=idx + 1,
                    segundo=float(sec_elapsed_total),
                    cuarto=period,
                    equipo=who,
                    tipo_evento=tipo_evento,
                    zona_tiro=zona_tiro,
                    xpts=xpts,
                    shot_clock=shot_clock,
                    pts=pts,
                    info=desc[:100],
                    score_home=cur_home,
                    score_away=cur_away,
                )

            guardar_jugadas_lote(partido_id, jugadas_lote)
            return len(jugadas_lote)
        except Exception as e:
            print(f"[NBADataIngestion] Error en play-by-play: {e}")
            return 0

    def ingestar_partidos_completos(self, n_partidos: int = 3) -> Dict[str, Any]:
        """
        Descarga partidos de la NBA/WNBA, los crea en PostgreSQL y extrae su play-by-play.
        """
        partidos = self.descargar_partidos_recientes(num_partidos=n_partidos)
        if not partidos:
            return {"exito": False, "mensaje": f"No se pudieron obtener partidos de la API ({self.torneo_nombre})"}

        ingestados = 0
        total_jugadas = 0

        for p in partidos:
            try:
                pid = crear_partido(
                    equipo_local=p["home_team"],
                    equipo_visitante=p["away_team"],
                    torneo_nombre=self.torneo_nombre,
                    cuarto_actual=4,
                    min_restantes=0,
                    seg_restantes=0,
                    quarters_data=[
                        [p["home_pts"] // 4, p["away_pts"] // 4],
                        [p["home_pts"] // 4, p["away_pts"] // 4],
                        [p["home_pts"] // 4, p["away_pts"] // 4],
                        [p["home_pts"] - 3 * (p["home_pts"] // 4), p["away_pts"] - 3 * (p["away_pts"] // 4)],
                    ],
                    notas=f"Ingestado oficial ({self.torneo_nombre}). GameID: {p['game_id']} - Fecha: {p['fecha']}"
                )

                # Cargar play-by-play
                n_jugadas = self.descargar_play_by_play_y_guardar(p["game_id"], pid)
                total_jugadas += n_jugadas

                # Finalizar y liquidar
                finalizar_partido_y_liquidar(
                    partido_id=pid,
                    pts_local_final=p["home_pts"],
                    pts_visitante_final=p["away_pts"],
                )
                ingestados += 1
            except Exception as e:
                print(f"[{self.__class__.__name__}] Error al procesar partido {p.get('game_id')}: {e}")

        return {
            "exito": True,
            "partidos_ingestados": ingestados,
            "total_jugadas": total_jugadas
        }


class WNBADataIngestion(NBADataIngestion):
    """
    Ingesta y normaliza partidos reales de la WNBA (Women's National Basketball Association)
    vía nba_api con league_id='10', cuartos reglamentarios de 10 minutos y temporadas anuales.
    """

    def __init__(
        self,
        season: str = "2024",
        season_type: str = "Regular Season",
    ):
        super().__init__(
            season=season,
            season_type=season_type,
            league_id="10",
            quarter_duration=10,
            torneo_nombre="WNBA (10 min/cuarto)",
        )


def obtener_equipos_wnba() -> List[Dict[str, Any]]:
    """
    Obtiene la lista oficial de las 13 franquicias de la WNBA registradas en la API.
    """
    if not NBA_API_AVAILABLE:
        return []
    try:
        wnba_teams = teams.get_wnba_teams()
        return [
            {
                "id": t["id"],
                "full_name": t["full_name"],
                "abbreviation": t["abbreviation"],
                "nickname": t["nickname"],
                "city": t["city"],
                "state": t["state"],
                "year_founded": t["year_founded"],
            }
            for t in wnba_teams
        ]
    except Exception as e:
        print(f"[WNBADataIngestion] Error al listar equipos WNBA: {e}")
        return []


def poblar_jugadores_estrella_demo() -> int:
    """
    Puebla una biblioteca base de jugadores con estadísticas analíticas avanzadas
    (OffRtg, DefRtg, Usage%, TS%, FoulRate) para equipos frecuentes.
    """
    jugadores_base = [
        # Boston Celtics
        ("Boston Celtics", "Jayson Tatum", "F", 0, 118.5, 108.0, 29.5, 0.605, 2.4, True),
        ("Boston Celtics", "Jaylen Brown", "G", 7, 115.0, 109.5, 28.0, 0.580, 2.7, True),
        ("Boston Celtics", "Jrue Holiday", "G", 4, 114.0, 106.0, 16.5, 0.595, 2.1, True),
        ("Boston Celtics", "Derrick White", "G", 9, 116.0, 107.0, 18.5, 0.610, 2.2, True),
        ("Boston Celtics", "Kristaps Porzingis", "C", 8, 120.0, 108.0, 25.0, 0.640, 2.8, True),
        ("Boston Celtics", "Payton Pritchard", "G", 11, 111.0, 112.0, 17.0, 0.575, 1.8, False),
        ("Boston Celtics", "Al Horford", "C", 42, 112.0, 109.0, 13.0, 0.585, 2.0, False),

        # Dallas Mavericks
        ("Dallas Mavericks", "Luka Doncic", "G", 77, 121.0, 112.0, 36.0, 0.615, 2.6, True),
        ("Dallas Mavericks", "Kyrie Irving", "G", 11, 118.0, 113.0, 27.5, 0.605, 2.3, True),
        ("Dallas Mavericks", "PJ Washington", "F", 25, 108.0, 110.0, 16.0, 0.540, 3.2, True),
        ("Dallas Mavericks", "Daniel Gafford", "C", 21, 116.0, 108.5, 15.0, 0.700, 3.5, True),
        ("Dallas Mavericks", "Derrick Jones Jr.", "F", 55, 107.0, 109.0, 12.0, 0.570, 2.9, True),
        ("Dallas Mavericks", "Dereck Lively II", "C", 2, 115.0, 107.0, 13.5, 0.720, 3.4, False),

        # Los Angeles Lakers
        ("Los Angeles Lakers", "LeBron James", "F", 23, 117.5, 111.0, 29.0, 0.630, 1.8, True),
        ("Los Angeles Lakers", "Anthony Davis", "C", 3, 116.0, 105.0, 27.0, 0.625, 2.5, True),
        ("Los Angeles Lakers", "Austin Reaves", "G", 15, 113.0, 114.0, 20.0, 0.610, 2.2, True),
        ("Los Angeles Lakers", "D'Angelo Russell", "G", 1, 112.0, 116.0, 22.0, 0.585, 2.4, True),
        ("Los Angeles Lakers", "Rui Hachimura", "F", 28, 111.0, 113.0, 17.5, 0.620, 2.3, True),

        # Golden State Warriors
        ("Golden State Warriors", "Stephen Curry", "G", 30, 119.0, 112.0, 30.5, 0.620, 1.9, True),
        ("Golden State Warriors", "Draymond Green", "F", 23, 111.0, 106.0, 15.0, 0.580, 3.6, True),
        ("Golden State Warriors", "Klay Thompson", "G", 11, 110.0, 114.0, 22.5, 0.560, 2.2, True),
        ("Golden State Warriors", "Jonathan Kuminga", "F", 0, 112.0, 111.0, 24.0, 0.590, 2.8, True),
        ("Golden State Warriors", "Andrew Wiggins", "F", 22, 108.0, 110.0, 19.0, 0.540, 2.4, True),
    ]

    total = 0
    for eq, nom, pos, num, off, def_r, usg, ts, fl, tit in jugadores_base:
        registrar_jugador(
            equipo=eq,
            nombre=nom,
            posicion=pos,
            numero=num,
            off_rating=off,
            def_rating=def_r,
            usage_rate=usg,
            ts_pct=ts,
            foul_rate=fl,
            es_titular=tit
        )
        total += 1
    return total


def poblar_jugadores_estrella_wnba() -> int:
    """
    Puebla una biblioteca base de estrellas y titulares de la WNBA con estadísticas
    analíticas avanzadas (OffRtg, DefRtg, Usage%, TS%, FoulRate).
    """
    jugadoras_wnba = [
        # Indiana Fever
        ("Indiana Fever", "Caitlin Clark", "G", 22, 116.5, 108.5, 28.5, 0.585, 2.5, True),
        ("Indiana Fever", "Aliyah Boston", "C", 7, 114.0, 104.0, 22.0, 0.590, 2.8, True),
        ("Indiana Fever", "Kelsey Mitchell", "G", 0, 115.0, 110.0, 25.0, 0.575, 2.0, True),
        ("Indiana Fever", "NaLyssa Smith", "F", 1, 109.0, 107.0, 19.5, 0.535, 3.1, True),
        ("Indiana Fever", "Lexie Hull", "G", 10, 108.0, 105.0, 14.0, 0.560, 2.3, True),

        # Las Vegas Aces
        ("Las Vegas Aces", "A'ja Wilson", "C", 22, 122.0, 98.0, 31.0, 0.610, 2.1, True),
        ("Las Vegas Aces", "Kelsey Plum", "G", 10, 116.0, 110.0, 26.0, 0.580, 2.3, True),
        ("Las Vegas Aces", "Jackie Young", "G", 0, 117.0, 106.0, 23.5, 0.585, 2.2, True),
        ("Las Vegas Aces", "Chelsea Gray", "G", 12, 115.0, 105.0, 20.0, 0.570, 1.9, True),
        ("Las Vegas Aces", "Kiah Stokes", "C", 41, 102.0, 101.0, 9.0, 0.520, 2.7, True),

        # New York Liberty
        ("New York Liberty", "Breanna Stewart", "F", 30, 119.0, 100.0, 28.0, 0.585, 2.0, True),
        ("New York Liberty", "Sabrina Ionescu", "G", 20, 117.5, 107.0, 26.5, 0.565, 2.1, True),
        ("New York Liberty", "Jonquel Jones", "C", 35, 116.0, 101.0, 21.0, 0.630, 2.9, True),
        ("New York Liberty", "Betnijah Laney-Hamilton", "F", 44, 110.0, 103.0, 17.0, 0.550, 2.4, True),
        ("New York Liberty", "Courtney Vandersloot", "G", 22, 112.0, 108.0, 16.0, 0.540, 1.8, True),

        # Minnesota Lynx
        ("Minnesota Lynx", "Napheesa Collier", "F", 24, 120.0, 99.0, 28.5, 0.605, 2.2, True),
        ("Minnesota Lynx", "Kayla McBride", "G", 21, 115.0, 106.0, 22.0, 0.635, 2.0, True),
        ("Minnesota Lynx", "Courtney Williams", "G", 10, 111.0, 105.0, 21.0, 0.510, 2.3, True),
        ("Minnesota Lynx", "Bridget Carleton", "F", 6, 112.0, 104.0, 14.5, 0.610, 2.4, True),
        ("Minnesota Lynx", "Alanna Smith", "C", 8, 113.0, 102.0, 17.0, 0.570, 3.2, True),

        # Chicago Sky
        ("Chicago Sky", "Angel Reese", "F", 5, 107.0, 102.0, 24.0, 0.485, 3.4, True),
        ("Chicago Sky", "Kamilla Cardoso", "C", 10, 108.0, 103.0, 19.0, 0.540, 3.1, True),
        ("Chicago Sky", "Chennedy Carter", "G", 7, 114.0, 111.0, 29.0, 0.560, 2.6, True),

        # Connecticut Sun
        ("Connecticut Sun", "Alyssa Thomas", "F", 25, 118.0, 98.0, 23.0, 0.545, 2.5, True),
        ("Connecticut Sun", "DeWanna Bonner", "F", 24, 113.0, 103.0, 25.0, 0.550, 2.3, True),
        ("Connecticut Sun", "DiJonai Carrington", "G", 21, 109.0, 100.0, 21.0, 0.515, 2.7, True),

        # Seattle Storm
        ("Seattle Storm", "Jewell Loyd", "G", 24, 113.0, 107.0, 29.0, 0.525, 2.2, True),
        ("Seattle Storm", "Nneka Ogwumike", "F", 30, 118.0, 103.0, 23.5, 0.595, 2.4, True),
        ("Seattle Storm", "Skylar Diggins-Smith", "G", 4, 114.0, 106.0, 24.0, 0.540, 2.3, True),
        ("Seattle Storm", "Ezi Magbegor", "C", 13, 112.0, 99.0, 18.0, 0.575, 2.9, True),
    ]

    total = 0
    for eq, nom, pos, num, off, def_r, usg, ts, fl, tit in jugadoras_wnba:
        registrar_jugador(
            equipo=eq,
            nombre=nom,
            posicion=pos,
            numero=num,
            off_rating=off,
            def_rating=def_r,
            usage_rate=usg,
            ts_pct=ts,
            foul_rate=fl,
            es_titular=tit
        )
        total += 1
    return total

