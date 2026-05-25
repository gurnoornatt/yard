# Engineering PRD — Sentinel OM Analyzer Agent (Hack-a-Claw 24h Build)

**Product name:** Sentinel — Autonomous OM Analysis Agent
**Hackathon:** Hack-a-Claw, 24 hours, due Saturday 6PM
**Track:** Nemotron (Cloud) — Brev GPU credits prize
**Runtime:** Hermes Agent (Nous Research) + NVIDIA Nemotron 3 models via NVIDIA NIM
**One-line pitch:** A live, autonomous agent that takes a multifamily broker offering memorandum, autonomously gathers public data from 8 sources, reasons through multiple steps with a visible thought trace, and produces a structured pursue/watchlist/pass recommendation in under 90 seconds.

> **Doc status (verified May 2026):** All Hermes commands, the `nvidia` provider, the skills layout, and the Nemotron model names below were checked against the live Hermes Agent docs and NVIDIA's current model catalog on the date of writing. Key correction from earlier drafts: the current generation is **Nemotron 3** (Nano / Super / Nano Omni), and the free NIM tier has **rate limits that affect the demo** — see Risks.

---

## What changed from v1 (read this first)

The original PRD planned a hand-rolled ReAct loop, a custom orchestrator, a NIM client wrapper, and a Streamlit trace panel. **All of that is replaced by Hermes Agent**, which is one of the hackathon's explicitly approved runtimes.

Hermes already provides, out of the box:

- The reason → act → observe loop (this was the "custom orchestrator")
- Tool calling and autonomous tool selection (this was the "routing prompt")
- A live, on-screen reasoning + tool trace (this was the "Streamlit trace panel")
- Persistent memory across sessions
- A built-in iteration budget cap (this was "MAX_ITERATIONS / runaway risk")
- A native `nvidia` provider (this was the "NIM client wrapper")

**Net effect:** the hardest ~5 hours of the original build disappear. That time is reinvested into the part judges actually scrutinize — realistic demo data and clean tools. Less code, more impressive demo, and it uses an approved runtime.

The parts of v1 that are unchanged: the three demo properties, the synthesis instructions, the demo script, the "what not to build" discipline, and the submission checklist.

---

## Why this wins the hackathon

The judging rubric scores six dimensions equally. Sentinel hits each one:

- **Creativity:** the OM analysis problem is a real, unsolved triage problem at the small-syndicator tier. This is not a chatbot demo.
- **Functionality:** end-to-end working agent with real PDF inputs and real recommendation outputs, running live.
- **Scope of Completion:** intake, multi-source enrichment, reasoning, synthesis, and deliverable — a full pipeline, not a fragment.
- **Presentation:** the demo shows Hermes' reasoning trace in real time — judges literally watch it think.
- **Use of NVIDIA Tools:** Nemotron models via NVIDIA's build.nvidia.com endpoints, driven by Hermes' native `nvidia` provider.
- **Use of Nemotron Models:** main reasoning runs on a Nemotron model; optionally a cheaper Nemotron model handles delegated subtasks, demonstrating intentional model selection per task complexity.

The hackathon doc explicitly says "show the agent thinking — its reasoning, planning, and tool calls. Don't just show outputs." Hermes' streaming trace is built for exactly this.

---

## What it does, end to end

A user provides a broker OM for a multifamily property (e.g. in San Antonio). The agent:

1. Parses the OM to extract address, units, asking price, and the broker's stated narrative
2. Plans its research approach (which sources matter for this property)
3. Autonomously calls 6–8 data tools: owner LLC chain, prior ownership, deed-of-trust filings, building permits, tax delinquency, code violations, recent submarket comps, owner portfolio activity
4. Reasons about each result as it arrives, updating its model of the property
5. Synthesizes everything into a structured 6-section analysis
6. Outputs the deliverable on screen and as a downloadable file
7. Streams the full reasoning trace live, which judges watch

