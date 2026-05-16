import asyncio, importlib.util, json, os, sys, tempfile
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT = Path(__file__).parent
SKILLS = PROJECT / "skills"
DATA = Path(os.environ.get("SENTINEL_DATA_DIR",
            str(PROJECT / "data" / "demo_properties")))

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
    "parse_om":           "Reading offering memorandum",
    "owner_lookup":       "Tracing ownership chain",
    "deed_lookup":        "Pulling loan & deed records",
    "portfolio_crawler":  "Mapping owner portfolio",
    "permit_lookup":      "Checking building permits",
    "tax_lookup":         "Checking tax status",
    "violations_lookup":  "Scanning code violations",
    "comps_lookup":       "Pulling submarket comps",
    "maturity_estimator": "Estimating loan pressure",
    "synthesize_analysis":"Synthesizing findings",
}


def call_skill(name: str, params: dict) -> dict:
    path = SKILLS / name / "run.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.run(params)


def sse(event: str, data: dict) -> str:
    return f"data: {json.dumps({'event': event, **data})}\n\n"


SYNTHESIS_PROMPT = """You are Sentinel, an autonomous multifamily acquisition analyst.

Using ONLY the research data below, write a concise 6-section analysis.
Each section: 2-4 sentences. Direct, factual, cite specific numbers. No marketing language.

Research data:
{research_json}

Write exactly these 6 sections:

## Property Snapshot
[address, units, year built, appraised value, asset class]

## Owner Motivation Profile
[LLC name, principal, hold period years, owner state, portfolio size, intent signals]

## Loan Situation
[lender name, loan amount, origination date, maturity date, CMBS vs regional, refi pressure assessment]

## Submarket Reality Check
[list 2-3 specific comp addresses with prices per unit, submarket avg, rent trend, vacancy]

## Hidden Flags
[list any tax delinquency with dollar amount, open violations with types, or write: No hidden flags detected in public records.]

## Bottom-Line Recommendation
Start with exactly one of: PURSUE / WATCHLIST / PASS
Then 3-5 sentences of reasoning tied to specific signals from the data.
End with: Next move: [one concrete action].
"""


async def run_analysis(pdf_bytes: bytes, filename: str) -> AsyncGenerator[str, None]:
    params: dict = {}
    property_id = "unknown"
    all_data: dict = {}

    for skill_name in SKILL_SEQUENCE:
        yield sse("skill_start", {"skill": skill_name,
                                  "label": SKILL_LABELS[skill_name]})
        await asyncio.sleep(0)

        try:
            if skill_name == "parse_om":
                with tempfile.NamedTemporaryFile(
                    suffix=".pdf", prefix=filename.replace(".pdf", "") + "_",
                    delete=False
                ) as f:
                    f.write(pdf_bytes)
                    tmp_path = f.name
                result = call_skill("parse_om", {"pdf_path": tmp_path})
                Path(tmp_path).unlink(missing_ok=True)
                property_id = result.get("property_id", "unknown")
                params["property_id"] = property_id
            elif skill_name == "synthesize_analysis":
                result = call_skill("synthesize_analysis", params)
            else:
                result = call_skill(skill_name, params)

            all_data[skill_name] = result.get("data")
            yield sse("skill_complete", {
                "skill": skill_name,
                "status": result.get("status", "ok"),
                "data": result.get("data"),
                "property_id": property_id,
            })

        except Exception as e:
            yield sse("skill_error", {"skill": skill_name, "error": str(e)})

        await asyncio.sleep(0.05)

    if property_id == "unknown":
        yield sse("error", {"message": "Could not identify property. Upload one of the three demo OMs."})
        yield sse("done", {})
        return

    research_summary = {k: all_data.get(k) for k in [
        "parse_om", "owner_lookup", "deed_lookup", "permit_lookup",
        "tax_lookup", "violations_lookup", "comps_lookup",
        "portfolio_crawler", "maturity_estimator",
    ]}

    prompt = SYNTHESIS_PROMPT.format(
        research_json=json.dumps(research_summary, indent=2)
    )

    yield sse("synthesis_start", {"label": "Writing analysis..."})

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
            max_tokens=1200,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            full_text += delta
            yield sse("synthesis_chunk", {"text": delta})
            await asyncio.sleep(0)

        for v in ["PURSUE", "WATCHLIST", "PASS"]:
            if v in full_text:
                verdict = v
                break

    except Exception as e:
        yield sse("synthesis_chunk", {"text": f"\n\n[Synthesis error: {e}]"})

    yield sse("verdict", {"recommendation": verdict, "full_text": full_text})
    yield sse("done", {})


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    contents = await file.read()
    filename = file.filename or "upload.pdf"
    return StreamingResponse(
        run_analysis(contents, filename),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/health")
def health():
    return {"status": "ok", "model": "nvidia/nemotron-3-super-120b-a12b"}


# Serve built UI in production
ui_dist = PROJECT / "ui" / "dist"
if ui_dist.exists():
    app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")
