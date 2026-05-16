# Sentinel — Autonomous OM Analysis Agent

An autonomous multifamily acquisition analyst. Drop in a broker offering memorandum; Sentinel researches 8 public-record sources and returns a structured PURSUE / WATCHLIST / PASS recommendation in under 90 seconds.

**Runtime:** [Hermes Agent](https://hermes-agent.nousresearch.com) (Nous Research)  
**Models:** `nvidia/nemotron-3-super-120b-a12b` via [NVIDIA NIM](https://build.nvidia.com) (primary)  
**Track:** Nemotron (Cloud) — Hack-a-Claw 2026

---

## How it works

Hermes drives the full reasoning loop autonomously:

1. `parse_om` → extract address, units, price, broker narrative from the PDF
2. `owner_lookup` → identify the LLC, principal, hold period, out-of-state flag
3. `deed_lookup` → surface loans: lender, maturity date, CMBS vs regional
4. `portfolio_crawler` → map the owner's other holdings for portfolio pressure
5. `permit_lookup` + `tax_lookup` + `violations_lookup` → hidden flags
6. `comps_lookup` → recent submarket sales to reality-check the ask
7. `maturity_estimator` → compute refi pressure from loan maturity date
8. `synthesize_analysis` → 6-section structured report → saves to `reports/`

Every step streams live in the terminal. Judges watch the agent think.

---

## Setup

### Prerequisites
- [Hermes Agent](https://hermes-agent.nousresearch.com) installed
- NVIDIA NIM API key from [build.nvidia.com](https://build.nvidia.com)
- Python 3.11+ via `uv`

### Install

```bash
# 1. Install Python deps
uv sync

# 2. Generate the three demo OM PDFs
uv run python scripts/generate_demo_oms.py

# 3. Install Sentinel skills into Hermes
mkdir -p ~/.hermes/skills/sentinel
cp -r skills/* ~/.hermes/skills/sentinel/

# 4. Configure Hermes
hermes config set display.streaming true
hermes config set display.show_reasoning true
hermes config set approvals.mode smart
```

### API Keys (in ~/.hermes/.env)
```
NVIDIA_API_KEY=nvapi-...
OPENROUTER_API_KEY=sk-or-...   # optional fallback for rate-limit protection
```

---

## Run the demo

```bash
hermes
```

Then type:
```
analyze the OM at demo_oms/mccullough_om.pdf
```

Watch Hermes reason through 8 research steps in real time. Report saves to `reports/`.

### Demo properties

| Property | Expected verdict | Key signal |
|---|---|---|
| `mccullough_om.pdf` | **PURSUE** | Frost Bank loan matured March 2026, 11yr out-of-state hold |
| `blanco_om.pdf` | **PASS** | $84k tax delinquency + 3 open violations + asking above comps |
| `culebra_om.pdf` | **WATCHLIST** | Loan maturity ambiguous, price fair, no violations |

---

## Architecture

```
hermes/SOUL.md          — agent identity and research order
skills/<name>/
  SKILL.md              — contract: when to call, exact JSON shape returned
  run.py                — JSON in → JSON out (same interface, every skill)
data/demo_properties/   — pre-cached data contract (one JSON file per property)
demo_oms/               — generated broker OM PDFs (run generate_demo_oms.py)
reports/                — analysis output (written by the agent)
```

No custom orchestrator. No REST server. No vector DB. Hermes is the agent; the skills are the tools.

---

## Models used

| Model | Role |
|---|---|
| `nvidia/nemotron-3-super-120b-a12b` | Primary reasoning — all research + synthesis |
| `nvidia/nemotron-3-nano-30b-a3b` | Optional delegation for subtasks (configurable) |

Both served via NVIDIA NIM at `integrate.api.nvidia.com`.

---

## Hackathon

**Hack-a-Claw 2026** — Nemotron (Cloud) track  
Built with Hermes Agent + NVIDIA Nemotron 3 in 24 hours.
