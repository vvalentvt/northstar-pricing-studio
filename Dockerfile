# Production image: FastAPI serves both the JSON API and the built
# React SPA from one process (see docs/DEPLOYMENT.md). Development
# keeps using `npm run dev` (Vite + a separate uvicorn process) and
# does not use this file.

FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY src/ ./src/
COPY config/ ./config/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

ENV NORTHSTAR_ENV=production \
    NORTHSTAR_DB_PATH=/data/northstar.db \
    PORT=8000

EXPOSE 8000

# $PORT is honored at container start (not baked in), matching how
# most hosting platforms assign a port. NORTHSTAR_DB_PATH should point
# at a mounted volume -- see docs/DEPLOYMENT.md for why container-local
# storage does not survive a redeploy.
CMD ["sh", "-c", "python -m uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
