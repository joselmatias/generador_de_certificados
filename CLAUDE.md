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

Sequential report numbers are stored in `contador_reporte` (starts at 83, next = 84) and `contador_asamblea` (starts at 17, next = 018). These are in Supabase, not local — never reset them.

## PDF generation

Two independent PDF generators using ReportLab:

- `utils/reporte_drac_pdf.py:generar_reporte_drac(...)` — DRAC capacity reports. Every page gets a header drawn via `onPage` callback (logo + blue stripe). The signature table ("ÁREAS Y PERSONAS RESPONSABLES") is drawn at a fixed Y position at the bottom of the last page. Page count is measured twice (full frame + full frame with a spacer simulating the signature area) to decide whether signatures share the last content page or get their own.

- `utils/acta_asamblea_pdf.py:generar_acta_asamblea_pdf(...)` — Assembly minutes. Single-pass build with a fixed frame that reserves header/footer space.

Both share the logo at `assets/image1.png`. User text must be passed through `xml.sax.saxutils.escape()` before embedding in `Paragraph` flowables to prevent silent truncation of text containing `<`, `>`, or `&`.

Certificate `.docx` generation uses `utils/docx_generator.py`, which fills Word template placeholders via XML manipulation and optionally converts to PDF with a LibreOffice subprocess (requires `libreoffice` from `packages.txt`).

## Key utilities

- `utils/ubicaciones_ec.py` — `PROVINCIAS_CANTONES` dict for chained province→canton dropdowns. Uppercase values throughout.
- `utils/convenios.py` — Static catalog of 20 institutional agreements. `CONTRAPARTES` list and `CONTRAPARTE_NUMEROS` dict are the two derived structures used in the report form.
- `utils/forms_parser.py` — Maps exact Google Forms column headers (including tildes) to internal schema. Column names are brittle — if the Forms structure changes, update this file.

## Per-office config in report generator

`modules/reportes/generador.py` has a `_OFICINA_CFG` dict keyed by `oficina_id` (`"guayaquil"`, `"cuenca"`, `"manabi"`, `"loja"`) with fields `revisado_por`, `area_elaborado`, `nombre_institucion`, `lineas_institucion`. These values appear in PDF headers and signature blocks.

## Git workflow

Always stage specific files — **never `git add .`**. The repo has `.streamlit/secrets.toml` and exploratory scripts (extract_doc*.py, *.pdf, *.docx) that must not be committed. After verified changes: `git add <specific files>` → `git commit` → `git push origin main`.
