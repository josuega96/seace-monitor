# Decision Log

## 2026-04-24

### DEC-001: Mantener `api/mock-data` deshabilitado
- Contexto: endpoint responde `410` por diseno actual.
- Decision: conservar modo "solo datos reales de SEACE".
- Impacto: mayor integridad de resultados; menor resiliencia offline.

### DEC-002: Aceptar fallback local en analisis IA
- Contexto: `ANTHROPIC_API_KEY` puede faltar en entornos dev.
- Decision: retornar analisis local en vez de fallar.
- Impacto: continuidad operativa; menor calidad analitica que modelo remoto.

### DEC-003: GTD como sistema oficial de continuidad
- Contexto: ausencia de metadata Git e historial distribuido.
- Decision: centralizar operacion diaria en `gtd/`.
- Impacto: menor dependencia de memoria individual.
