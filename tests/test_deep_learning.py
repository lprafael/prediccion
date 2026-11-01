"""
🧪 Pruebas Unitarias para el Extractor de Secuencias y la Arquitectura de Deep Learning.
"""

import os
import pytest
import numpy as np

from model.deep_extractor import SequenceExtractor
from model.deep_learning import (
    TORCH_AVAILABLE,
    DeepMomentumResidualNet,
    BasketballDataset,
    entrenar_modelo_deep_learning,
    guardar_modelo_torch,
    cargar_modelo_torch,
    inferir_ajuste_momentum,
)

if TORCH_AVAILABLE:
    import torch


class TestSequenceExtractor:
    """Pruebas del extractor de características y secuencias de momentum."""

    def test_extraer_secuencia_vacia(self):
        extractor = SequenceExtractor(window_size=15)
        mat = extractor.extraer_secuencia_jugadas([], team_a="Local", team_b="Visitante")
        assert mat.shape == (15, 10)
        assert np.all(mat == 0.0)

    def test_extraer_secuencia_con_jugadas(self):
        extractor = SequenceExtractor(window_size=15)
        plays = [
            {"seq": 1, "who": "HOME", "pts": 2, "score_home": 2, "score_away": 0, "team": "Local"},
            {"seq": 2, "who": "AWAY", "pts": 3, "score_home": 2, "score_away": 3, "team": "Visitante"},
            {"seq": 3, "who": "HOME", "pts": 1, "score_home": 3, "score_away": 3, "team": "Local"},
        ]
        mat = extractor.extraer_secuencia_jugadas(plays, team_a="Local", team_b="Visitante")
        assert mat.shape == (15, 10)
        # Las primeras 12 filas deben ser padding de ceros
        assert np.all(mat[:12] == 0.0)
        # La última fila es la jugada 3 (1 pt de HOME)
        assert mat[-1, 0] == pytest.approx(1.0 / 3.0, rel=1e-3)  # pts normalizado
        assert mat[-1, 1] == 1.0                                 # anotó local
        assert mat[-1, 2] == 1.0                                 # flag tiro libre

    def test_extraer_vector_macro(self):
        extractor = SequenceExtractor()
        vec = extractor.extraer_vector_macro(
            minutos_jugados=20.0,
            pts_local=42.0,
            pts_visitante=40.0,
            cuarto=2,
            total_game_min=40.0,
            ritmo_base=4.1
        )
        assert vec.shape == (16,)
        # t/T debe ser 0.5
        assert vec[0] == pytest.approx(0.5, rel=1e-2)
        # cuarto 2 flag
        assert vec[9] == 1.0
        assert vec[8] == 0.0

    def test_extraer_estado_en_vivo(self):
        extractor = SequenceExtractor(window_size=15)
        plays = [
            {"seq": 1, "who": "HOME", "pts": 3, "score_home": 3, "score_away": 0, "team": "TeamA"}
        ]
        x_seq, x_macro = extractor.extraer_estado_en_vivo(
            plays=plays,
            team_a="TeamA",
            team_b="TeamB",
            minutos_jugados=5.0,
            pts_local=12.0,
            pts_visitante=10.0,
            cuarto=1
        )
        assert x_seq.shape == (1, 15, 10)
        assert x_macro.shape == (1, 16)

    def test_generador_dataset_sintetico(self):
        extractor = SequenceExtractor()
        muestras = extractor.generar_dataset_sintetico_calibracion(num_partidos=5, seed=123)
        assert len(muestras) > 0
        sample = muestras[0]
        assert "x_seq" in sample
        assert "x_macro" in sample
        assert "y_delta_pace" in sample
        assert sample["x_seq"].shape == (15, 10)
        assert sample["x_macro"].shape == (16,)


@pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch no está instalado en el entorno")
class TestDeepLearningModel:
    """Pruebas de la red neuronal DeepMomentumResidualNet en PyTorch."""

    def test_forward_pass_dimensiones(self):
        model = DeepMomentumResidualNet(seq_feature_dim=10, macro_feature_dim=16)
        x_seq = torch.randn(4, 15, 10)
        x_macro = torch.randn(4, 16)

        out = model(x_seq, x_macro)

        assert "delta_pace" in out
        assert "pts_mean" in out
        assert "pts_logvar" in out
        assert "win_prob" in out

        assert out["delta_pace"].shape == (4, 1)
        assert out["pts_mean"].shape == (4, 1)
        assert out["pts_logvar"].shape == (4, 1)
        assert out["win_prob"].shape == (4, 1)

        # Delta pace acotado por Tanh a [-1.5, 1.5]
        assert torch.all(out["delta_pace"] >= -1.5)
        assert torch.all(out["delta_pace"] <= 1.5)

        # Probabilidad de victoria entre 0 y 1
        assert torch.all(out["win_prob"] >= 0.0)
        assert torch.all(out["win_prob"] <= 1.0)

    def test_entrenamiento_mini_ciclo(self, tmp_path):
        extractor = SequenceExtractor()
        muestras = extractor.generar_dataset_sintetico_calibracion(num_partidos=10, seed=99)
        test_model_path = os.path.join(str(tmp_path), "test_model.pt")

        res = entrenar_modelo_deep_learning(
            muestras=muestras,
            epochs=3,
            batch_size=8,
            learning_rate=1e-3,
            save_path=test_model_path,
            device="cpu"
        )

        assert res["exito"] is True
        assert res["epochs"] == 3
        assert os.path.exists(test_model_path)

        # Cargar y verificar inferencia con el modelo guardado
        inf = inferir_ajuste_momentum(
            plays=[{"seq": 1, "who": "HOME", "pts": 3, "score_home": 3, "score_away": 0}],
            team_a="Local",
            team_b="Visitante",
            minutos_jugados=10.0,
            pts_local=25.0,
            pts_visitante=22.0,
            cuarto=1,
            model_path=test_model_path
        )

        assert inf["activo"] is True
        assert "delta_pace" in inf
        assert "multiplicador_ritmo" in inf
        assert "incertidumbre_pts" in inf
        assert "etiqueta_momentum" in inf

    def test_acoplamiento_basketball_predictor(self):
        from model.config import TOURNAMENT_PRESETS
        from model.engine import BasketballPredictor

        cfg = TOURNAMENT_PRESETS["FIBA"]
        predictor = BasketballPredictor(cfg)

        plays = [
            {"seq": 1, "who": "HOME", "pts": 3, "score_home": 3, "score_away": 0, "team": "Local"},
            {"seq": 2, "who": "HOME", "pts": 2, "score_home": 5, "score_away": 0, "team": "Local"},
            {"seq": 3, "who": "AWAY", "pts": 2, "score_home": 5, "score_away": 2, "team": "Visitante"},
        ]

        summary = predictor.run_live_simulation(
            current_quarter=2,
            elapsed_seconds_in_quarter=300.0,
            quarters_data=[(22, 18), (10, 8), (0, 0), (0, 0)],
            n_simulations=1000,
            plays=plays,
            use_deep_learning=True
        )

        assert hasattr(summary, "dl_active")
        assert hasattr(summary, "dl_delta_pace")
        assert hasattr(summary, "dl_pace_multiplier")
        assert hasattr(summary, "dl_momentum_label")
        assert summary.total_mean > 0.0
        assert summary.dl_pace_multiplier > 0.5 and summary.dl_pace_multiplier < 1.5

    def test_forward_pass_con_lineup_y_spread(self):
        from model.deep_learning import BasketballTransformerNet
        model = BasketballTransformerNet(seq_feature_dim=10, macro_feature_dim=16, lineup_feature_dim=10)
        x_seq = torch.randn(2, 15, 10)
        x_macro = torch.randn(2, 16)
        x_lineup = torch.randn(2, 10)

        out = model(x_seq, x_macro, x_lineup)
        assert "spread_margin" in out
        assert "spread_std" in out
        assert "xai_factors" in out
        assert out["spread_margin"].shape == (2, 1)
        assert out["spread_std"].shape == (2, 1)
        assert out["xai_factors"].shape == (2, 4)
        # Sum of softmax XAI weights must be 1.0
        assert torch.allclose(torch.sum(out["xai_factors"], dim=-1), torch.ones(2), atol=1e-3)

    def test_extractor_lineup_vector(self):
        extractor = SequenceExtractor()
        lineup_a = [{"off_rating": 118.0, "def_rating": 106.0, "usage_rate": 28.0, "ts_pct": 0.61, "foul_rate": 2.0}]
        lineup_b = [{"off_rating": 105.0, "def_rating": 112.0, "usage_rate": 20.0, "ts_pct": 0.52, "foul_rate": 4.0}]
        vec = extractor.extraer_vector_lineup(lineup_a, lineup_b, fouls_local=2, fouls_visitante=5)

        assert vec.shape == (10,)
        # net_a is 118 - 106 = 12.0 -> positive
        assert vec[0] > 0
        # net_b is 105 - 112 = -7.0 -> negative
        assert vec[1] < 0
        # diff_net is 12 - (-7) = 19.0 -> positive
        assert vec[2] > 0
        # team B has 1 player with foul_rate >= 3.0
        assert vec[8] > 0
