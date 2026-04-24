# Handoff del Proyecto SEACE Monitor (2026-04-24)

## 1) Estado actual verificado
- Backend levantado y saludable en `http://localhost:8080` (`/api/health` responde `200`).
- Frontend levantado y accesible en `http://localhost:5173` (`200`).
- Flujo de busqueda real contra SEACE validado con `POST /api/search` (`200`, devolviendo items reales).
- Flujo de analisis IA validado con fallback local (`POST /api/analyze` responde `200` con `model=local-fallback` si falta `ANTHROPIC_API_KEY`).
- Flujo batch validado (`POST /api/batch` inicia proceso y `/api/batch/status` reporta avance/finalizacion).

## 2) Hallazgos de repositorio
- No existe carpeta `.git` en este workspace.
- Impacto: no se puede reconstruir historial de bugs por commits/tags/PRs.
- Se reconstruyo historial tecnico desde logs y comportamiento actual.

## 3) Historial de bugs/incidentes (evidencia local)

### 3.1 Dependencias Python no instaladas (resuelto)
- Evidencia: `backend_test.err.log` muestra `ModuleNotFoundError: No module named 'flask'`.
- Estado actual: resuelto en entorno actual (backend operativo).
- Leccion: usar `python setup.py` antes de correr backend en entornos nuevos.

### 3.2 Errores intermitentes en `/api/search` (parcialmente resuelto)
- Evidencia:
  - `backend_diag.err.log` muestra `POST /api/search` con `500` (21-Apr-2026).
  - `backend_live.err.log` mezcla respuestas `200` y algunos `500`.
- Estado actual: `POST /api/search` probado hoy y responde `200` con datos reales.
- Riesgo residual: por dependencia de cambios de DOM/flujo SEACE o bloqueos externos.

### 3.3 Error en analisis IA cuando Anthropic no estaba disponible (resuelto con fallback)
- Evidencia: `backend_live.err.log` registra `POST /api/analyze` con `500` en corrida previa.
- Estado actual: endpoint devuelve `200` usando fallback local (`model: local-fallback`) cuando falta `ANTHROPIC_API_KEY`.
- Implementacion observada: `api_analyze()` captura excepcion y responde analisis local.

### 3.4 Frontend Vite fallando por `spawn EPERM` en entorno sandbox (resuelto operativo)
- Evidencia de ejecucion local: `npm run dev` daba `Error: spawn EPERM`.
- Estado actual: frontend levanta correctamente al correr fuera del sandbox/restriccion.
- Nota operativa: si reaparece, ejecutar con permisos no restringidos.

## 4) Arquitectura funcional actual
- Backend Flask:
  - `POST /api/search`
  - `POST /api/cronograma`
  - `POST /api/batch`
  - `GET /api/batch/status`
  - `POST /api/analyze`
  - `POST /api/mock-data` (deshabilitado intencionalmente, responde `410`)
  - `GET /api/logs` (SSE)
  - `GET /api/health`
- Scraper Playwright en `backend/scraper.py` con soporte de:
  - busqueda multi criterio
  - extraccion de `accion_refs`
  - extraccion de cronograma (tabla y ruta OCR fallback)
- Frontend React:
  - tabs: Busqueda, Seguimiento, Lote Excel, Analisis IA
  - SSE de logs
  - tracking persistente en `localStorage`
  - carga de cronograma por item

## 5) Riesgos y pendientes tecnicos
- `api/cronograma` puede tardar bastante o expirar en ejecucion larga (dependencia del sitio externo).
- Falta metadata Git para auditoria historica de cambios.
- Proyecto contiene `frontend/node_modules` y `frontend/dist` versionados en workspace local (vigilar limpieza si luego se migra a Git).

## 6) Runbook rapido (para cualquier agente)
1. Backend:
   - `.\.venv\Scripts\python.exe backend/server.py`
2. Frontend:
   - `cd frontend`
   - `npm run dev -- --host 0.0.0.0 --port 5173`
3. Health checks:
   - `GET http://localhost:8080/api/health`
   - `GET http://localhost:5173`
4. Test funcional minimo:
   - `POST /api/search` con `searches:[{descripcion:'SERVICIO DE LIMPIEZA'}]`
   - `POST /api/analyze` con item dummy
   - `POST /api/batch` con 1 nomenclatura y revisar `/api/batch/status`

## 7) Convenciones para continuidad
- Usar carpeta `gtd/` como fuente de verdad operativa diaria.
- Registrar cada bug nuevo en `gtd/50_BUG_HISTORY.md`.
- Registrar decisiones en `gtd/60_DECISIONS.md`.
- Mover tareas cerradas a `gtd/40_DONE.md` con fecha.

## 8) Proxima accion recomendada
- Ejecutar una pasada de endurecimiento de `api/cronograma` (timeouts, reintentos parametrizables, telemetria de etapa fallida) y pruebas automatizadas smoke para `/api/search`, `/api/analyze`, `/api/batch`.
