"""
Configuración de Torneos y Dinámica por Cuarto para Baloncesto.
Contiene los promedios reglamentarios, duraciones y factores tácticos.
"""

from dataclasses import dataclass
from typing import Dict, Tuple

@dataclass
class TournamentConfig:
    name: str
    quarter_duration: int          # minutos por cuarto (10 o 12)
    team_avg_quarter_min: float   # puntos promedio mín por equipo en 1 Q
    team_avg_quarter_max: float   # puntos promedio máx por equipo en 1 Q
    description: str
    key: str
    # Parámetros analíticos avanzados
    league_pace: float = 99.5           # Posesiones totales promedio de liga por partido
    league_off_rating: float = 114.0    # Pts anotados por 100 posesiones promedio de liga
    typical_total_std: float = 19.5     # Desviación estándar típica para puntos totales
    home_court_advantage: float = 2.8   # Ventaja de localía neta en puntos
    b2b_penalty_per_100: float = 2.0    # Penalización en OffRtg por Back-to-Back
    league_3pt_pct: float = 0.350       # Porcentaje de acierto de triple promedio de la liga
    league_3pt_rate: float = 0.35       # Proporción de tiros que son triples (3P Attempt Rate)

    @property
    def team_avg_quarter(self) -> float:
        """Punto medio del promedio por equipo en un cuarto."""
        return (self.team_avg_quarter_min + self.team_avg_quarter_max) / 2.0

    @property
    def total_avg_quarter(self) -> float:
        """Total combinado esperado por cuarto (ambos equipos)."""
        return self.team_avg_quarter * 2.0

    @property
    def total_game_duration(self) -> int:
        """Duración total en minutos del partido reglamentario (4 cuartos)."""
        return self.quarter_duration * 4

    @property
    def total_game_avg(self) -> float:
        """Total combinado esperado para el partido completo."""
        return self.total_avg_quarter * 4.0


# Diccionario maestro de los 3 tipos de torneos solicitados
TOURNAMENT_PRESETS: Dict[str, TournamentConfig] = {
    "NBA": TournamentConfig(
        name="NBA (National Basketball Association)",
        quarter_duration=12,
        team_avg_quarter_min=28.0,
        team_avg_quarter_max=29.0,
        description="12 minutos por periodo. Alto volumen de posesiones (~100/partido), posesiones rápidas y gran eficacia perimetral.",
        key="NBA",
        league_pace=99.5,
        league_off_rating=115.0,
        typical_total_std=20.0,
        home_court_advantage=2.8,
        b2b_penalty_per_100=2.0,
        league_3pt_pct=0.365,
        league_3pt_rate=0.39
    ),
    "FIBA": TournamentConfig(
        name="FIBA / Euroliga / Ligas Locales",
        quarter_duration=10,
        team_avg_quarter_min=20.0,
        team_avg_quarter_max=22.0,
        description="10 minutos por periodo. Formato oficial FIBA, Euroliga y ligas locales europeas/latinoamericanas. 4 cuartos de 10 min (40 min total).",
        key="FIBA",
        league_pace=74.5,
        league_off_rating=105.0,
        typical_total_std=15.5,
        home_court_advantage=3.5,
        b2b_penalty_per_100=2.2,
        league_3pt_pct=0.340,
        league_3pt_rate=0.34
    ),
    "NBL": TournamentConfig(
        name="NBL (Australia & Nueva Zelanda)",
        quarter_duration=10,
        team_avg_quarter_min=22.0,
        team_avg_quarter_max=24.0,
        description="10 minutos por periodo. La liga de 40 min con mayor ritmo del mundo (~84 posesiones), transiciones rápidas y gran volumen perimetral.",
        key="NBL",
        league_pace=84.0,
        league_off_rating=109.5,
        typical_total_std=17.5,
        home_court_advantage=3.0,
        b2b_penalty_per_100=2.0,
        league_3pt_pct=0.348,
        league_3pt_rate=0.37
    ),
    "NCAA_FEMENIL": TournamentConfig(
        name="NCAA Femenil",
        quarter_duration=10,
        team_avg_quarter_min=16.0,
        team_avg_quarter_max=18.0,
        description="10 minutos por periodo. Enfoque táctico universitario con posesiones más elaboradas y defensa cerrada.",
        key="NCAA_FEMENIL",
        league_pace=70.0,
        league_off_rating=95.0,
        typical_total_std=14.5,
        home_court_advantage=3.2,
        b2b_penalty_per_100=1.8,
        league_3pt_pct=0.315,
        league_3pt_rate=0.31
    ),
    "WNBA": TournamentConfig(
        name="WNBA (Women's National Basketball Association)",
        quarter_duration=10,
        team_avg_quarter_min=20.0,
        team_avg_quarter_max=21.5,
        description="10 minutos por periodo (40 min reglamentarios). 13 franquicias oficiales, posesiones dinámicas (~81 posesiones), gran nivel técnico y juego perimetral.",
        key="WNBA",
        league_pace=81.2,
        league_off_rating=102.5,
        typical_total_std=14.8,
        home_court_advantage=2.5,
        b2b_penalty_per_100=1.8,
        league_3pt_pct=0.342,
        league_3pt_rate=0.33
    )
}

