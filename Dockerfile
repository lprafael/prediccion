# ─── Stage 1: Build Frontend React + Vite ─────────────────────────────────────
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install


COPY frontend/ ./
RUN npm run build

# ─── Stage 2: Runtime Backend Python + FastAPI ───────────────────────────────
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DB_HOST=db \
    DB_PORT=5432 \
    DB_NAME=prediccion_basket \
    DB_USER=postgres \
    DB_PASSWORD=admin123

# Instalar dependencias del sistema mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Actualizar pip e instalar dependencias Python
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt


# Copiar código fuente
COPY model/ /app/model/
COPY api/ /app/api/
COPY app.py /app/app.py

# Copiar bundle de producción generado en Stage 1
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

EXPOSE 8000 8501

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
