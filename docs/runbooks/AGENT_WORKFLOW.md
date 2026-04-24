# Agent Workflow

## Objetivo
Permitir continuidad sin perdida de contexto entre agentes.

## Protocolo de ejecucion
1. Selecciona una sola tarea activa en `gtd/20_IN_PROGRESS.md`.
2. Define criterio de cierre claro.
3. Implementa cambios pequenos y verificables.
4. Ejecuta validaciones minimas.
5. Registra resultados y riesgos.

## Reglas de handoff
- Si tocas arquitectura, actualiza `docs/architecture/PROJECT_MAP.md`.
- Si corriges un bug, agrega entrada en `gtd/50_BUG_HISTORY.md`.
- Si tomas una decision con tradeoff, registrala en `gtd/60_DECISIONS.md`.
- Si cambias comandos de arranque, actualiza `README.md` y `gtd/70_RUNBOOK.md`.

## Definition of Done
- Codigo funcional validado localmente.
- Documentacion minima actualizada.
- Estado de tarea reflejado en GTD.
- Sin secretos o artefactos locales comiteados.

