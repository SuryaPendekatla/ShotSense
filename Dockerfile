# One image serves the React app and the API on the same port.
# Works on Hugging Face Spaces (Docker SDK), Render, Railway or any container host.

# --- Build the frontend ---
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- Python runtime ---
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=7860

# Hugging Face Spaces runs containers as user 1000.
RUN useradd -m -u 1000 app
WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/model ./model
COPY --from=frontend /frontend/dist ./static
RUN mkdir -p /app/data && chown -R app:app /app
USER app

# SQLite fallback lives in /app/data; set DATABASE_URL to use PostgreSQL instead.
ENV DATABASE_URL=sqlite:////app/data/shotsense.db
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
