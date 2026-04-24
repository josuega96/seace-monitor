import json
import os
import queue
import re
import threading
import time
import urllib.error
import urllib.request
import unicodedata
from collections import deque
from datetime import datetime
from typing import Any, Dict, List

from flask import Flask, Response, jsonify, request
from flask_cors import CORS

from scraper import SeaceScraper


ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


class LogHub:
    def __init__(self) -> None:
        self._subscribers: List[queue.Queue] = []
        self._history = deque(maxlen=500)
        self._lock = threading.Lock()

    def emit(self, message: str, log_type: str = "info") -> None:
        payload = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "message": message,
            "type": log_type,
        }
        with self._lock:
            self._history.append(payload)
            for q in self._subscribers:
                q.put(payload)

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
            for item in list(self._history)[-50:]:
                q.put(item)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)


LOGS = LogHub()
SCRAPER = SeaceScraper(LOGS.emit)


batch_state: Dict[str, Any] = {
    "running": False,
    "progress": 0,
    "total": 0,
    "results": [],
}
batch_lock = threading.Lock()


def anthropic_request(system_prompt: str, user_prompt: str, max_tokens: int = 900) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY no esta configurada.")

    body = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    payload = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(
        ANTHROPIC_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=80) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        parts = data.get("content", [])
        texts = [p.get("text", "") for p in parts if p.get("type") == "text"]
        return "\n".join(texts).strip()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Error Anthropic {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"No se pudo conectar con Anthropic: {e.reason}")


def generate_local_mock(filters: Dict[str, Any], count: int = 6) -> List[Dict[str, Any]]:
    desc = filters.get("descripcion") or "Servicio Especializado"
    entidad = filters.get("entidad") or "Entidad Publica Nacional"
    anio = filters.get("anio") or str(datetime.now().year)
    tipo = filters.get("tipo") or "Adjudicacion Simplificada"
    objeto = filters.get("objeto") or "Servicios"
    regiones = filters.get("regiones") or []
    if isinstance(regiones, list) and regiones:
        entidad = f"{entidad} - {regiones[0]}"

    samples = []
    for i in range(1, count + 1):
        samples.append(
            {
                "nomenclatura": f"AS-SM-{i:03d}-{anio}-{entidad[:4].upper()}",
                "descripcion": f"{desc} - Paquete {i}",
                "entidad": entidad,
                "tipo": tipo,
                "objeto": objeto,
                "estado": "Convocado",
                "monto_referencial": f"S/ {150000 + i * 7800:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."),
                "fecha_convocatoria": f"{anio}-0{((i - 1) % 9) + 1}-1{(i % 9)}",
                "ai_generated": True,
            }
        )
    return samples


def parse_json_array_from_text(text: str) -> List[Dict[str, Any]]:
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("La respuesta no contiene un arreglo JSON valido.")
    return json.loads(text[start : end + 1])


def normalize_text(value: str) -> str:
    raw = (value or "").strip().lower()
    return "".join(ch for ch in unicodedata.normalize("NFKD", raw) if not unicodedata.combining(ch))


def filter_results_by_regions(items: List[Dict[str, Any]], regions: List[str]) -> List[Dict[str, Any]]:
    normalized_regions = [normalize_text(str(r)) for r in (regions or []) if str(r).strip()]
    if not normalized_regions:
        return items

    filtered: List[Dict[str, Any]] = []
    for item in items:
        haystack = " ".join(
            [
                str(item.get("entidad", "")),
                str(item.get("descripcion", "")),
                str(item.get("objeto", "")),
            ]
        )
        normalized_haystack = normalize_text(haystack)
        if any(region in normalized_haystack for region in normalized_regions):
            filtered.append(item)
    return filtered


def parse_description_terms(raw_text: str, raw_list: Any) -> List[str]:
    terms: List[str] = []
    if isinstance(raw_list, list):
        terms.extend([str(x).strip() for x in raw_list if str(x).strip()])
    text = (raw_text or "").strip()
    if text:
        parts = [p.strip() for p in re.split(r"[\n,;]+", text) if p.strip()]
        terms.extend(parts if parts else [text])
    deduped: List[str] = []
    seen = set()
    for term in terms:
        key = normalize_text(term)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(term)
    return deduped


