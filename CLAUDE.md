# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```powershell
streamlit run app.py
```

App runs on `http://localhost:8501`. No build step required. Streamlit Community Cloud redeploys automatically on every push to `main` at `generadordecertificados.streamlit.app`.

## Database

PostgreSQL on Supabase. Connection string in `.streamlit/secrets.toml` (not committed) under key `DATABASE_URL`. For local dev, set the env var instead:

```powershell
$env:DATABASE_URL = "postgresql://..."
streamlit run app.py
```

Schema is initialized idempotently at startup via `database/init_db.py:init_db()`. New columns are added with `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` in that same function — this is the migration strategy.

## Architecture

**Entry point:** `app.py` shows an office selector (Guayaquil/master, Portoviejo, Loja, Cuenca), stores `oficina_id`/`oficina_nombre`/`oficina_rol` in `st.session_state`, then routes to a sidebar module. No login at startup — auth is handled inside individual modules via `auth/login.py:obtener_sesion()`.

**Office roles:**
- `master` (Guayaquil) — sees all modules including Dashboard DRAC
- `regional` — same modules minus dashboard DRAC

**Module routing (app.py sidebar):**
- `cap_carga` → `modules/capacitaciones/upload.py` — bulk upload from Google Forms CSV/Excel
- `cap_certificados` → `modules/capacitaciones/certificados.py` — generates .docx certificates (ZIP download)
- `cap_virtual` → `modules/capacitaciones/capacitacion_virtual.py` — self-service virtual training + certificate
- `generador_reportes` → `modules/reportes/generador.py` — DRAC reports + Actas de Asambleas Productivas
- `dashboard_drac` → `modules/master/dashboard_drac.py` — master-only, 2025 static + 2026 live data

**Note:** `modules/capacitaciones/dashboard.py`, `modules/master/dashboard_global.py`, and the stubs in `modules/asambleas/` and `modules/convenios/` exist but are **not wired into app.py navigation**.

## Data layer (`database/db.py`)

`get_connection()` is a context manager yielding a `_Conn` wrapper that mimics sqlite3's `.execute(sql, params).fetchone()/fetchall()` API. Rows return as `RealDictRow` (dict-like). Always use `with get_connection() as con:` — it auto-commits on success, rolls back on exception.

Sequential report numbers are stored in `contador_reporte` (starts at 83, next = 84) and `contador_asamblea` (starts at 17, next = 018). Certificate codes (`DRAC-{year}-NNNN`, starting at 1676) use `contador_certificado` (keyed by `year`), incremented atomically by the requested range size via `INSERT ... ON CONFLICT ... DO UPDATE` in `db.py:reservar_rango_codigos_certificado`. All three counters are in Supabase, not local — never reset them, and never derive the next number by counting/deleting rows in the data table (that was the original certificate design and it silently produces duplicate codes if some but not all test rows get deleted before the next one is generated).

Certificate generation must not insert participant or survey rows into `capacitaciones`. Bulk exports are assumed to be pre-validated, remain only in `st.session_state`, and require a linked training report. Codes are reserved as one atomic range only when PDF generation begins; Supabase persists only the tiny `contador_certificado` update and one summary row in `lotes_certificados` (including `numero_reporte_vinculado`). Individual certificates follow the same persistence rule. Existing historical rows in `capacitaciones` are preserved for compatibility but are not fed by active certificate flows.

## PDF generation

Two independent PDF generators using ReportLab:

- `utils/reporte_drac_pdf.py:generar_reporte_drac(...)` — DRAC capacity reports. Every page gets a header drawn via `onPage` callback (logo + blue stripe). The signature table ("ÁREAS Y PERSONAS RESPONSABLES") is drawn at a fixed Y position at the bottom of the last page. Page count is measured twice (full frame + full frame with a spacer simulating the signature area) to decide whether signatures share the last content page or get their own.

