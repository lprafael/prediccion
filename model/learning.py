"""
🧠 Módulo de Machine Learning, Calibración Probabilística y Cotejo de Hitos
Implementa:
1. Calibración de probabilidades empíricas mediante Platt Scaling (Regresión Logística con SciPy).
2. Optimización adaptativa de hiperparámetros de simulación (inercia bayesiana 'k' y corrección de sesgo).
3. Cotejador post-partido hito a hito (Milestone Evaluator) frente al marcador final real.
4. Optimizador de umbrales para apuestas ficticias de cuota elevada y alto valor esperado (EV).
"""

from typing import Dict, List, Optional, Tuple, Union, Any
import numpy as np
from scipy.optimize import minimize, minimize_scalar
import math

from model.database import (
    obtener_partido,
    listar_snapshots,
    listar_hitos,
    listar_apuestas,
    obtener_calibracion_activa,
    guardar_calibracion,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Calibración de Probabilidades (Platt Scaling)
# ─────────────────────────────────────────────────────────────────────────────

def _sigmoid(z: np.ndarray) -> np.ndarray:
    """Función sigmoide numéricamente estable."""
    return np.where(z >= 0, 1.0 / (1.0 + np.exp(-z)), np.exp(z) / (1.0 + np.exp(z)))


def _logit(p: np.ndarray, eps: float = 1e-4) -> np.ndarray:
    """Transformación logit con acotamiento de seguridad."""
    p_clipped = np.clip(p, eps, 1.0 - eps)
    return np.log(p_clipped / (1.0 - p_clipped))


def calibrar_probabilidad(
    p_raw: float,
    platt_a: float = 1.0,
    platt_b: float = 0.0,
    a: Optional[float] = None,
    b: Optional[float] = None
) -> float:
    """
    Aplica la calibración aprendida Platt Scaling a una probabilidad cruda de Monte Carlo:
    P_calibrada = sigma(a * logit(p_raw) + b)
    """
    if a is not None:
        platt_a = a
    if b is not None:
        platt_b = b

    if p_raw <= 0.0001:
        return 0.0001
    if p_raw >= 0.9999:
        return 0.9999
    try:
        logit_val = math.log(p_raw / (1.0 - p_raw))
        z = platt_a * logit_val + platt_b
        # Estabilidad numérica
        if z >= 35.0:
            return 0.9999
        if z <= -35.0:
            return 0.0001
        p_cal = 1.0 / (1.0 + math.exp(-z))
        return round(float(np.clip(p_cal, 0.001, 0.999)), 4)
    except Exception:
        return float(p_raw)


def entrenar_platt_scaling(
    probs: Union[np.ndarray, List[float]],
    outcomes: Union[np.ndarray, List[float]]
) -> Tuple[float, float, float]:
    """
    Entrena los parámetros (a, b) de Platt Scaling mediante minimización de la
    pérdida logarítmica (Log Loss / Cross-Entropy) con regularización L2.

    Retorna:
        (a, b, brier_score_calibrado)
    """
    probs = np.asarray(probs, dtype=float)
    outcomes = np.asarray(outcomes, dtype=float)

    if len(probs) < 4:
        # Insuficientes datos para ajustar; retornar identidad
        brier = float(np.mean((probs - outcomes) ** 2)) if len(probs) > 0 else 0.25
        return 1.0, 0.0, round(brier, 4)

    logits = _logit(probs)

    def _loss(params):
        a, b = params
        z = a * logits + b
        p_hat = _sigmoid(z)
        eps = 1e-6
        p_hat = np.clip(p_hat, eps, 1.0 - eps)
        # Binary Cross-Entropy + Regularización L2 leve hacia a=1, b=0
        bce = -np.mean(outcomes * np.log(p_hat) + (1.0 - outcomes) * np.log(1.0 - p_hat))
        reg = 0.01 * ((a - 1.0) ** 2 + b ** 2)
        return bce + reg

    res = minimize(_loss, x0=[1.0, 0.0], bounds=[(0.2, 3.0), (-2.0, 2.0)], method="L-BFGS-B")
    if res.success:
        a_opt, b_opt = float(res.x[0]), float(res.x[1])
    else:
        a_opt, b_opt = 1.0, 0.0

    p_cal = _sigmoid(a_opt * logits + b_opt)
    brier = float(np.mean((p_cal - outcomes) ** 2))

    return round(a_opt, 4), round(b_opt, 4), round(brier, 4)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Afinación de Hiperparámetros (Inercia Bayesiana 'k' y Corrección de Sesgo)
# ─────────────────────────────────────────────────────────────────────────────

def optimizar_hiperparametros_ritmo(
    snapshots: List[dict],
    totales_reales: Dict[int, float]
) -> Tuple[float, float, float]:
    """
    Encuentra el valor óptimo del parámetro de contracción bayesiana 'k' (shrinkage)
    y el offset de sesgo (bias) que minimizan el error cuadrático medio (MSE)
    entre las proyecciones de los snapshots y el total final real del partido.

    Retorna:
        (k_optimo, bias_offset_optimo, mae_puntos)
    """
    if not snapshots or not totales_reales:
        return 20.0, 0.0, 0.0

    muestras = []
    for s in snapshots:
        pid = s.get("partido_id")
        if pid in totales_reales:
            t_real = totales_reales[pid]
            proj = float(s.get("total_proyectado") or 0.0)
            obs_pace = float(s.get("ritmo_obs") or 0.0)
            base_pace = float(s.get("ritmo_base") or 0.0)
            min_jug = float(s.get("minutos_jugados") or 0.0)
            tot_act = float(s.get("total_actual") or 0.0)
            if min_jug > 0 and proj > 0:
                muestras.append({
                    "total_real": t_real,
                    "proj_original": proj,
                    "ritmo_obs": obs_pace,
                    "ritmo_base": base_pace,
                    "minutos_jugados": min_jug,
                    "total_actual": tot_act,
                })

    if len(muestras) < 4:
        return 20.0, 0.0, 0.0

    # 1. Sesgo medio observado (residuo medio)
    residuos = [m["total_real"] - m["proj_original"] for m in muestras]
    bias_offset = float(np.mean(residuos))

    # 2. Optimización de k en el suavizado bayesiano w(t) = t / (t + k)
    def _mse_k(k_val):
        errores = []
        for m in muestras:
            t = m["minutos_jugados"]
            tot_game_min = 40.0
            rem_min = max(0.0, tot_game_min - t)
            w = t / (t + k_val)
            ritmo_blend = w * m["ritmo_obs"] + (1.0 - w) * m["ritmo_base"]
            proj_k = m["total_actual"] + ritmo_blend * rem_min + bias_offset
            errores.append((proj_k - m["total_real"]) ** 2)
        return np.mean(errores)

    res_k = minimize_scalar(_mse_k, bounds=(5.0, 60.0), method="bounded")
    k_opt = float(res_k.x) if res_k.success else 20.0

    mae = float(np.mean([abs(r) for r in residuos]))

    return round(k_opt, 2), round(bias_offset, 2), round(mae, 2)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Cotejador Post-Partido Hito a Hito (Milestone Evaluator)
# ─────────────────────────────────────────────────────────────────────────────

def cotejar_hitos_partido(
    partido_id: int,
    pts_local_real: Optional[int] = None,
    pts_visitante_real: Optional[int] = None
) -> dict:
    """
    Coteja retrospectivamente todos los hitos y snapshots registrados de un partido
    contra el resultado final real.
    
    Calcula:
    - Error absoluto de puntos en cada hito (MAE)
    - Acierto de ganador (Local vs Visitante)
    - Acierto de línea Over/Under evaluada en ese hito
    - Cobertura dentro del cono de incertidumbre (Intervalos 80% y 95%)
    - Calificación de precisión de cada hito
    """
    partido = obtener_partido(partido_id)
    if not partido:
        return {"error": f"Partido #{partido_id} no encontrado", "hitos": []}

    # Determinar marcador final real
    if pts_local_real is not None and pts_visitante_real is not None:
        loc_fin = int(pts_local_real)
        vis_fin = int(pts_visitante_real)
    elif partido.get("pts_local_final") is not None and partido.get("pts_visitante_final") is not None:
        loc_fin = int(partido["pts_local_final"])
        vis_fin = int(partido["pts_visitante_final"])
    else:
        # Sumar marcadores de cuarto existentes
        marcadores = partido.get("marcadores", [])
        loc_fin = sum(m["pts_local"] for m in marcadores)
        vis_fin = sum(m["pts_visitante"] for m in marcadores)

    total_real = loc_fin + vis_fin
    ganador_real = partido["equipo_local"] if loc_fin > vis_fin else (
        partido["equipo_visitante"] if vis_fin > loc_fin else "EMPATE"
    )

    hitos_raw = listar_hitos(partido_id)
    if not hitos_raw:
        # Si no se marcaron con flag es_hito, usar todos los snapshots
        hitos_raw = listar_snapshots(partido_id)

    evaluaciones_hitos = []
    errores_absolutos = []
    aciertos_ganador = 0
    aciertos_linea = 0
    total_lineas_eval = 0
    en_cono_80 = 0
    en_cono_95 = 0

    for idx, h in enumerate(hitos_raw, 1):
        nombre = h.get("nombre_hito") or f"Snapshot #{idx} (Q{h.get('cuarto_snapshot', '?')})"
        t_proy = float(h.get("total_proyectado") or 0.0)
        p10 = float(h.get("total_p10") or h.get("total_p05") or 0.0)
        p90 = float(h.get("total_p90") or h.get("total_p95") or 0.0)
        p025 = float(h.get("total_p025") or (t_proy - 20.0))
        p975 = float(h.get("total_p975") or (t_proy + 20.0))

        err_puntos = round(total_real - t_proy, 1)
        mae_hito = round(abs(err_puntos), 1)
        errores_absolutos.append(mae_hito)

        # Ganador proyectado
        p_vic_a = float(h.get("prob_victoria_local") or 0.5)
        ganador_proy = partido["equipo_local"] if p_vic_a >= 0.5 else partido["equipo_visitante"]
        acerto_gan = (ganador_proy == ganador_real) if ganador_real != "EMPATE" else True
        if acerto_gan:
            aciertos_ganador += 1

        # Intervalos de incertidumbre
        dentro_80 = (p10 <= total_real <= p90)
        dentro_95 = (p025 <= total_real <= p975)
        if dentro_80:
            en_cono_80 += 1
        if dentro_95:
            en_cono_95 += 1

        # Calificación del hito
        if mae_hito <= 3.0:
            calif = "🎯 Preciso (≤3 pts)"
            badge_color = "#38a169"
        elif dentro_80:
            calif = "🟢 En Rango 80%"
            badge_color = "#48bb78"
        elif dentro_95:
            calif = "🟡 En Rango 95%"
            badge_color = "#ecc94b"
        else:
            calif = "🔴 Desviado"
            badge_color = "#f56565"

        # Over / Under si tenía línea registrada en el hito
        linea_hito = h.get("linea_apuesta")
        rec_ou = "—"
        res_ou = "—"
        acerto_ou_flag = None
        if linea_hito is not None and float(linea_hito) > 0:
            l_val = float(linea_hito)
            p_ov = float(h.get("prob_over") or 0.5)
            rec_ou = f"OVER {l_val:.1f}" if p_ov >= 0.5 else f"UNDER {l_val:.1f}"
            res_ou = f"OVER ({total_real})" if total_real > l_val else (f"UNDER ({total_real})" if total_real < l_val else "PUSH")
            acerto_ou_flag = (
                (p_ov >= 0.5 and total_real > l_val) or
                (p_ov < 0.5 and total_real < l_val) or
                (total_real == l_val)
            )
            total_lineas_eval += 1
            if acerto_ou_flag:
                aciertos_linea += 1

        evaluaciones_hitos.append({
            "idx": idx,
            "nombre": nombre,
            "cuarto": h.get("cuarto_snapshot", 1),
            "minutos_jugados": h.get("minutos_jugados", 0.0),
            "marcador_momento": f"{h.get('pts_local_actual',0)} - {h.get('pts_visitante_actual',0)}",
            "total_momento": h.get("total_actual", 0),
            "total_proyectado": t_proy,
            "total_real": total_real,
            "error_puntos": err_puntos,
            "mae": mae_hito,
            "rango_80": f"[{p10:.0f} – {p90:.0f}]",
            "rango_95": f"[{p025:.0f} – {p975:.0f}]",
            "dentro_80": dentro_80,
            "dentro_95": dentro_95,
            "ganador_proy": ganador_proy,
            "acerto_ganador": acerto_gan,
            "linea_evaluada": linea_hito,
            "recomendacion_ou": rec_ou,
            "resultado_ou": res_ou,
            "acerto_ou": acerto_ou_flag,
            "calificacion": calif,
            "badge_color": badge_color,
            "guardado_en": str(h.get("guardado_en", ""))[:16]
        })

    num_hitos = len(evaluaciones_hitos)
    mae_promedio = round(float(np.mean(errores_absolutos)), 1) if errores_absolutos else 0.0
    pct_ganador = round((aciertos_ganador / num_hitos * 100.0), 1) if num_hitos > 0 else 0.0
    pct_cono_80 = round((en_cono_80 / num_hitos * 100.0), 1) if num_hitos > 0 else 0.0
    pct_cono_95 = round((en_cono_95 / num_hitos * 100.0), 1) if num_hitos > 0 else 0.0
    pct_linea = round((aciertos_linea / total_lineas_eval * 100.0), 1) if total_lineas_eval > 0 else 0.0

    return {
        "partido_id": partido_id,
        "equipo_local": partido["equipo_local"],
        "equipo_visitante": partido["equipo_visitante"],
        "marcador_final": f"{loc_fin} - {vis_fin}",
        "total_real": total_real,
        "ganador_real": ganador_real,
        "total_hitos": num_hitos,
        "mae_promedio": mae_promedio,
        "pct_acierto_ganador": pct_ganador,
        "pct_cobertura_80": pct_cono_80,
        "pct_cobertura_95": pct_cono_95,
        "pct_acierto_lineas": pct_linea,
        "hitos": evaluaciones_hitos
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. Análisis de Pagos de la Casa & Filtros de Apuestas Ficticias
# ─────────────────────────────────────────────────────────────────────────────

def clasificar_pago_casa(
    cuota_casa: float,
    prob_modelo: float,
    umbral_cuota_alta: float = 2.10,
    umbral_ev_min: float = 0.06
) -> dict:
    """
    Analiza el monto que paga la casa y determina si califica como:
    - 'PAGO_ELEVADO' (cuota >= 2.10 con probabilidad sólida y EV positivo)
    - 'VALOR_ALTO' (EV >= +6%)
    - 'PAGO_ESTANDAR' (cuota de línea regular 1.80 - 2.05)
    - 'SIN_VALOR' (cuota desfavorable / EV negativo)
    
    Retorna la regla de activación recomendada para apuestas ficticias.
    """
    if not cuota_casa or cuota_casa <= 1.0:
        return {
            "categoria": "SIN_DATOS",
            "es_pago_elevado": False,
            "disparar_apuesta_ficticia": False,
            "ev": 0.0,
            "motivo": "Sin cuota válida de la casa."
        }

    ev = (prob_modelo * cuota_casa) - 1.0

    # 1. Pago elevado con valor: cuota alta donde el modelo proyecta viabilidad
    if cuota_casa >= umbral_cuota_alta and ev >= 0.02 and prob_modelo >= 0.38:
        return {
            "categoria": "PAGO_ELEVADO",
            "es_pago_elevado": True,
            "disparar_apuesta_ficticia": True,
            "ev": round(ev, 4),
            "regla": "PAGO_ELEVADO",
            "motivo": f"🔥 Pago elevado de la casa ({cuota_casa:.2f}) con EV de {ev*100:+.1f}% y {prob_modelo*100:.1f}% prob."
        }

    # 2. Alto Valor Esperado (EV >= +6%)
    if ev >= umbral_ev_min:
        return {
            "categoria": "ALTO_EV",
            "es_pago_elevado": cuota_casa >= 2.0,
            "disparar_apuesta_ficticia": True,
            "ev": round(ev, 4),
            "regla": "ALTO_EV",
            "motivo": f"💰 Ventaja matemática significativa: EV {ev*100:+.1f}% a cuota {cuota_casa:.2f}."
        }

    # 3. Pago estándar con ventaja moderada
    if ev > 0.02:
        return {
            "categoria": "PAGO_ESTANDAR",
            "es_pago_elevado": False,
            "disparar_apuesta_ficticia": False,
            "ev": round(ev, 4),
            "regla": "VALOR_MODERADO",
            "motivo": f"Ventaja moderada (EV {ev*100:+.1f}%)."
        }

    return {
        "categoria": "SIN_VALOR",
        "es_pago_elevado": False,
        "disparar_apuesta_ficticia": False,
        "ev": round(ev, 4),
        "regla": "SIN_EDGE",
        "motivo": f"Línea ajustada o cuota castigada (EV {ev*100:+.1f}%)."
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. Pipeline de Auto-Entrenamiento y Afinación Continua
# ─────────────────────────────────────────────────────────────────────────────

def ejecutar_auto_entrenamiento_ml(modelo_nombre: str = "default_mc") -> dict:
    """
    Ejecuta el ciclo completo de aprendizaje y afinación del modelo:
    1. Recolecta todas las apuestas resueltas (reales y ficticias).
    2. Recolecta todos los snapshots de partidos finalizados.
    3. Entrena los coeficientes de calibración Platt Scaling (a, b).
    4. Optimiza el factor de contracción bayesiana 'k' y el sesgo de puntos.
    5. Guarda y persiste la nueva calibración en PostgreSQL.
    6. Retorna un dict con las métricas del antes y después.
    """
    # 1. Apuestas resueltas para calibración de probabilidades
    apuestas = listar_apuestas(limit=1000)
    resueltas = [a for a in apuestas if a.get("resultado") in ("GANADA", "PERDIDA") and a.get("prob_modelo") is not None]

    total_apuestas_eval = len(resueltas)
    probs_list = []
    outcomes_list = []

    for a in resueltas:
        try:
            p = float(a["prob_modelo"])
            if 0.0 < p < 1.0:
                probs_list.append(p)
                outcomes_list.append(1.0 if a["resultado"] == "GANADA" else 0.0)
        except (ValueError, TypeError):
            continue

    probs_arr = np.array(probs_list)
    outcomes_arr = np.array(outcomes_list)

    # 2. Entrenar Platt Scaling
    if len(probs_arr) >= 4:
        brier_antes = float(np.mean((probs_arr - outcomes_arr) ** 2))
        platt_a, platt_b, brier_despues = entrenar_platt_scaling(probs_arr, outcomes_arr)
    else:
        platt_a, platt_b, brier_antes, brier_despues = 1.0, 0.0, 0.25, 0.25

    # 3. Partidos finalizados y snapshots para optimizar k y bias
    from model.database import listar_partidos
    partidos_fin = [p for p in listar_partidos(limit=200) if p.get("estado") == "finalizado"]
    totales_reales = {}
    todos_snaps = []

    for p in partidos_fin:
        pid = p["id"]
        t_final = p.get("total_final")
        if t_final is None:
            t_final = (p.get("total_local") or 0) + (p.get("total_visitante") or 0)
        if t_final > 0:
            totales_reales[pid] = float(t_final)
            snaps_p = listar_snapshots(pid)
            todos_snaps.extend(snaps_p)

    k_opt, bias_opt, mae_puntos = optimizar_hiperparametros_ritmo(todos_snaps, totales_reales)

    # 4. Guardar calibración afinada en la BD
    cid = guardar_calibracion(
        platt_a=platt_a,
        platt_b=platt_b,
        bayes_k_optimo=k_opt,
        bias_offset=bias_opt,
        umbral_cuota_min=2.10,
        umbral_ev_min=0.06,
        brier_score_actual=brier_despues,
        mae_puntos_actual=mae_puntos,
        total_partidos_entrenados=len(totales_reales),
        total_apuestas_evaluadas=total_apuestas_eval,
        modelo_nombre=modelo_nombre
    )

    return {
        "exito": True,
        "calibracion_id": cid,
        "muestras_usadas": total_apuestas_eval + len(totales_reales),
        "brier_nuevo": round(brier_despues, 4),
        "brier_previo": round(brier_antes, 4),
        "platt_a": platt_a,
        "platt_b": platt_b,
        "bayes_k_optimo": k_opt,
        "bias_offset": bias_opt,
        "brier_score_antes": round(brier_antes, 4),
        "brier_score_despues": round(brier_despues, 4),
        "mejora_brier_pct": round(max(0.0, (brier_antes - brier_despues) / max(brier_antes, 1e-4) * 100.0), 1),
        "mae_puntos": mae_puntos,
        "partidos_entrenados": len(totales_reales),
        "apuestas_evaluadas": total_apuestas_eval,
        "fecha": str(np.datetime64("now"))
    }
