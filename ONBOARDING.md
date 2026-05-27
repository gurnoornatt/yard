# Nido & Key — Agent Onboarding

## What This Is

A real estate acquisitions intelligence product for multifamily buyers in San Antonio, TX. Two things:

1. **On-demand OM analysis** — buyer uploads a PDF offering memorandum, pipeline runs in ~3-5 min, returns a structured 7-section analysis with PURSUE / WATCHLIST / PASS verdict and a downloadable PDF report
2. **Monthly motivated seller scanner** — ATTOM bulk query of all Bexar County apartments, scores properties by seller pressure signals, emails ranked list to subscribers as a PDF

The client never touches software. They email an OM or upload it at the web app. They get a PDF back.

---

## Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI (`server.py`), Python 3.12, uv venv |
| AI | NVIDIA Nemotron (`nvidia/nemotron-3-super-120b-a12b`) via OpenAI-compatible API |
| Browser automation | Browserbase + Stagehand (for BCAD scraping) |
| PDF generation | WeasyPrint + Jinja2 |
| Email delivery | Resend (`noor@nidoandkey.com`) |
| Database | Supabase (`nbbpykkxgrarlkuytare.supabase.co`) |
| Landing page | Static HTML on Vercel (`nidoandkey.com`) |
| Data sources | ATTOM API, Bexar County Appraisal District (BCAD), Census ACS5, SA Open Data |

---

## Repo Layout

```
server.py                  — FastAPI app. /analyze (SSE), /export (PDF), /admin (dashboard)
scanner/
  scan_bexar.py            — Monthly ATTOM scan. Run: python3 scanner/scan_bexar.py --dry-run
  score.py                 — Motivation scoring logic (year-built, tax burden, hold period)
skills/
  parse_om/run.py          — PDF extraction via Nemotron
  owner_lookup/run.py      — BCAD owner via Stagehand/Browserbase
  tax_lookup/run.py        — BCAD tax status via Stagehand
  deed_lookup/run.py       — Deed/loan records
  comps_lookup/run.py      — Census + ATTOM comps
  underwrite/run.py        — NOI/cap rate math
  violations_lookup/run.py — SA Open Data code violations
  permit_lookup/run.py     — Building permits
  maturity_estimator/run.py— Loan maturity pressure estimate
  synthesize_analysis/run.py — Pre-synthesis skill (feeds into Nemotron)
reports/
  generate.py              — WeasyPrint renderer. build_om_context() + render_pdf()
  deliver.py               — Resend email delivery. send_monthly_report() + send_om_report()
  templates/
    om_analysis.html       — Single OM analysis PDF template
    monthly_report.html    — Monthly motivated seller list template
landing/
  index.html               — Marketing site (nidoandkey.com)
  privacy.html             — Privacy policy
  favicon.svg              — Stacked docs icon with terracotta pin
  og-image.png             — Link preview image for iMessage/social
  api/submit.py            — Vercel serverless function: form → Resend email + Supabase log
  assets/sample-memo.pdf   — Sample analysis PDF attached to form submissions
  vercel.json              — Vercel config (cleanUrls: true)
start.sh                   — Start server with DYLD_LIBRARY_PATH set (required for WeasyPrint)
.claude/agents/
  sentinel-runner.md       — Sub-agent: runs/validates pipeline (model: sonnet)
  sentinel-monitor.md      — Sub-agent: checks Supabase pipeline_runs (model: haiku)
```

---

## Environment Variables

All in `.env` at root. Never commit this file.

```
NVIDIA_API_KEY             — Nemotron (LLM for synthesis)
RESEND_API_KEY             — Email delivery
BROWSERBASE_API_KEY        — Stagehand browser automation (BCAD scraping)
ATTOM_API_KEY              — Property data bulk queries
CENSUS_API_KEY             — ACS5 market rent benchmarks
SUPABASE_SERVICE_ROLE_KEY  — Supabase admin access
SUPABASE_URL               — https://nbbpykkxgrarlkuytare.supabase.co
HUD_API_TOKEN              — HUD SAFMR fair market rents (optional)
```