def dedupe_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    output: List[Dict[str, Any]] = []
    for item in items:
        key = "||".join(
            [
                str(item.get("nomenclatura", "")),
                str(item.get("entidad", "")),
                str(item.get("descripcion", "")),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def _action_tokens(item: Dict[str, Any]) -> set:
    refs = item.get("accion_refs", [])
    tokens = set()
    if not isinstance(refs, list):
        return tokens
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        token = normalize_text(str(ref.get("token", "")))
        if token:
            tokens.add(token)
    return tokens


def _match_score(target: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    score = 0
    reasons: List[str] = []

    target_tokens = _action_tokens(target)
    cand_tokens = _action_tokens(candidate)
    common_tokens = target_tokens.intersection(cand_tokens)
    if common_tokens:
        score += 300
        reasons.append("accion_refs")

    t_nom = normalize_text(str(target.get("nomenclatura", "")))
    c_nom = normalize_text(str(candidate.get("nomenclatura", "")))
    if t_nom and c_nom and t_nom == c_nom:
        score += 140
        reasons.append("nomenclatura")
    elif t_nom and c_nom and (t_nom in c_nom or c_nom in t_nom):
        score += 70
        reasons.append("nomenclatura_parcial")

    t_ent = normalize_text(str(target.get("entidad", "")))
    c_ent = normalize_text(str(candidate.get("entidad", "")))
    if t_ent and c_ent and t_ent == c_ent:
        score += 90
        reasons.append("entidad")
    elif t_ent and c_ent and (t_ent in c_ent or c_ent in t_ent):
        score += 45
        reasons.append("entidad_parcial")

    t_desc = normalize_text(str(target.get("descripcion", "")))
    c_desc = normalize_text(str(candidate.get("descripcion", "")))
    if t_desc and c_desc and t_desc == c_desc:
        score += 90
        reasons.append("descripcion")
    elif t_desc and c_desc and (t_desc in c_desc or c_desc in t_desc):
        score += 45
        reasons.append("descripcion_parcial")

    t_fecha = normalize_text(str(target.get("fecha_convocatoria", "")))
    c_fecha = normalize_text(str(candidate.get("fecha_convocatoria", "")))
    if t_fecha and c_fecha and t_fecha == c_fecha:
        score += 40
        reasons.append("fecha")

    return {"score": score, "reasons": reasons}


def _best_match(target: Dict[str, Any], candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    best_item: Dict[str, Any] = {}
    best_score = -1
    best_reasons: List[str] = []
    for cand in candidates:
        result = _match_score(target, cand)
        score = int(result["score"])
        if score > best_score:
            best_score = score
            best_item = cand
            best_reasons = list(result["reasons"])
    return {"item": best_item, "score": best_score, "reasons": best_reasons}


def build_search_requests(body: Dict[str, Any], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    requests: List[Dict[str, Any]] = []
    raw_searches = body.get("searches", [])

    if isinstance(raw_searches, list) and raw_searches:
        for search in raw_searches[:12]:
            if not isinstance(search, dict):
                continue
            regions = search.get("regiones", [])
            if not isinstance(regions, list):
                regions = []
            terms = parse_description_terms(
                search.get("descripcion", ""),
                search.get("descripciones", []),
            )
            for term in terms:
                requests.append({"descripcion": term, "regiones": regions})
        return requests

    terms = parse_description_terms(filters.get("descripcion", ""), filters.get("descripciones", []))
    if not terms:
        terms = [""]
    for term in terms[:8]:
        requests.append({"descripcion": term, "regiones": filters.get("regiones", [])})
    return requests


def generate_local_analysis(item: Dict[str, Any]) -> str:
    estado = (item.get("estado") or "Sin estado").strip()
    tipo = (item.get("tipo") or "No especificado").strip()
    objeto = (item.get("objeto") or "No especificado").strip()
    monto = (item.get("monto_referencial") or "No informado").strip()
    entidad = (item.get("entidad") or "No informada").strip()

    return (
        "1) Evaluacion de riesgo\n"
        f"- Estado actual: {estado}.\n"
        f"- Riesgo operativo: medio, por posible variacion de requisitos en procesos {tipo.lower()}.\n"
        "- Validar bases, cronograma y requisitos habilitantes antes de ofertar.\n\n"
        "2) Oportunidad para proveedor\n"
        f"- Objeto: {objeto}. Entidad: {entidad}.\n"
        f"- Referencia economica reportada: {monto}.\n"
        "- Oportunidad moderada-alta si se cuenta con experiencia especifica y capacidad documentaria.\n\n"
        "3) Alertas de cumplimiento\n"
        "- Confirmar vigencia de RNP y no tener impedimentos para contratar con el Estado.\n"
        "- Revisar garantias, penalidades y criterios de evaluacion tecnica/economica.\n"
        "- Preparar consultas y observaciones dentro del plazo oficial del proceso.\n\n"
        "4) Recomendacion estrategica\n"
        "- Ejecutar checklist documental previo a la presentacion.\n"
        "- Definir estrategia de precio con margen y plan de ejecucion realista.\n"
        "- Monitorear el expediente en SEACE para responder cambios y absoluciones."
    )


def run_batch(nomenclaturas: List[str], headless: bool) -> None:
    with batch_lock:
        batch_state["running"] = True
        batch_state["progress"] = 0
        batch_state["total"] = len(nomenclaturas)
        batch_state["results"] = []

    LOGS.emit(f"Batch iniciado con {len(nomenclaturas)} nomenclaturas", "info")
    for idx, nom in enumerate(nomenclaturas):
        base = f"Lote {idx + 1}/{len(nomenclaturas)} - {nom}"
        try:
            for step in range(1, 11):
                LOGS.emit(f"{base} - paso {step}/10", "info")
                time.sleep(0.05)

            filters = {
                "descripcion": nom,
                "entidad": "",
                "anio": "",
                "tipo": "",
                "objeto": "",
                "headless": headless,
                "max_pages": 1,
            }
            result = SCRAPER.search(filters)
            with batch_lock:
                batch_state["results"].append({"nomenclatura": nom, "items": result})
                batch_state["progress"] = idx + 1
            LOGS.emit(f"{base} - completado con {len(result)} registros", "success")
        except Exception as e:
            with batch_lock:
                batch_state["results"].append({"nomenclatura": nom, "error": str(e), "items": []})
                batch_state["progress"] = idx + 1
            LOGS.emit(f"{base} - error: {e}", "error")

    with batch_lock:
        batch_state["running"] = False
    LOGS.emit("Batch finalizado", "sync")


@app.post("/api/search")
def api_search():
    body = request.get_json(silent=True) or {}
    filters = {
        "descripcion": body.get("descripcion", ""),
        "descripciones": body.get("descripciones", []),
        "entidad": body.get("entidad", ""),
        "anio": body.get("anio", ""),
        "tipo": body.get("tipo", ""),
        "objeto": body.get("objeto", ""),
        "regiones": body.get("regiones", []),
        "include_cronograma": body.get("include_cronograma", False),
        "headless": body.get("headless", True),
        "max_pages": body.get("max_pages", 3),
    }
    LOGS.emit("Solicitud /api/search recibida", "info")
    try:
        requests = build_search_requests(body, filters)
        if not requests:
            return jsonify([])

        all_items: List[Dict[str, Any]] = []
        for idx, req in enumerate(requests):
            run_filters = dict(filters)
            run_filters["descripcion"] = req.get("descripcion", "")
            LOGS.emit(
                f"Busqueda {idx + 1}/{len(requests)} por descripcion: {run_filters['descripcion'] or '(vacia)'}",
                "info",
            )
            run_items = SCRAPER.search(run_filters)
            run_items = filter_results_by_regions(run_items, req.get("regiones", []))
            all_items.extend(run_items)

        data = dedupe_items(all_items)
        LOGS.emit(f"/api/search completado: {len(data)} resultados", "success")
        return jsonify(data)
    except Exception as e:
        LOGS.emit(f"/api/search fallo: {e}", "error")
        return jsonify({"error": str(e)}), 500


@app.post("/api/cronograma")
def api_cronograma():
    body = request.get_json(silent=True) or {}
    item = body.get("item") or {}
    if not isinstance(item, dict) or not item:
        return jsonify({"error": "Debes enviar item para buscar cronograma."}), 400

    descripcion = str(item.get("descripcion") or item.get("nomenclatura") or "").strip()
    if not descripcion:
        return jsonify({"error": "El item no tiene descripcion o nomenclatura para consultar cronograma."}), 400

    preferred_headless = bool(body.get("headless", True))
    max_pages = int(body.get("max_pages", 3) or 3)
    max_pages = max(1, min(max_pages, 6))
    tries = [preferred_headless]
    if preferred_headless:
        tries.append(False)

    trace: List[str] = []
    proc_ref = str(item.get("nomenclatura") or item.get("descripcion") or "SIN-COD")
    LOGS.emit(f"Cronograma solicitado para {proc_ref}", "info")

    for attempt_idx, headless_mode in enumerate(tries, start=1):
        mode_name = "headless" if headless_mode else "visible"
        trace.append(f"Intento {attempt_idx}: modo {mode_name}")
        LOGS.emit(f"Cronograma {proc_ref}: intento {attempt_idx} en modo {mode_name}", "info")

        filters = {
            "descripcion": descripcion,
            "descripciones": [],
            "entidad": body.get("entidad", ""),
            "anio": body.get("anio", ""),
            "tipo": body.get("tipo", ""),
            "objeto": body.get("objeto", ""),
            "regiones": [],
            "include_cronograma": True,
            "headless": headless_mode,
            "max_pages": max_pages,
        }

        try:
            results = SCRAPER.search(filters)
        except Exception as e:
            msg = f"Intento {attempt_idx} error scraper: {e}"
            trace.append(msg)
            LOGS.emit(f"Cronograma {proc_ref}: {msg}", "warn")
            continue

        trace.append(f"Intento {attempt_idx}: resultados recibidos {len(results)}")
        if not results:
            LOGS.emit(f"Cronograma {proc_ref}: sin resultados en intento {attempt_idx}", "warn")
            continue

        match = _best_match(item, results)
        matched = match.get("item") or {}
        score = int(match.get("score") or 0)
        reasons = match.get("reasons") or []
        trace.append(f"Intento {attempt_idx}: mejor match score={score} razones={','.join(reasons) or 'ninguna'}")

        if not matched or score < 40:
            LOGS.emit(
                f"Cronograma {proc_ref}: no se logró match confiable en intento {attempt_idx} (score={score})",
                "warn",
            )
            continue

        schedule = matched.get("cronograma", [])
        if not isinstance(schedule, list):
            schedule = []
        trace.append(f"Intento {attempt_idx}: etapas detectadas {len(schedule)}")
        LOGS.emit(
            f"Cronograma {proc_ref}: match ok ({','.join(reasons) or 'sin razon'}) etapas={len(schedule)}",
            "success" if schedule else "warn",
        )

        if schedule:
            return jsonify(
                {
                    "ok": True,
                    "cronograma": schedule,
                    "matched_item": matched,
                    "trace": trace,
                    "mode_used": mode_name,
                }
            )

    LOGS.emit(f"Cronograma {proc_ref}: no se detectaron etapas tras {len(tries)} intentos", "warn")
    return jsonify({"ok": False, "cronograma": [], "trace": trace}), 404


@app.post("/api/batch")
def api_batch():
    body = request.get_json(silent=True) or {}
    nomenclaturas = body.get("nomenclaturas", [])
    headless = bool(body.get("headless", True))
    if not isinstance(nomenclaturas, list) or not nomenclaturas:
        return jsonify({"error": "Debes enviar nomenclaturas: string[]"}), 400

    with batch_lock:
        if batch_state["running"]:
            return jsonify({"error": "Ya existe un proceso batch en ejecucion"}), 409

    thread = threading.Thread(target=run_batch, args=(nomenclaturas, headless), daemon=True)
    thread.start()
    return jsonify({"ok": True, "message": "Batch iniciado"})


@app.get("/api/batch/status")
def api_batch_status():
    with batch_lock:
        return jsonify(
            {
                "running": batch_state["running"],
                "progress": batch_state["progress"],
                "total": batch_state["total"],
                "results": batch_state["results"],
            }
        )


@app.post("/api/analyze")
def api_analyze():
    body = request.get_json(silent=True) or {}
    item = body.get("item")
    if not item:
        return jsonify({"error": "Falta item para analizar"}), 400

    LOGS.emit(f"Analisis IA solicitado para {item.get('nomenclatura', 'SIN-COD')}", "info")
    try:
        system_prompt = (
            "Eres analista senior de contrataciones publicas del Peru (SEACE). "
            "Responde en espanol profesional, claro y accionable."
        )
        user_prompt = (
            "Analiza este procedimiento y entrega 4 secciones con titulos:\n"
            "1) Evaluacion de riesgo\n"
            "2) Oportunidad para proveedor\n"
            "3) Alertas de cumplimiento\n"
            "4) Recomendacion estrategica\n\n"
            f"Datos:\n{json.dumps(item, ensure_ascii=False, indent=2)}"
        )
        text = anthropic_request(system_prompt, user_prompt, max_tokens=900)
        LOGS.emit("Analisis IA completado", "success")
        return jsonify({"analysis": text, "model": ANTHROPIC_MODEL})
    except Exception as e:
        LOGS.emit(f"Anthropic no disponible. Se usa analisis local: {e}", "warn")
        return jsonify(
            {
                "analysis": generate_local_analysis(item),
                "model": "local-fallback",
                "warning": str(e),
            }
        )


@app.post("/api/mock-data")
def api_mock_data():
    LOGS.emit("Solicitud /api/mock-data rechazada: datos mock deshabilitados", "warn")
    return jsonify({"error": "Datos mock deshabilitados. Solo se permiten resultados reales de SEACE."}), 410


@app.get("/api/logs")
def api_logs():
    q = LOGS.subscribe()

    def stream():
        try:
            while True:
                try:
                    item = q.get(timeout=15)
                    yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            LOGS.unsubscribe(q)

    return Response(stream(), mimetype="text/event-stream")


@app.get("/api/health")
def api_health():
    return jsonify({"ok": True, "service": "seace-monitor-backend", "time": datetime.utcnow().isoformat() + "Z"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    LOGS.emit(f"Backend SEACE Monitor inicializado en puerto {port}", "success")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)
