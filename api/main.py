"""
🏀 Basketball Predictor — FastAPI Main Application
Expone el motor de predicción probabilística, base de datos y WebSockets
como una API REST moderna. Compatibilidad total con model/ existente.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from model.database import init_db

# ─── Routers ───────────────────────────────────────────────────────────────────
from api.routers import torneos, partidos, simulacion, apuestas, snapshots, calibracion, scraper, forebet_cruce, cupones
from api.ws_live import router as ws_router



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la base de datos al arrancar el servidor con reintentos."""
    print("[API] Iniciando Basketball Predictor API...")
    import time
    for attempt in range(1, 6):
        try:
            init_db()
            print(f"[API] Base de datos conectada e inicializada correctamente (intento {attempt}).")
            break
        except Exception as e:
            print(f"[API] Esperando conexion a DB ({attempt}/5): {e}")
            if attempt < 5:
                time.sleep(2)
            else:
                print("[API] Advertencia: la API continuara pero algunas consultas a DB fallaran hasta que el servidor este disponible.")

    # Actualizacion automatica 24/7 del cruce (fuentes oficiales x Aposta.la)
    import asyncio
    from starlette.concurrency import run_in_threadpool

    async def _actualizador_cruce():
        from model.forebet_cruce import execute_forebet_aposta_cross
        from model.fuentes_oficiales import fuentes_configuradas
        intervalo = float(os.getenv("CRUCE_INTERVAL_MIN", "120") or 0)
        if intervalo <= 0 or not any(fuentes_configuradas().values()):
            print("[Cruce] Actualizacion automatica desactivada (sin claves o CRUCE_INTERVAL_MIN=0).")
            return
        await asyncio.sleep(20)
        while True:
            try:
                res = await run_in_threadpool(execute_forebet_aposta_cross, True)
                print(f"[Cruce] Actualizado: {res.get('summary', {})}")
            except Exception as e:
                print(f"[Cruce] Error en actualizacion automatica: {e}")
            await asyncio.sleep(intervalo * 60)

    tarea_cruce = asyncio.create_task(_actualizador_cruce())
    yield
    tarea_cruce.cancel()
    print("[API] API apagada.")


