# SEACE MONITOR

Plataforma full-stack para monitoreo de contrataciones publicas en SEACE, con scraping, lote por nomenclaturas, seguimiento y analisis asistido por IA (con fallback local).

## Estado rapido
- Backend: Flask + Playwright
- Frontend: React + Vite
- Transporte: REST + SSE
- Planificacion: estructura GTD en `gtd/`
- Continuidad multi-agente: guias en `docs/runbooks/`

## Estructura del proyecto
```text
backend/                 API y scraping
frontend/                App React
scripts/                 Automatizaciones de entorno local
docs/
  architecture/          Mapa tecnico
  handoff/               Handoffs historicos
  runbooks/              Guias operativas
gtd/                     Sistema Get Things Done del proyecto
logs/                    Logs locales de ejecucion (no versionar)
```

## Requisitos
- Python 3.10+
- Node.js 18+
- npm

## Setup inicial (Windows PowerShell)
```powershell
python setup.py
cd frontend
npm install
cd ..
```

## Arranque rapido
Terminal 1:
```powershell
.\.venv\Scripts\python.exe backend\server.py
```

Terminal 2:
```powershell
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

## Salud del sistema
```powershell
Invoke-WebRequest -Uri "http://localhost:8080/api/health" -UseBasicParsing
Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing
```

## API principal
- `POST /api/search`
- `POST /api/cronograma`
- `POST /api/batch`
- `GET /api/batch/status`
- `POST /api/analyze`
- `GET /api/logs`
- `GET /api/health`

Nota: `POST /api/mock-data` esta deshabilitado intencionalmente (`410`).

## Flujo de trabajo GTD
1. Captura en `gtd/00_INBOX.md`
2. Planifica en `gtd/10_NEXT_ACTIONS.md`
3. Ejecuta en `gtd/20_IN_PROGRESS.md`
4. Registra bloqueos en `gtd/30_BLOCKED.md`
5. Cierra en `gtd/40_DONE.md`
6. Historico de bugs en `gtd/50_BUG_HISTORY.md`
7. Decisiones en `gtd/60_DECISIONS.md`

## Git recomendado (primera vez)
```powershell
git init -b main
git add .
git commit -m "chore: bootstrap proyecto y estructura gtd"
```

## Documentacion clave para agentes
- `docs/runbooks/START_HERE.md`
- `docs/runbooks/AGENT_WORKFLOW.md`
- `docs/architecture/PROJECT_MAP.md`
- `docs/handoff/PROJECT_HANDOFF_2026-04-24.md`

