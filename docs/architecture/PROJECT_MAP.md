# Project Map

## Backend
- `backend/server.py`
  - API Flask
  - Orquestacion de scraping
  - SSE de logs
  - Batch en thread separado
- `backend/scraper.py`
  - Navegacion Playwright contra SEACE
  - Extraccion de resultados
  - Extraccion de cronograma y fallback OCR

## Frontend
- `frontend/src/App.jsx`
  - Tabs: Busqueda, Seguimiento, Lote, Analisis
  - Polling de `api/health`
  - Stream SSE de `api/logs`
  - Persistencia local de seguimiento
- `frontend/src/styles.css`
  - Tema visual y layout

## Operacion
- `scripts/bootstrap.ps1`: instala dependencias base
- `scripts/check_health.ps1`: valida backend/frontend
- `scripts/dev_up.ps1`: guia automatizada de arranque

