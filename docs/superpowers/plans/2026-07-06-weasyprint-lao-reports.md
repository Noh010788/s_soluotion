# WeasyPrint Lao Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the custom quotation, delivery slip, and invoice PDFs with correct Lao shaping while leaving all other Odoo reports on wkhtmltopdf.

**Architecture:** Extend `ir.actions.report._run_wkhtmltopdf` and dispatch only the three custom report names to a focused WeasyPrint renderer. Build a local Odoo image containing WeasyPrint/Pango/HarfBuzz, preserve Odoo paper-format margins, and merge multiple rendered bodies with `pypdf`.

**Tech Stack:** Odoo 18, Python, WeasyPrint, Pango/HarfBuzz, pypdf, Docker Compose.

---

### Task 1: Add renderer dispatch tests

**Files:**
- Create: `custom_addon/sale_quotation_ss_report/tests/test_report_renderer.py`
- Modify: `custom_addon/sale_quotation_ss_report/tests/__init__.py`

- [ ] Write tests proving the three custom report names select WeasyPrint and unrelated reports select wkhtmltopdf.
- [ ] Run the tests and verify failure because the renderer does not exist.

### Task 2: Implement the scoped WeasyPrint renderer

**Files:**
- Create: `custom_addon/sale_quotation_ss_report/models/ir_actions_report.py`
- Modify: `custom_addon/sale_quotation_ss_report/models/__init__.py`

- [ ] Add `_is_weasyprint_report()` with the exact custom report-name allowlist.
- [ ] Add `_run_weasyprint()` that renders each prepared HTML body with Odoo's base URL and paper margins.
- [ ] Merge multi-body output with `pypdf.PdfReader` and `PdfWriter`.
- [ ] Override `_run_wkhtmltopdf()` so only allowlisted reports use WeasyPrint and all others call `super()`.
- [ ] Run unit tests and verify they pass.

### Task 3: Add the local runtime dependency

**Files:**
- Create: `Dockerfile`
- Modify: `docker-compose.yml`

- [ ] Build from `odoo:18.0`.
- [ ] Install `python3-weasyprint`, Pango, and HarfBuzz support from Debian packages.
- [ ] Configure the Odoo service to build and use the local image.
- [ ] Rebuild and start the local Odoo container.

### Task 4: Verify real reports

**Files:**
- Verify: `tmp/pdfs/ss_quote_weasyprint.pdf`
- Verify: `tmp/pdfs/ss_quote_weasyprint.png`

- [ ] Upgrade `sale_quotation_ss_report`.
- [ ] Render S00033 through the normal Odoo report API.
- [ ] Confirm logs show WeasyPrint dispatch rather than wkhtmltopdf for the custom report.
- [ ] Render the PDF to PNG and visually inspect Lao headings, totals, and signatures.
- [ ] Verify module state, HTTP 200, tests, and local-only git status.

