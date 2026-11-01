# Tareas de Migración FastAPI + React

## Fase 1 — Backend FastAPI
- [x] Leer archivos restantes (database.py completo, learning.py, live_betting.py)
- [x] `api/__init__.py`
- [x] `api/main.py` — Aplicación FastAPI, CORS, startup, static SPA serving
- [x] `api/schemas/partidos.py` — Pydantic models
- [x] `api/schemas/simulacion.py` — Schemas de Monte Carlo, trayectorias, baselines
- [x] `api/schemas/apuestas.py` — Schemas de apuestas, EV, Kelly y métricas
- [x] `api/routers/torneos.py` — Presets de torneos (NBA, FIBA, NBL, NCAA)
- [x] `api/routers/partidos.py` — CRUD y finalización de partidos
- [x] `api/routers/simulacion.py` — POST /api/simular y GET /api/baseline
- [x] `api/routers/apuestas.py` — CRUD apuestas, métricas y recomendaciones
- [x] `api/routers/snapshots.py` — Snapshots e hitos de predicción
- [x] `api/routers/calibracion.py` — Platt Scaling y auto-entrenamiento ML
- [x] `api/websocket/manager.py` — ConnectionManager para broadcasting en tiempo real
- [x] `api/ws_live.py` — Canal WebSocket `/ws/live/{partido_id}`
- [x] Actualizar `requirements.txt` con fastapi, pydantic, httpx
- [x] Verificación de import y registro de rutas operativas

## Fase 2 — Frontend React + Vite
- [x] Inicializar proyecto Vite + React + TypeScript en `frontend/`
- [x] Configurar Lucide Icons, tipografía Outfit/JetBrains Mono y diseño cyber-sports
- [x] `src/api/client.ts` — Fetch REST client completo
- [x] `src/api/websocket.ts` — Hook `useLiveMatchSocket` con auto-reconexión
- [x] `src/utils/audio.ts` — Generador de alertas sonoras nativo (Web Audio API)
- [x] `src/components/Navbar.tsx` — Navegación, selector de pestañas, mute y badge de estado WS
- [x] `src/components/ScoreBoard.tsx` — Marcador dinámico en vivo LED y reloj digital
- [x] `src/components/QuarterInput.tsx` — Edición interactiva por cuarto con botones rápidos +1/+2/+3
- [x] `src/components/MonteCarloChart.tsx` — Histograma de proyección sobre Canvas con línea de apuesta
- [x] `src/components/TimelineChart.tsx` — Trayectoria minuto a minuto con bandas de confianza
- [x] `src/components/LiveBettingPanel.tsx` — Calculadora Over/Under, EV, cuotas justas y Criterio de Kelly
- [x] `src/components/SnapshotTable.tsx` — Registro y auditoría de hitos de predicción
- [x] `src/pages/Dashboard.tsx` — Vista de partidos activos y filtros
- [x] `src/pages/NuevoPartido.tsx` — Creación de partido con parámetros reglamentarios
- [x] `src/pages/PartidoLive.tsx` — Mesa de control y predicción en vivo
- [x] `src/pages/Apuestas.tsx` — Registro, P&L, ROI y liquidación
- [x] `src/pages/Calibracion.tsx` — Supervisión Platt Scaling y auto-entrenamiento ML
- [x] `src/App.tsx` + orquestación
- [x] Compilación y verificación de build de producción con `npm run build` (0 errores)

## Fase 3 — Integración y verificación
- [x] Validar endpoints REST con suite automatizada TestClient (8/8 endpoints 200 OK)
- [x] Servir el frontend compilado directamente desde FastAPI
- [x] Verificar coexistencia con Streamlit (`app.py` intacto como fallback)

## Dockerización
- [x] Crear `Dockerfile` multi-stage (Node 22 para build de React + Python 3.12 para FastAPI)
- [x] Crear `docker-compose.yml` con PostgreSQL 16, FastAPI + React y Streamlit opcional
- [x] Construir imagen `prediccion-app` con `docker compose build`
- [x] Levantar contenedores con `docker compose up -d`
- [x] Verificar funcionamiento de PostgreSQL (`poliverso_db`) y FastAPI/React (`poliverso_web`) en `http://localhost:8000`

## Integración y Automatización Aposta.la
- [x] Endpoint `POST /api/scraper/extraer` para consulta en vivo de Kambi CDN
- [x] Endpoint `POST /api/partidos/crear-desde-aposta` para creación en 1-clic
- [x] Endpoint `POST /api/partidos/{partido_id}/sync-aposta` con emisión WebSocket
- [x] Card de Importación Rápida 1-Clic en el Dashboard principal (`Dashboard.tsx`)
- [x] Módulo de Importación y Pre-llenado en `NuevoPartido.tsx`
- [x] Barra de Sincronización en Vivo y Auto-Sync periódico (10s/15s/30s/60s) en `PartidoLive.tsx`
- [x] Ejecución desacoplada en ThreadPool para no interferir con el bucle de eventos asyncio

## Motor de Cruce Forebet vs Aposta.la (+EV Value Betting)
- [x] Extractor Headless Playwright para Forebet (`model/forebet_cruce.py`)
- [x] Integración de cuotas pre-partido y en vivo de Aposta.la (Kambi Sportsbook API)
- [x] Motor matemático de Expected Value (+EV), Edge, Probabilidad Implícita y Criterio de Kelly (1/4)
- [x] Endpoints REST `GET /api/forebet-cruce`, `POST /api/forebet-cruce/escanear` y `GET /api/forebet-cruce/status`
- [x] Caché inteligente en PostgreSQL (`forebet_cache`) y persistencia
- [x] Interfaz de usuario completa `ForebetValueBets.tsx` con filtros por liga, búsqueda por equipo y selector de retorno mínimo
- [x] Pestaña de navegación en Navbar con badge dinámico `+EV` y compilación de producción validada
- [x] Script `sync_forebet.py` para sincronización residencial hacia el servidor VPS

## Despliegue en Servidor VPS (187.77.247.23)
- [x] Código sincronizado en `/root/prediccion`
- [x] Contenedores Docker levantados y saludables (`poliverso_web` en puerto 8000, `poliverso_db` en 5438)
- [x] Salud del sistema verificada internamente con `curl http://localhost:8000/api/health`
- [x] Base de datos remota poblada con partidos cruzados y cuotas en vivo de Aposta.la

## Integración de FlareSolverr (Bypass Automático Cloudflare en VPS)
- [x] Agregar servicio `flaresolverr` (`ghcr.io/flaresolverr/flaresolverr:latest`) al `docker-compose.yml`
- [x] Configurar variable de entorno `FLARESOLVERR_URL: http://flaresolverr:8191/v1`
- [x] Añadir parser HTML estructurado con BeautifulSoup en `model/forebet_cruce.py`
- [x] Conectar llamada automática a FlareSolverr para eludir Cloudflare de forma nativa en el VPS
- [x] Añadir fallback Playwright Stealth con banderas de evasión (`--disable-blink-features=AutomationControlled`, eliminación de `navigator.webdriver`)
- [x] Actualizar `requirements.txt` con `beautifulsoup4`
- [x] Añadir soporte de bucle/intervalo `--interval` en `sync_forebet.py`
