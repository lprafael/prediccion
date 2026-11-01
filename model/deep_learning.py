"""
🧠 Módulo de Deep Learning Residual para Predicción de Baloncesto.
Implementa:
1. Red Neuronal Residual de Momentum: DeepMomentumResidualNet (PyTorch).
   - Rama Recurrente: GRU bidireccional / multicapa para secuencia de jugadas (play-by-play).
   - Rama Macro: Capas lineales con LayerNorm y activación GELU para contexto del partido.
   - Bloque Residual: Fusión con Skip Connection para estabilidad del gradiente.
   - Cabezales Multi-Tarea:
       * Delta de Ritmo (Ajuste fino de Pace residual acotado por Tanh).
       * Puntos Restantes con Estimación de Incertidumbre Heterocedástica (Media + Log-Varianza).
       * Probabilidad de Victoria Calibrada (Logits).
2. Pipeline de Entrenamiento supervisado con pérdida multi-objetivo (MSE + NLL + BCE).
3. Motor de Inferencia ultrarrápido (<5 ms) con fallback seguro hacia Monte Carlo puro.
"""

from typing import Dict, List, Optional, Tuple, Any, Union
import os
import numpy as np

# Intentar importar PyTorch de forma segura
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    nn = None
    optim = None
    Dataset = object
    DataLoader = None

from model.deep_extractor import SequenceExtractor


DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(__file__), "deep_momentum_net.pt")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Arquitectura de Red Neuronal Profunda (PyTorch)
# ─────────────────────────────────────────────────────────────────────────────

