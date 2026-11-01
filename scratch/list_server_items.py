import requests

r = requests.get('http://187.77.247.23:8000/api/forebet-cruce')
data = r.json()
print(f"Total: {data.get('total_items')}")
for item in data.get('items', []):
    fb = item.get('forebet', {})
    bp = item.get('best_pick', {})
    print(f"[{fb.get('tournament')}] {fb.get('home')} vs {fb.get('away')} -> Pick {bp.get('pick')} | Cuota: {bp.get('cuota_aposta')} | EV: +{bp.get('ev_pct')}%")
