# Nido & Key — Sentinel OM Analysis Agent

## Start of every session — do this first

Before writing any code, run the health check and eval suite to surface any pre-existing failures:

```bash
# 1. Start server in background
./start.sh &
sleep 3

# 2. Check all API keys + dependencies
curl -s http://localhost:8000/health | python3 -m json.tool

# 3. Run skill evals to see what's passing
.venv/bin/python3 scripts/eval.py
```

If `/health` shows `"status": "degraded"`, fix those errors before building anything new.
Errors already present will mask the real impact of your changes.

## Python environment — critical

**Always use `.venv/bin/python3`, never `python3`.**
System Python is 3.9 and missing all project deps. The venv is 3.12 with everything installed.

```bash
# Run anything Python
.venv/bin/python3 scripts/eval.py
.venv/bin/python3 -m uvicorn server:app --port 8000

# Install new deps
uv add <package>          # preferred — updates uv.lock
pip install <package>     # fallback inside venv only
```

## Start the server

```bash
./start.sh
# Sets DYLD_LIBRARY_PATH=/opt/homebrew/lib (required for WeasyPrint on macOS)
# Then launches uvicorn on port 8000
```

If WeasyPrint crashes with "cannot find libgobject", run:
```bash
DYLD_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python3 -m uvicorn server:app --port 8000
```

## Run evaluators — do this before claiming anything works

```bash
.venv/bin/python3 scripts/eval.py              # all evals
.venv/bin/python3 scripts/eval.py parse_om     # just parse_om (9 OMs)
.venv/bin/python3 scripts/eval.py deed_lookup  # just deed_lookup (3 addresses)
```

**Rule: build the eval first, run it, then claim the skill works.** We wasted 2 sessions claiming parse_om extracted loan data. It never did. The eval caught it in 30 seconds.

## Skills architecture

Each skill lives at `skills/<name>/run.py` with one required function:

```python
def run(params: dict) -> dict:
    return {
        "job": "<skill_name>",
        "status": "ok" | "error" | "data_unavailable",
        "data": {...} | None,
        "reason": "..."  # only on error/unavailable
    }
```

To add a new skill:
1. Create `skills/<name>/run.py` with `run(params)` function
2. Add eval cases to `scripts/eval.py`
3. Run eval — confirm it PASSes before touching server.py
4. Wire into `server.py` pipeline if needed

## Key technical lessons learned the hard way

### Stagehand extract() returns freeform text, not a structured dict

`session.extract()` always returns `{"extraction": "Key: Value\nKey: Value\n..."}`.
Accessing `resp.data.result.get("grantee")` returns None every time.

**Fix: parse the extraction blob:**
```python
if resp and resp.data and resp.data.result:
    r = resp.data.result
    if isinstance(r, dict) and "extraction" in r:
        return _parse_extraction_blob(str(r["extraction"]))
```

See `skills/deed_lookup/run.py` and `skills/owner_lookup/run.py` for working examples.

### OMs never contain loan data

Tested 9 real OMs — 0/9 have loan terms. parse_om loan fields are correctly null.
Loan/mortgage data always requires external sources (deed_lookup → Bexar County Clerk).

### Demo OM addresses are fictional

culebra_om.pdf → "2455 Culebra Rd" — no Bexar County records
blanco_om.pdf → "7821 Blanco Rd" — no Bexar County records
mccullough_om.pdf → "4123 McCullough Ave" — no Bexar County records

Don't test deed_lookup against these. Use real SA addresses (confirmed: "200 N Main Ave", "100 Dolorosa").

### deed_lookup uses direct URL, not form-filling

Stagehand form-filling is unreliable. Direct URL approach works:
```python
f"https://bexar.tx.publicsearch.us/results?department=RP&propertyAddress={addr}&recordedDateRange=18000101,{today}&searchType=advancedSearch"
```

deed_lookup is Bexar County, TX only. Non-TX returns `data_unavailable`.

### BatchData has $0 balance — do not use

