# Nido & Key — Agent Onboarding

## What This Is

A real estate acquisitions intelligence tool for multifamily buyers in Texas. Two things:

1. **On-demand OM analysis** — buyer uploads a PDF offering memorandum, pipeline runs in ~60-90s, returns a structured 7-section analysis with PURSUE / WATCHLIST / PASS verdict. Pulls public records the broker didn't include.
2. **Monthly motivated seller scanner** — pulls all 1,270 Bexar County multifamily parcels from ArcGIS (free, no key), scores by seller pressure signals, emails ranked list to subscribers as PDF.

The client never touches software. They upload at the web app. They get a structured analysis back with sourced numbers.

**Business model:** AI-native agency. We use the tool internally and deliver finished intelligence reports. Not SaaS — clients pay for the output, not access. Current pricing: $500/report or $2K/month retainer. Goal: custom workflow integrations at $5K/month once we understand client pain from discovery calls.

**GTM:** OM tool is the door opener. Cold email SA multifamily firms with free report offer. Cold call national firms as research (student script). Convert conversations into custom workflows.

---

## Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI (`server.py`), Python 3.12, uv venv |
| OM parsing | Mistral OCR (`mistral-ocr-latest`) + document_annotation Pydantic schema — primary path |
| LLM synthesis | OpenRouter — Llama 3.3 70B primary, Gemma 4 31B + Llama 3.2 3B fallbacks |
| Browser automation | Browserbase (cloud, REST API) + Playwright CSS selectors — `tax_lookup` only. `deed_lookup` uses Stagehand. |
| PDF generation | WeasyPrint + Jinja2 |
| Email delivery | Resend (`noor@nidoandkey.com`) — domain verified |
| Database | Supabase (`nbbpykkxgrarlkuytare.supabase.co`) |
| App | `app.nidoandkey.com` — Railway, deployed via Dockerfile |
| Landing page | `nidoandkey.com` — static HTML on Vercel |
| Property data | Bexar County ArcGIS (scanner), Census ACS5, SA Open Data, Bexar County Clerk, BCAD, acttax.com |

---

## Repo Layout

