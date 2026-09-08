# Cranmore Carpenters QA — Base44 Dev Environment

## Stack
- **Backend**: FastAPI + MongoDB (motor). Single `server.py` (~1200 lines). Uvicorn with `--reload` on port 8001.
- **Frontend**: React 19 + CRA (craco) + Tailwind + shadcn/ui. Yarn 1.x. Dev server on port 3000.
- **Database**: MongoDB 7 in compose. DB name `cranmore_qa`.

## Running
```bash
docker compose -f docker-compose.base44.yml up -d
```
- Frontend: http://localhost:3000 (preview port)
- Backend API: http://localhost:8001/api

## Key details
- **Seed data**: `seed_data.py` runs on FastAPI startup. Creates admin user (`factory@maxxdoors.com.au` / `Cranmore2026!`), 5 companies, 1 project (Summerset Oakleigh South), templates, locations, ~137 documents from `backend/data/summerset/`. Seeded documents are served from local files (not external storage).
- **Auth**: JWT in httpOnly cookies (`Secure; SameSite=None`). CORS allows the frontend public URL via `FRONTEND_URL` env var. Bearer token fallback also supported.
- **External storage**: `EMERGENT_LLM_KEY` is needed for photo/attachment uploads (Emergent object storage proxy). Storage init is caught in try/except — the app boots and seeded documents work without it, but new file uploads will fail until the key is set.
- **emergentintegrations** PyPI package is excluded from the backend Dockerfile (private package, not imported by the app).
- **craco.config.js** modified: added `allowedHosts: "all"` to `makeDevServerV5Compatible` so the preview proxy host is accepted.

## Env vars
- Backend: `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `FRONTEND_URL`, `CORS_ORIGINS`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `EMERGENT_LLM_KEY` (optional)
- Frontend: `REACT_APP_BACKEND_URL` (baked at dev-server start), `HOST=0.0.0.0`, `PORT=3000`

## Test credentials
- Admin: `factory@maxxdoors.com.au` / `Cranmore2026!`
- Trade (plumbing): `plumbing@maxxdoors.com.au` / `Cranmore2026!`
