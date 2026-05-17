# Sentinel — Autonomous OM Analysis Agent

An autonomous multifamily acquisition analyst. Drop in a broker offering memorandum; Sentinel researches 8 public-record sources and returns a structured PURSUE / WATCHLIST / PASS recommendation with real data from live APIs.

**Backend:** FastAPI + asyncio  
**Browser Automation:** [Stagehand](https://github.com/browserbase/stagehand) (Browserbase AI-driven browser agent)  
**LLM:** `nvidia/nemotron-3-super-120b-a12b` via NVIDIA NIM (OM parsing) + `openai/gpt-4o-mini` (BCAD navigation)  
**Frontend:** React + TypeScript + Vite  
**Track:** Hack-a-Claw 2026

---

## How it works

Sentinel runs 10 skills in parallel, each hitting a real public data source:

| Skill | Data Source | What it finds |
|---|---|---|
| `parse_om` | Offering Memorandum (PDF) | Address, units, asking price, year built |
| `owner_lookup` | BCAD via Stagehand | LLC name, principal, out-of-state flag |
| `deed_lookup` | ATTOM Data Solutions | Loan lender, maturity date, CMBS flag |
| `portfolio_crawler` | BCAD via Stagehand | All properties owned by the same LLC |
| `permit_lookup` | SA Open Data Portal | Recent permits by address |
| `tax_lookup` | BCAD via Stagehand | Tax status, delinquency flag |
| `violations_lookup` | SA Open Data Portal | Code violations by address |
| `comps_lookup` | ATTOM + US Census ACS5 | Recent sales comps, market rent, vacancy |
| `maturity_estimator` | Derived from deed records | Refi pressure, days-to-maturity |
| `synthesize_analysis` | NVIDIA Nemotron | 6-section structured investment verdict |

Results stream live to the UI via Server-Sent Events. Every data point shows its source.

---

## Architecture

```
server.py               — FastAPI backend, SSE streaming, skill orchestration
skills/<name>/
  run.py                — JSON in → JSON out (same interface, every skill)
  SKILL.md              — contract: when to call, exact JSON shape
ui/                     — React frontend (Vite + TypeScript)
  src/components/
    DataFeed.tsx        — live SSE feed with source citations
    SynthesisPanel.tsx  — structured verdict display
```

**Stagehand skills** (`owner_lookup`, `tax_lookup`, `portfolio_crawler`) run as subprocesses to avoid asyncio event-loop conflicts. Each gets a 60-second timeout.

---

## Setup

### Prerequisites

- Python 3.11+ and [`uv`](https://github.com/astral-sh/uv)
- Node.js 18+
- API keys (see below)

### Install

```bash
# Python deps
uv sync

# Frontend deps
cd ui && npm install && npm run build && cd ..
```

### API Keys

Create a `.env` file in the project root (never commit this):

```
NVIDIA_API_KEY=nvapi-...          # NVIDIA NIM — OM parsing
BROWSERBASE_API_KEY=bb_live_...   # Browserbase — cloud browser for BCAD
OPENAI_API_KEY=sk-proj-...        # OpenAI gpt-4o-mini — Stagehand AI navigation
MODEL_API_KEY=sk-proj-...         # Same as OPENAI_API_KEY (Stagehand alias)
ATTOM_API_KEY=...                 # ATTOM Data Solutions — deed + comps
CENSUS_API_KEY=...                # US Census — market data (free at api.census.gov)
OPENROUTER_API_KEY=sk-or-...      # Optional fallback
```

---

## Run

```bash
# Load env vars and start the server
set -a && source .env && set +a
uv run uvicorn server:app --port 8000

# Open in browser
open http://localhost:8000
```

Upload any multifamily OM PDF. Sentinel:
1. Parses the PDF for address and deal terms
2. Launches 8 parallel research tasks (real APIs + live browser sessions)
3. Streams every result to the UI as it completes
4. Synthesizes a full investment memo with PURSUE / WATCHLIST / PASS verdict

---

## Data sources (all live, no mocks)

| Source | Coverage | API |
|---|---|---|
| BCAD (Bexar County Appraisal District) | Bexar County TX | Stagehand browser automation |
| ATTOM Data Solutions | National | `api.gateway.attomdata.com` |
| SA Open Data Portal | San Antonio TX | `data.sanantonio.gov` CKAN API |
| US Census ACS5 | National (ZIP level) | `api.census.gov` |
| NVIDIA NIM | — | `integrate.api.nvidia.com` |

---

## Hackathon

**Hack-a-Claw 2026** — Built in 24 hours.
