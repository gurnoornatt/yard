import asyncio
import importlib.util
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sentinel")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT = Path(__file__).parent
SKILLS = PROJECT / "skills"
NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY", "")

SKILL_SEQUENCE = [
    "parse_om",
    "owner_lookup",
    "deed_lookup",
    "portfolio_crawler",
    "permit_lookup",
    "tax_lookup",
    "violations_lookup",
    "comps_lookup",
    "maturity_estimator",
    "synthesize_analysis",
]

SKILL_LABELS = {
    "parse_om": "Reading offering memorandum",
    "owner_lookup": "Tracing ownership chain",
    "deed_lookup": "Pulling loan & deed records",
    "portfolio_crawler": "Mapping owner portfolio",
    "permit_lookup": "Checking building permits",
    "tax_lookup": "Checking tax status",
    "violations_lookup": "Scanning code violations",
    "comps_lookup": "Pulling submarket comps",
    "maturity_estimator": "Estimating loan pressure",
    "synthesize_analysis": "Synthesizing findings",
}


def call_skill(name: str, params: dict) -> dict:
    path = SKILLS / name / "run.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.run(params)


def sse(event: str, data: dict) -> str:
    return f"data: {json.dumps({'event': event, **data})}\n\n"


def _slug(address: str, zip_: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "_", address.lower()).strip("_")
    return f"{clean}_{zip_}" if zip_ else clean


SYNTHESIS_PROMPT = """You are Sentinel, an autonomous real estate acquisition analyst. Output ONLY the 6 sections below — no preamble, no thinking, no meta-commentary. Begin immediately with "## Property Snapshot".

Using ONLY the research data below, write a concise 6-section analysis.
Each section: 2-4 sentences. Direct, factual, cite specific numbers. No marketing language.
If a data source shows "data_unavailable" or null, note it briefly and move on.

{asset_class_note}

Research data:
{research_json}

Write exactly these 6 sections (start NOW with ## Property Snapshot):

## Property Snapshot
[address, property type, units if applicable, year built, asking price, appraised value]

## Owner Motivation Profile
[owner name, hold period if known, owner state (flag if out-of-state), portfolio size, motivation signals]

## Loan Situation
[lender, loan amount, origination date, maturity date, loan type, refinance pressure assessment]

## Submarket Reality Check
[nearby comparable sales with prices, market rent level, vacancy rate, trend]

## Hidden Flags
[tax delinquency with dollar amount, open code violations with types — or: No hidden flags detected in public records.]

## Bottom-Line Recommendation
Start with exactly one of: PURSUE / WATCHLIST / PASS
Then 3-5 sentences of reasoning tied to specific signals from the data.
End with: Next move: [one concrete action].
"""


async def run_analysis(pdf_bytes: bytes, filename: str) -> AsyncGenerator[str, None]:
    ctx: dict = {}  # address context, grows as skills complete
    all_data: dict = {}
    property_id = "upload"
    pipeline_start = time.time()
    log.info("=== ANALYSIS START: %s (%d bytes) ===", filename, len(pdf_bytes))

    for skill_name in SKILL_SEQUENCE:
        yield sse(
            "skill_start", {"skill": skill_name, "label": SKILL_LABELS[skill_name]}
        )
        await asyncio.sleep(0)
        skill_start = time.time()

        try:
            if skill_name == "parse_om":
                with tempfile.NamedTemporaryFile(
                    suffix=".pdf",
                    prefix=re.sub(r"[^\w]", "_", filename.replace(".pdf", "")) + "_",
                    delete=False,
                ) as f:
                    f.write(pdf_bytes)
                    tmp_path = f.name
                result = call_skill("parse_om", {"pdf_path": tmp_path})
                Path(tmp_path).unlink(missing_ok=True)

                if result.get("status") == "ok" and result.get("data"):
                    ctx = dict(result["data"])
                    property_id = _slug(ctx.get("address", ""), ctx.get("zip", ""))

            else:
                result = call_skill(skill_name, ctx)

                # Merge key fields back into ctx so downstream skills can use them
                data = result.get("data") or {}
                if skill_name == "owner_lookup" and isinstance(data, dict):
                    if data.get("owner_name"):
                        ctx["owner_name"] = data["owner_name"]
                    if data.get("bcad_prop_id"):
                        ctx["bcad_prop_id"] = data["bcad_prop_id"]

                elif skill_name == "deed_lookup" and isinstance(data, dict):
                    if data.get("maturity_date"):
                        ctx["deed_maturity_date"] = data["maturity_date"]

            elapsed = round(time.time() - skill_start, 2)
            status = result.get("status", "ok")
            log.info("  ✓ %s [%s] %.2fs", skill_name, status, elapsed)
            if status not in ("ok",):
                log.info("    reason: %s", result.get("reason", "—"))

            all_data[skill_name] = result.get("data")
            yield sse(
                "skill_complete",
                {
                    "skill": skill_name,
                    "status": status,
                    "data": result.get("data"),
                    "property_id": property_id,
                },
            )

        except Exception as e:
            log.error("  ✗ %s EXCEPTION: %s", skill_name, e)
            yield sse("skill_error", {"skill": skill_name, "error": str(e)})

        await asyncio.sleep(0.05)

    # Build research summary for synthesis
    research_keys = [
        "parse_om",
        "owner_lookup",
        "deed_lookup",
        "permit_lookup",
        "tax_lookup",
        "violations_lookup",
        "comps_lookup",
        "portfolio_crawler",
        "maturity_estimator",
    ]
    research_summary = {k: all_data.get(k) for k in research_keys}

    asset_class = ctx.get("asset_class", "")
    asset_class_note = (
        f"NOTE: This property is classified as '{asset_class}', not multifamily. "
        "Adjust your verdict criteria accordingly — for commercial assets, focus on "
        "lease terms, tenant quality, cap rate vs market, and debt coverage."
        if asset_class and asset_class not in ("multifamily", "unknown")
        else ""
    )

    prompt = SYNTHESIS_PROMPT.format(
        research_json=json.dumps(research_summary, indent=2),
        asset_class_note=asset_class_note,
    )

    yield sse("synthesis_start", {"label": "Writing analysis..."})
    log.info("  → synthesis starting (property_id=%s)", property_id)

    full_text = ""
    verdict = "UNKNOWN"

    try:
        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=NVIDIA_KEY,
        )
        stream = client.chat.completions.create(
            model="nvidia/nemotron-3-super-120b-a12b",
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            max_tokens=3000,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content or ""
            full_text += delta
            yield sse("synthesis_chunk", {"text": delta})
            await asyncio.sleep(0)

        for v in ("PURSUE", "WATCHLIST", "PASS"):
            if v in full_text:
                verdict = v
                break

    except Exception as e:
        log.error("  ✗ synthesis EXCEPTION: %s", e)
        yield sse("synthesis_chunk", {"text": f"\n\n[Synthesis error: {e}]"})

    total = round(time.time() - pipeline_start, 1)
    log.info("=== ANALYSIS DONE: verdict=%s total=%.1fs ===", verdict, total)
    yield sse("verdict", {"recommendation": verdict, "full_text": full_text})
    yield sse("done", {})


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    contents = await file.read()
    filename = file.filename or "upload.pdf"
    log.info("POST /analyze — file=%s size=%d", filename, len(contents))
    return StreamingResponse(
        run_analysis(contents, filename),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/health")
def health():
    return {"status": "ok", "model": "nvidia/nemotron-3-super-120b-a12b"}


ui_dist = PROJECT / "ui" / "dist"
if ui_dist.exists():
    app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")