Time to complete: 60–120 seconds per OM.

---

## System architecture (Hermes-native)

```
┌──────────────────────────────────────────────────────────────┐
│                        USER                                   │
│        CLI  (or Telegram/Discord via Hermes gateway)          │
└───────────────────────────┬──────────────────────────────────┘
                            │  OM file + "analyze this"
┌───────────────────────────▼──────────────────────────────────┐
│                     HERMES AGENT                              │
│  • reason → act → observe loop  (built in)                    │
│  • autonomous tool selection    (built in)                    │
│  • live streaming trace         (built in)                    │
│  • persistent memory + skills   (built in)                    │
│  • iteration budget cap         (built in)                    │
└───────┬───────────────────────────────────────┬──────────────┘
        │  reasoning calls                       │  tool calls
┌───────▼───────────────────┐        ┌──────────▼───────────────┐
│  NEMOTRON via NVIDIA NIM   │        │  JOB LAYER (skills)       │
│  (provider: nvidia)        │        │  every job = one folder,  │
│  primary: nemotron-3-      │        │  one run.py, JSON in →    │
│           super-120b-a12b  │        │  JSON out. Uniform shape. │
│  optional sub: nemotron-3- │        │  owner / deed / permit /  │
│           nano-30b-a3b     │        │  tax / violations / comps │
└────────────────────────────┘       │  / portfolio / maturity   │
                                      └────────────┬──────────────┘
                                                   │ reads
                                      ┌────────────▼──────────────┐
                                      │  SHARED DATA CONTRACT      │
                                      │  one JSON file per demo    │
                                      │  property = single source  │
                                      │  of truth                  │
                                      └────────────────────────────┘

        (optional stretch) ── verdict UI reads Hermes' trace ──┐
                                                                ▼
                                          Vite + React + TS + Tailwind (Bun)
```

There is no custom orchestrator, no custom client wrapper, no Streamlit app. Hermes is the orchestrator. Every job is a uniform, self-describing JSON endpoint the agent discovers and calls.

---

## Engineering philosophy: agent-native, uniform JSON jobs

The whole codebase is built **for the agent to read and follow, not for a human to navigate.** This is a deliberate discipline, and it costs zero extra time — it is a set of conventions, not an extra build. The principle: every capability is a uniform, self-describing endpoint the agent can discover and call without archaeology.

Three rules, applied to every single job with no exceptions:

1. **Same call, same return, every job.** Every job is a folder with one entry point, `run.py`, called the identical way: one JSON object in (e.g. `{"property_id": "4123_mccullough"}`), one JSON object out. Once the agent has seen one job, it knows how all of them work. No special cases, no second pattern to learn.

2. **The folder name is the job name.** `owner_lookup/` does owner lookup. `deed_lookup/` does deed lookup. No clever names, no indirection layers. The agent finds capabilities by reading the directory listing — the structure *is* the documentation.

3. **`SKILL.md` is the contract, written for the agent.** A plain statement of: what this job is, exactly when to call it, and the exact JSON shape that comes back. Missing data is always an explicit `null` or `"data_unavailable"` — never a missing key, never a sentence. The agent never has to parse English to know what happened.

**Explicitly out of scope (this is where the idea becomes over-engineering):** no HTTP server, no real REST API tier, no service registry, no OpenAPI spec, no gateway. Those are correct in production and fatal in a 24-hour build — they are hours of plumbing the judges never see. Hermes' skill system *already is* a lazy-discovery, self-describing endpoint architecture: it loads a compact index of all jobs at startup (~3k tokens) and pulls a job's full contract only when it decides to call it. The uniform-JSON discipline above gives us the full agent-native win using that existing machinery. A real endpoint server is a post-hackathon stretch goal only.

---

