# Nido & Key — Agent Onboarding

## What This Is

A real estate acquisitions intelligence product for multifamily buyers in San Antonio, TX. Two things:

1. **On-demand OM analysis** — buyer uploads a PDF offering memorandum, pipeline runs in ~60-90s, returns a structured 7-section analysis with PURSUE / WATCHLIST / PASS verdict
2. **Monthly motivated seller scanner** — ATTOM bulk query of all Bexar County apartments, scores properties by seller pressure signals, emails ranked list to subscribers as a PDF

The client never touches software. They upload at the web app. They get a structured analysis back with sourced numbers.

---

## Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI (`server.py`), Python 3.12, uv venv |
| OM parsing | Mistral OCR (`mistral-ocr-latest`) + document_annotation Pydantic schema — primary path |
| LLM synthesis | OpenRouter — Llama 3.3 70B primary, Gemma 4 31B + Llama 3.2 3B fallbacks |
| Browser automation | Browserbase (cloud, REST API) + Playwright CSS selectors — `tax_lookup` only. `deed_lookup` uses Stagehand. |
| PDF generation | WeasyPrint + Jinja2 |
| Email delivery | Resend (`noor@nidoandkey.com`) |
| Database | Supabase (`nbbpykkxgrarlkuytare.supabase.co`) |
| App | `app.nidoandkey.com` — Railway, deployed via Dockerfile |
| Landing page | `nidoandkey.com` — static HTML on Vercel |
| Property data | ATTOM API (scanner + owner_lookup), Census ACS5, SA Open Data, Bexar County Clerk, BCAD |

---

## Repo Layout

```
server.py                  — FastAPI app. /analyze (SSE stream), /export (PDF), /health
Dockerfile                 — Multi-stage: Bun builds UI → Python serves everything
railway.json               — Railway deploy config
scanner/
  scan_bexar.py            — Monthly ATTOM scan. Run: .venv/bin/python3 scanner/scan_bexar.py --dry-run
  score.py                 — Motivation scoring logic
skills/
  _stagehand.py            — Shared Stagehand client factory (Browserbase or local Chrome)
  parse_om/run.py          — Mistral OCR + Pydantic document_annotation. Returns 15 citations per OM.
                             Falls back to pdfplumber+LLM if MISTRAL_API_KEY not set.
  owner_lookup/run.py      — ATTOM expandedprofile API (~200ms, no browser). Falls back to Bexar ArcGIS.
  tax_lookup/run.py        — BCAD via Browserbase REST API + Playwright CSS selectors. NO Stagehand AI.
                             Returns estimated_annual_tax + total_tax_rate. Does NOT return delinquency
                             (BCAD is appraisal district, not tax collector).
  deed_lookup/run.py       — Bexar County Clerk via Stagehand + regex. Mechanics liens, UCC filings.
  comps_lookup/run.py      — Census ACS5 market rents. ATTOM sale comps (often empty — TX non-disclosure).
  underwrite/run.py        — NOI/cap rate math from OM data.
  violations_lookup/run.py — SA Open Data code violations.
  permit_lookup/run.py     — SA Open Data building permits.
  maturity_estimator/run.py— Loan maturity pressure from deed origination date + 5yr estimate.
  synthesize_analysis/run.py — Pre-synthesis eligibility check.
  portfolio_crawler/run.py — Owner portfolio via BCAD owner name search (Stagehand). Often unavailable.
reports/
  generate.py              — WeasyPrint renderer.
  deliver.py               — Resend email delivery.
  templates/
    om_analysis.html       — Single OM analysis PDF template
    monthly_report.html    — Monthly motivated seller list template
ui/                        — React + Vite + Tailwind frontend. Built by Dockerfile into ui/dist/.
landing/
  index.html               — Marketing site (nidoandkey.com)
  api/submit.py            — Vercel serverless: form → Resend email + Supabase log
start.sh                   — Start server with DYLD_LIBRARY_PATH set (required for WeasyPrint on macOS)
scripts/
  eval.py                  — Skill evaluator. Run constantly. Never claim a skill works without it.
```

---

## Environment Variables

All in `.env` at root. Never commit this file. Also set all of these in Railway dashboard.

```
MISTRAL_API_KEY            — Mistral OCR for parse_om (primary path). Without this, falls back to pdfplumber.
OPENROUTER_API_KEY         — LLM synthesis (Llama 3.3 70B + fallbacks)
BROWSERBASE_API_KEY        — Browserbase cloud browser (tax_lookup, deed_lookup)
BROWSERBASE_PROJECT_ID     — Required for Browserbase REST API session creation
MODEL_API_KEY              — OpenAI key used by Stagehand sessions (gpt-4o-mini)
ATTOM_API_KEY              — owner_lookup + scanner bulk queries
CENSUS_API_KEY             — ACS5 market rent benchmarks
SUPABASE_SERVICE_ROLE_KEY  — Supabase admin access
SUPABASE_URL               — https://nbbpykkxgrarlkuytare.supabase.co
RESEND_API_KEY             — Email delivery
HUD_API_TOKEN              — HUD SAFMR fair market rents (optional)
NVIDIA_API_KEY             — Legacy, unused in current synthesis path
```

