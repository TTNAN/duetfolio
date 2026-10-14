# Single-container image: builds the UI and serves it from the API process
# (same origin, no nginx needed). Used for one-click deploys (Render etc.)
# and handy for `docker run`. For the two-container setup see
# docker-compose.yml.
#
#   docker build -t duetfolio .
#   docker run -p 8000:8000 -v duetfolio-data:/data duetfolio
#   docker run -p 8000:8000 -e DEMO_MODE=true duetfolio   # read-only demo

FROM node:20-alpine AS ui
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/ ./
COPY --from=ui /ui/dist /app/frontend/dist

RUN useradd --system --uid 10001 --no-create-home duetfolio \
    && mkdir -p /data && chown -R duetfolio:duetfolio /data /app
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENV DATABASE_URL=sqlite:////data/duetfolio.db \
    BASE_CURRENCY=HKD \
    CORS_ORIGINS= \
    PORT=8000
VOLUME ["/data"]
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
# PORT is injected by most PaaS (Render, Railway, Zeabur)
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