| Component | Choice | Why |
|---|---|---|
| Agent runtime | Hermes Agent (Nous Research) | Approved hackathon runtime; provides the loop, trace, memory, tool calling for free |
| LLM provider | `nvidia` (Hermes built-in NIM provider) | Native support; no custom endpoint wiring; required for prize. Verified in Hermes provider docs. |
| Primary model | `nvidia/nemotron-3-super-120b-a12b` | Current-gen (Nemotron 3). 120B hybrid MoE, ~12B active, 1M context. Strong reasoning + tool calling. Free on NIM. |
| Optional sub-model | `nvidia/nemotron-3-nano-30b-a3b` | Current-gen Nano (30B, ~3B active). Cheap/fast for delegated subtasks. ~4x throughput of prior Nano. |
| Multimodal (not used) | `nvidia/nemotron-3-nano-omni` (Nano Omni) | Exists, handles image/video/audio. We parse OMs as text, so out of scope — noted for completeness. |
| Legacy fallback | `nvidia/nvidia-nemotron-nano-9b-v2`, `nvidia/llama-3_3-nemotron-super-49b-v1_5` | Previous-gen; still live. Use only if a Nemotron 3 model is unavailable at the endpoint during the event. |
| Tools / jobs | Hermes skills (agentskills.io format), uniform `run.py` | Portable, autonomously selected by Hermes, the official extension path |
| Job language | **Python 3.11, managed by `uv`** | Hermes is Python-native; every skill/helper/`execute_code` path is Python. `uv` is the verified 2026 default and is what the Hermes installer itself uses. Zero integration friction. Not Bun/TS for jobs — that means two runtimes and awkward shell-out for zero benefit. |
| Job dependencies | Python stdlib first; `pypdf`/`pdfplumber` only in `parse_om` | A job is ~30 lines. Fewer deps = fewer demo-day failures. |
| OM parsing | `pypdf` / `pdfplumber` inside the `parse_om` job | Standard, reliable |
| Demo data | One JSON file per demo property (the shared data contract) | Demo-safe, deterministic, single source of truth |
| Live fallback | Hermes web/browser tools | Built in; used only for non-demo properties |
| Deliverable output | Markdown / simple HTML written by the agent | No PDF toolchain needed for a working demo |
| Terminal backend | `docker` if available, else `local` | Sandboxing story for the demo |
| **UI (stretch goal only)** | **Vite + React + TypeScript + Tailwind, Bun** as package manager | 2026 default for a fast, sharp single-screen app. Bun's one justified use here (fast install/dev server); not for the agent jobs. Built only if time remains — see UI section. |
| Repo | GitHub public | Required for submission |

**Critical decision — single runtime:** we do NOT also build a custom ReAct loop or a separate Streamlit UI. Doing both means building the same agent twice in 24 hours. Hermes is the agent; we only build the tools and the demo data.

**Critical decision — model split is optional:** the v1 plan split routing (Nano) vs synthesis (Super). In Hermes this maps to the `delegation` feature (main model = Super, `delegation.model` = Nano). It is a nice talking point but adds a failure surface. **Default: run everything on the Super model.** Only add the split in the final polish window if time allows and it is stable.

**Critical decision — the UI is a stretch goal, not a foundation.** Hermes' native streaming terminal trace *is* a complete, compelling visualization on its own — judges watching the agent think in the terminal is a winning demo with zero UI risk. The custom verdict UI is built only after the agent works end to end. Starting with the UI because it is the fun visible part is the classic way this project dies: it is the lowest-scoring layer and the highest yak-shaving risk. Core first, polish second.

---

## Project structure