---

## How to Start the Server

```bash
./start.sh
# Sets DYLD_LIBRARY_PATH=/opt/homebrew/lib (WeasyPrint needs this on macOS)
# Then launches uvicorn on :8000
```

**Always use `.venv/bin/python3`, never `python3`.** System Python is 3.9 and missing all deps.

Server at `http://localhost:8000`. UI at `/`, health at `/health`.

---

## Running Evals

```bash
.venv/bin/python3 scripts/eval.py              # all skills
.venv/bin/python3 scripts/eval.py parse_om     # just parse_om
.venv/bin/python3 scripts/eval.py deed_lookup  # just deed_lookup
```

Never claim a skill "works" without a passing eval.

---

## What's Working (Current State — May 2026)

| Skill | Status | Notes |
|---|---|---|
| `parse_om` | **Working** | Mistral OCR path: 15 citations per OM, handles scanned PDFs, no hallucinated loan data. Loan fields always null — normal, OMs don't contain loan terms. Falls back to pdfplumber if no MISTRAL_API_KEY. |
| `deed_lookup` | **Working** | Bexar County Clerk via Stagehand + regex. 11 mechanics liens confirmed on Rio 1604 via session replay. Finds distress signals reliably. |
| `tax_lookup` | **Working** | Rewrote from Stagehand AI to Browserbase REST API + Playwright CSS selectors. No AI in form filling. Returns `estimated_annual_tax` and `total_tax_rate` from BCAD. Does NOT return delinquency — BCAD is the appraisal district, not tax collector. |
| `owner_lookup` | Error | ATTOM expandedprofile returns 504 for SA properties. Pre-existing. Falls back to ArcGIS but that also fails. Needs investigation. |
| `violations_lookup` | **Working** | SA Open Data. 15 violations (3 open) confirmed on Rio 1604. |
| `permit_lookup` | **Working** | SA Open Data. |
| `comps_lookup` | **Partial** | Census ACS5 market rents work. ATTOM sale comps return empty — TX non-disclosure state + ATTOM tier limitation. |
| `underwrite` | **Working** | NOI/cap rate math. Verified $734,763 NOI on Rio 1604. |
| `maturity_estimator` | **Working** | Derived from deed origination date. 53 months to maturity on Rio 1604. |
| `synthesis` | **Working** | 7-section format, PURSUE/WATCHLIST/PASS. temperature=0. 3-model fallback chain (Llama 70B → Gemma 4 31B → Llama 3.2 3B). No chain-of-thought leaking. |
| App deployment | **Live** | `app.nidoandkey.com` on Railway via Dockerfile. |
| Landing page | **Live** | `nidoandkey.com` on Vercel. |
| PDF export | Built | `/export` endpoint exists. WeasyPrint + Jinja2. |
| Email delivery | Built | Resend wired up. Needs verified sender domain. |
| Scanner | Built | ATTOM bulk query + scoring logic exists. Not yet run live. |

---

## Critical Technical Lessons

### parse_om: Mistral OCR document_annotation

`mistral-ocr-latest` with `document_annotation_format=response_format_from_pydantic_model(OMExtraction)` does OCR + structured extraction in one call. Returns citations (page + section) per field.

Key: `resp.document_annotation` returns a JSON string, not a typed object. Parse it:
```python
raw = json.loads(resp.document_annotation)
extraction = OMExtraction.model_validate(raw)
```

Runs in 8-15 seconds. Costs ~$0.05/OM. Handles scanned PDFs (pdfplumber returns 0 chars on those).

### tax_lookup: Browserbase REST + Playwright CSS selectors

BCAD TrueAutomation blocks headless browsers from local IPs after repeated requests. Solution:

1. POST to `https://api.browserbase.com/v1/sessions` with `X-BB-API-Key` header → get `connectUrl`
2. `playwright.chromium.connect_over_cdp(connect_url)` — no local Chrome needed
3. Click `#propertySearchOptions_advanced` — triggers ASP.NET postback (full page reload)
4. After postback: fill `#propertySearchOptions_streetNumber` and `#propertySearchOptions_streetName`
5. Click `#propertySearchOptions_searchAdv` (button ID changes in advanced mode)
6. Click `a[href*='prop_id=']` first result
7. Click "Taxing Jurisdiction" text to expand section
8. Parse `Taxes w/Current Exemptions: $X` and `Total Tax Rate: X`

BCAD returns estimated annual tax based on appraised value × composite rate. It does NOT report whether taxes are actually paid or delinquent. For delinquency you'd need the Bexar County Tax Assessor-Collector (separate system, not yet wired up).