- `utils/acta_asamblea_pdf.py:generar_acta_asamblea_pdf(...)` — Assembly minutes. Single-pass build with a fixed frame that reserves header/footer space.

Both share the logo at `assets/image1.png`. User text must be passed through `xml.sax.saxutils.escape()` before embedding in `Paragraph` flowables to prevent silent truncation of text containing `<`, `>`, or `&`.

Certificate `.docx` generation uses `utils/docx_generator.py`, which fills Word template placeholders via XML manipulation and optionally converts to PDF with a LibreOffice subprocess (requires `libreoffice` from `packages.txt`).

### Certificate template (`formato de certificado de asistencia.docx`)

This file **is tracked in git** and must be committed/pushed like any source file — Streamlit Cloud only sees what's pushed to `main`, so a template edited locally but not committed silently keeps serving the old version (this caused a real incident: the deployed cert kept showing "Guayaquil - Ecuador" / "1 Hora" fixed text after the template had supposedly been updated).

Do not hand-edit `«placeholder»` text directly in Word when adding/renaming a placeholder. Word's autocorrect/spellcheck frequently splits the `«`/`»` guillemets and the inner text into separate `<w:r>` XML runs, which breaks plain-text `str.replace()` substitution silently (the placeholder just doesn't get filled, no error). Prefer scripted XML surgery (open the docx as a zip, regex-replace in `word/document.xml`, verify with `xml.dom.minidom.parseString` + exact placeholder counts before/after, keep a `.bak`) over asking the user to retype guillemets in Word. `utils/docx_generator.py:_repair_placeholder_runs()` defragments split placeholders defensively at render time, but a clean template is still preferable.

Placeholder substitution in `docx_generator.py` runs against every zip part matching `word/(document|header\d+|footer\d+)\.xml` — a `.docx` stores page headers/footers as separate parts (`word/header1.xml`, `header2.xml`, `header3.xml`, `footer*.xml`), distinct from `word/document.xml`. Text typed into a Word header (e.g. a running date in the corner) lives in one of those header parts, not the body — a placeholder added there is invisible to substitution logic that only touches `document.xml`. If a placeholder "won't fill in" after confirming the template itself is correct, check `zipfile.namelist()` to see which part it actually lives in before assuming a code or deployment bug. Floating text boxes (`wps:txbx` + legacy `v:shapetype` VML fallback under `mc:Choice`/`mc:Fallback`) legitimately store the same text twice in the XML for Word-version compatibility — a correct renderer shows it once; this duplication is normal and not something to "fix" by deleting one copy.

MERGEFIELD markers (`<w:instrText> MERGEFIELD X </w:instrText>`) are stripped by `_strip_merge_fields()` before substitution — LibreOffice re-evaluates real mail-merge fields at PDF-conversion time and blanks out any substituted value if one slips into the template.

## Key utilities

- `utils/ubicaciones_ec.py` — `PROVINCIAS_CANTONES` dict for chained province→canton dropdowns. Uppercase values throughout.
- `utils/convenios.py` — Static catalog of 20 institutional agreements. `CONTRAPARTES` list and `CONTRAPARTE_NUMEROS` dict are the two derived structures used in the report form.
- `utils/forms_parser.py` — Maps exact Google Forms column headers (including tildes) to internal schema. Column names are brittle — if the Forms structure changes, update this file.

## Per-office config in report generator

`modules/reportes/generador.py` has a `_OFICINA_CFG` dict keyed by `oficina_id` (`"guayaquil"`, `"cuenca"`, `"manabi"`, `"loja"`) with fields `revisado_por`, `area_elaborado`, `nombre_institucion`, `lineas_institucion`. These values appear in PDF headers and signature blocks.

## Git workflow

Always stage specific files — **never `git add .`**. The repo has `.streamlit/secrets.toml` and exploratory scripts (extract_doc*.py, *.pdf, *.docx) that must not be committed. After verified changes: `git add <specific files>` → `git commit` → `git push origin main`.
