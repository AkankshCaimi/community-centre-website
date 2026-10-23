# The website in one image: Flask serves the built React application and the API.
# Spec: docs/specs/deploy.md (M1 to M5).

# --- Stage 1: build the frontend
FROM node:24-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build && test -f dist/index.html

# --- Stage 2: the application
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIST=/app/frontend/dist

WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/gunicorn.conf.py ./
COPY backend/app ./app
COPY backend/db ./db
COPY --from=frontend /build/dist /app/frontend/dist

# The build fails here if the frontend or the London time zone is missing (M5).
RUN test -f /app/frontend/dist/index.html \
    && python -c "from zoneinfo import ZoneInfo; ZoneInfo('Europe/London')"

RUN useradd --system --no-create-home --uid 10001 app
USER 10001

EXPOSE 8000
# No access log: a visitor's network address must not reach the log (M3).
# No control socket: nothing manages gunicorn from inside the container.
# The address comes from gunicorn.conf.py: 0.0.0.0 on PORT, 8000 by default (deploy-free P1, P4).
CMD ["gunicorn", "--config", "gunicorn.conf.py", "--workers", "2", "--no-control-socket", "app:create_app()"]