```
sentinel/
├── README.md                       # description, setup, how to run the demo
├── pyproject.toml                  # uv-managed; pypdf + pdfplumber only
├── uv.lock                         # reproducible installs
├── hermes/
│   ├── config-notes.md             # exact hermes config commands used
│   └── SOUL.md                     # agent identity: "you are Sentinel, an OM analyst"
├── skills/                         # the real work — every job is identical in shape
│   ├── parse_om/
│   │   ├── SKILL.md                # contract: when to call, exact JSON returned
│   │   └── run.py                  # JSON in → JSON out. The one entry point.
│   ├── owner_lookup/
│   │   ├── SKILL.md
│   │   └── run.py
│   ├── deed_lookup/
│   │   ├── SKILL.md
│   │   └── run.py
│   ├── permit_lookup/
│   │   ├── SKILL.md
│   │   └── run.py
│   ├── tax_lookup/
│   │   ├── SKILL.md
│   │   └── run.py
│   ├── violations_lookup/
│   │   ├── SKILL.md
│   │   └── run.py
│   ├── comps_lookup/
│   │   ├── SKILL.md
│   │   └── run.py
│   ├── portfolio_crawler/
│   │   ├── SKILL.md
│   │   └── run.py
│   ├── maturity_estimator/
│   │   ├── SKILL.md
│   │   └── run.py
│   └── synthesize_analysis/
│       ├── SKILL.md
│       └── run.py
├── data/
│   └── demo_properties/            # the shared data contract — one file = one property
│       ├── 4123_mccullough.json
│       ├── 7821_blanco.json
│       └── 2455_culebra.json
├── demo_oms/
│   ├── mccullough_om.pdf
│   ├── blanco_om.pdf
│   └── culebra_om.pdf
└── ui/                             # STRETCH GOAL ONLY — do not start here
    └── (Vite + React + TS + Tailwind, Bun — added only if core is done early)
```

Every job folder is identical in shape: `SKILL.md` (the contract) + `run.py` (the entry point). The agent reads the directory, sees uniform jobs, and follows the structure with no guesswork. The skills + the demo JSON are the entire core build. Everything else is Hermes.

---

## How the agent reasons (no code to write — this is Hermes' built-in loop)

You do not implement this. Hermes does it. You only describe the goal in the agent's identity file and provide the tools. For reference, the loop Hermes runs is:

1. **Thought** — Hermes reasons about what it knows and what is missing
2. **Action** — Hermes autonomously picks and calls one of your skills
3. **Observation** — the skill returns structured data; Hermes ingests it
4. Repeat until it has enough data
5. **Synthesis** — Hermes calls the `synthesize_analysis` skill / writes the final 6-section report

Hermes streams every Thought / Action / Observation to the screen automatically. That is the "watch it think" demo, with zero UI code.

---

## The agent identity (replaces the old routing prompt)

Instead of a hand-tuned routing prompt, you write a short `SOUL.md` that defines the agent. Hermes loads this as the agent's primary identity.

```
You are Sentinel, an autonomous multifamily acquisition analyst.

When given a broker offering memorandum (OM), your job is to decide whether a
syndication firm should PURSUE, WATCHLIST, or PASS on the property.

Process:
1. Use parse_om to extract address, units, asking price, broker narrative.
2. Always research owner first (owner_lookup), then loans (deed_lookup),
   then owner portfolio (portfolio_crawler) if there is an LLC.
3. Then check permits, tax status, and code violations for hidden flags.
4. Then pull recent submarket comps for a price reality check.
5. Do not call the same tool twice with the same input.
6. When you have enough signal, call synthesize_analysis and stop.

Be direct and factual. Never invent data — if a tool returns nothing, say
"data unavailable." Reference specific numbers (loan amount, hold-period years,
comp prices). No marketing language. The recommendation must be defensible
from the evidence gathered.
```

---

## The synthesis instructions (unchanged from v1, now lives in a skill)

The `synthesize_analysis` skill instructs the model to write a 6-section analysis, each section 2–4 sentences, direct and factual:

1. **Property Snapshot** — address, units, year built, appraised value, asset class.
2. **Owner Motivation Profile** — LLC chain, principal, hold period, portfolio size, intent signals.
3. **Loan Situation** — lender, origination date, estimated maturity, CMBS vs regional bank, refinance assessment.
4. **Submarket Reality Check** — recent comps (specific addresses + prices), rent trajectory, supply, headwinds.
5. **Hidden Flags** — code violations, tax delinquency, lawsuits; if none, say "No hidden flags detected in public records."
6. **Bottom-Line Recommendation** — exactly one of PURSUE / WATCHLIST / PASS, 3–5 sentences of reasoning tied to specific signals, plus the next concrete move.

Rules: never invent facts; cite specific numbers from the research; no marketing language; the call must be defensible from the evidence.

---

## The uniform job contract

Every job — all ten — obeys the same contract. This is the heart of the agent-native discipline. Build `owner_lookup` once as the canonical reference, then stamp the other nine from it.

**`run.py` — identical interface, every job:**

```python
# skills/owner_lookup/run.py
# Contract: one JSON object in (argv[1] or stdin), one JSON object out (stdout).
# Same shape for every job. No prose. No human formatting.
import json, sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data" / "demo_properties"

def run(params: dict) -> dict:
    property_id = params.get("property_id")
    f = DATA / f"{property_id}.json"
    if not f.exists():
        return {"job": "owner_lookup", "status": "data_unavailable",
                "property_id": property_id, "data": None}
    record = json.loads(f.read_text()).get("owner_lookup")
    return {"job": "owner_lookup",
            "status": "ok" if record else "data_unavailable",
            "property_id": property_id,
            "data": record}

if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
```

Every job returns the same envelope: `{"job", "status", "property_id", "data"}`. `status` is always one of `"ok"` / `"data_unavailable"`. `data` is the job's payload or explicit `null`. The agent never parses English and never learns a second pattern.

**`SKILL.md` — the contract, written for the agent:**

```markdown
---
name: owner_lookup
description: >
  Look up the legal owner of a multifamily property. CALL THIS FIRST for any
  OM analysis. Returns owner LLC, principal, mailing address, acquisition
  date, and hold-period years.
---
# owner_lookup

## When to call
First research step for any property. Needs {"property_id": "<id>"}.

## How to call
Run: `uv run python ${HERMES_SKILL_DIR}/run.py '{"property_id":"<id>"}'`

## Returns (exact shape)
{"job":"owner_lookup","status":"ok|data_unavailable",
 "property_id":"<id>","data":{...}|null}

data, when status is ok:
  llc_name, principal, mailing_address, acquisition_date,
  hold_period_years, is_entity, owner_state
```

**The shared data contract** — one JSON file per property, every job reads its own slice by a stable key:

```json
{
  "owner_lookup": {
    "llc_name": "MCCULLOUGH ARMS LLC",
    "principal": "Robert Chen",
    "mailing_address": "1234 Greenwich St, New Haven, CT 06511",
    "acquisition_date": "2014-08-22",
    "hold_period_years": 11.3,
    "is_entity": true,
    "owner_state": "CT"
  },
  "deed_lookup": {
    "loans": [{
      "lender": "Frost Bank",
      "origination_date": "2021-03-15",
      "loan_amount": 8200000,
      "estimated_maturity": "2026-03-15",
      "is_cmbs": false,
      "lender_type": "regional_bank"
    }]
  },
  "permit_lookup": {
    "permits": [{
      "permit_number": "2025-04-1287",
      "type": "PLUMBING - INTERIOR",
      "date": "2025-04-12",
      "value": 45000,
      "is_new_construction": false
    }]
  }
}
```

For the demo, jobs read from this file. The live-fetch path (Hermes web/browser tools) exists behind the same envelope for non-demo properties but is off during the demo.

---

## Setup steps (the actual commands)

