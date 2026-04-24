import re
from pathlib import Path
from typing import Any, Callable, Dict, List

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


SEACE_PUBLIC_URL = (
    "https://prodapp2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/"
    "buscadorPublico.xhtml"
)


class SeaceScraper:
    def __init__(self, logger: Callable[[str, str], None]):
        self.logger = logger

    def _log_step(self, step: int, message: str, log_type: str = "info") -> None:
        self.logger(f"Paso {step}/10 · {message}", log_type)

    def _safe_fill(self, page, selectors: List[str], value: str) -> bool:
        if not value:
            return False
        for selector in selectors:
            locator = page.locator(selector).first
            if locator.count() > 0:
                locator.fill("")
                locator.fill(value)
                return True
        return False

    def _open_procedure_search_tab(self, page) -> None:
        for selector in [
            "a:has-text('Buscador de Procedimientos de Selección')",
            "a:has-text('Buscador de Procedimientos de Seleccion')",
        ]:
            tab = page.locator(selector).first
            if tab.count() > 0:
                tab.click()
                page.wait_for_timeout(700)
                return

    def _click_first_visible(self, page, selectors: List[str]) -> bool:
        for selector in selectors:
            loc = page.locator(selector)
            for i in range(loc.count()):
                candidate = loc.nth(i)
                try:
                    if candidate.is_visible():
                        candidate.click()
                        return True
                except Exception:
                    continue
        return False

    def _safe_select(self, page, selectors: List[str], value: str) -> bool:
        if not value:
            return False
        for selector in selectors:
            locator = page.locator(selector).first
            if locator.count() > 0:
                options = locator.locator("option")
                for i in range(options.count()):
                    label = options.nth(i).inner_text().strip().lower()
                    if value.lower() in label:
                        val = options.nth(i).get_attribute("value")
                        if not val:
                            continue
                        try:
                            locator.select_option(val)
                            return True
                        except Exception:
                            # Some SEACE selects are hidden; force the value via DOM events.
                            try:
                                changed = page.evaluate(
                                    """([sel, targetVal]) => {
                                        const el = document.querySelector(sel);
                                        if (!el) return false;
                                        el.value = targetVal;
                                        el.dispatchEvent(new Event('input', { bubbles: true }));
                                        el.dispatchEvent(new Event('change', { bubbles: true }));
                                        return true;
                                    }""",
                                    [selector, val],
                                )
                                if changed:
                                    return True
                            except Exception:
                                pass
                try:
                    locator.select_option(label=value)
                    return True
                except Exception:
                    try:
                        changed = page.evaluate(
                            """([sel, targetText]) => {
                                const el = document.querySelector(sel);
                                if (!el || !el.options) return false;
                                const opts = Array.from(el.options);
                                const found = opts.find(o => (o.textContent || '').toLowerCase().includes(targetText.toLowerCase()));
                                if (!found) return false;
                                el.value = found.value;
                                el.dispatchEvent(new Event('input', { bubbles: true }));
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                                return true;
                            }""",
                            [selector, value],
                        )
                        if changed:
                            return True
                    except Exception:
                        pass
        return False

    def _clean_money(self, text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    def _normalize_compact(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip().lower()

    def _collect_action_refs(self, row) -> List[Dict[str, str]]:
        refs: List[Dict[str, str]] = []
        try:
            action_cell = row.locator("td").last
            anchors = action_cell.locator("a")
            for idx in range(anchors.count()):
                a = anchors.nth(idx)
                img = a.locator("img").first
                entry = {
                    "kind": "a",
                    "index": str(idx),
                    "title": a.get_attribute("title") or "",
                    "href": a.get_attribute("href") or "",
                    "onclick": a.get_attribute("onclick") or "",
                    "aria_label": a.get_attribute("aria-label") or "",
                    "img_alt": img.get_attribute("alt") if img.count() > 0 else "",
                    "img_src": img.get_attribute("src") if img.count() > 0 else "",
                }
                token_raw = " | ".join(
                    [
                        entry.get("title", ""),
                        entry.get("href", ""),
                        entry.get("onclick", ""),
                        entry.get("aria_label", ""),
                        entry.get("img_alt", ""),
                        entry.get("img_src", ""),
                    ]
                )
                entry["token"] = self._normalize_compact(token_raw)
                refs.append(entry)
        except Exception:
            pass
        return refs

    def _extract_cronograma_via_ocr(self, page) -> List[Dict[str, str]]:
        try:
            import io
            import tempfile

            import pytesseract
            from PIL import Image, ImageOps
        except Exception:
            return []

        try:
            default_tesseract = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
            if default_tesseract.exists():
                pytesseract.pytesseract.tesseract_cmd = str(default_tesseract)
        except Exception:
            pass

        ocr_targets = [
            "div:has-text('Cronograma')",
            "fieldset:has-text('Cronograma')",
            "table:has-text('Etapa')",
            "body",
        ]

        text = ""
        for selector in ocr_targets:
            try:
                loc = page.locator(selector).first
                if loc.count() == 0:
                    continue
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_path = tmp.name
                loc.screenshot(path=tmp_path)
                img = Image.open(tmp_path)
                # Enhance contrast for OCR
                gray = ImageOps.grayscale(img)
                bw = gray.point(lambda x: 0 if x < 165 else 255, "1")
                buf = io.BytesIO()
                bw.save(buf, format="PNG")
                text = pytesseract.image_to_string(Image.open(io.BytesIO(buf.getvalue())), lang="spa+eng")
                if text and len(text.strip()) > 30:
                    break
            except Exception:
                continue

        if not text:
            return []

        date_re = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
        time_re = re.compile(r"^\d{2}:\d{2}$")
        lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines() if ln.strip()]
        lines = [
            ln
            for ln in lines
            if "cronograma" not in ln.lower()
            and "etapa" not in ln.lower()
            and "fecha inicio" not in ln.lower()
            and "fecha fin" not in ln.lower()
            and not time_re.match(ln)
        ]

        schedule: List[Dict[str, str]] = []
        stage_buffer: List[str] = []
        pending_stage = ""
        pending_start = ""

        for line in lines:
            dates = date_re.findall(line)
            if len(dates) >= 2:
                first_date_idx = line.find(dates[0])
                prefix = line[:first_date_idx].strip() if first_date_idx >= 0 else ""
                etapa = prefix or " ".join(stage_buffer).strip() or pending_stage
                if etapa:
                    schedule.append(
                        {
                            "etapa": etapa,
                            "fecha_inicio": dates[0],
                            "fecha_fin": dates[1],
                        }
                    )
                stage_buffer = []
                pending_stage = ""
                pending_start = ""
                continue

            if len(dates) == 1:
                first_date_idx = line.find(dates[0])
                prefix = line[:first_date_idx].strip() if first_date_idx >= 0 else ""
                stage_candidate = prefix or " ".join(stage_buffer).strip() or pending_stage
                if not pending_start:
                    pending_start = dates[0]
                    pending_stage = stage_candidate
                else:
                    etapa = stage_candidate or pending_stage
                    if etapa:
                        schedule.append(
                            {
                                "etapa": etapa,
                                "fecha_inicio": pending_start,
                                "fecha_fin": dates[0],
                            }
                        )
                    pending_start = ""
                    pending_stage = ""
                    stage_buffer = []
                continue

            stage_buffer.append(line)

        deduped: List[Dict[str, str]] = []
        seen = set()
        for row in schedule:
            key = (row.get("etapa", ""), row.get("fecha_inicio", ""), row.get("fecha_fin", ""))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        return deduped

    def _extract_cronograma(self, page) -> List[Dict[str, str]]:
        try:
            tab = page.locator(
                "a:has-text('Cronograma'), button:has-text('Cronograma'), "
                "[role='tab']:has-text('Cronograma'), li:has-text('Cronograma'), "
                "span:has-text('Cronograma')"
            ).first
            if tab.count() > 0 and tab.is_visible():
                tab.click()
                page.wait_for_timeout(1200)
        except Exception:
            pass

        # Give SEACE time to render cronograma table content after opening the ficha/tab.
        try:
            page.wait_for_selector("table tr", timeout=6000)
        except Exception:
            pass

        def _parse_rows(rows) -> List[Dict[str, str]]:
            parsed: List[Dict[str, str]] = []
            for i in range(rows.count()):
                tr = rows.nth(i)
                cells = tr.locator("th,td")
                if cells.count() < 2:
                    continue
                etapa = re.sub(r"\s+", " ", cells.nth(0).inner_text().strip()) if cells.count() > 0 else ""
                fecha_inicio = re.sub(r"\s+", " ", cells.nth(1).inner_text().strip()) if cells.count() > 1 else ""
                fecha_fin = re.sub(r"\s+", " ", cells.nth(2).inner_text().strip()) if cells.count() > 2 else ""

                if not etapa or etapa.lower().startswith("etapa"):
                    continue
                if not fecha_inicio and not fecha_fin:
                    continue
                parsed.append(
                    {
                        "etapa": etapa,
                        "fecha_inicio": fecha_inicio,
                        "fecha_fin": fecha_fin or fecha_inicio,
                    }
                )
            return parsed

        # Primary target from your screenshot:
        # fieldset/legend "Cronograma" and all rows under that block.
        contexts = [page]
        try:
            contexts.extend(list(page.frames))
        except Exception:
            pass

        for ctx in contexts:
            try:
                cronograma_panel = ctx.locator(
                    "fieldset:has(legend:has-text('Cronograma')), "
                    "div:has(> legend:has-text('Cronograma')), "
                    "div:has-text('Cronograma')"
                ).first
                if cronograma_panel.count() == 0:
                    continue

                panel_rows = cronograma_panel.locator(
                    "tbody[id$='dtCronograma_data'] tr, "
                    "tbody[id*='Cronograma_data'] tr, "
                    "div[id*='dtCronograma'] tbody tr, "
                    "table tbody tr"
                )
                schedule_from_panel = _parse_rows(panel_rows)
                if schedule_from_panel:
                    return schedule_from_panel
            except Exception:
                continue

        # Fast-path SEACE: cronograma table body commonly renders as
        # tbody id like "tbFicha:dtCronograma_data".
        direct_selectors = [
            "tbody[id='tbFicha:dtCronograma_data'] tr",
            "tbody[id$='dtCronograma_data'] tr",
            "tbody[id*='dtCronograma_data'] tr",
            "tbody[id*='Cronograma_data'] tr",
            "table[id*='dtCronograma'] tbody tr",
        ]
        for ctx in contexts:
            for selector in direct_selectors:
                try:
                    rows = ctx.locator(selector)
                    if rows.count() == 0:
                        continue
                    direct_schedule = _parse_rows(rows)
                    if direct_schedule:
                        return direct_schedule
                except Exception:
                    continue

        def _extract_from_context(ctx) -> List[Dict[str, str]]:
            out: List[Dict[str, str]] = []
            date_re = re.compile(r"\d{2}/\d{2}/\d{4}")

            selectors = [
                "table:has(th:has-text('Etapa')) tr",
                "table:has(td:has-text('Etapa')) tr",
                "table tr",
            ]
            for selector in selectors:
                rows = ctx.locator(selector)
                row_count = rows.count()
                if row_count == 0:
                    continue
                for i in range(row_count):
                    tr = rows.nth(i)
                    cells = tr.locator("th,td")
                    if cells.count() < 3:
                        continue
                    c0 = cells.nth(0).inner_text().strip()
                    c1 = cells.nth(1).inner_text().strip()
                    c2 = cells.nth(2).inner_text().strip()
                    if not c0:
                        continue
                    c0_l = c0.lower()
                    if c0_l.startswith("etapa"):
                        continue
                    if not (date_re.search(c1) or date_re.search(c2)):
                        continue
                    out.append({"etapa": c0, "fecha_inicio": c1, "fecha_fin": c2})
                # Fallback inside same selector: parse full text row when columns are merged/irregular.
                if not out:
                    for i in range(row_count):
                        tr = rows.nth(i)
                        row_text = tr.inner_text().strip()
                        if not row_text:
                            continue
                        if "etapa" in row_text.lower() and "fecha" in row_text.lower():
                            continue
                        dates = date_re.findall(row_text)
                        if not dates:
                            continue
                        lines = [ln.strip() for ln in row_text.splitlines() if ln.strip()]
                        if not lines:
                            continue
                        etapa = lines[0]
                        fecha_inicio = dates[0] if len(dates) > 0 else ""
                        fecha_fin = dates[1] if len(dates) > 1 else (dates[0] if len(dates) == 1 else "")
                        if etapa:
                            out.append({"etapa": etapa, "fecha_inicio": fecha_inicio, "fecha_fin": fecha_fin})
                if out:
                    return out
            return out

        # Try main page and every frame (some fichas render schedule table inside an iframe).
        schedule: List[Dict[str, str]] = _extract_from_context(page)
        if schedule:
            return schedule
        try:
            for frame in page.frames:
                schedule = _extract_from_context(frame)
                if schedule:
                    return schedule
        except Exception:
            pass

        # Final fallback: parse any row that looks like a schedule row by date columns.
        date_re = re.compile(r"\d{2}/\d{2}/\d{4}")
        generic_rows = page.locator("table tr")
        schedule = []
        for i in range(generic_rows.count()):
            tr = generic_rows.nth(i)
            cells = tr.locator("th,td")
            if cells.count() < 3:
                continue
            c0 = cells.nth(0).inner_text().strip()
            c1 = cells.nth(1).inner_text().strip()
            c2 = cells.nth(2).inner_text().strip()
            if not c0:
                continue
            if c0.lower().startswith("etapa"):
                continue
            if not (date_re.search(c1) or date_re.search(c2)):
                continue
            schedule.append({"etapa": c0, "fecha_inicio": c1, "fecha_fin": c2})
        if schedule:
            return schedule

        # OCR fallback for cases where SEACE renders cronograma in non-standard DOM.
        self._log_step(8, "Fallback OCR para cronograma: capturando panel", "warn")
        ocr_schedule = self._extract_cronograma_via_ocr(page)
        if ocr_schedule:
            self._log_step(8, f"OCR cronograma detectó {len(ocr_schedule)} etapas", "success")
            return ocr_schedule
        self._log_step(8, "OCR cronograma no detectó etapas", "warn")
        return []

    def _go_back_to_results(self, page) -> None:
        try:
            back = page.locator("a:has-text('Regresar'), button:has-text('Regresar')").first
            if back.count() > 0 and back.is_visible():
                back.click()
                page.wait_for_timeout(1200)
        except Exception:
            pass

        try:
            page.wait_for_selector("table tbody tr", timeout=8000)
            return
        except Exception:
            pass

        try:
            page.go_back(timeout=8000)
            page.wait_for_selector("table tbody tr", timeout=8000)
        except Exception:
            pass

    def _extract_row_schedule(self, page, row) -> List[Dict[str, str]]:
        def try_action(action_locator) -> List[Dict[str, str]]:
            try:
                with page.context.expect_page(timeout=2500) as pop_wait:
                    action_locator.click()
                popup = pop_wait.value
                popup.wait_for_load_state("domcontentloaded", timeout=6000)
                popup.wait_for_timeout(1200)
                schedule_ = self._extract_cronograma(popup)
                popup.close()
                return schedule_
            except Exception:
                pass

            try:
                action_locator.click()
            except Exception:
                try:
                    action_locator.click(force=True)
                except Exception:
                    return []

            try:
                page.wait_for_selector("text=Cronograma", timeout=6000)
                page.wait_for_timeout(1200)
            except Exception:
                self._go_back_to_results(page)
                return []

            schedule_ = self._extract_cronograma(page)
            self._go_back_to_results(page)
            return schedule_

        action_candidates = [
            "td:last-child a[title*='Ficha']",
            "td:last-child a[onclick*='ficha']",
            "td:last-child a:has(img[alt*='Ficha'])",
            "td:last-child a:has(img[src*='ficha'])",
            "td:last-child a:nth-child(2)",
            "td:last-child a:nth-child(1)",
            "td:last-child a",
            "td:last-child button",
            "td:last-child input[type='image']",
        ]

        # Try every action icon in "Acciones", prioritizing those that look like "Ficha".
        action_cell = row.locator("td").last
        anchors = action_cell.locator("a")
        scored: List[tuple[int, int]] = []
        for idx in range(anchors.count()):
            score = 0
            a = anchors.nth(idx)
            meta_parts = []
            for attr in ["title", "href", "onclick", "aria-label"]:
                try:
                    meta_parts.append(a.get_attribute(attr) or "")
                except Exception:
                    pass
            try:
                img = a.locator("img").first
                if img.count() > 0:
                    meta_parts.append(img.get_attribute("alt") or "")
                    meta_parts.append(img.get_attribute("title") or "")
                    meta_parts.append(img.get_attribute("src") or "")
            except Exception:
                pass
            meta = " ".join(meta_parts).lower()
            if "ficha" in meta:
                score += 10
            if "seleccion" in meta or "selección" in meta:
                score += 8
            if "cronograma" in meta:
                score += 6
            if "pdf" in meta or "descarga" in meta:
                score -= 6
            scored.append((score, idx))

        for _, idx in sorted(scored, key=lambda x: (-x[0], x[1])):
            schedule = try_action(anchors.nth(idx))
            if schedule:
                return schedule

        for selector in action_candidates:
            loc = row.locator(selector)
            if loc.count() == 0:
                continue
            schedule = try_action(loc.first)
            if schedule:
                return schedule
        return []

    def _result_rows_locator(self, page):
        selectors = [
            "table:has(th:has-text('Nomenclatura')) tbody tr",
            "table:has(th:has-text('Descripción')) tbody tr",
            "table[id*='resultado'] tbody tr",
            "table[id*='result'] tbody tr",
            "div[id*='resultado'] table tbody tr",
        ]
        for selector in selectors:
            rows = page.locator(selector)
            if rows.count() > 0:
                return rows
        return page.locator("table tbody tr")

    def _is_valid_result_row(self, row: Dict[str, Any]) -> bool:
        combined = " ".join(
            [
                row.get("nomenclatura", ""),
                row.get("descripcion", ""),
                row.get("entidad", ""),
                row.get("tipo", ""),
                row.get("objeto", ""),
                row.get("estado", ""),
                row.get("monto_referencial", ""),
                row.get("fecha_convocatoria", ""),
            ]
        ).lower()
        blocked_tokens = [
            "no se encontraron datos",
            "campo obligatorio",
            "[seleccione]",
            "nombre o sigla de entidad",
            "fecha de la publicación",
            "buscar",
            "limpiar",
            "ui-button",
        ]
        if any(token in combined for token in blocked_tokens):
            return False
        if len(row.get("nomenclatura", "")) > 140 or len(row.get("descripcion", "")) > 500:
            return False

        required = [
            row.get("nomenclatura", "").strip(),
            row.get("descripcion", "").strip(),
            row.get("tipo", "").strip(),
            row.get("objeto", "").strip(),
        ]
        if not required[0] or not required[1]:
            return False
        if sum(1 for value in required if value) < 3:
            return False
        return True

    def _parse_row(self, cells: List[str]) -> Dict[str, Any]:
        # Tabla extendida de "Buscador de Procedimientos de Seleccion":
        # 0 N°, 1 Entidad, 2 Fecha/Hora, 3 Nomenclatura, 4 Reiniciado Desde,
        # 5 Objeto, 6 Descripcion, 7 Codigo SNIP, 8 CUI,
        # 9 VR/VE/Cuantia, 10 Moneda, 11 Version SEACE, 12 Acciones
        if len(cells) >= 10 and cells[0].strip().isdigit():
            entidad = cells[1].strip() if len(cells) > 1 else ""
            fecha = cells[2].strip() if len(cells) > 2 else ""
            nomenclatura = cells[3].strip() if len(cells) > 3 else ""
            objeto = cells[5].strip() if len(cells) > 5 else ""
            descripcion = cells[6].strip() if len(cells) > 6 else ""
            cuantia = cells[9].strip() if len(cells) > 9 else ""
            moneda = cells[10].strip() if len(cells) > 10 else ""
            tipo = nomenclatura.split("-")[0].strip() if "-" in nomenclatura else ""
            monto = self._clean_money(" ".join([cuantia, moneda]).strip())

            return {
                "nomenclatura": nomenclatura,
                "descripcion": descripcion,
                "entidad": entidad,
                "tipo": tipo,
                "objeto": objeto,
                "estado": "",
                "monto_referencial": monto,
                "fecha_convocatoria": fecha,
            }

        # SEACE "Buscador de Procedimientos de Seleccion":
        # N°, Entidad, Fecha Publicacion, Nro Seleccion, Objeto, Descripcion
        if len(cells) >= 6 and cells[0].strip().isdigit():
            values = [c.strip() for c in cells[1:] if c and c.strip()]
            fecha = ""
            nro_sel = ""
            objeto = ""
            descripcion = ""
            entidad = ""

            date_re = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
            code_re = re.compile(r"\b[A-Z]{2,}[-\s].*\d{4}.*\b")

            for v in values:
                if not fecha and date_re.search(v):
                    fecha = v
                    continue
                if not nro_sel and code_re.search(v):
                    nro_sel = v
                    continue

            for v in values:
                low = v.lower()
                if v == fecha or v == nro_sel:
                    continue
                if not objeto and (
                    "consultor" in low
                    or low == "obras"
                    or low == "bienes"
                    or low == "servicios"
                ):
                    objeto = v
                    continue

            candidates = [v for v in values if v not in {fecha, nro_sel, objeto}]
            if candidates:
                descripcion = max(candidates, key=len)
                for v in candidates:
                    if v != descripcion:
                        entidad = v
                        break
                if not entidad:
                    entidad = candidates[0]

            if not descripcion:
                descripcion = objeto or (values[-1] if values else "")
            if not entidad:
                entidad = values[0] if values else ""
            if not objeto:
                objeto = "Consultoría de Obra"

            tipo = nro_sel.split("-")[0].strip() if "-" in nro_sel else ""
            return {
                "nomenclatura": nro_sel,
                "descripcion": descripcion,
                "entidad": entidad,
                "tipo": tipo,
                "objeto": objeto,
                "estado": "",
                "monto_referencial": "",
                "fecha_convocatoria": fecha,
            }

        padded = cells + [""] * (10 - len(cells))
        return {
            "nomenclatura": padded[0],
            "descripcion": padded[1],
            "entidad": padded[2],
            "tipo": padded[3],
            "objeto": padded[4],
            "estado": padded[5],
            "monto_referencial": self._clean_money(padded[6]),
            "fecha_convocatoria": padded[7],
        }

    def search(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        descripcion = (filters.get("descripcion") or "supervision").strip()
        entidad = (filters.get("entidad") or "").strip()
        anio = (filters.get("anio") or "").strip()
        tipo = (filters.get("tipo") or "").strip()
        objeto = (filters.get("objeto") or "Consultoria de Obra").strip()
        headless = bool(filters.get("headless", True))
        max_pages = int(filters.get("max_pages", 1) or 1)
        max_pages = max(1, min(max_pages, 20))
        include_cronograma = bool(filters.get("include_cronograma", False))

        results: List[Dict[str, Any]] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()
            page.set_default_timeout(25000)
            page.set_default_navigation_timeout(35000)

            try:
                self._log_step(1, "Cargando portal público de SEACE")
                page.goto(SEACE_PUBLIC_URL, wait_until="domcontentloaded")
                self._open_procedure_search_tab(page)

                self._log_step(2, "Verificando posible bloqueo por captcha", "warn")
                iframe_captcha = page.locator("iframe[src*='captcha'], iframe[src*='recaptcha']").count() > 0
                text_captcha = page.locator("text=/captcha/i").count() > 0
                captcha_detected = iframe_captcha or text_captcha
                if captcha_detected:
                    self._log_step(
                        2,
                        "Posible CAPTCHA detectado. Se intentará continuar con la búsqueda.",
                        "warn",
                    )

                self._log_step(3, "Completando filtros de búsqueda")
                self._safe_fill(
                    page,
                    [
                        "input[id*='idFormBuscarProceso'][id*='descripcion']",
                        "input[id*='descripcion']",
                        "input[name*='descripcion']",
                        "input[placeholder*='descrip']",
                    ],
                    descripcion,
                )
                self._safe_fill(
                    page,
                    [
                        "input[id*='entidad']",
                        "input[name*='entidad']",
                        "input[placeholder*='entidad']",
                    ],
                    entidad,
                )
                self._safe_select(
                    page,
                    [
                        "select[id*='idFormBuscarProceso'][id*='anioConvocatoria']",
                        "select[id*='anio']",
                        "select[name*='anio']",
                    ],
                    anio,
                )
                self._safe_select(
                    page,
                    [
                        "select[id*='idFormBuscarProceso'][id*='tipoSeleccion']",
                        "select[id*='tipo']",
                        "select[name*='tipo']",
                    ],
                    tipo,
                )
                self._safe_select(
                    page,
                    [
                        "select[id*='idFormBuscarProceso'][id*='objetoContratacion']",
                        "select[id*='objeto']",
                        "select[name*='objeto']",
                    ],
                    objeto,
                )

                self._log_step(4, "Ejecutando búsqueda (botón Buscar)")
                clicked = self._click_first_visible(
                    page,
                    [
                        "button[id*='idFormBuscarProceso'][id*='btnBuscar']",
                        "form[id*='idFormBuscarProceso'] button:has-text('Buscar')",
                        "button:has-text('Buscar')",
                        "input[value='Buscar']",
                        "a:has-text('Buscar')",
                    ],
                )
                if not clicked:
                    raise RuntimeError("No se encontró el botón de búsqueda 'Buscar'.")

                self._log_step(5, "Esperando tabla de resultados")
                try:
                    page.wait_for_selector("table tbody tr", timeout=15000)
                except PlaywrightTimeoutError:
                    self._log_step(
                        5,
                        "No aparecieron filas en la tabla dentro del tiempo esperado.",
                        "warn",
                    )

                current_page = 1
                while current_page <= max_pages:
                    self._log_step(
                        6, f"Extrayendo filas de resultados en página {current_page}"
                    )
                    rows = self._result_rows_locator(page)
                    row_count = rows.count()
                    if row_count == 0:
                        break

                    self._log_step(7, f"Tabla detectada con {row_count} filas", "success")
                    for i in range(row_count):
                        row = rows.nth(i)
                        cells = row.locator("td")
                        text_cells = []
                        for j in range(cells.count()):
                            text_cells.append(cells.nth(j).inner_text().strip())
                        if any(text_cells):
                            self._log_step(8, f"Parseando fila {i + 1} de la página {current_page}")
                            parsed = self._parse_row(text_cells)
                            parsed["accion_refs"] = self._collect_action_refs(row)
                            if self._is_valid_result_row(parsed):
                                if include_cronograma:
                                    parsed["cronograma"] = self._extract_row_schedule(page, row)
                                results.append(parsed)

                    self._log_step(9, "Gestionando paginación")
                    next_button = page.locator(
                        "a:has-text('Siguiente'), button:has-text('Siguiente'), "
                        "a[aria-label*='next'], a.ui-paginator-next"
                    ).first
                    can_go_next = next_button.count() > 0 and not (
                        "disabled" in ((next_button.get_attribute("class") or "").lower())
                    )
                    if not can_go_next or current_page >= max_pages:
                        break

                    next_button.click()
                    page.wait_for_timeout(1500)
                    current_page += 1

                self._log_step(
                    10,
                    f"Sincronizando {len(results)} resultados en memoria",
                    "sync",
                )
                return results
            finally:
                context.close()
                browser.close()