`BATCHDATA_SERVER_SIDE_TOKEN` is in `.env` but wallet is empty. Will return 403.

## Project structure

```
skills/          — one dir per skill, each with run.py
scanner/         — scan_bexar.py (ATTOM bulk query), score.py (motivation scoring)
reports/         — generate.py (WeasyPrint PDF), deliver.py (Resend email)
reports/templates/ — monthly_report.html, om_analysis.html (Jinja2)
scripts/         — eval.py (skill evaluator — run this constantly)
server.py        — FastAPI: POST /analyze (SSE stream), POST /export (PDF download)
ui/              — React frontend (bun)
landing/         — Vercel-hosted landing page
demo_oms/        — 3 demo OMs (fictional SA addresses, real OM format)
OM/              — real OMs from clients (mixed quality)
models/          — additional OMs for testing
.env             — API keys (never commit)
```

## API keys in .env

| Key | Used by | Notes |
|-----|---------|-------|
| OPENROUTER_API_KEY | parse_om, synthesize | Primary LLM |
| ATTOM_API_KEY | scanner | ATTOM property data |
| BROWSERBASE_API_KEY | owner_lookup, tax_lookup, deed_lookup | Stagehand sessions |
| MODEL_API_KEY | Stagehand | OpenAI key for browser agent |
| RESEND_API_KEY | reports/deliver.py | Email delivery |
| SUPABASE_SERVICE_ROLE_KEY | Supabase writes | |
| CENSUS_API_KEY | comps_lookup | Market rent benchmarks |
| HUD_API_TOKEN | comps_lookup | ZIP-level rent data |

## Supabase tables

- `subscribers` — email, firm, market, active, created_at
- `reports` — type, property_address, recipient_email, pdf_url, created_at
- `pipeline_runs` — tracked by sentinel-monitor agent

MCP is connected. Use `mcp__supabase__execute_sql` or `mcp__supabase__apply_migration` directly.

## Frontend

```bash
cd ui && bun run dev     # dev server on :5173
cd ui && bun run build   # build for prod
```

Landing page is on Vercel (`landing/`). Deploy with `vercel --prod` from `landing/`.

## Linting

```bash
ruff check . --fix    # auto-fix lint errors
ruff format .         # format
```

Ruff runs on commit via pre-commit (if set up). Always fix ruff errors before committing.

## Git workflow

Main branch is `main`. No force pushes.
For parallel feature work: `claude --worktree feature-name`

## What is and isn't working

| Feature | Status | Notes |
|---------|--------|-------|
| parse_om | Working | 4/4 fields pass on Bexar demo OMs; misses on non-standard formats |
| deed_lookup | Working | Extracts lender/date from Bexar County Clerk; loan_amount always null (results table doesn't show it) |
| owner_lookup | Working | BCAD scraper via Stagehand |
| tax_lookup | Working | BCAD tax delinquency via Stagehand |
| comps_lookup | Partial | Census ACS works; HUD ZIP rents need token verification |
| scanner | Built | ATTOM bulk query + scoring — not yet run against live data |
| PDF reports | Built | WeasyPrint + Jinja2 templates exist |
| Email delivery | Built | Resend wired up — needs verified sender domain |
| /export endpoint | Planned | Not yet wired into server.py |
| Slack | Not built | |

## What to build next

1. deed_lookup: add address normalization + owner-name fallback (2 hrs)
2. deed_lookup: click into document detail to get loan_amount (1 hr)
3. /export endpoint in server.py (1 hr)
4. Export PDF button in SynthesisPanel.tsx (30 min)
5. Run scanner live against ATTOM, confirm top 20 list
6. First client outreach — attach sample-memo.pdf, send from noor@nidoandkey.com

## Never do

- Commit .env or any API key
- Use `python3` instead of `.venv/bin/python3`
- Claim a skill "works" without running scripts/eval.py first
- Use BatchData API (no balance)
- Push to main without reviewing the diff
