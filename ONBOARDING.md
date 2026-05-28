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
| AI / LLM | OpenRouter (`OPENROUTER_API_KEY`) — Nemotron for synthesis and parse_om |
| Browser automation | Browserbase + Stagehand — **only** `deed_lookup` and `tax_lookup` still use this |
| PDF generation | WeasyPrint + Jinja2 |
| Email delivery | Resend (`noor@nidoandkey.com`) |
| Database | Supabase (`nbbpykkxgrarlkuytare.supabase.co`) |
| Landing page | Static HTML on Vercel (`nidoandkey.com`) |
| Property data | ATTOM API (primary), Bexar County ArcGIS (fallback), Census ACS5, SA Open Data |

---

## Repo Layout

```
server.py                  — FastAPI app. /analyze (SSE stream), /export (PDF), /health
scanner/
  scan_bexar.py            — Monthly ATTOM scan. Run: python3 scanner/scan_bexar.py --dry-run
  score.py                 — Motivation scoring logic (year-built, hold period, tax burden)
skills/
  parse_om/run.py          — PDF extraction via LLM (OpenRouter/Nemotron)
  owner_lookup/run.py      — Owner name + mailing address via ATTOM expandedprofile.
                             Falls back to Bexar County ArcGIS. NO Browserbase.
  tax_lookup/run.py        — BCAD tax delinquency via Stagehand (still uses Browserbase)
  deed_lookup/run.py       — Bexar County Clerk lien/UCC records via Stagehand + regex.
                             Finds mechanics liens and UCC lender filings by address.
  comps_lookup/run.py      — Census + ATTOM comps
  underwrite/run.py        — NOI/cap rate math
  violations_lookup/run.py — SA Open Data code violations
  permit_lookup/run.py     — Building permits
  maturity_estimator/run.py— Loan maturity pressure estimate
  synthesize_analysis/run.py — Pre-synthesis skill
reports/
  generate.py              — WeasyPrint renderer. build_om_context() + render_pdf()
  deliver.py               — Resend email delivery. send_monthly_report() + send_om_report()
  templates/
    om_analysis.html       — Single OM analysis PDF template
    monthly_report.html    — Monthly motivated seller list template
landing/
  index.html               — Marketing site (nidoandkey.com)
  api/submit.py            — Vercel serverless: form → Resend email + Supabase log
  assets/sample-memo.pdf   — Sample analysis PDF attached to form submissions
start.sh                   — Start server with DYLD_LIBRARY_PATH set (required for WeasyPrint)
scripts/
  eval.py                  — Skill evaluator. Run constantly. Never claim a skill works without it.
```

---

## Environment Variables

All in `.env` at root. Never commit this file.

```
OPENROUTER_API_KEY         — LLM (parse_om, synthesize_analysis)
RESEND_API_KEY             — Email delivery
BROWSERBASE_API_KEY        — Stagehand browser automation (deed_lookup, tax_lookup only)
MODEL_API_KEY              — OpenAI key used by Stagehand sessions (gpt-4o-mini)
ATTOM_API_KEY              — Property data: owner, lender, appraised value, bulk queries
CENSUS_API_KEY             — ACS5 market rent benchmarks
SUPABASE_SERVICE_ROLE_KEY  — Supabase admin access
SUPABASE_URL               — https://nbbpykkxgrarlkuytare.supabase.co
HUD_API_TOKEN              — HUD SAFMR fair market rents (optional, comps_lookup)
```

Vercel env vars (set via `vercel env add` or dashboard):
- `RESEND_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`

---

## How to Start the Server

```bash
./start.sh
# NOT: python3 -m uvicorn server:app
# WeasyPrint needs DYLD_LIBRARY_PATH=/opt/homebrew/lib on macOS or PDF export silently fails
```

**Always use `.venv/bin/python3`, never `python3`.** System Python is 3.9 and missing all deps.

Server runs at `http://localhost:8000`. UI at `/`, health at `/health`.

---

## Running Evals — Do This First Every Session

```bash
.venv/bin/python3 scripts/eval.py              # all skills
.venv/bin/python3 scripts/eval.py owner_lookup # just owner_lookup
.venv/bin/python3 scripts/eval.py deed_lookup  # just deed_lookup
```

Never claim a skill "works" without a passing eval. We burned 2+ sessions on this.

---

## How to Run the Scanner