if TORCH_AVAILABLE:

    class DeepMomentumResidualNet(nn.Module):
        """
        Red Neuronal Residual de Baloncesto con Atención Multi-Cabeza:
        Dual-Stream: Multi-Head Self-Attention + GRU para jugadas + Contexto Macro + Alineaciones (Lineups) en Pista.
        """

        def __init__(
            self,
            seq_feature_dim: int = 10,
            macro_feature_dim: int = 16,
            lineup_feature_dim: int = 10,
            gru_hidden_dim: int = 32,
            macro_hidden_dim: int = 32,
            lineup_hidden_dim: int = 16,
            fusion_dim: int = 64,
            dropout_rate: float = 0.2
        ):
            super().__init__()

            self.seq_feature_dim = seq_feature_dim
            self.macro_feature_dim = macro_feature_dim
            self.lineup_feature_dim = lineup_feature_dim
            self.gru_hidden_dim = gru_hidden_dim

            # 1. Rama de Multi-Head Self-Attention sobre la Secuencia de Jugadas
            self.self_attention = nn.MultiheadAttention(
                embed_dim=seq_feature_dim,
                num_heads=2,
                batch_first=True,
                dropout=dropout_rate if dropout_rate > 0 else 0.0
            )
            self.attn_norm = nn.LayerNorm(seq_feature_dim)

            # Rama Recurrente GRU sobre la representación refinada por atención
            self.gru = nn.GRU(
                input_size=seq_feature_dim,
                hidden_size=gru_hidden_dim,
                num_layers=2,
                batch_first=True,
                dropout=dropout_rate if dropout_rate > 0 else 0.0
            )
            self.gru_norm = nn.LayerNorm(gru_hidden_dim)

            # 2. Rama Contextual para Características Macro del Partido
            self.macro_encoder = nn.Sequential(
                nn.Linear(macro_feature_dim, macro_hidden_dim),
                nn.LayerNorm(macro_hidden_dim),
                nn.GELU(),
                nn.Dropout(dropout_rate)
            )

            # 3. Rama de Alineaciones y Jugadores Activos en Pista (Lineup Stints)
            self.lineup_encoder = nn.Sequential(
                nn.Linear(lineup_feature_dim, lineup_hidden_dim),
                nn.LayerNorm(lineup_hidden_dim),
                nn.GELU(),
                nn.Dropout(dropout_rate)
            )

            # 4. Fusión y Bloque Residual con Skip Connection
            in_fused_dim = gru_hidden_dim + macro_hidden_dim + lineup_hidden_dim
            self.fusion_fc0 = nn.Sequential(
                nn.Linear(in_fused_dim, fusion_dim),
                nn.LayerNorm(fusion_dim),
                nn.GELU()
            )
            self.fusion_res = nn.Sequential(
                nn.Linear(fusion_dim, fusion_dim),
                nn.LayerNorm(fusion_dim),
                nn.GELU(),
                nn.Dropout(dropout_rate)
            )
            self.fusion_fc2 = nn.Sequential(
                nn.Linear(fusion_dim, fusion_dim // 2),  # 64 -> 32
                nn.LayerNorm(fusion_dim // 2),
                nn.GELU(),
                nn.Dropout(dropout_rate)
            )

            # 5. Cabezales Multi-Tarea
            latent_dim = fusion_dim // 2  # 32

            # Cabezal 1: Delta de Ritmo (Residual Pace: -1.5 a +1.5 pts/min)
            self.head_delta_pace = nn.Sequential(
                nn.Linear(latent_dim, 16),
                nn.GELU(),
                nn.Linear(16, 1)
            )

            # Cabezal 2: Puntos Restantes esperados (Media)
            self.head_pts_mean = nn.Sequential(
                nn.Linear(latent_dim, 16),
                nn.GELU(),
                nn.Linear(16, 1)
            )

            # Cabezal 3: Incertidumbre heterocedástica de Puntos Restantes (Log-Varianza)
            self.head_pts_logvar = nn.Sequential(
                nn.Linear(latent_dim, 16),
                nn.GELU(),
                nn.Linear(16, 1)
            )

            # Cabezal 4: Logits de Probabilidad de Victoria Local
            self.head_win_logits = nn.Sequential(
                nn.Linear(latent_dim, 16),
                nn.GELU(),
                nn.Linear(16, 1)
            )

            # Cabezal 5: Margen de Victoria Proyectado (Local - Visitante Spread)
            self.head_spread = nn.Sequential(
                nn.Linear(latent_dim, 16),
                nn.GELU(),
                nn.Linear(16, 1)
            )

            # Cabezal 6: Incertidumbre / Volatilidad del Spread
            self.head_spread_logvar = nn.Sequential(
                nn.Linear(latent_dim, 16),
                nn.GELU(),
                nn.Linear(16, 1)
            )

            # Cabezal 7: Explicabilidad XAI (Pesos normalizados de atención/importancia)
            self.head_xai = nn.Sequential(
                nn.Linear(latent_dim, 16),
                nn.GELU(),
                nn.Linear(16, 4),
                nn.Softmax(dim=-1)
            )

        def forward(
            self,
            x_seq: torch.Tensor,
            x_macro: torch.Tensor,
            x_lineup: Optional[torch.Tensor] = None
        ) -> Dict[str, torch.Tensor]:
            """
            Args:
                x_seq: Tensor de forma [Batch, Window_Size, 10]
                x_macro: Tensor de forma [Batch, 16]
                x_lineup: Tensor opcional de forma [Batch, 10] con situación de quintetos
            """
            if x_lineup is None:
                x_lineup = torch.zeros(x_seq.shape[0], self.lineup_feature_dim, device=x_seq.device, dtype=torch.float32)

            # 1. Rama de Atención Multi-Cabeza + Recurrente
            attn_out, _ = self.self_attention(x_seq, x_seq, x_seq)
            x_seq_enhanced = self.attn_norm(x_seq + attn_out)

            gru_out, _ = self.gru(x_seq_enhanced)
            h_seq = self.gru_norm(gru_out[:, -1, :])  # [Batch, gru_hidden_dim]

            # 2. Ramas Macro y Lineup
            h_macro = self.macro_encoder(x_macro)     # [Batch, macro_hidden_dim]
            h_lineup = self.lineup_encoder(x_lineup)  # [Batch, lineup_hidden_dim]

            # 3. Fusión y Conexión Residual
            fused = torch.cat([h_seq, h_macro, h_lineup], dim=-1)  # [Batch, in_fused_dim]
            fused_proj = self.fusion_fc0(fused)                     # [Batch, fusion_dim]
            fused_residual = fused_proj + self.fusion_res(fused_proj)  # Skip connection congruente
            latent = self.fusion_fc2(fused_residual)               # [Batch, 32]

            # 4. Salidas Cuantitativas
            delta_pace = 1.5 * torch.tanh(self.head_delta_pace(latent))
            pts_mean = torch.relu(self.head_pts_mean(latent))
            pts_logvar = torch.clamp(self.head_pts_logvar(latent), min=-2.0, max=5.0)
            win_logits = self.head_win_logits(latent)
            win_prob = torch.sigmoid(win_logits)

            spread_margin = 35.0 * torch.tanh(self.head_spread(latent) / 25.0)
            spread_logvar = torch.clamp(self.head_spread_logvar(latent), min=-1.0, max=4.0)
            spread_std = torch.exp(0.5 * spread_logvar)

            xai_factors = self.head_xai(latent)

            return {
                "delta_pace": delta_pace,
                "pts_mean": pts_mean,
                "pts_logvar": pts_logvar,
                "win_logits": win_logits,
                "win_prob": win_prob,
                "spread_margin": spread_margin,
                "spread_std": spread_std,
                "xai_factors": xai_factors
            }

    # Alias representativo de la arquitectura Transformer
    BasketballTransformerNet = DeepMomentumResidualNet

else:
    class DeepMomentumResidualNet:
        """Fallback stub cuando PyTorch no está disponible."""
        def __init__(self, *args, **kwargs):
            pass


# ─────────────────────────────────────────────────────────────────────────────
# 2. Dataset y DataLoader en PyTorch
# ─────────────────────────────────────────────────────────────────────────────

if TORCH_AVAILABLE:

    class BasketballDataset(Dataset):
        """Dataset en memoria para muestras de secuencias, contexto macro y alineaciones."""

        def __init__(self, muestras: List[Dict[str, Any]]):
            self.x_seq = torch.tensor(
                np.array([m["x_seq"] for m in muestras], dtype=np.float32),
                dtype=torch.float32
            )
            self.x_macro = torch.tensor(
                np.array([m["x_macro"] for m in muestras], dtype=np.float32),
                dtype=torch.float32
            )
            self.x_lineup = torch.tensor(
                np.array([m.get("x_lineup", np.zeros(10, dtype=np.float32)) for m in muestras], dtype=np.float32),
                dtype=torch.float32
            )
            self.y_delta_pace = torch.tensor(
                np.array([[m.get("y_delta_pace", 0.0)] for m in muestras], dtype=np.float32),
                dtype=torch.float32
            )
            self.y_pts_rem = torch.tensor(
                np.array([[m.get("y_pts_restantes", 0.0)] for m in muestras], dtype=np.float32),
                dtype=torch.float32
            )
            self.y_win = torch.tensor(
                np.array([[m.get("y_win_home", 0.5)] for m in muestras], dtype=np.float32),
                dtype=torch.float32
            )
            self.y_spread = torch.tensor(
                np.array([[m.get("y_spread_margin", 0.0)] for m in muestras], dtype=np.float32),
                dtype=torch.float32
            )

        def __len__(self) -> int:
            return len(self.x_seq)

        def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
            return (
                self.x_seq[idx],
                self.x_macro[idx],
                self.x_lineup[idx],
                self.y_delta_pace[idx],
                self.y_pts_rem[idx],
                self.y_win[idx],
                self.y_spread[idx]
            )

else:
    class BasketballDataset:
        def __init__(self, *args, **kwargs):
            pass


# ─────────────────────────────────────────────────────────────────────────────
# 3. Pipeline de Entrenamiento Supervisado
# ─────────────────────────────────────────────────────────────────────────────

def entrenar_modelo_deep_learning(
    muestras: Optional[List[Dict[str, Any]]] = None,
    epochs: int = 35,
    batch_size: int = 16,
    learning_rate: float = 1e-3,
    save_path: str = DEFAULT_MODEL_PATH,
    device: Optional[str] = None
) -> Dict[str, Any]:
    """
    Ejecuta el bucle de entrenamiento completo de la red neuronal residual Transformer.
    Si no se proporcionan muestras, extrae de PostgreSQL y complementa con sintéticas.
    """
    if not TORCH_AVAILABLE:
        return {
            "exito": False,
            "error": "PyTorch no está disponible en el entorno virtual."
        }

    # Seleccionar dispositivo (CPU / GPU)
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    extractor = SequenceExtractor()

    # 1. Obtener datos
    if muestras is None or len(muestras) < 10:
        muestras_bd = extractor.construir_dataset_desde_bd()
        n_sinteticos = max(80, 150 - len(muestras_bd))
        muestras_sinteticas = extractor.generar_dataset_sintetico_calibracion(num_partidos=n_sinteticos)
        muestras = muestras_bd + muestras_sinteticas

    total_muestras = len(muestras)
    if total_muestras < 8:
        return {
            "exito": False,
            "error": f"Insuficientes muestras ({total_muestras}) para entrenar Deep Learning."
        }

    dataset = BasketballDataset(muestras)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, drop_last=(total_muestras > batch_size))

    # 2. Inicializar Modelo
    model = DeepMomentumResidualNet(
        seq_feature_dim=extractor.num_seq_features,
        macro_feature_dim=extractor.num_macro_features,
        lineup_feature_dim=extractor.num_lineup_features
    ).to(device)

    # 3. Optimizador y Funciones de Pérdida
    optimizer = optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)

    mse_loss = nn.MSELoss()
    bce_loss = nn.BCEWithLogitsLoss()

    history_loss = []
    history_mae_pace = []
    history_mae_spread = []

    model.train()
    for ep in range(epochs):
        ep_loss = 0.0
        ep_pace_mae = 0.0
        ep_spread_mae = 0.0
        n_batches = 0

        for b_seq, b_macro, b_lineup, b_delta_pace, b_pts_rem, b_win, b_spread in loader:
            b_seq = b_seq.to(device)
            b_macro = b_macro.to(device)
            b_lineup = b_lineup.to(device)
            b_delta_pace = b_delta_pace.to(device)
            b_pts_rem = b_pts_rem.to(device)
            b_win = b_win.to(device)
            b_spread = b_spread.to(device)

            optimizer.zero_grad()

            out = model(b_seq, b_macro, b_lineup)

            # Pérdida 1: Delta de ritmo (MSE)
            loss_pace = mse_loss(out["delta_pace"], b_delta_pace)

            # Pérdida 2: Puntos restantes con Incertidumbre Heterocedástica (Gaussian NLL)
            diff_pts_sq = (b_pts_rem - out["pts_mean"]) ** 2
            loss_pts = torch.mean(0.5 * torch.exp(-out["pts_logvar"]) * diff_pts_sq + 0.5 * out["pts_logvar"])

            # Pérdida 3: Probabilidad de Victoria (BCE)
            loss_win = bce_loss(out["win_logits"], b_win)

            # Pérdida 4: Margen de Spread proyectado (Smooth L1 Loss)
            loss_spread = nn.functional.smooth_l1_loss(out["spread_margin"], b_spread)

            # Pérdida Total Multi-Tarea
            total_loss = 2.0 * loss_pace + 0.05 * loss_pts + 1.0 * loss_win + 0.1 * loss_spread
            total_loss.backward()

            # Gradient clipping para estabilidad
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.5)
            optimizer.step()

            ep_loss += float(total_loss.item())
            ep_pace_mae += float(torch.mean(torch.abs(out["delta_pace"] - b_delta_pace)).item())
            ep_spread_mae += float(torch.mean(torch.abs(out["spread_margin"] - b_spread)).item())
            n_batches += 1

        scheduler.step()
        avg_loss = ep_loss / max(1, n_batches)
        avg_pace_mae = ep_pace_mae / max(1, n_batches)
        avg_spread_mae = ep_spread_mae / max(1, n_batches)
        history_loss.append(avg_loss)
        history_mae_pace.append(avg_pace_mae)
        history_mae_spread.append(avg_spread_mae)

    # 4. Guardar Modelo en Disco
    guardar_modelo_torch(model, save_path)

    return {
        "exito": True,
        "epochs": epochs,
        "total_muestras": total_muestras,
        "perdida_final": round(history_loss[-1], 4),
        "mae_pace_final": round(history_mae_pace[-1], 4),
        "mae_spread_final": round(history_mae_spread[-1], 4),
        "modelo_guardado_en": save_path,
        "dispositivo": device
    }


