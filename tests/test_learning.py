"""
Pruebas unitarias y de integración para el subsistema de Aprendizaje Automático (ML),
calibración probabilística (Platt Scaling), cotejo de hitos post-partido y apuestas ficticias en Guaraníes.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from model.learning import (
    calibrar_probabilidad,
    entrenar_platt_scaling,
    optimizar_hiperparametros_ritmo,
    cotejar_hitos_partido,
    clasificar_pago_casa,
    ejecutar_auto_entrenamiento_ml,
)
from model.database import (
    crear_partido,
    actualizar_partido,
    registrar_hito,
    registrar_apuesta,
    finalizar_partido_y_liquidar,
    calcular_metricas_rendimiento_apuestas,
    obtener_calibracion_activa,
    guardar_calibracion,
    eliminar_partido,
)
from model.engine import SimulationSummary
import pandas as pd
import numpy as np


class TestMachineLearningAndBetting(unittest.TestCase):

    def test_platt_scaling_bounds(self):
        """Verificar que la calibración Platt mantenga las probabilidades acotadas entre (0, 1)."""
        test_probs = [0.001, 0.05, 0.25, 0.50, 0.75, 0.95, 0.999]
        for p in test_probs:
            calibrated = calibrar_probabilidad(p, a=1.1, b=-0.05)
            self.assertGreater(calibrated, 0.0)
            self.assertLess(calibrated, 1.0)

        # Si a=1 y b=0, debe preservar el valor prácticamente sin cambio
        self.assertAlmostEqual(calibrar_probabilidad(0.5, a=1.0, b=0.0), 0.5, places=3)

    def test_entrenar_platt_scaling(self):
        """Entrenar calibrador Platt con datos sintéticos sobre-confiados y verificar reducción de error."""
        # Supongamos que el modelo es sobre-confiado (predice 0.8 cuando la tasa real es 0.6)
        probs = [0.85] * 60 + [0.15] * 40
        outcomes = [1] * 50 + [0] * 10 + [0] * 30 + [1] * 10
        a_opt, b_opt, brier_calib = entrenar_platt_scaling(probs, outcomes)
        self.assertIsInstance(a_opt, float)
        self.assertIsInstance(b_opt, float)
        self.assertLessEqual(brier_calib, 0.25)

    def test_clasificar_pago_casa(self):
        """Validar detección de pago elevado (>= 2.10 o alto EV) y cuotas normales."""
        # Cuota >= 2.10 y probabilidad favorable -> PAGO ELEVADO
        pago_alto = clasificar_pago_casa(cuota_casa=2.25, prob_modelo=0.55)
        self.assertTrue(pago_alto["es_pago_elevado"])
        self.assertEqual(pago_alto["categoria"], "PAGO_ELEVADO")

        # Cuota estándar 1.85
        pago_std = clasificar_pago_casa(cuota_casa=1.85, prob_modelo=0.52)
        self.assertFalse(pago_std["es_pago_elevado"])

        # Cuota baja < 1.40
        pago_bajo = clasificar_pago_casa(cuota_casa=1.35, prob_modelo=0.70)
        self.assertFalse(pago_bajo["es_pago_elevado"])

    def test_flujo_hitos_y_apuesta_ficticia_guaranies(self):
        """
        Validar flujo completo:
        1. Crear partido de prueba
        2. Registrar hitos durante el partido
        3. Registrar apuesta ficticia de 100.000 Gs. con cuota de pago elevado
        4. Finalizar y liquidar partido
        5. Cotejar hitos
        6. Validar tablero de rendimiento con filtro de ficticias en Gs.
        """
        # 1. Crear partido
        pid = crear_partido(
            equipo_local="Olimpia Kings",
            equipo_visitante="San José Basketball",
            torneo_nombre="FIBA / Euroliga / Ligas Locales",
            cuarto_actual=2,
            min_restantes=5,
            seg_restantes=0,
            quarters_data=[(22, 20), (18, 16)],
            notas="Prueba de Hitos y ML"
        )
        self.assertIsNotNone(pid)

        from model.config import TOURNAMENT_PRESETS
        from model.engine import BasketballPredictor
        cfg = TOURNAMENT_PRESETS["FIBA"]
        pred = BasketballPredictor(cfg)
        summary = pred.run_live_simulation(
            current_quarter=2,
            elapsed_seconds_in_quarter=5.0 * 60,
            quarters_data=[(22.0, 20.0), (18.0, 16.0)],
            n_simulations=500
        )

        # 2. Registrar dos hitos
        hid1 = registrar_hito(
            partido_id=pid,
            nombre_hito="PRE_PARTIDO",
            cuarto_snapshot=1,
            minutos_jugados=0.0,
            pts_local_actual=0,
            pts_visitante_actual=0,
            summary=summary,
            linea_apuesta=168.5,
            prob_over=0.55,
            prob_under=0.45,
            cuota_over=1.90,
            cuota_under=1.90
        )
        self.assertIsNotNone(hid1)

        hid2 = registrar_hito(
            partido_id=pid,
            nombre_hito="MEDIO_TIEMPO",
            cuarto_snapshot=2,
            minutos_jugados=20.0,
            pts_local_actual=40,
            pts_visitante_actual=36,
            summary=summary,
            linea_apuesta=169.5,
            prob_over=0.62,
            prob_under=0.38,
            cuota_over=2.15,
            cuota_under=1.75
        )
        self.assertIsNotNone(hid2)

        # 3. Registrar apuesta ficticia de 100.000 Gs.
        aid = registrar_apuesta(
            partido_id=pid,
            cuarto_apuesta=2,
            minutos_jugados=20.0,
            linea=169.5,
            tipo="OVER",
            monto=100000.0,  # 100.000 Gs.
            cuota_casa=2.15, # Pago elevado
            prob_modelo=0.62,
            ev=0.333,
            kelly_pct=0.08,
            notas="Apuesta ficticia testeando pago elevado 100.000 Gs.",
            grado_apuesta="GRADO A+ (PAGO ELEVADO)",
            spread_edge=2.5,
            es_ficticia=True,
            hito_origen="MEDIO_TIEMPO",
            regla_activacion="PAGO_ELEVADO"
        )
        self.assertIsNotNone(aid)

        # 4. Finalizar y liquidar partido (Total: 88 + 84 = 172 pts > 169.5 -> OVER GANA)
        res_liq = finalizar_partido_y_liquidar(pid, pts_local_final=88, pts_visitante_final=84)
        self.assertEqual(res_liq["total_final"], 172)
        self.assertGreaterEqual(res_liq["apuestas_liquidadas"], 1)
        self.assertGreaterEqual(res_liq["ganadas"], 1)

        # 5. Cotejar hitos
        cotejo = cotejar_hitos_partido(pid)
        self.assertIsNotNone(cotejo)
        self.assertEqual(cotejo["total_real"], 172)
        self.assertGreaterEqual(len(cotejo["hitos"]), 2)
        self.assertIn("mae_promedio", cotejo)

        # 6. Tablero de rendimiento filtrado por apuestas ficticias
        rend_ficticias = calcular_metricas_rendimiento_apuestas(filtro_ficticia=True)
        self.assertGreaterEqual(rend_ficticias["total_apuestas"], 1)
        self.assertIn("por_cuota", rend_ficticias)

        # 7. Limpiar partido de prueba para no dejar duplicados en la BD
        eliminar_partido(pid)

    def test_auto_entrenamiento_ml_pipeline(self):
        """Ejecutar el auto-entrenamiento ML y verificar persistencia en BD."""
        res_train = ejecutar_auto_entrenamiento_ml()
        self.assertIn("exito", res_train)
        if res_train["exito"]:
            self.assertGreaterEqual(res_train["muestras_usadas"], 0)
            self.assertIn("platt_a", res_train)
            self.assertIn("bayes_k_optimo", res_train)

        # Verificar que la calibración activa esté presente en BD
        activa = obtener_calibracion_activa()
        self.assertIsNotNone(activa)
        self.assertIn("platt_a", activa)
        self.assertIn("platt_b", activa)
        self.assertIn("bayes_k_optimo", activa)


if __name__ == "__main__":
    unittest.main()