Vercel env vars (set via `vercel env add` or dashboard):
- `RESEND_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`

---

## How to Start the Server

```bash
./start.sh
# NOT: python3 -m uvicorn server:app
# WeasyPrint needs DYLD_LIBRARY_PATH=/opt/homebrew/lib on macOS or PDF export fails
```

Server runs at `http://localhost:8000`. UI at `/`, admin at `/admin`, health at `/health`.

---

## How to Run the Scanner

```bash
# Dry run (score only, no pipeline, no PDF)
python3 scanner/scan_bexar.py --dry-run

# Full run, top 5, save PDF, no email
python3 scanner/scan_bexar.py --top 5 --no-email --output /tmp/test.pdf

# Production run (emails all active subscribers)
python3 scanner/scan_bexar.py --top 20
```

ATTOM query: `assessment/snapshot` with `geoid=CO48029` (Bexar County FIPS). Returns ~1,500-1,972 apartment properties. Two-pass scoring: initial score → enrich top 2N with sale dates → rescore.

---

## Supabase Tables

- `pipeline_runs` — logs every OM analysis and scanner run (type, verdict, elapsed, skill results)
- `subscribers` — email list for monthly scanner report (email, active bool)
- `contacts` — landing page form submissions

---

## What's Verified Working

- ATTOM bulk query returns ~1,500 Bexar County apartments
- parse_om extracts correct fields from real OMs (verified zero hallucination on 3 demo OMs)
- owner_lookup and tax_lookup work via Stagehand on real BCAD addresses
- Full OM pipeline runs end-to-end: ~3-5 min, 7/9 sources typically return data
- PDF export via `/export` endpoint: ~60KB output, WeasyPrint renders correctly
- Resend sends from `noor@nidoandkey.com` (domain verified)
- Landing page form (`/api/submit`) sends sample PDF via Resend
- `nidoandkey.com` is live on Vercel, DNS fully configured

---

## Known Limitations

- `deed_lookup` returns errors on most properties (BCAD deed records not reliably structured)
- `maturity_estimator` returns `data_unavailable` when deed_lookup fails (no loan date = no estimate)
- ATTOM `assessment/snapshot` does not include unit count — `units` field is always null from scanner; mini-pipeline fills it via BCAD
- ATTOM loan origination data not available on our plan — scanner scores on year-built + tax burden instead of loan maturity
- WeasyPrint requires `DYLD_LIBRARY_PATH=/opt/homebrew/lib` on macOS (use `start.sh`)
- `owner_lookup` returns empty fields for demo OM addresses (they're not real BCAD addresses)

---

## Brand / Product Details

- **Brand:** Nido & Key ("nido" = nest in Spanish)
- **Domain:** nidoandkey.com
- **Email:** noor@nidoandkey.com (Google Workspace + Resend)
- **Target client:** Multifamily syndicators and PE acquisitions teams in Texas
- **Pricing:** $4,000/month retainer (4 OMs + weekly motivated seller list) or $500/memo one-off
- **Score never shown to clients** — internal only. Clients see "signals," not numbers.
- **PDF report style:** Navy + off-white, 2 pages max, no clutter, methodology footnote on every report

---

## Git / Deploy

- Repo: `github.com/gurnoornatt/yard`
- Branch: `main` — deploys automatically to Vercel on push
- Landing page deploys from `landing/` directory
- Server (`server.py`) is not on Vercel — runs locally or needs separate hosting (Railway, Fly, etc.)

---

## What's Left

- [ ] First client outreach (warm emails, attach `landing/assets/sample-memo.pdf`)
- [ ] Resend domain — monthly quota is currently on free tier (100 emails/day)
- [ ] Scanner Routine — schedule monthly run via `claude.ai/code/routines` once subscriber list exists
- [ ] Server hosting — currently local only; needs deployment for the `/analyze` endpoint to be client-accessible