# Modificadores de ritmo según el comportamiento típico de cada cuarto
QUARTER_PACE_FACTORS = {
    1: 1.03,   # 1° Cuarto: ritmo dinámico y piernas frescas (+3%)
    2: 1.02,   # 2° Cuarto: continuidad de rotaciones (+2%)
    3: 0.95,   # 3° Cuarto: ajustes defensivos de vestuario (-5%)
    4: 0.94    # 4° Cuarto: posesiones más trabajadas a media cancha (-6%)
}

# Prórroga (Overtime) - En apuestas deportivas los mercados de totales incluyen prórroga
OVERTIME_MINUTES = 5.0
OVERTIME_PACE_FACTOR = 1.05       # Posesiones concentradas y faltas al final del OT
OVERTIME_FATIGUE_FACTOR = 0.95    # Fatiga acumulada tras 40/48 min de juego

# Motor gradual de finales cerrados (Clutch / Carrusel de tiros libres)
CLUTCH_THRESHOLD_MINUTES = 2.0     # Últimos 2 minutos de partido
CLUTCH_FOUL_DIFF_THRESHOLD = 5     # Dif <= 5 pts: Faltas intencionales sistemáticas (surge extremo)
CLUTCH_MODERATE_DIFF_THRESHOLD = 9 # Dif 6-9 pts: Ritmo acelerado buscando triples pero sin faltas garantizadas
CLUTCH_POINT_DIFF_CLOSE = 8        # Compatibilidad hacia atrás
CLUTCH_SURGE_MULTIPLIER = 1.32     # Compatibilidad hacia atrás
CLUTCH_SURGE_FOUL_MULT = 1.65      # Incremento del ritmo por faltas continuas con reloj detenido
CLUTCH_SURGE_MODERATE_MULT = 1.18  # Posesiones rápidas con tiros de 3 pts
CLUTCH_CLOCK_KILL_MULT = 0.65      # Consumo de los 24 segundos por equipo líder con ventaja >= 10

# Regresión de Triples a la Media (Normalización de Rachas Calientes/Frías)
THREE_POINT_REGRESSION_MIN_SHOTS = 6   # Mínimo de intentos triples para calcular desviación de acierto
THREE_POINT_LUCK_SHRINKAGE = 0.55      # Coeficiente de regresión hacia el promedio esperado en minutos futuros

BLOWOUT_DIFF_THRESHOLD = 18     # Si la diferencia es > 18 pts al final
GARBAGE_TIME_Q4_THRESHOLD = 22  # Diferencia > 22 pts al entrar al 4Q
BLOWOUT_DECAY_MULTIPLIER = 0.94 # Desaceleración calibrada moderada por rotaciones (sin colapso artificial)
Q4_FAST_PACE_THRESHOLD = 3.6    # Ritmo en pts/min en 4Q que invalida la hipótesis de Garbage Time lento
Q4_ADAPTIVE_EVAL_MINUTES = 1.0  # Minutos mínimos transcurridos en 4Q para evaluar ritmo empírico adaptativo

# Ponderaciones de los Cuatro Factores de Dean Oliver
FOUR_FACTORS_WEIGHTS = {
    "efg": 0.40,   # Tiro efectivo (eFG%)
    "tov": 0.25,   # Porcentaje de pérdidas (TOV%)
    "orb": 0.20,   # Rebote ofensivo (ORB%)
    "ftr": 0.15    # Tasa de tiros libres (FT Rate)
}

# Benchmarks de los Cuatro Factores según competición
FOUR_FACTORS_BENCHMARKS = {
    "NBA": {"efg": 0.540, "tov": 0.135, "orb": 0.265, "ftr": 0.240},
    "FIBA": {"efg": 0.520, "tov": 0.150, "orb": 0.280, "ftr": 0.260},
    "NBL": {"efg": 0.535, "tov": 0.138, "orb": 0.290, "ftr": 0.255},
    "NCAA_FEMENIL": {"efg": 0.480, "tov": 0.170, "orb": 0.310, "ftr": 0.270}
}