### deed_lookup: Address search only finds certain doc types

On `bexar.tx.publicsearch.us`:
- **Appears by address**: mechanics liens, UCC filings, releases, affidavits
- **Does NOT appear by address**: Deeds of Trust, mortgage assignments

Real distress signal is mechanics liens (unpaid contractors). 11 on Rio 1604 = significant cash flow distress.

### Synthesis: free tier rate limits

`meta-llama/llama-3.3-70b-instruct:free` on OpenRouter/Venice has aggressive rate limits. Server has a 3-model fallback:
```python
["meta-llama/llama-3.3-70b-instruct:free", "google/gemma-4-31b-it:free", "meta-llama/llama-3.2-3b-instruct:free"]
```
Different providers = rate limits don't stack. On 429 or 404, falls through to next model automatically.

### BROWSERBASE_SKILLS subprocess isolation

```python
BROWSERBASE_SKILLS = {"tax_lookup", "portfolio_crawler"}
```

These run as subprocesses (isolated event loop). Stagehand/Playwright asyncio conflicts with FastAPI's event loop. Don't add synchronous HTTP skills to this set.

### OMs never contain loan data

0/9 tested OMs have loan terms. Loan data comes from:
- Current servicer / UCC filings: Bexar County Clerk (`deed_lookup`)
- Original lender + amount: ATTOM `assessment.mortgage.FirstConcurrent` (when owner_lookup works)

### Test address for real data

`14900 Nacogdoches Rd, San Antonio, TX 78247` (Rio @ 1604) — confirmed working across all skills. Do not test against demo OM addresses (culebra_om, blanco_om, mccullough_om) — those are fictional.

---

## Supabase Tables

- `pipeline_runs` — every OM analysis + scanner run (type, verdict, elapsed, skill results)
- `om_analyses` — structured OM data after each analysis (institutional context graph — feeds prior-deal context into synthesis)
- `subscribers` — email list for monthly scanner report
- `contacts` — landing page form submissions

---

## Verified E2E Run — Rio @ 1604 (14900 Nacogdoches Rd)

Reference numbers. If a future run diverges significantly, investigate before assuming it's correct.

| Field | Value | Source |
|---|---|---|
| Units | 132 | Mistral OCR from OM |
| Year built | 1984 | Mistral OCR from OM |
| Occupancy | 95% | Mistral OCR from OM |
| In-place revenue | $1,988,946/yr | Mistral OCR from OM |
| NOI | $734,763 | Calculated ($1,988,946 × 0.95 − $8,748 × 132) |
| Broker cap rate | 6.25% | Mistral OCR from OM |
| Offering structure | Free and Clear | Mistral OCR from OM |
| Lender | Ready Capital Mortgage Financing 2021-FL7 LLC | Bexar County Clerk session replay confirmed |
| Mechanics liens | 11 | Bexar County Clerk session replay confirmed |
| Origination date | 10/14/2025 | Bexar County Clerk |
| Loan maturity | 2030-10-14 (53 months) | Derived |
| Estimated annual tax | $341,130.35 | BCAD session replay confirmed |
| Tax rate | 2.267474% | Bexar County composite |
| Open violations | 3 | SA Open Data |
| Verdict | WATCHLIST | No asking price → can't run cap rate at ask |

---

## What's Left To Do

- [ ] **owner_lookup** — ATTOM 504s on SA properties. Either fix ATTOM endpoint or switch to BCAD scrape
- [ ] **Verify Resend sender domain** — `resend.com/domains`, verify DNS. Required before any email sends
- [ ] **Run scanner live** — `.venv/bin/python3 scanner/scan_bexar.py --dry-run` first, then full run
- [ ] **First client outreach** — warm emails, attach sample memo PDF
- [ ] **Scanner routine** — schedule monthly once subscriber list exists
- [ ] **Tax delinquency** — real delinquency requires Bexar County Tax Assessor-Collector (separate from BCAD). Not yet built.

---

## Deployment

- **App**: `app.nidoandkey.com` → Railway, auto-deploys on push to `main`
- **Landing**: `nidoandkey.com` → Vercel, auto-deploys on push to `main` from `landing/`
- **Dockerfile**: Stage 1 = Bun builds React UI. Stage 2 = Python + FastAPI serves both API and `ui/dist/`
- **Repo**: `github.com/gurnoornatt/yard`, branch `main`

To deploy: `git push origin main` — Railway builds Docker image, deploys automatically (~5 min).

All env vars must be set in Railway dashboard Variables. Local `.env` is not used in production.

---

## Brand / Product

- **Brand:** Nido & Key ("nido" = nest in Spanish)
- **Email:** noor@nidoandkey.com
- **Target client:** Multifamily syndicators and PE acquisitions teams in Texas
- **Pricing:** $4,000/month retainer (4 OMs + weekly motivated seller list) or $500/memo one-off
