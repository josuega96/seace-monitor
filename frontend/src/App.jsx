import { Fragment, useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8080";

const ESTADO_COLORS = {
  Convocado: "badge-blue",
  Consentido: "badge-green",
  Otorgado: "badge-green",
  Desierto: "badge-red",
  Cancelado: "badge-red",
  EnCurso: "badge-amber",
  "En curso": "badge-amber",
};

const TABS = ["BÃšSQUEDA", "SEGUIMIENTO", "LOTE EXCEL", "ANÃLISIS IA"];

const TIPOS = [
  "",
  "LicitaciÃ³n PÃºblica",
  "Concurso PÃºblico",
  "AdjudicaciÃ³n Simplificada",
  "Subasta Inversa",
  "ComparaciÃ³n de Precios",
];

const OBJETOS = ["", "Bienes", "Servicios", "Obras", "ConsultorÃ­a de Obra"];

const REGIONES = [
  "Amazonas",
  "Ancash",
  "Apurimac",
  "Arequipa",
  "Ayacucho",
  "Cajamarca",
  "Callao",
  "Cusco",
  "Huancavelica",
  "Huanuco",
  "Ica",
  "Junin",
  "La Libertad",
  "Lambayeque",
  "Lima",
  "Loreto",
  "Madre de Dios",
  "Moquegua",
  "Pasco",
  "Piura",
  "Puno",
  "San Martin",
  "Tacna",
  "Tumbes",
  "Ucayali",
];

const YEARS = (() => {
  const current = new Date().getFullYear();
  return ["", ...Array.from({ length: 8 }, (_, i) => String(current - i))];
})();

const TRACKING_STORAGE_KEY = "seace_tracking_items_v1";

function formatDate() {
  return new Date().toLocaleDateString("es-PE", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function statusBadgeClass(estado) {
  return ESTADO_COLORS[estado] || "badge-blue";
}

function parseCsvFirstColumn(text) {
  const lines = text
    .split(/\r?\n/)
    .map((v) => v.trim())
    .filter(Boolean);
  const rows = [];
  for (const line of lines) {
    const parts = line.split(/[;,]/).map((v) => v.trim());
    if (parts[0]) rows.push(parts[0]);
  }
  return [...new Set(rows)];
}

function trackingId(item) {
  return `${item.nomenclatura || ""}::${item.entidad || ""}::${item.descripcion || ""}`;
}

export default function App() {
  const [tab, setTab] = useState("BÃšSQUEDA");
  const [backendOk, setBackendOk] = useState(false);
  const [headless, setHeadless] = useState(true);
  const [logs, setLogs] = useState([]);
  const [searching, setSearching] = useState(false);
  const [expanded, setExpanded] = useState({});
  const [searchError, setSearchError] = useState("");
  const [filters, setFilters] = useState({
    entidad: "",
    tipo: "",
    objeto: "ConsultorÃ­a de Obra",
    regiones: [],
    anio: "",
    max_pages: 3,
  });
  const [results, setResults] = useState([]);
  const [batchItems, setBatchItems] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [batchStatus, setBatchStatus] = useState({
    running: false,
    progress: 0,
    total: 0,
    results: [],
  });
  const [selectedItem, setSelectedItem] = useState(null);
  const [analysis, setAnalysis] = useState("");
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState("");
  const [trackingItems, setTrackingItems] = useState([]);
  const [searchQueries, setSearchQueries] = useState([]);
  const [queryDescripcion, setQueryDescripcion] = useState("");
  const [queryRegiones, setQueryRegiones] = useState([]);

  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/health`);
        setBackendOk(res.ok);
      } catch (_) {
        setBackendOk(false);
      }
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = window.localStorage.getItem(TRACKING_STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      setTrackingItems(Array.isArray(parsed) ? parsed : []);
    } catch (_) {
      setTrackingItems([]);
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const onStorage = (ev) => {
      if (ev.key !== TRACKING_STORAGE_KEY) return;
      try {
        const parsed = ev.newValue ? JSON.parse(ev.newValue) : [];
        setTrackingItems(Array.isArray(parsed) ? parsed : []);
      } catch (_) {}
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  useEffect(() => {
    const es = new EventSource(`${API_BASE}/api/logs`);
    es.onmessage = (ev) => {
      try {
        const item = JSON.parse(ev.data);
        setLogs((prev) => [...prev.slice(-249), item]);
      } catch (_) {}
    };
    es.onerror = () => {};
    return () => es.close();
  }, []);

  useEffect(() => {
    if (!batchStatus.running) return;
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/batch/status`);
        const data = await res.json();
        setBatchStatus(data);
      } catch (_) {}
    }, 1500);
    return () => clearInterval(timer);
  }, [batchStatus.running]);

  async function runSearch(e) {
    e.preventDefault();
    if (!searchQueries.length) {
      setSearchError("Agrega al menos una bÃºsqueda compuesta para ejecutar la consulta.");
      return;
    }
    setSearching(true);
    setSearchError("");
    setResults([]);
    setExpanded({});
    try {
      const payload = { ...filters, headless };
      payload.searches = searchQueries.map((q) => ({
        descripcion: q.descripcion,
        regiones: q.regiones,
      }));
      payload.include_cronograma = false;
      const res = await fetch(`${API_BASE}/api/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Error en bÃºsqueda");
      setResults(Array.isArray(data) ? data : []);
    } catch (err) {
      setSearchError(err.message || "No se pudo completar la bÃºsqueda");
    } finally {
      setSearching(false);
    }
  }

  async function startBatch() {
    if (!batchItems.length) return;
    try {
      const res = await fetch(`${API_BASE}/api/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nomenclaturas: batchItems, headless }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "No se pudo iniciar lote");
      setBatchStatus({ running: true, progress: 0, total: batchItems.length, results: [] });
    } catch (err) {
      setSearchError(err.message || "Error de lote");
    }
  }

  async function analyzeItem(item) {
    setSelectedItem(item);
    setTab("ANÃLISIS IA");
    setAnalysisLoading(true);
    setAnalysisError("");
    setAnalysis("");
    try {
      const res = await fetch(`${API_BASE}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "No se pudo analizar");
      setAnalysis(data.analysis || "");
    } catch (err) {
      setAnalysisError(err.message || "Error en anÃ¡lisis IA");
    } finally {
      setAnalysisLoading(false);
    }
  }

  function addRegion(region) {
    if (!region) return;
    setFilters((prev) => {
      if (prev.regiones.includes(region)) return prev;
      return { ...prev, regiones: [...prev.regiones, region] };
    });
  }

  function removeRegion(region) {
    setFilters((prev) => ({ ...prev, regiones: prev.regiones.filter((r) => r !== region) }));
  }

  function addQueryRegion(region) {
    if (!region) return;
    setQueryRegiones((prev) => (prev.includes(region) ? prev : [...prev, region]));
  }

  function removeQueryRegion(region) {
    setQueryRegiones((prev) => prev.filter((r) => r !== region));
  }

  function addSearchQuery() {
    const descripcion = queryDescripcion.trim();
    if (!descripcion) return;
    setSearchQueries((prev) => [...prev, { descripcion, regiones: queryRegiones }]);
    setQueryDescripcion("");
    setQueryRegiones([]);
  }

  function removeSearchQuery(index) {
    setSearchQueries((prev) => prev.filter((_, i) => i !== index));
  }

  function addToTracking(item) {
    setTrackingItems((prev) => {
      const id = trackingId(item);
      if (prev.some((x) => trackingId(x) === id)) return prev;
      const next = [
        {
          ...item,
          cronograma: item.cronograma || [],
          cronograma_loaded: Array.isArray(item.cronograma) && item.cronograma.length > 0,
          cronograma_loading: false,
          cronograma_error: "",
          cronograma_trace: [],
          saved_at: new Date().toISOString(),
        },
        ...prev,
      ];
      if (typeof window !== "undefined") {
        window.localStorage.setItem(TRACKING_STORAGE_KEY, JSON.stringify(next));
      }
      return next;
    });
    fetchCronogramaForTrackingItem(item);
  }

  function removeFromTracking(item) {
    const id = trackingId(item);
    setTrackingItems((prev) => {
      const next = prev.filter((x) => trackingId(x) !== id);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(TRACKING_STORAGE_KEY, JSON.stringify(next));
      }
      return next;
    });
  }

  async function fetchCronogramaForTrackingItem(item) {
    const id = trackingId(item);
    setTrackingItems((prev) => {
      const next = prev.map((x) =>
        trackingId(x) === id ? { ...x, cronograma_loading: true, cronograma_error: "" } : x,
      );
      if (typeof window !== "undefined") {
        window.localStorage.setItem(TRACKING_STORAGE_KEY, JSON.stringify(next));
      }
      return next;
    });

    try {
      const payload = {
        item,
        entidad: "",
        anio: filters.anio || "",
        tipo: "",
        objeto: filters.objeto || "",
        max_pages: 3,
        headless,
      };
      const res = await fetch(`${API_BASE}/api/cronograma`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || !data || data.ok !== true) {
        const err = new Error(data?.error || "No se pudo cargar cronograma");
        err.trace = Array.isArray(data?.trace) ? data.trace : [];
        throw err;
      }
      const schedule = Array.isArray(data.cronograma) ? data.cronograma : [];
      const trace = Array.isArray(data.trace) ? data.trace : [];
      setTrackingItems((prev) => {
        const next = prev.map((x) =>
          trackingId(x) === id
            ? {
                ...x,
                cronograma: schedule,
                cronograma_loaded: true,
                cronograma_loading: false,
                cronograma_trace: trace,
                cronograma_error: schedule.length ? "" : "No se encontraron etapas de cronograma.",
              }
            : x,
        );
        if (typeof window !== "undefined") {
          window.localStorage.setItem(TRACKING_STORAGE_KEY, JSON.stringify(next));
        }
        return next;
      });
    } catch (err) {
      setTrackingItems((prev) => {
        const next = prev.map((x) =>
          trackingId(x) === id
            ? {
                ...x,
                cronograma_loading: false,
                cronograma_loaded: true,
                cronograma_trace: Array.isArray(err?.trace) ? err.trace : [],
                cronograma_error: err?.message || "No se pudo cargar el cronograma.",
              }
            : x,
        );
        if (typeof window !== "undefined") {
          window.localStorage.setItem(TRACKING_STORAGE_KEY, JSON.stringify(next));
        }
        return next;
      });
    }
  }

  function onDropFile(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result || "");
      setBatchItems(parseCsvFirstColumn(text));
    };
    reader.readAsText(file);
  }

  const logCounters = useMemo(() => {
    const counters = { info: 0, warn: 0, error: 0, success: 0, sync: 0 };
    for (const l of logs) counters[l.type] = (counters[l.type] || 0) + 1;
    return counters;
  }, [logs]);

  const progressPct =
    batchStatus.total > 0 ? Math.round((batchStatus.progress / batchStatus.total) * 100) : 0;
  const trackingIds = useMemo(() => new Set(trackingItems.map((x) => trackingId(x))), [trackingItems]);
  const isMonitorWindow =
    typeof window !== "undefined" && window.location.pathname.toLowerCase() === "/monitor";
  const isTrackingWindow =
    typeof window !== "undefined" && window.location.pathname.toLowerCase() === "/seguimiento";

  function openMonitorWindow() {
    if (typeof window === "undefined") return;
    window.open(
      `${window.location.origin}/monitor`,
      "seace-monitor-live",
      "width=520,height=800,resizable=yes,scrollbars=yes",
    );
  }

  function openTrackingWindow() {
    if (typeof window === "undefined") return;
    window.open(
      `${window.location.origin}/seguimiento`,
      "seace-monitor-tracking",
      "width=980,height=800,resizable=yes,scrollbars=yes",
    );
  }

  if (isMonitorWindow) {
    return (
      <div className="app-root monitor-page">
        <aside className="sidebar monitor-detached">
          <h3>Monitor en tiempo real</h3>
          <div className="logs">
            {logs.slice().reverse().map((log, idx) => (
              <div key={`${log.time}-${idx}`} className={`log-line log-${log.type}`}>
                <span>[{log.time}]</span> {log.message}
              </div>
            ))}
          </div>
          <div className="log-counters">
            <span>info: {logCounters.info || 0}</span>
            <span>warn: {logCounters.warn || 0}</span>
            <span>error: {logCounters.error || 0}</span>
            <span>success: {logCounters.success || 0}</span>
            <span>sync: {logCounters.sync || 0}</span>
          </div>
        </aside>
      </div>
    );
  }

  if (isTrackingWindow) {
    return (
      <div className="app-root">
        <section className="card">
          <h3>Seguimiento de Contratos</h3>
          <p className="muted">Contratos marcados como "Me interesa".</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>DescripciÃƒÂ³n / Nomenclatura</th>
                  <th>Entidad</th>
                  <th>Tipo</th>
                  <th>VR / VE / CuantÃƒÂ­a</th>
                  <th>Fecha</th>
                  <th>AcciÃƒÂ³n</th>
                </tr>
              </thead>
              <tbody>
                {trackingItems.map((row, i) => (
                  <tr key={`${trackingId(row)}-${i}`}>
                    <td>
                      <div className="row-title">{row.descripcion || "-"}</div>
                      <div className="muted">{row.nomenclatura || "-"}</div>
                      {row.cronograma_loading && <p className="muted">Cargando cronograma...</p>}
                      {!!row.cronograma_error && <p className="warn-text">{row.cronograma_error}</p>}
                      {!!row.cronograma_loaded && !row.cronograma?.length && !row.cronograma_error && (
                        <p className="muted">Cronograma cargado sin etapas visibles.</p>
                      )}
                      {!!row.cronograma?.length && (
                        <div className="schedule-block">
                          <strong>Cronograma:</strong>
                          <ul>
                            {row.cronograma.map((c, idx) => (
                              <li key={`${c.etapa}-${idx}`}>
                                {c.etapa} | Inicio: {c.fecha_inicio || "-"} | Fin: {c.fecha_fin || "-"}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {!!row.cronograma_trace?.length && (
                        <div className="trace-block">
                          <strong>Trazabilidad:</strong>
                          <ul>
                            {row.cronograma_trace.map((t, idx) => (
                              <li key={`trace-${idx}`}>{t}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </td>
                    <td>{row.entidad || "-"}</td>
                    <td>{row.tipo || "-"}</td>
                    <td className="money">{row.monto_referencial || "-"}</td>
                    <td>{row.fecha_convocatoria || "-"}</td>
                    <td>
                      <div className="action-stack">
                        <button
                          className="btn-secondary"
                          disabled={row.cronograma_loading}
                          onClick={() => fetchCronogramaForTrackingItem(row)}
                        >
                          {row.cronograma_loading ? "Cargando..." : "Cargar cronograma"}
                        </button>
                        <button className="btn-danger" onClick={() => removeFromTracking(row)}>
                          Quitar
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {!trackingItems.length && (
                  <tr>
                    <td colSpan={6} className="muted">
                      AÃƒÂºn no tienes contratos en seguimiento.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="app-root">
      <header className="topbar">
        <div>
          <h1>MONITOR - SEACE</h1>
        </div>
        <div className="topbar-right">
          <button type="button" className="btn-secondary" onClick={openMonitorWindow}>
            Abrir monitor
          </button>
          <span className="date-pill">{formatDate()}</span>
          <label className="inline-toggle">
            <input type="checkbox" checked={headless} onChange={(e) => setHeadless(e.target.checked)} />
            Headless
          </label>
          <span className={`health-dot ${backendOk ? "up" : "down"}`} />
        </div>
      </header>

      <div className="layout main-only">
        <main className="main-pane">
          <nav className="tabs">
            {TABS.map((t) => (
              <button key={t} className={tab === t ? "tab active" : "tab"} onClick={() => setTab(t)}>
                {t}
              </button>
            ))}
          </nav>

          {tab === "BÃšSQUEDA" && (
            <section className="card">
              <form className="grid-form" onSubmit={runSearch}>
                <label>
                  Crear bÃºsquedas compuestas
                  <input
                    value={queryDescripcion}
                    onChange={(e) => setQueryDescripcion(e.target.value)}
                    placeholder="Ej: supervision"
                  />
                  <select value="" onChange={(e) => addQueryRegion(e.target.value)}>
                    <option value="">Regiones para esta bÃºsqueda (vacÃ­o = todo PerÃº)</option>
                    {REGIONES.map((r) => (
                      <option key={`draft-${r}`} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                  <div className="region-chips">
                    {queryRegiones.map((region) => (
                      <button
                        key={`draft-chip-${region}`}
                        type="button"
                        className="region-chip"
                        onClick={() => removeQueryRegion(region)}
                      >
                        {region} Ã—
                      </button>
                    ))}
                  </div>
                  <button type="button" className="btn-secondary" onClick={addSearchQuery}>
                    Agregar bÃºsqueda
                  </button>
                  <div className="query-list">
                    {searchQueries.map((q, idx) => (
                      <div key={`${q.descripcion}-${idx}`} className="query-item">
                        <span>
                          {q.descripcion} â€” {q.regiones.length ? q.regiones.join(", ") : "Todo PerÃº"}
                        </span>
                        <button type="button" className="btn-danger" onClick={() => removeSearchQuery(idx)}>
                          Quitar
                        </button>
                      </div>
                    ))}
                  </div>
                  {searchQueries.length > 0 && (
                    <span className="muted">
                      Se usarÃ¡n estas bÃºsquedas compuestas y se consolidarÃ¡n en una sola lista.
                    </span>
                  )}
                </label>
                <label>
                  Entidad
                  <input
                    value={filters.entidad}
                    onChange={(e) => setFilters({ ...filters, entidad: e.target.value })}
                    placeholder="Ej. Ministerio de Salud"
                  />
                </label>
                <label>
                  Tipo de procedimiento
                  <select value={filters.tipo} onChange={(e) => setFilters({ ...filters, tipo: e.target.value })}>
                    {TIPOS.map((x) => (
                      <option key={x || "all"} value={x}>
                        {x || "Todos"}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Objeto
                  <select
                    value={filters.objeto}
                    onChange={(e) => setFilters({ ...filters, objeto: e.target.value })}
                  >
                    {OBJETOS.map((x) => (
                      <option key={x || "all"} value={x}>
                        {x || "Todos"}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Regiones objetivo
                  <select value="" onChange={(e) => addRegion(e.target.value)}>
                    <option value="">Selecciona una regiÃ³n...</option>
                    {REGIONES.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                  <div className="region-chips">
                    {filters.regiones.map((region) => (
                      <button
                        key={region}
                        type="button"
                        className="region-chip"
                        onClick={() => removeRegion(region)}
                        title={`Quitar ${region}`}
                      >
                        {region} Ã—
                      </button>
                    ))}
                  </div>
                </label>
                <label>
                  AÃ±o
                  <select value={filters.anio} onChange={(e) => setFilters({ ...filters, anio: e.target.value })}>
                    {YEARS.map((x) => (
                      <option key={x || "all"} value={x}>
                        {x || "Todos"}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  MÃ¡x. pÃ¡ginas
                  <input
                    type="number"
                    min="1"
                    max="20"
                    value={filters.max_pages}
                    onChange={(e) => setFilters({ ...filters, max_pages: Number(e.target.value) || 1 })}
                  />
                </label>
                <button className="btn-primary" disabled={searching}>
                  {searching ? "Buscando..." : "Buscar"}
                </button>
              </form>

              {searchError && <p className="error-text">{searchError}</p>}
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>DescripciÃ³n / Nomenclatura</th>
                      <th>Nombre o Sigla de la Entidad</th>
                      <th>Tipo</th>
                      <th>VR / VE / CuantÃ­a de la contrataciÃ³n</th>
                      <th>Fecha</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((row, i) => {
                      const key = `${row.nomenclatura || "row"}-${i}`;
                      return (
                        <Fragment key={key}>
                          <tr key={key} onClick={() => setExpanded((p) => ({ ...p, [key]: !p[key] }))}>
                            <td>
                              <div className="row-title">{row.descripcion || "-"}</div>
                              <div className="muted">{row.nomenclatura || "-"}</div>
                            </td>
                            <td>{row.entidad || "-"}</td>
                            <td>{row.tipo || "-"}</td>
                            <td className="money">{row.monto_referencial || "-"}</td>
                            <td>{row.fecha_convocatoria || "-"}</td>
                          </tr>
                          {expanded[key] && (
                            <tr className="expanded-row">
                              <td colSpan={5}>
                                <p>
                                  <strong>Entidad:</strong> {row.entidad || "-"}
                                </p>
                                <p>
                                  <strong>Objeto:</strong> {row.objeto || "-"}
                                </p>
                                {!!row.cronograma?.length && (
                                  <div className="schedule-block">
                                    <strong>Cronograma:</strong>
                                    <ul>
                                      {row.cronograma.map((c, idx) => (
                                        <li key={`${c.etapa}-${idx}`}>
                                          {c.etapa} | Inicio: {c.fecha_inicio || "-"} | Fin: {c.fecha_fin || "-"}
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                                <div className="row-actions">
                                  <button
                                    className={trackingIds.has(trackingId(row)) ? "btn-danger" : "btn-secondary"}
                                    onClick={() =>
                                      trackingIds.has(trackingId(row))
                                        ? removeFromTracking(row)
                                        : addToTracking(row)
                                    }
                                  >
                                    {trackingIds.has(trackingId(row)) ? "Quitar interÃ©s" : "Me interesa"}
                                  </button>
                                  <button className="btn-secondary" onClick={() => analyzeItem(row)}>
                                    Analizar con IA
                                  </button>
                                </div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
                    {!results.length && !searching && (
                      <tr>
                        <td colSpan={5} className="muted">
                          Sin resultados aÃºn.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {tab === "LOTE EXCEL" && (
            <section className="card">
              <div
                className={dragging ? "dropzone active" : "dropzone"}
                onDragEnter={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragOver={(e) => e.preventDefault()}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragging(false);
                  const file = e.dataTransfer.files?.[0];
                  onDropFile(file);
                }}
              >
                <p>Arrastra y suelta CSV aquÃ­ (primera columna = nomenclaturas)</p>
                <input
                  type="file"
                  accept=".csv,text/csv"
                  onChange={(e) => onDropFile(e.target.files?.[0])}
                />
              </div>

              <div className="preview-list">
                <h3>Vista previa ({batchItems.length})</h3>
                <ul>
                  {batchItems.slice(0, 50).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>

              <div className="batch-controls">
                <button className="btn-primary" disabled={!batchItems.length || batchStatus.running} onClick={startBatch}>
                  {batchStatus.running ? "Procesando..." : "Iniciar lote"}
                </button>
                <div className="progress-bar">
                  <div style={{ width: `${progressPct}%` }} />
                </div>
                <p>
                  Progreso: {batchStatus.progress}/{batchStatus.total} ({progressPct}%)
                </p>
                {!!batchStatus.results.length && !batchStatus.running && (
                  <p className="success-text">
                    Completado: {batchStatus.results.length} nomenclaturas procesadas.
                  </p>
                )}
              </div>
            </section>
          )}

          {tab === "ANÃLISIS IA" && (
            <section className="card">
              {!selectedItem && <p className="muted">Selecciona un procedimiento desde la pestaÃ±a BÃšSQUEDA.</p>}
              {selectedItem && (
                <>
                  <h3>{selectedItem.nomenclatura || "Procedimiento seleccionado"}</h3>
                  <p className="muted">{selectedItem.descripcion}</p>
                  <div className="analysis-card">
                    {analysisLoading && <p>Analizando con Anthropic...</p>}
                    {analysisError && <p className="error-text">{analysisError}</p>}
                    {!analysisLoading && !analysisError && <pre>{analysis || "Sin anÃ¡lisis disponible."}</pre>}
                  </div>
                </>
              )}
            </section>
          )}

          {tab === "SEGUIMIENTO" && (
            <section className="card">
              <h3>Seguimiento de Contratos</h3>
              <p className="muted">Contratos marcados como "Me interesa".</p>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>DescripciÃ³n / Nomenclatura</th>
                      <th>Entidad</th>
                      <th>Tipo</th>
                      <th>VR / VE / CuantÃ­a</th>
                      <th>Fecha</th>
                      <th>AcciÃ³n</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trackingItems.map((row, i) => (
                      <tr key={`${trackingId(row)}-${i}`}>
                        <td>
                          <div className="row-title">{row.descripcion || "-"}</div>
                          <div className="muted">{row.nomenclatura || "-"}</div>
                          {row.cronograma_loading && <p className="muted">Cargando cronograma...</p>}
                          {!!row.cronograma_error && <p className="warn-text">{row.cronograma_error}</p>}
                          {!!row.cronograma_loaded && !row.cronograma?.length && !row.cronograma_error && (
                            <p className="muted">Cronograma cargado sin etapas visibles.</p>
                          )}
                          {!!row.cronograma?.length && (
                            <div className="schedule-block">
                              <strong>Cronograma:</strong>
                              <ul>
                                {row.cronograma.map((c, idx) => (
                                  <li key={`${c.etapa}-${idx}`}>
                                    {c.etapa} | Inicio: {c.fecha_inicio || "-"} | Fin: {c.fecha_fin || "-"}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {!!row.cronograma_trace?.length && (
                            <div className="trace-block">
                              <strong>Trazabilidad:</strong>
                              <ul>
                                {row.cronograma_trace.map((t, idx) => (
                                  <li key={`trace-main-${idx}`}>{t}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </td>
                        <td>{row.entidad || "-"}</td>
                        <td>{row.tipo || "-"}</td>
                        <td className="money">{row.monto_referencial || "-"}</td>
                        <td>{row.fecha_convocatoria || "-"}</td>
                        <td>
                          <div className="action-stack">
                            <button
                              className="btn-secondary"
                              disabled={row.cronograma_loading}
                              onClick={() => fetchCronogramaForTrackingItem(row)}
                            >
                              {row.cronograma_loading ? "Cargando..." : "Cargar cronograma"}
                            </button>
                            <button className="btn-danger" onClick={() => removeFromTracking(row)}>
                              Quitar
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {!trackingItems.length && (
                      <tr>
                        <td colSpan={6} className="muted">
                          AÃºn no tienes contratos en seguimiento.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}

