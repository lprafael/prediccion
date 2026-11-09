import math

import pytest

from model.forebet_cruce import same_team, teams_match
from model.combinadas import probabilidades_mercados, generar_combinadas, _resumen_combinada


@pytest.mark.parametrize("a,b,esperado", [
    ("Manchester United", "Manchester City", False),
    ("Inter", "Internacional", False),
    ("Inter Milan", "Inter", True),
    ("Atletico Mineiro", "Atlético Mineiro-MG", True),
    ("Atletico Mineiro", "Atlético Nacional S.A", False),
    ("Real Madrid", "Atlético Madrid", False),
    ("Chelsea", "Chelsea (F)", False),
    ("Manchester United", "Manchester United U21", False),
    ("Tottenham Hotspur", "Tottenham", True),
    ("Paris Saint Germain", "PSG", True),
    ("1. FC Köln", "FC Koln", True),
])
def test_same_team(a, b, esperado):
    assert same_team(a, b) is esperado


def test_teams_match_requiere_ambos():
    assert teams_match("Arsenal", "Chelsea", "Arsenal FC", "Chelsea")
    assert not teams_match("Arsenal", "Chelsea", "Arsenal", "Fulham")


def test_probabilidades_coherentes():
    pr = probabilidades_mercados(0.55, 0.25, 0.20)
    assert pr[("DC", "1X")][0] == pytest.approx(0.80, abs=1e-6)
    assert pr[("DNB", "1")][1] == pytest.approx(0.25, abs=1e-6)  # devolucion = empate
    for l in (1.5, 2.5, 3.5):
        assert pr[(f"OU {l}", "over")][0] + pr[(f"OU {l}", "under")][0] == pytest.approx(1.0)
    # mas lineas altas -> menos probabilidad de "mas de"
    assert pr[("OU 1.5", "over")][0] > pr[("OU 2.5", "over")][0] > pr[("OU 3.5", "over")][0]
    lh, la = pr["_lambdas"]
    assert lh > la  # el favorito local marca mas


def test_poisson_respeta_linea_de_mercado():
    pr = probabilidades_mercados(0.45, 0.28, 0.27, p_over={2.5: 0.40})
    assert pr[("OU 2.5", "over")][0] == pytest.approx(0.40)
    assert pr[("OU 2.5", "over")][2] == "mercado"


def _sel(eid, p, cuota, push=0.0, fuente="mercado"):
    return {"evento_id": eid, "partido": f"P{eid}", "prob": p, "prob_devolucion": push,
            "prob_no_perder": p + push, "cuota": cuota, "ev_pct": (p * cuota + push - 1) * 100,
            "fuente_prob": fuente}


def test_resumen_combinada_ev_exacto():
    r = _resumen_combinada([_sel(1, 0.8, 1.30), _sel(2, 0.75, 1.40)])
    assert r["cuota_total"] == pytest.approx(1.82)
    assert r["prob_ganar"] == pytest.approx(0.6)
    assert r["ev_pct"] == pytest.approx((0.8 * 1.3 * 0.75 * 1.4 - 1) * 100, abs=0.01)


def test_generar_combinadas_filtra_ev_negativo_y_mismo_partido():
    sels = [
        _sel(1, 0.80, 1.30),             # EV +4%
        _sel(1, 0.78, 1.35),             # mismo partido: solo una puede entrar
        _sel(2, 0.75, 1.40),             # EV +5%
        _sel(3, 0.85, 1.12),             # EV -4.8% -> fuera
        _sel(4, 0.60, 1.90),             # prob baja -> fuera
        _sel(5, 0.74, 1.40, fuente="modelo"),  # EV +3.6% modelo -> entra (>=3%)
    ]
    r = generar_combinadas(sels, bankroll=10_000_000, cuota_min=1.5, cuota_max=4.0, prob_min_combinada=0.3)
    assert r["combinadas"], "debe haber combinadas"
    for c in r["combinadas"]:
        ids = [p["evento_id"] for p in c["patas"]]
        assert len(ids) == len(set(ids))
        assert 3 not in ids and 4 not in ids
        assert c["ev_pct"] > 0
        assert 0 < c["monto_sugerido"] <= 300_000  # tope 3 %


def test_metricas_cupones():
    from model.cupones import metricas
    cup = [
        {"estado": "ganada", "monto": 1000, "pago": 1300, "cuota": 1.3, "n_selecciones": 1, "fecha": "2026-11-01T10:00"},
        {"estado": "perdida", "monto": 500, "pago": 0, "cuota": 12.0, "n_selecciones": 9, "fecha": "2026-11-01T11:00"},
        {"estado": "cobro_anticipado", "monto": 1000, "pago": 300, "cuota": 1.5, "n_selecciones": 1, "fecha": "2026-11-02T10:00"},
        {"estado": "abierta", "monto": 100, "pago": 0, "cuota": 2.0, "n_selecciones": 2, "fecha": "2026-11-03T10:00"},
    ]
    m = metricas(cup)
    assert m["total"]["n"] == 3 and m["abiertas"] == 1
    assert m["total"]["beneficio"] == 1300 + 300 - 2500
    assert m["por_selecciones"]["9+"]["ganadas"] == 0
    assert m["cobros_anticipados"] == {"n": 1, "apostado": 1000, "recuperado": 300}
