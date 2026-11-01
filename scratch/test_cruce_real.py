import sys, os
sys.path.insert(0, os.path.abspath("."))
from dotenv import load_dotenv
load_dotenv()

from model.forebet_cruce import execute_forebet_aposta_cross

res = execute_forebet_aposta_cross(force_refresh=True)
summary = res.get("summary", {})
items = res.get("items", [])

print("=" * 60)
print("RESUMEN DE CRUCE REAL (FILTROS CORREGIDOS)")
print("=" * 60)
for k, v in summary.items():
    print(f"  {k}: {v}")

print("\n" + "=" * 60)
print(f"DETALLE DE LOS PARTIDOS CRUZADOS ({len(items)} TOTALES)")
print("=" * 60)
for it in items:
    fb = it.get("forebet", {})
    bp = it.get("best_pick", {})
    if bp:
        pick = bp.get("pick")
        cuota = bp.get("cuota_aposta")
        ev = bp.get("ev_pct")
        edge = bp.get("edge_pct")
        is_val = it.get("has_value")
        rev = bp.get("revisar_cruce", False)
        print(f"[{'VALOR' if is_val else 'SIN VALOR'}] {fb.get('home')} vs {fb.get('away')}")
        print(f"    Pick: {pick} | Cuota: {cuota} | EV: +{ev}% | Edge: {edge}% | Sospechoso/Revisar: {rev}")
