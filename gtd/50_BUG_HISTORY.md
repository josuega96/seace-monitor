# Historial de Bugs

## 2026-04-24

### BUG-001: `ModuleNotFoundError: No module named 'flask'`
- Evidencia: `backend_test.err.log`.
- Causa probable: entorno Python sin dependencias instaladas.
- Estado: resuelto en entorno actual.
- Prevencion: ejecutar `python setup.py` en onboarding.

### BUG-002: `POST /api/search` devolviendo `500` intermitente
- Evidencia: `backend_diag.err.log` y `backend_live.err.log` (21-Apr-2026).
- Causa probable: inestabilidad externa de scraping (DOM/captcha/cambios SEACE).
- Estado: actualmente responde `200` en pruebas recientes.
- Prevencion: reforzar retries, timeouts y observabilidad por etapa.

### BUG-003: `POST /api/analyze` devolviendo `500` (corridas previas)
- Evidencia: `backend_live.err.log` (21-Apr-2026 10:58:43).
- Estado actual: resuelto por fallback local en ausencia de `ANTHROPIC_API_KEY`.
- Prevencion: validar key al arranque y advertencia temprana en frontend.

### BUG-004: `npm run dev` con `Error: spawn EPERM` en entorno restringido
- Evidencia: corrida local del 2026-04-24.
- Estado: resuelto al ejecutar frontend fuera del sandbox.
- Prevencion: documentar requisito de permisos para Vite/esbuild.
