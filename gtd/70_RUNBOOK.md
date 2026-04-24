# Runbook Operativo

## Arranque

### Backend
```powershell
.\.venv\Scripts\python.exe backend/server.py
```

### Frontend
```powershell
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

## Verificaciones rapidas
```powershell
Invoke-WebRequest -Uri 'http://localhost:8080/api/health' -UseBasicParsing
Invoke-WebRequest -Uri 'http://localhost:5173' -UseBasicParsing
```

## Smoke de API
1. `POST /api/search`
2. `POST /api/analyze`
3. `POST /api/batch`
4. `GET /api/batch/status`

## Diagnostico
- Logs backend:
  - `logs/backend/backend_live.err.log`
  - `logs/backend/backend_diag.err.log`
  - `logs/backend/backend_test.err.log`
- Si `npm run dev` lanza `spawn EPERM`, correr con permisos no restringidos.
- Si falla `analyze`, verificar `ANTHROPIC_API_KEY` (si no existe, usar fallback local).