```bash
# 1. Install Hermes (Linux / macOS / WSL2) — installer brings uv + Python 3.11
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
source ~/.bashrc          # or ~/.zshrc
hermes doctor             # confirm clean install

# 1b. Project deps via uv (uv is installed by the Hermes installer)
cd sentinel
uv sync                   # installs pypdf + pdfplumber from pyproject.toml
# every job runs as:  uv run python skills/<job>/run.py '{"property_id":"..."}'

# 2. Point Hermes at Nemotron (key from build.nvidia.com)
hermes config set NVIDIA_API_KEY nvapi-your-key-here
hermes model              # interactive: pick NVIDIA NIM provider + a Nemotron model
# direct alternative (verified provider/model strings):
hermes config set model nvidia/nemotron-3-super-120b-a12b

# 3. Turn on the visible "thinking" demo
hermes config set display.streaming true
hermes config set display.show_reasoning true
hermes config set display.tool_progress all

# 4. Safety for a smooth live demo (no mid-demo permission pauses, still sandboxed)
hermes config set approvals.mode smart
hermes config set terminal.backend docker     # omit if Docker not available -> stays "local"

# 5. Install the Sentinel skills (point Hermes at the skills/ folder)
# 5. Install the Sentinel skills.
#    Hermes reads skills from ~/.hermes/skills/<category>/<name>/SKILL.md
#    Skills are picked up immediately — no restart needed.
mkdir -p ~/.hermes/skills/sentinel
cp -r skills/* ~/.hermes/skills/sentinel/
hermes skills list        # confirm all Sentinel skills are detected
hermes
# > analyze the OM at demo_oms/mccullough_om.pdf
```

Note: `"main"` is not a valid value for `model.provider`; use the real provider name `nvidia`.

---

## The UI (stretch goal — read the warning first)

**Default demo: no custom UI.** Hermes streams every thought, tool call, and observation to its own terminal in real time. A clean terminal trace of the agent reasoning through a real-estate decision is genuinely compelling and is a complete, winning demo on its own. This is the highest expected-value option: zero build cost, zero integration risk.

**Stretch UI (only if the core is done with hours to spare):** a single-screen web app that watches the agent and renders the live trace plus a polished PURSUE / WATCHLIST / PASS verdict card. A verdict card lands harder with judges than terminal text for this particular product, so it is worth doing *if and only if* the agent already works end to end.

If built, the verified 2026-optimal stack for this one screen:

- **Vite + React + TypeScript + Tailwind** — the current default for spinning up a sharp single-screen app fast. Not Next.js: no SSR, routing, or server framework is needed for one screen, and Next is heavier than the job requires.
- **Bun** as the package manager / dev server for the UI only — meaningfully faster install and dev loop than npm, stable in 2026. This is Bun's one justified use in the project; it is deliberately *not* used for the agent jobs (those are Python+uv for zero Hermes friction).
- **No hand-built backend.** The UI reads Hermes' session/trace output (or Hermes' API-server mode). Hermes is the backend.

**The trap, stated plainly:** do not start with the UI because it is the fun visible part. It is the lowest-scoring layer and the highest yak-shaving risk. A working agent with a plain terminal trace beats a beautiful UI wired to a half-working agent every single time. Core first; the UI is the last thing built, not the first.

---

**Friday 7PM–10PM (Hour 0–3): Foundation**
- [ ] Get NVIDIA Nemotron API key from build.nvidia.com **and request the free-tier credit increase immediately** (it is not instant — do this first, before building)
- [ ] Install Hermes (brings uv), run `hermes doctor`, point it at `nvidia/nemotron-3-super-120b-a12b`
- [ ] Configure a fallback provider via `hermes fallback` (legacy Nemotron or OpenRouter Nemotron) so a demo-day 429 fails over silently
- [ ] Confirm a plain `hermes` chat works against Nemotron (hello-world)
- [ ] `uv init` the project, add `pypdf` + `pdfplumber`, write `SOUL.md`
- [ ] Build `owner_lookup` as the **canonical job** — exact `run.py` envelope + `SKILL.md` contract. Confirm Hermes discovers and calls it autonomously. This is the template for all nine others.