```bash
# Dry run (score only, no pipeline, no PDF)
.venv/bin/python3 scanner/scan_bexar.py --dry-run

# Full run, top 5, save PDF, no email
.venv/bin/python3 scanner/scan_bexar.py --top 5 --no-email --output /tmp/test.pdf

# Production run (emails all active subscribers)
.venv/bin/python3 scanner/scan_bexar.py --top 20
```

ATTOM query: `assessment/snapshot` with `geoid=CO48029` (Bexar County FIPS). Returns ~1,500 apartment properties.

---

## Supabase Tables

- `pipeline_runs` — logs every OM analysis and scanner run (type, verdict, elapsed, skill results)
- `subscribers` — email list for monthly scanner report (email, active bool)
- `contacts` — landing page form submissions

---

## What's Verified Working (Current State)

| Skill | Status | Notes |
|---|---|---|
| `parse_om` | Working | Extracts address, units, year_built, asking_price from 9 OMs. Loan fields always null — normal, OMs don't have them. |
| `owner_lookup` | Working, 2/2 eval | ATTOM API primary (~200ms, structured JSON). ArcGIS fallback. Returns: owner_name, owner_address, owner_state, out_of_state, absentee_owner, corporate_owner, appraised_value, attom_lender, attom_loan_amount, attom_loan_date. No Browserbase. |
| `deed_lookup` | Working, 3/4 eval | Bexar County Clerk via Stagehand + regex. Finds mechanics liens and UCC lender filings by property address. NOT full TX — Bexar County only. |
| `tax_lookup` | Working | BCAD Stagehand. Checks tax delinquency. |
| `comps_lookup` | Partial | Census ACS works. HUD ZIP rents need token verification. |
| `underwrite` | Working | NOI/cap rate math from OM data. |
| `violations_lookup` | Working | SA Open Data. |
| `/export` endpoint | Working | POST /export → WeasyPrint PDF → optional Resend email. |
| PDF template | Working | Shows ATTOM lender, loan amount, appraised value, absentee flag, mechanics liens, distress signals. |
| "Get the Full Memo" button | Working | In IngestionView.tsx, calls /export, downloads PDF. |
| Email delivery (Resend) | Code done | **Needs verified sender domain in Resend dashboard before use.** |
| Scanner (scan_bexar.py) | Built, not run live | Code exists, needs first run against real ATTOM data. |
| Landing page | Live | nidoandkey.com on Vercel. |

---

## Critical Technical Lessons (Hard-Won)

### owner_lookup: Use ATTOM, not Browserbase/BCAD

`owner_lookup` was rewritten from Stagehand/BCAD scraping to ATTOM API. The ATTOM `expandedprofile` endpoint returns everything in one call:
- `assessment.owner.owner1.fullName` — owner name
- `assessment.owner.mailingAddressOneLine` — mailing address (detect out-of-state)
- `assessment.owner.absenteeOwnerStatus` — "A" = absentee
- `assessment.owner.corporateIndicator` — "Y" = LLC/corporation
- `assessment.market.mktTtlValue` — appraised value
- `assessment.mortgage.FirstConcurrent` — original lender, amount, date

Endpoint: `GET https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/expandedprofile`
Params: `address1=<street>`, `address2=<city, TX zip>`

**If ATTOM misses a property**, fall back to Bexar County ArcGIS:
`GET https://maps.bexar.org/arcgis/rest/services/Parcels/MapServer/0/query`
Field name is `Situs` (not `SITEADDR`). Query: `Situs LIKE '%14900%NACOG%'`

### deed_lookup: Bexar County Clerk does NOT index all doc types by address

When searching `bexar.tx.publicsearch.us` by property address:
- **DOES appear**: mechanics liens, UCC filings, releases, waivers, affidavits
- **DOES NOT appear**: Deeds of Trust, Assignments of Deed of Trust

These are indexed differently in this system (by grantor/grantee name, not address). Do not expect to find DTs or assignment chains via address search.

The real distress signal is mechanics liens (unpaid contractors) and UCC filings (lender continuation statements). These DO appear by address.

### deed_lookup: Use regex on raw accessibility tree, not LLM extraction

`session.extract()` with no args returns `{"pageText": "..."}` — the raw accessibility tree text. Cell values follow the pattern `cell: VALUE`. Parse with:
```python
cell_values = re.findall(r"cell: ([^\n\\]+)", page_text)
```
Each row = 14 cells: `[checkbox, menu, status, grantor, grantee, doc_type, date, ...]`