```
server.py                  — FastAPI app. /analyze (SSE stream), /export (PDF), /health
Dockerfile                 — Multi-stage: Bun builds UI → Python serves everything
railway.json               — Railway deploy config
scanner/
  scan_bexar.py            — Monthly ArcGIS scan (NOT ATTOM — ATTOM 504s). Run: .venv/bin/python3 scanner/scan_bexar.py --dry-run
  score.py                 — Motivation scoring: out-of-state owner, vintage, improvement ratio, owner type
skills/
  _stagehand.py            — Shared Stagehand client factory (Browserbase or local Chrome)
  parse_om/run.py          — Mistral OCR + Pydantic document_annotation. Returns 15 citations per OM.
  owner_lookup/run.py      — ArcGIS primary (free, full mailing address). ATTOM fallback (often 504s).
  tax_lookup/run.py        — Two sources:
                             (1) BCAD via Browserbase + Playwright → estimated_annual_tax, total_tax_rate
                             (2) acttax.com via pure HTTP POST → real delinquency status, prior_year_due, lawsuits
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
OPENROUTER_API_KEY         — LLM synthesis (Llama 3.3 70B + fallbacks). Add $50 credit to avoid 429s.
BROWSERBASE_API_KEY        — Browserbase cloud browser (tax_lookup, deed_lookup)
BROWSERBASE_PROJECT_ID     — Required for Browserbase REST API session creation
MODEL_API_KEY              — OpenAI key used by Stagehand sessions (gpt-4o-mini)
ATTOM_API_KEY              — owner_lookup fallback (often 504s on SA properties)
CENSUS_API_KEY             — ACS5 market rent benchmarks
SUPABASE_SERVICE_ROLE_KEY  — Supabase admin access
SUPABASE_URL               — https://nbbpykkxgrarlkuytare.supabase.co
RESEND_API_KEY             — Email delivery (nidoandkey.com domain verified)
HUD_API_TOKEN              — HUD SAFMR fair market rents (optional)
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
| `parse_om` | **Working** | Mistral OCR: 15 citations per OM, handles scanned PDFs. Loan fields always null — normal, OMs don't contain loan terms. |
| `owner_lookup` | **Working** | Fixed. ArcGIS primary — returns full owner mailing address (name, street, city, state, zip). ATTOM wrapped in try/except so 504s no longer block ArcGIS fallback. |
| `deed_lookup` | **Working** | Bexar County Clerk via Stagehand + regex. Lien count can overcount due to 14-cell stride parsing bug — verify against county clerk before citing. |
| `tax_lookup` | **Working** | Two sources merged: BCAD (estimated annual tax) + acttax.com (real delinquency status). `delinquent` field is now real bool, not null. No Stagehand — pure Browserbase+Playwright for BCAD, pure httpx for acttax. |
| `violations_lookup` | **Working** | SA Open Data. 15 violations (3 open) confirmed on Rio 1604 via case numbers. |
| `permit_lookup` | **Working** | SA Open Data. |
| `comps_lookup` | **Partial** | Census ACS5 market rents work. ATTOM sale comps return empty — TX non-disclosure state. |
| `underwrite` | **Working** | NOI/cap rate math. Verified $734,763 NOI on Rio 1604. |
| `maturity_estimator` | **Working** | Derived from deed origination date. 53 months to maturity on Rio 1604. |
| `synthesis` | **Working** | 7-section format, PURSUE/WATCHLIST/PASS. temperature=0. 3-model fallback. No chain-of-thought leaking. Rate-limits if all 3 free models hit simultaneously — fix: add $50 OpenRouter credit. |
| Scanner | **Working** | Replaced ATTOM (504s) with Bexar County ArcGIS. 1,270 parcels in 2 seconds, free. Scores: out-of-state owner, vintage, improvement ratio, individual owner. PropID → bcad_prop_id passthrough. |
| App deployment | **Live** | `app.nidoandkey.com` on Railway via Dockerfile. |
| Landing page | **Live** | `nidoandkey.com` on Vercel. |
| Email delivery | **Working** | Resend + nidoandkey.com domain verified. Confirmed live send. |

---

## Critical Technical Lessons

### owner_lookup: ArcGIS is primary, not fallback

ArcGIS fields `AddrLn1/AddrLn2/AddrLn3/AddrCity/AddrSt/Zip` are the owner's mailing address — not the property address. ATTOM 504s on SA properties. Fixed by wrapping ATTOM in try/except so it always falls through to ArcGIS.

Rio @ 1604 ArcGIS result: `RIO @ 1604 LLC, PO BOX 190, DRAPER, UT 84020`

### tax_lookup: Two separate systems

- **BCAD** (`bexar.trueautomation.com`) = appraisal district. Returns estimated annual tax (assessed value × rate). Does NOT report payment status.
- **acttax.com** (`bexar.acttax.com`) = Tax Assessor-Collector. Returns actual delinquency. Direct HTTP POST, no browser needed. Form: `searchby=6&criteria=14900+NACOGDOCHES` → `showlist.jsp` → click first result with market value > $10K → parse `Prior Year(s) Amount Due`.

Delinquent = `Prior Year(s) Amount Due > $0`.

### scanner: ArcGIS, not ATTOM

ATTOM `assessment/snapshot` 504s on our plan tier (confirmed: 0 hits in dashboard despite 20+ calls). Replaced with `maps.bexar.org/arcgis/rest/services/Parcels/MapServer/0/query`.

MultifamilyPropUse codes: `800, 801, 810, 814, 815, 817, 820, 8100, 8105` = 1,270 properties.

ArcGIS `Zip` field = owner mailing ZIP, NOT property ZIP. Property ZIP not available from ArcGIS export.

### deed_lookup: Lien count can overcount

14-cell stride parser goes out of sync when accessibility tree has extra cells. Real count = what you see on `bexar.tx.publicsearch.us`. Verify before citing. Rio @ 1604 = 6 real liens (we reported 11 at one point).

### parse_om: Mistral OCR document_annotation

`resp.document_annotation` returns a JSON string, not a typed object:
```python
raw = json.loads(resp.document_annotation)
extraction = OMExtraction.model_validate(raw)
```

### Synthesis: free tier rate limits

3-model fallback: `["meta-llama/llama-3.3-70b-instruct:free", "google/gemma-4-31b-it:free", "meta-llama/llama-3.2-3b-instruct:free"]`. If all 3 rate-limit simultaneously, synthesis fails. Fix: add $50 to OpenRouter account.

### BROWSERBASE_SKILLS subprocess isolation

```python
BROWSERBASE_SKILLS = {"tax_lookup", "portfolio_crawler"}
```
These run as subprocesses (isolated event loop). Don't add synchronous HTTP skills to this set.

### OMs never contain loan data

0/9 tested OMs have loan terms. Loan data comes from deed_lookup (Bexar County Clerk).

### Test address for real data

`14900 Nacogdoches Rd, San Antonio, TX 78247` (Rio @ 1604). Do not test against demo OM addresses — those are fictional.

---

## Supabase Tables

- `pipeline_runs` — every OM analysis + scanner run
- `om_analyses` — structured OM data (feeds prior-deal context into synthesis)
- `subscribers` — email list for monthly scanner report
- `contacts` — landing page form submissions

---

## Verified E2E Run — Rio @ 1604 (14900 Nacogdoches Rd)

Reference numbers. Investigate if a future run diverges significantly.

| Field | Value | Source |
|---|---|---|
| Units | 132 | Mistral OCR |
| Year built | 1984 | Mistral OCR |
| Occupancy | 95% | Mistral OCR |
| In-place revenue | $1,988,946/yr | Mistral OCR |
| NOI | $734,763 | Calculated |
| Broker cap rate | 6.25% | Mistral OCR |
| Offering structure | Free and Clear | Mistral OCR |
| Owner | RIO @ 1604 LLC, PO Box 190, Draper UT 84020 | ArcGIS |
| Lender | Ready Capital Mortgage Financing 2021-FL7 LLC | Bexar County Clerk |
| Mechanics liens | 6 (real) | Bexar County Clerk (verified on site) |
| Origination date | 10/14/2025 | Bexar County Clerk |
| Loan maturity | 2030-10-14 (53 months) | Derived |
| Estimated annual tax | $341,130.35 | BCAD |
| Actual 2025 levy | $323,115.06 | acttax.com (paid current) |
| Delinquent | false | acttax.com |
| Active lawsuits | None | acttax.com |
| Open violations | 3 | SA Open Data (case 1020492909 confirmed) |
| Verdict | WATCHLIST | No asking price → can't run cap rate at ask |

---

## What's Left To Do

**Product:**
- [ ] Fix deed_lookup lien count parsing bug (14-cell stride goes out of sync)
- [ ] Add $50 OpenRouter credit (synthesis 429s under load)
- [ ] Expand public records to Harris County (Houston) + Travis County (Austin) — same TrueAutomation platform, likely one-line URL change per county. Required before most TX firms will pay.
- [ ] Run scanner full run end-to-end with PDF + email delivery

**GTM (priority over building right now):**
- [ ] Build 50-person outreach list: Origami.chat query + Apollo free tier for emails
- [ ] Set up EDGAR Form D alerts at `efts.sec.gov` (free — TX RE fund closings = dry powder signal)
- [ ] Send 5 cold emails/day to SA multifamily firms (free OM analysis offer)
- [ ] Run 15 research calls/day to national firms (student script — learn pain, don't pitch)
- [ ] First paying client: target week 3-4

---

## Deployment

- **App**: `app.nidoandkey.com` → Railway, auto-deploys on push to `main`
- **Landing**: `nidoandkey.com` → Vercel, auto-deploys on push to `main` from `landing/`
- **Dockerfile**: Stage 1 = Bun builds React UI. Stage 2 = Python + FastAPI serves both API and `ui/dist/`
- **Repo**: `github.com/gurnoornatt/yard`, branch `main`

To deploy: `git push origin main` — Railway builds and deploys (~5 min).

All env vars must be set in Railway dashboard Variables.

---

## Brand / Product

- **Brand:** Nido & Key ("nido" = nest in Spanish)
- **Email:** noor@nidoandkey.com (domain verified on Resend)
- **Target client:** 1-20 person multifamily acquisitions shops in Texas. Not Greystar. The overworked team with no Leni seat.
- **Pricing now:** $500/report one-off or $2K/month retainer
- **Pricing goal:** $5K/month custom workflow integrations per client
- **Differentiation:** V7 and Leni process the broker's story. We check if the broker's story has holes — pulling county records the broker doesn't control.