**Friday 10PM–Saturday 5AM (Hour 3–10): Stamp the jobs + demo data**
- [ ] Stamp the other 9 jobs from the `owner_lookup` template (only the `data` slice + key differ — interface is identical). `parse_om` and `synthesize_analysis` included.
- [ ] Write the three demo property JSON files — the shared data contract. Realistic, internally consistent. **Spend serious time here; this is what judges scrutinize.**
- [ ] Run the full agent on each demo property; confirm it reaches a recommendation
- [ ] Tune `SOUL.md` until tool order and stopping behavior look right on all 3
- [ ] Sleep 4–5 hours

**Saturday 5AM–12PM (Hour 10–17): Quality**
- [ ] Tune `synthesize_analysis` until all 3 properties produce clean 6-section reports
- [ ] Confirm the live terminal trace looks good (streaming + reasoning + tool progress) — **this is the demo; it must be solid here**
- [ ] Have the agent write the final report to a file and confirm it is readable
- [ ] (Optional, only if stable) add the Nano delegation split for subtasks

**Saturday 12PM–3PM (Hour 17–20): Polish, fallback, and ONLY THEN the UI**
- [ ] Wire one or two jobs to a real live fetch as a fallback for non-demo properties (same envelope)
- [ ] Test on a non-demo property; if it is rough, that is fine — demos are pre-cached
- [ ] Record a 60-second backup video of one full clean run
- [ ] Push to GitHub, write the README
- [ ] **If and only if everything above is done and solid:** scaffold the Vite/React/TS/Tailwind/Bun verdict UI. If short on time, skip entirely — the terminal trace is the demo.

**Saturday 3PM–6PM (Hour 20–23): Practice and submit**
- [ ] Practice the 3-minute judge pitch 5 times; time it
- [ ] Final run of all 3 demo properties
- [ ] Submit before 6PM
- [ ] Rest until results

---

## The demo script (3-minute judge version)

**0:00–0:30 — The problem**
"Multifamily syndicators get 30–50 broker offering memorandums a month. Each takes a junior analyst hours to underwrite, and most are noise. The triage problem is real and unsolved. We built Sentinel."

**0:30–1:00 — What it does**
"Sentinel takes a broker OM and autonomously analyzes the property. It runs a multi-step research process across 8 public-record sources and produces a structured pursue/watchlist/pass recommendation in under 90 seconds. It runs on Hermes Agent driving NVIDIA Nemotron. Watch it work, live."

**1:00–2:15 — The live demo**
- Drop in the McCullough Ave OM
- Narrate the live Hermes trace as it streams:
  - "It plans its research first"
  - "Pulling owner data — 11-year hold, out-of-state owner, classic tired-landlord profile"
  - "Checking loans — regional-bank loan maturing in March, the forced-seller signal"
  - "Crawling the owner's other holdings for portfolio pressure"
  - "Every step here is Nemotron reasoning — you're watching it think"
  - "Now it writes the synthesis"
- Show the final recommendation and the saved report

**2:15–2:45 — Why Nemotron + Hermes**
"Hermes gives us a real autonomous agent — memory, tool use, a visible reasoning loop. Nemotron is the reasoning core, called through NVIDIA's endpoints. Cost per analysis is a few cents versus hours of analyst time."

**2:45–3:00 — The market**
"This targets the wave of distressed multifamily debt over the next 18 months. Sentinel is the agent that catches what brokers leave out. Thank you."

---

## What to NOT build (the discipline)