app = FastAPI(
    title="🏀 Basketball Predictor API",
    description=(
        "API REST + WebSocket para predicción probabilística de baloncesto en vivo. "
        "Motor Bayesiano + Monte Carlo + Deep Learning Residual."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ─── CORS ──────────────────────────────────────────────────────────────────────
# Permite el frontend React en desarrollo (Vite :5173) y producción (:80)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Autenticación por API Key & Cookies ─────────────────────────────────────────
from fastapi import Request, Form
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse

API_KEY = os.getenv("POLIVERSO_API_KEY", "").strip()

PUBLIC_PATHS = {
    "/api/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/login",
    "/logout",
}

@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    """
    Verifica que la petición contenga una API Key válida cuando POLIVERSO_API_KEY
    está configurada en el entorno. Si no está configurada, opera en modo abierto.
    Soporta cabecera X-API-Key, Bearer Token, Cookie del navegador y Query Param.
    """
    if not API_KEY:
        return await call_next(request)

    path = request.url.path

    # Rutas públicas siempre permitidas
    if path in PUBLIC_PATHS:
        return await call_next(request)

    # Permitir peticiones preflight CORS
    if request.method == "OPTIONS":
        return await call_next(request)

    # Buscar clave en cabeceras, cookie del navegador o query params
    req_key = (
        request.headers.get("X-API-Key")
        or request.headers.get("x-api-key")
        or request.cookies.get("poliverso_api_key")
        or request.query_params.get("api_key")
        or request.query_params.get("key")
    )
    if not req_key:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            req_key = auth_header[7:].strip()

    is_valid = bool(req_key and req_key == API_KEY)

    # Si es endpoint de API REST y no es válida -> 401 JSON
    if path.startswith("/api"):
        if not is_valid:
            return JSONResponse(
                status_code=401,
                content={"detail": "No autorizado: API Key no proporcionada o inválida (use cabecera X-API-Key)."},
            )
        return await call_next(request)

    # Si es navegación web en el navegador y no tiene clave:
    # Eximir archivos estáticos para que carguen CSS/JS/imágenes
    if not is_valid:
        if not path.startswith("/assets") and not path.endswith((".js", ".css", ".ico", ".svg", ".png", ".jpg", ".woff2")):
            return RedirectResponse(url="/login")

    response = await call_next(request)

    # Si vino la clave válida por query param en el navegador, guardar cookie por 1 año
    query_key = request.query_params.get("api_key") or request.query_params.get("key")
    if query_key and query_key == API_KEY:
        response.set_cookie(
            key="poliverso_api_key",
            value=query_key,
            max_age=60 * 60 * 24 * 365,
            httponly=False,
            samesite="lax",
        )

    return response


# ─── Routers REST ──────────────────────────────────────────────────────────────
app.include_router(torneos.router,     prefix="/api", tags=["Torneos"])
app.include_router(partidos.router,    prefix="/api", tags=["Partidos"])
app.include_router(simulacion.router,  prefix="/api", tags=["Simulación"])
app.include_router(apuestas.router,    prefix="/api", tags=["Apuestas"])
app.include_router(snapshots.router,   prefix="/api", tags=["Snapshots & Hitos"])
app.include_router(calibracion.router, prefix="/api", tags=["Calibración ML"])
app.include_router(scraper.router,     prefix="/api", tags=["Scraper Aposta.la"])
app.include_router(forebet_cruce.router, prefix="/api", tags=["Value Bets Forebet"])
app.include_router(cupones.router,     prefix="/api", tags=["Cupones Aposta.la"])


# ─── WebSocket ─────────────────────────────────────────────────────────────────
app.include_router(ws_router, tags=["WebSocket Live"])


# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["Health"])
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "2.0.0"}


# ─── Autenticación Web: Login / Logout ─────────────────────────────────────────
@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request):
    """Página de inicio de sesión estilizada para acceder a la consola web."""
    cookie_key = request.cookies.get("poliverso_api_key")
    if cookie_key and cookie_key == API_KEY:
        return RedirectResponse(url="/")

    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Acceso Seguro — Poliverso Predictor</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                background: radial-gradient(circle at 50% 20%, #1e1b4b 0%, #09090b 100%);
                font-family: 'Outfit', sans-serif;
                color: #f4f4f5;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 1.5rem;
            }
            .card {
                background: rgba(24, 24, 27, 0.85);
                backdrop-filter: blur(16px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 1.25rem;
                padding: 2.5rem;
                max-width: 440px;
                width: 100%;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5), 0 0 40px rgba(99, 102, 241, 0.15);
            }
            .logo { font-size: 2.5rem; text-align: center; margin-bottom: 0.5rem; }
            h1 { font-size: 1.5rem; font-weight: 700; text-align: center; color: #ffffff; margin-bottom: 0.5rem; }
            p { font-size: 0.95rem; color: #a1a1aa; text-align: center; margin-bottom: 2rem; line-height: 1.5; }
            .input-group { margin-bottom: 1.5rem; }
            label { display: block; font-size: 0.85rem; font-weight: 600; color: #d4d4d8; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.05em; }
            input {
                width: 100%;
                background: #09090b;
                border: 1px solid #3f3f46;
                border-radius: 0.75rem;
                padding: 0.85rem 1rem;
                color: #fff;
                font-size: 0.95rem;
                font-family: monospace;
                outline: none;
                transition: border-color 0.2s, box-shadow 0.2s;
            }
            input:focus { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25); }
            button {
                width: 100%;
                background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%);
                color: #ffffff;
                border: none;
                border-radius: 0.75rem;
                padding: 0.9rem;
                font-size: 1rem;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.1s, opacity 0.2s;
                box-shadow: 0 4px 14px rgba(79, 70, 229, 0.4);
            }
            button:hover { opacity: 0.95; }
            button:active { transform: scale(0.98); }
            .hint { margin-top: 1.5rem; text-align: center; font-size: 0.8rem; color: #71717a; }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="logo">🏀</div>
            <h1>Poliverso Predictor</h1>
            <p>Ingresa tu clave de acceso (API Key) para desbloquear la consola y el motor en vivo.</p>
            <form method="POST" action="/login">
                <div class="input-group">
                    <label for="api_key">API Key de Acceso</label>
                    <input type="password" id="api_key" name="api_key" required placeholder="poliverso_sec_..." autofocus autocomplete="off">
                </div>
                <button type="submit">Acceder al Sistema</button>
            </form>
            <div class="hint">Tu sesión se guardará en este navegador para que no tengas que ingresarla otra vez.</div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.post("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_action(api_key: str = Form(...)):
    """Procesa el formulario de login y establece la cookie si la clave es correcta."""
    if api_key.strip() == API_KEY:
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key="poliverso_api_key",
            value=api_key.strip(),
            max_age=60 * 60 * 24 * 365,
            httponly=False,
            samesite="lax",
        )
        return response

    error_html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Error de Acceso — Poliverso</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            body { background: #09090b; color: #fff; font-family: 'Outfit', sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; text-align: center; }
            .card { background: #18181b; padding: 2.5rem; border-radius: 1rem; border: 1px solid #ef4444; max-width: 400px; }
            h2 { color: #f87171; margin-bottom: 1rem; }
            p { color: #a1a1aa; margin-bottom: 1.5rem; }
            a { background: #374151; color: #fff; text-decoration: none; padding: 0.6rem 1.2rem; border-radius: 0.5rem; font-weight: 600; display: inline-block; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Clave Incorrecta</h2>
            <p>La API Key proporcionada no es válida para este servidor.</p>
            <a href="/login">← Volver a intentar</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=error_html, status_code=401)


@app.get("/logout", include_in_schema=False)
async def logout():
    """Cierra la sesión borrando la cookie."""
    response = RedirectResponse(url="/login")
    response.delete_cookie(key="poliverso_api_key")
    return response


# ─── Servir frontend React en producción ───────────────────────────────────────
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(request: Request, full_path: str):
        """Sirve el SPA React para cualquier ruta no capturada por la API."""
        if full_path.startswith("api") or full_path.startswith("ws"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Endpoint no encontrado")
        index_path = os.path.join(FRONTEND_DIST, "index.html")
        response = FileResponse(index_path)

        query_key = request.query_params.get("api_key") or request.query_params.get("key")
        if query_key and API_KEY and query_key == API_KEY:
            response.set_cookie(
                key="poliverso_api_key",
                value=query_key,
                max_age=60 * 60 * 24 * 365,
                httponly=False,
                samesite="lax",
            )
        return response