LLM-based schema extraction (`session.extract(schema={...})`) is nondeterministic for counting. Use regex for counts — it's deterministic and faster.

### networkidle never resolves on bexar.tx.publicsearch.us

The site fires continuous analytics requests. `waitUntil: "networkidle"` times out at 30s. Use:
```python
await session.navigate(url=url)
await asyncio.sleep(5)
```

### Stagehand extract() always returns {"extraction": "freeform text"}

Schema params are effectively ignored. The result is always a freeform text blob. Parse key:value lines manually. See `_parse_extraction_blob()` in `skills/owner_lookup/run.py` for the pattern (though that skill no longer uses Stagehand).

### BROWSERBASE_SKILLS in server.py

```python
BROWSERBASE_SKILLS = {"tax_lookup", "portfolio_crawler"}
```

Skills in this set run as subprocesses (isolated event loop — Stagehand asyncio conflicts with FastAPI). `owner_lookup` was removed from this set when it was rewritten to use httpx (synchronous, no event loop issues). Don't add synchronous HTTP skills back to this set.

### OMs never contain loan data

Tested 9 real OMs — 0/9 have loan terms in the PDF. Loan data always comes from external sources:
- Origination lender + amount: ATTOM `assessment.mortgage.FirstConcurrent`
- Current servicer / UCC continuation: Bexar County Clerk (`deed_lookup`)

### Demo OM addresses are fictional

`culebra_om.pdf` → "2455 Culebra Rd" — no ATTOM or county records
`blanco_om.pdf` → "7821 Blanco Rd" — no ATTOM or county records
`mccullough_om.pdf` → "4123 McCullough Ave" — no ATTOM or county records

Use `14900 Nacogdoches Rd` (San Antonio, TX 78247) for real data testing.

---

## Skill Pipeline Flow (server.py)

```
parse_om          → extracts address, units, year_built, asking_price from PDF
owner_lookup      → ATTOM: owner name, mailing address, absentee flag, lender info
deed_lookup       → Bexar County Clerk: mechanics liens, UCC filings
tax_lookup        → BCAD: tax delinquency (Stagehand)
violations_lookup → SA Open Data: open code violations
comps_lookup      → Census: market rents by ZIP
underwrite        → NOI, cap rate, price/unit math from OM data
maturity_estimator→ Loan pressure (uses origination_date + 5yr estimate)
synthesize_analysis → Builds structured prompt
[LLM synthesis]   → 7-section analysis, PURSUE/WATCHLIST/PASS verdict
```

Key context fields wired between skills in server.py (lines ~258-290):
- `owner_lookup` → ctx: `owner_name`, `attom_lender`, `attom_loan_amount`, `attom_loan_date`, `absentee_owner`, `corporate_owner`, `attom_id`, `apn`
- `deed_lookup` → ctx: `deed_maturity_date` (origination + 5yr), `loan_distress_signals`, `loan_assignments`

---

## What's Left To Do

- [ ] **Verify Resend sender domain** — `resend.com/domains`, verify `noor-acq.com` DNS. Required before any email sends. (~10 min)
- [ ] **Add first subscriber** — `INSERT INTO subscribers (email, firm) VALUES ('your@email.com', 'Noor Acquisitions');` in Supabase
- [ ] **Run scanner live** — `scanner/scan_bexar.py --dry-run` first, confirm top 20 list, then full run
- [ ] **First client outreach** — warm emails, attach `landing/assets/sample-memo.pdf`
- [ ] **Server hosting** — currently local only; needs deployment (Railway, Fly, etc.) for clients to use `/analyze`
- [ ] **Scanner routine** — schedule monthly run once subscriber list exists

---

## Brand / Product Details

- **Brand:** Nido & Key ("nido" = nest in Spanish)
- **Domain:** nidoandkey.com
- **Email:** noor@nidoandkey.com (Google Workspace + Resend)
- **Target client:** Multifamily syndicators and PE acquisitions teams in Texas
- **Pricing:** $4,000/month retainer (4 OMs + weekly motivated seller list) or $500/memo one-off
- **Score never shown to clients** — internal only. Clients see "signals," not numbers.
- **PDF style:** Navy `#1e3a5f` + near-black `#1a1a1a`, amber for flags, 2 pages max, methodology footnote on every report

---

## Git / Deploy

- Repo: `github.com/gurnoornatt/yard`
- Branch: `main`
- Landing page deploys from `landing/` automatically to Vercel on push
- Server (`server.py`) is not on Vercel — runs locally or needs separate hosting