- **No custom ReAct loop / orchestrator.** Hermes is the loop.
- **No custom NIM client wrapper.** Hermes' `nvidia` provider handles it.
- **No HTTP server, REST tier, service registry, or OpenAPI spec.** The uniform-JSON skill discipline gives the agent-native win for free; a real endpoint server is a post-hackathon stretch only.
- **No second runtime for jobs.** Jobs are Python+uv only. No Bun/TS in the agent core.
- **No custom UI as a foundation.** Hermes' terminal trace is the demo. The web UI is the last thing built, or not at all.
- **No login, auth, or user accounts.** Single-user demo.
- **No database.** The shared per-property JSON files are the data layer.
- **No multi-property batch processing.** One OM at a time.
- **No fine-tuning or custom training.** Models as-is.
- **No vector DB / RAG.** The agent fetches structured data, not text corpora.
- **No live county scraping during the demo.** Pre-cached only; live fallback exists behind the same envelope but is off for the demo.
- **No PDF generation toolchain.** A clean Markdown/HTML report is enough for a working demo.

---

## Risks and mitigations

**Risk 1: NVIDIA NIM free-tier rate limits or credit exhaustion during the demo.**
This is the single biggest verified risk. The free build.nvidia.com tier is **40 requests/minute** and **~1,000 inference credits on signup** (up to 5,000 on request). One full Sentinel run is a multi-step agent loop — easily 8–15 model calls. Rehearsing repeatedly and then running live for judges can rate-limit you at the worst moment, or drain credits.
Mitigations: (a) request the credit increase early Friday night, before building; (b) during rehearsal, test the *logic* with the cheap Nano model and reserve Super for final dry-runs; (c) configure a Hermes **fallback provider** so a 429 mid-demo silently fails over instead of dying — e.g. fallback to the legacy `nvidia/llama-3_3-nemotron-super-49b-v1_5`, or an OpenRouter Nemotron route, set via `hermes fallback`; (d) keep a pre-recorded 60-second backup video cued on a second tab; (e) do not spam re-runs in the 10 minutes before judging — let the per-minute budget recover.

**Risk 2: NVIDIA endpoint downtime or a model name changing during the event.**
Mitigation: the legacy Nemotron model names are documented in the stack table as a known-good fallback. If `nemotron-3-super-120b-a12b` is unavailable at the endpoint, switch the one config line to a legacy Super and keep going.

**Risk 3: OM parsing fails on an unexpected PDF format.**
Mitigation: the `parse_om` skill falls back to the pre-loaded demo property data when the upload is a demo OM. Demo path never depends on live parsing.

**Risk 4: Agent picks wrong tools or loops.**
Mitigation: Hermes' built-in iteration budget caps turns (default 90, with budget-pressure warnings). The `SOUL.md` enforces tool order and a stop condition. Tested against all 3 demo properties before submission.

**Risk 5: Synthesis is generic and ignores the data.**
Mitigation: the synthesis skill requires citing specific numbers from the research; tested on all 3 properties until output is specific.

**Risk 6: Demo machine / network fails.**
Mitigation: run locally as primary; backup video as fallback; GitHub repo submitted regardless.

**Risk 7: Burnout at hour 18 and shipping something broken.**
Mitigation: the schedule includes 4–5 hours of sleep. Take it. A working demo from a rested presenter beats a broken one from an exhausted one.

---

## Submission checklist

- [ ] GitHub repo public with full source (skills + demo data + README)
- [ ] README with: one-paragraph description, setup commands, "how to run the demo," architecture summary, and explicit acknowledgment of the Nemotron model(s) and Hermes used
- [ ] 60-second backup demo video
- [ ] Hackathon submission form completed before 6PM Saturday
- [ ] Agent confirmed running live on all 3 demo properties

---

## Honest note on framing

The hackathon rules require a real, live, working agent — not a pitch or a slideshow. This plan is genuinely functional, so it qualifies. Keep market-sizing and roadmap claims brief and clearly framed as context; let the live run carry the demo. The agent working in front of the judges is the submission. Everything else is supporting narrative.

---

End of Engineering PRD — Sentinel OM Analyzer Agent (Hermes + Nemotron 3, v3 — agent-native uniform-JSON architecture).
