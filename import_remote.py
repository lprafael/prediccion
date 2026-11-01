import json
import urllib.request

with open("/root/prediccion/cruce_resultados.json", "r", encoding="utf-8") as f:
    raw = json.load(f)

matches = [x["fb"] for x in raw if "fb" in x]
print(f"Enviando {len(matches)} partidos de Forebet al API...")

req = urllib.request.Request(
    "http://localhost:8000/api/forebet-cruce/importar",
    data=json.dumps({"matches": matches}).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
res = urllib.request.urlopen(req)
print("Respuesta:", res.read().decode("utf-8"))