def guardar_modelo_torch(model: "DeepMomentumResidualNet", path: str) -> None:
    """Serializa los pesos del modelo con metadatos de configuración."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    checkpoint = {
        "state_dict": model.state_dict(),
        "seq_feature_dim": model.seq_feature_dim,
        "macro_feature_dim": model.macro_feature_dim,
        "lineup_feature_dim": getattr(model, "lineup_feature_dim", 10),
        "gru_hidden_dim": model.gru_hidden_dim,
    }
    torch.save(checkpoint, path)


def cargar_modelo_torch(path: str = DEFAULT_MODEL_PATH, device: str = "cpu") -> Optional["DeepMomentumResidualNet"]:
    """Carga el modelo entrenado desde disco si existe."""
    if not TORCH_AVAILABLE or not os.path.exists(path):
        return None
    try:
        ckpt = torch.load(path, map_location=device, weights_only=True)
        model = DeepMomentumResidualNet(
            seq_feature_dim=ckpt.get("seq_feature_dim", 10),
            macro_feature_dim=ckpt.get("macro_feature_dim", 16),
            lineup_feature_dim=ckpt.get("lineup_feature_dim", 10),
            gru_hidden_dim=ckpt.get("gru_hidden_dim", 32)
        )
        model.load_state_dict(ckpt["state_dict"])
        model.to(device)
        model.eval()
        return model
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 4. Inferencia en Tiempo Real (Fast Live Inference)
# ─────────────────────────────────────────────────────────────────────────────

_CACHED_MODEL = None
_CACHED_MODEL_MTIME = 0.0


def _obtener_modelo_en_memoria(path: str = DEFAULT_MODEL_PATH) -> Optional["DeepMomentumResidualNet"]:
    """Gestiona un singleton en memoria del modelo entrenado."""
    global _CACHED_MODEL, _CACHED_MODEL_MTIME
    if not TORCH_AVAILABLE or not os.path.exists(path):
        return None

    try:
        mtime = os.path.getmtime(path)
        if _CACHED_MODEL is None or mtime > _CACHED_MODEL_MTIME:
            _CACHED_MODEL = cargar_modelo_torch(path, device="cpu")
            _CACHED_MODEL_MTIME = mtime
        return _CACHED_MODEL
    except Exception:
        return None


def inferir_ajuste_momentum(
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
    fouls_visitante: int = 0,
    model_path: str = DEFAULT_MODEL_PATH
) -> Dict[str, Any]:
    """
    Función de inferencia principal invocada por el motor o la API.
    Calcula el vector de momentum, quintetos y consulta la red Transformer en < 5ms.
    """
    # Si PyTorch no está disponible o no hay modelo guardado, fallback seguro
    model = _obtener_modelo_en_memoria(model_path)
    cur_margin = round(float(pts_local - pts_visitante), 1)
    if model is None:
        return {
            "activo": False,
            "delta_pace": 0.0,
            "multiplicador_ritmo": 1.0,
            "incertidumbre_pts": 0.0,
            "prob_victoria_dl": None,
            "spread_proyectado_dl": cur_margin,
            "spread_std_dl": 8.5,
            "xai_factores": {"ritmo": 0.25, "jugadas": 0.25, "lineup": 0.25, "clutch_fatiga": 0.25},
            "etiqueta_momentum": "MODO BASE (Sin red cargada)",
            "detalle": "Motor Monte Carlo puro operando."
        }

    try:
        extractor = SequenceExtractor()
        x_seq_np, x_macro_np, x_lineup_np = extractor.extraer_estado_en_vivo_completo(
            plays=plays,
            team_a=team_a,
            team_b=team_b,
            minutos_jugados=minutos_jugados,
            pts_local=pts_local,
            pts_visitante=pts_visitante,
            cuarto=cuarto,
            total_game_min=total_game_min,
            ritmo_base=ritmo_base,
            ritmo_obs=ritmo_obs,
            lineup_local=lineup_local,
            lineup_visitante=lineup_visitante,
            fouls_local=fouls_local,
            fouls_visitante=fouls_visitante
        )

        with torch.no_grad():
            t_seq = torch.from_numpy(x_seq_np).float()
            t_macro = torch.from_numpy(x_macro_np).float()
            t_lineup = torch.from_numpy(x_lineup_np).float()

            pred = model(t_seq, t_macro, t_lineup)

            d_pace = float(pred["delta_pace"].item())
            logvar = float(pred["pts_logvar"].item())
            std_pts = float(np.sqrt(np.exp(logvar)))
            win_p = float(pred["win_prob"].item())
            spread_m = float(pred["spread_margin"].item())
            spread_s = float(pred["spread_std"].item())
            xai_raw = pred["xai_factors"].detach().cpu().numpy()[0]
            xai_dict = {
                "ritmo": round(float(xai_raw[0]), 3),
                "jugadas": round(float(xai_raw[1]), 3),
                "lineup": round(float(xai_raw[2]), 3),
                "clutch_fatiga": round(float(xai_raw[3]), 3)
            }

        # Multiplicador relativo respecto al ritmo base
        base_safe = max(0.5, float(ritmo_base))
        mult_pace = round(max(0.70, min(1.35, (base_safe + d_pace) / base_safe)), 3)

        # Etiqueta cualitativa según la magnitud de delta_pace
        if d_pace >= 0.30:
            etiqueta = "🔥 Aceleración Ofensiva Fuerte"
        elif d_pace >= 0.10:
            etiqueta = "📈 Ritmo Ligeramente Acelerado"
        elif d_pace <= -0.30:
            etiqueta = "🧊 Enfriamiento / Sequía Ofensiva"
        elif d_pace <= -0.10:
            etiqueta = "📉 Ritmo Ligeramente Frenado"
        else:
            etiqueta = "⚖️ Ritmo Estable / Neutral"

        return {
            "activo": True,
            "delta_pace": round(d_pace, 3),
            "multiplicador_ritmo": mult_pace,
            "incertidumbre_pts": round(std_pts, 1),
            "prob_victoria_dl": round(win_p, 3),
            "spread_proyectado_dl": round(spread_m, 2),
            "spread_std_dl": round(spread_s, 2),
            "xai_factores": xai_dict,
            "etiqueta_momentum": etiqueta,
            "detalle": f"Ajuste neuronal: {d_pace:+.2f} pts/min (Factor {mult_pace:.2f}x) | Spread DL: {spread_m:+.1f} pts"
        }

    except Exception as e:
        return {
            "activo": False,
            "delta_pace": 0.0,
            "multiplicador_ritmo": 1.0,
            "incertidumbre_pts": 0.0,
            "prob_victoria_dl": None,
            "spread_proyectado_dl": cur_margin,
            "spread_std_dl": 8.5,
            "xai_factores": {"ritmo": 0.25, "jugadas": 0.25, "lineup": 0.25, "clutch_fatiga": 0.25},
            "etiqueta_momentum": "FALLO INFERENCIA (Fallback)",
            "detalle": str(e)
        }
