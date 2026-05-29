import asyncio
import importlib.util
import json
import logging
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from collections.abc import AsyncGenerator

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, File, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import HTMLResponse, Response, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from openai import OpenAI  # noqa: E402

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
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
_OR_BASE = "https://openrouter.ai/api/v1"

SKILL_SEQUENCE = [
    "parse_om",
    "owner_lookup",
    "deed_lookup",
    "portfolio_crawler",
    "permit_lookup",
    "tax_lookup",
    "violations_lookup",
    "comps_lookup",
    "underwrite",
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
    "underwrite": "Running financial underwrite",
    "maturity_estimator": "Estimating loan pressure",
    "synthesize_analysis": "Synthesizing findings",
}


def call_skill(name: str, params: dict) -> dict:
    path = SKILLS / name / "run.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.run(params)


BROWSERBASE_SKILLS = {"tax_lookup", "portfolio_crawler"}


async def call_skill_async(name: str, params: dict) -> dict:
    if name in BROWSERBASE_SKILLS:
        # Run in a subprocess — completely isolated event loop, no asyncio conflicts
        path = str(SKILLS / name / "run.py")
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=json.dumps(params).encode()),
                timeout=60.0,
            )
        except TimeoutError:
            proc.kill()
            log.warning("  %s subprocess timed out", name)
            return {
                "job": name,
                "status": "data_unavailable",
                "reason": "BCAD timeout",
                "data": None,
            }
        if proc.returncode == 0 and stdout.strip():
            return json.loads(stdout)
        log.error("  %s subprocess failed: %s", name, stderr.decode()[:300])
        return {
            "job": name,
            "status": "data_unavailable",
            "reason": "BCAD unavailable",
            "data": None,
        }
    # Run blocking skill in thread pool so it doesn't stall the event loop
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, call_skill, name, params)


def sse(event: str, data: dict) -> str:
    return f"data: {json.dumps({'event': event, **data})}\n\n"


def _slug(address: str, zip_: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "_", address.lower()).strip("_")
    return f"{clean}_{zip_}" if zip_ else clean


QUALITY_SKILLS = [
    "parse_om",
    "owner_lookup",
    "deed_lookup",
    "permit_lookup",
    "tax_lookup",
    "violations_lookup",
    "comps_lookup",
    "underwrite",
    "maturity_estimator",
]

SYNTHESIS_PROMPT = """You are Sentinel, an autonomous real estate acquisition analyst.

RULES — obey exactly:
1. Start your response with the line: ## Bottom-Line Recommendation
2. Your FIRST word after that header must be PURSUE, WATCHLIST, or PASS.
3. Write ONLY the 7 sections listed below. No preamble. No thinking. No meta-commentary. No reasoning steps.
4. If any field is null or unavailable: write `data_unavailable (from [source])` — do NOT explain or reason about why it is missing.
5. Every number cited must be followed by its source tag. Use ONLY these: (from OM), (calculated from OM), (from HUD SAFMR), (from Census ACS), (from ATTOM), (from BCAD), (from deed_lookup), (from tax_lookup). deed_lookup data = Bexar County Clerk, NOT BCAD. tax_lookup data = BCAD. Do not mix them up.
6. Each section: 2-4 sentences. Direct and factual. No marketing language.

{asset_class_note}
{coverage_note}
{context_deals}

Research data:
{research_json}

Write exactly these 7 sections (START with ## Bottom-Line Recommendation):

## Bottom-Line Recommendation
First word: PURSUE, WATCHLIST, or PASS. Then 2 sentences max. End: Next move: [one action].

## Property Snapshot
[address, property type, units, year built, asking price, appraised value — each with source tag]

## Owner Motivation Profile
[owner name, hold period if known, owner state (flag if out-of-state), portfolio size, motivation signals]

## Loan Situation
[lender, loan amount, origination date, estimated maturity date, loan type, refinance pressure assessment.
If loan_distress_signals or loan_assignments are present in the data, describe the assignment chain and what it suggests about the borrower's situation — multiple loan assignments in a short period indicate special servicing and likely forced sale pressure.]

## Financial Underwrite
[NOI estimate with source, cap rate at ask if available, price per unit if available, value-add payback math if available. Then: for each bedroom type in the unit_mix, show in_place_rent (this is MONTHLY per-unit rent in dollars, e.g. $1,200/mo) vs Census median rent and the discount-to-market percentage. Do NOT use annual revenue figures here. If underwrite data is null, state that financial section was not found in the OM.]

## Submarket Reality Check
[nearby comparable multifamily sales with prices, market rent level, vacancy rate, trend]

## Hidden Flags
[tax delinquency with dollar amount, open code violations with types — or: No hidden flags detected in public records.]
"""


async def _log_run(
    address: str,
    verdict: str,
    confidence: str,
    skill_results: list,
    synthesis_chars: int,
    total_elapsed: float,
    pdf_filename: str = "",
    all_data: dict | None = None,
    ctx: dict | None = None,
):
    try:
        import httpx as _httpx

        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not supabase_url or not supabase_key:
            return

        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }

        async with _httpx.AsyncClient() as client:
            # pipeline_runs (existing)
            await client.post(
                f"{supabase_url}/rest/v1/pipeline_runs",
                headers=headers,
                json={
                    "type": "om_analysis",
                    "property_address": address,
                    "verdict": verdict,
                    "confidence": confidence,
                    "total_elapsed_s": total_elapsed,
                    "skill_results": skill_results,
                    "synthesis_chars": synthesis_chars,
                },
                timeout=5,
            )

            # om_analyses — institutional context graph (Stage 4)
            if all_data and ctx:
                # all_data["parse_om"] is already the data dict (server stores result.get("data"))
                parse_data = all_data.get("parse_om") or {}
                financials = parse_data.get("financials") or {}
                deed = all_data.get("deed_lookup") or {}
                tax = all_data.get("tax_lookup") or {}
                violations = all_data.get("violations_lookup") or {}

                has_liens = bool(deed.get("mechanics_liens"))
                tax_delinquent = bool(tax.get("delinquent"))
                open_violations = len(violations.get("violations") or [])

                await client.post(
                    f"{supabase_url}/rest/v1/om_analyses",
                    headers=headers,
                    json={
                        "address": ctx.get("address"),
                        "city": ctx.get("city"),
                        "state": ctx.get("state"),
                        "zip": ctx.get("zip"),
                        "asset_class": ctx.get("asset_class"),
                        "units": ctx.get("units"),
                        "year_built": ctx.get("year_built"),
                        "asking_price": ctx.get("asking_price"),
                        "annual_in_place_revenue": financials.get(
                            "annual_in_place_revenue"
                        ),
                        "annual_projected_revenue": financials.get(
                            "annual_projected_revenue"
                        ),
                        "broker_cap_rate": financials.get("broker_cap_rate"),
                        "offering_structure": financials.get("offering_structure"),
                        "citations": parse_data.get("citations") or {},
                        "has_liens": has_liens,
                        "tax_delinquent": tax_delinquent,
                        "open_violations": open_violations,
                        "verdict": verdict,
                        "confidence": confidence,
                        "pdf_filename": pdf_filename,
                    },
                    timeout=5,
                )
    except Exception:
        pass


async def _get_context_deals(state: str, asset_class: str, current_address: str) -> str:
    """Pull last 3 similar deals from om_analyses for institutional context."""
    try:
        import httpx as _httpx

        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not supabase_url or not supabase_key:
            return ""

        async with _httpx.AsyncClient() as client:
            resp = await client.get(
                f"{supabase_url}/rest/v1/om_analyses",
                headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                },
                params={
                    "state": f"eq.{state}",
                    "asset_class": f"eq.{asset_class}",
                    "address": f"neq.{current_address}",
                    "order": "created_at.desc",
                    "limit": "3",
                    "select": "address,verdict,annual_in_place_revenue,has_liens,tax_delinquent,open_violations",
                },
                timeout=3,
            )
            deals = resp.json()
            if not deals or not isinstance(deals, list):
                return ""
            lines = []
            for d in deals:
                rev = (
                    f"${d['annual_in_place_revenue']:,}"
                    if d.get("annual_in_place_revenue")
                    else "N/A"
                )
                lines.append(
                    f"- {d['address']}: {d.get('verdict', '?')} | revenue {rev} | "
                    f"liens:{d.get('has_liens', False)} | tax_delinquent:{d.get('tax_delinquent', False)}"
                )
            return "Prior similar deals analyzed by this firm:\n" + "\n".join(lines)
    except Exception:
        return ""


def _apply_deed_ctx(ctx: dict, data: dict) -> None:
    """Merge deed_lookup result into ctx: maturity estimate + distress signals."""
    orig = data.get("origination_date", "")
    if orig and not ctx.get("deed_maturity_date"):
        try:
            from datetime import date as _date
            import re as _re

            m_orig = _re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", orig)
            y4_orig = _re.match(r"(\d{4})-(\d{2})-(\d{2})", orig)
            if y4_orig:
                orig_d = _date(
                    int(y4_orig.group(1)), int(y4_orig.group(2)), int(y4_orig.group(3))
                )
            elif m_orig:
                orig_d = _date(
                    int(m_orig.group(3)), int(m_orig.group(1)), int(m_orig.group(2))
                )
            else:
                orig_d = None
            if orig_d:
                maturity_d = _date(orig_d.year + 5, orig_d.month, orig_d.day)
                ctx["deed_maturity_date"] = maturity_d.isoformat()
                log.info("  maturity estimated: %s (orig=%s + 5yr)", maturity_d, orig_d)
        except Exception as _e:
            log.warning("  maturity estimation failed: %s", _e)
    if data.get("distress_signals"):
        ctx["loan_distress_signals"] = data["distress_signals"]
    if data.get("assignments"):
        ctx["loan_assignments"] = data["assignments"]


async def run_analysis(pdf_bytes: bytes, filename: str) -> AsyncGenerator[str, None]:
    ctx: dict = {}
    all_data: dict = {}
    skill_log: list = []
    property_id = "upload"
    pipeline_start = time.time()
    log.info("=== ANALYSIS START: %s (%d bytes) ===", filename, len(pdf_bytes))

    # ── WAVE 1: parse_om ──────────────────────────────────────────────────────
    yield sse("skill_start", {"skill": "parse_om", "label": SKILL_LABELS["parse_om"]})
    await asyncio.sleep(0)
    t0 = time.time()
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".pdf",
            prefix=re.sub(r"[^\w]", "_", filename.replace(".pdf", "")) + "_",
            delete=False,
        ) as f:
            f.write(pdf_bytes)
            tmp_path = f.name
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, call_skill, "parse_om", {"pdf_path": tmp_path}
        )
        Path(tmp_path).unlink(missing_ok=True)
        if result.get("status") == "ok" and result.get("data"):
            ctx = dict(result["data"])
            property_id = _slug(ctx.get("address", ""), ctx.get("zip", ""))
            financials = ctx.get("financials") or {}
            for _fkey in [
                "unit_mix",
                "occupancy_rate",
                "annual_in_place_revenue",
                "total_expense_per_unit_annual",
                "value_add_rent_premium_per_unit",
                "renovation_cost_per_unit",
            ]:
                if financials.get(_fkey) is not None:
                    ctx[_fkey] = financials[_fkey]
        status = result.get("status", "ok")
        elapsed = round(time.time() - t0, 2)
        log.info("  ✓ parse_om [%s] %.2fs", status, elapsed)
        all_data["parse_om"] = result.get("data")
        skill_log.append(
            {
                "skill": "parse_om",
                "status": status,
                "elapsed_s": elapsed,
                "has_data": all_data["parse_om"] is not None,
            }
        )
        yield sse(
            "skill_complete",
            {
                "skill": "parse_om",
                "status": status,
                "data": result.get("data"),
                "property_id": property_id,
            },
        )
    except Exception as e:
        log.error("  ✗ parse_om EXCEPTION: %s", e)
        yield sse("skill_error", {"skill": "parse_om", "error": str(e)})

    # ── WAVE 2: owner_lookup (fast ATTOM call; gives bcad_prop_id to tax_lookup) ──
    yield sse(
        "skill_start", {"skill": "owner_lookup", "label": SKILL_LABELS["owner_lookup"]}
    )
    await asyncio.sleep(0)
    t0 = time.time()
    try:
        result = await call_skill_async("owner_lookup", ctx)
        data = result.get("data") or {}
        for field in (
            "owner_name",
            "attom_lender",
            "attom_loan_amount",
            "attom_loan_date",
            "absentee_owner",
            "corporate_owner",
            "attom_id",
            "apn",
            "bcad_prop_id",
        ):
            if data.get(field):
                ctx[field] = data[field]
        status = result.get("status", "ok")
        elapsed = round(time.time() - t0, 2)
        log.info("  ✓ owner_lookup [%s] %.2fs", status, elapsed)
        all_data["owner_lookup"] = result.get("data")
        skill_log.append(
            {
                "skill": "owner_lookup",
                "status": status,
                "elapsed_s": elapsed,
                "has_data": all_data["owner_lookup"] is not None,
            }
        )
        yield sse(
            "skill_complete",
            {
                "skill": "owner_lookup",
                "status": status,
                "data": result.get("data"),
                "property_id": property_id,
            },
        )
    except Exception as e:
        log.error("  ✗ owner_lookup EXCEPTION: %s", e)
        yield sse("skill_error", {"skill": "owner_lookup", "error": str(e)})

    # ── WAVE 3: all remaining enrichment skills in parallel ───────────────────
    PARALLEL_SKILLS = [
        "deed_lookup",
        "portfolio_crawler",
        "permit_lookup",
        "tax_lookup",
        "violations_lookup",
        "comps_lookup",
        "underwrite",
        "synthesize_analysis",
    ]
    for name in PARALLEL_SKILLS:
        yield sse("skill_start", {"skill": name, "label": SKILL_LABELS[name]})
    await asyncio.sleep(0)

    ctx_snap = dict(ctx)  # snapshot so all parallel skills see consistent state

    async def _run_parallel(name: str):
        t = time.time()
        try:
            res = await call_skill_async(name, dict(ctx_snap))
            return name, res, round(time.time() - t, 2), None
        except Exception as exc:
            return (
                name,
                {"status": "error", "data": None, "reason": str(exc)},
                round(time.time() - t, 2),
                str(exc),
            )

    tasks = [asyncio.create_task(_run_parallel(n)) for n in PARALLEL_SKILLS]
    for coro in asyncio.as_completed(tasks):
        name, result, elapsed, err = await coro
        data = result.get("data") or {}
        status = result.get("status", "ok")
        log.info("  ✓ %s [%s] %.2fs", name, status, elapsed)
        if name == "deed_lookup" and isinstance(data, dict):
            _apply_deed_ctx(ctx, data)
        all_data[name] = result.get("data")
        skill_log.append(
            {
                "skill": name,
                "status": status,
                "elapsed_s": elapsed,
                "has_data": all_data[name] is not None,
            }
        )
        if err:
            yield sse("skill_error", {"skill": name, "error": err})
        else:
            yield sse(
                "skill_complete",
                {
                    "skill": name,
                    "status": status,
                    "data": result.get("data"),
                    "property_id": property_id,
                },
            )
        await asyncio.sleep(0)

    # ── WAVE 4: maturity_estimator — needs deed_maturity_date from wave 3 ────────
    yield sse(
        "skill_start",
        {"skill": "maturity_estimator", "label": SKILL_LABELS["maturity_estimator"]},
    )
    await asyncio.sleep(0)
    t0 = time.time()
    try:
        result = await call_skill_async("maturity_estimator", ctx)
        status = result.get("status", "ok")
        elapsed = round(time.time() - t0, 2)
        log.info("  ✓ maturity_estimator [%s] %.2fs", status, elapsed)
        all_data["maturity_estimator"] = result.get("data")
        skill_log.append(
            {
                "skill": "maturity_estimator",
                "status": status,
                "elapsed_s": elapsed,
                "has_data": all_data["maturity_estimator"] is not None,
            }
        )
        yield sse(
            "skill_complete",
            {
                "skill": "maturity_estimator",
                "status": status,
                "data": result.get("data"),
                "property_id": property_id,
            },
        )
    except Exception as e:
        log.error("  ✗ maturity_estimator EXCEPTION: %s", e)
        yield sse("skill_error", {"skill": "maturity_estimator", "error": str(e)})

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
        "underwrite",
        "maturity_estimator",
    ]
    research_summary = {k: all_data.get(k) for k in research_keys}

    # Inject distress signals derived from deed_lookup into synthesis context
    if ctx.get("loan_distress_signals"):
        research_summary["loan_distress_signals"] = ctx["loan_distress_signals"]
    if ctx.get("loan_assignments"):
        research_summary["loan_assignments"] = ctx["loan_assignments"]

    # Data quality score
    clean = [k for k in QUALITY_SKILLS if all_data.get(k) is not None]
    missing = [k for k in QUALITY_SKILLS if all_data.get(k) is None]
    score = len(clean)
    confidence = "HIGH" if score >= 6 else "MEDIUM" if score >= 4 else "LOW"
    coverage_note = (
        f"Data coverage: {score}/{len(QUALITY_SKILLS)} sources returned data."
        + (f" Missing: {', '.join(missing)}." if missing else "")
    )

    asset_class = ctx.get("asset_class", "")
    asset_class_note = (
        f"NOTE: This property is classified as '{asset_class}', not multifamily. "
        "Adjust your verdict criteria accordingly — for commercial assets, focus on "
        "lease terms, tenant quality, cap rate vs market, and debt coverage."
        if asset_class and asset_class not in ("multifamily", "unknown")
        else ""
    )

    # Stage 4: pull institutional context (last 3 similar deals this firm analyzed)
    context_deals = await _get_context_deals(
        state=ctx.get("state", ""),
        asset_class=ctx.get("asset_class", "multifamily"),
        current_address=ctx.get("address", ""),
    )

    prompt = SYNTHESIS_PROMPT.format(
        research_json=json.dumps(research_summary, indent=2),
        asset_class_note=asset_class_note,
        coverage_note=coverage_note,
        context_deals=context_deals,
    )

    yield sse("synthesis_start", {"label": "Writing analysis..."})
    log.info("  → synthesis starting (property_id=%s)", property_id)

    full_text = ""
    verdict = "UNKNOWN"

    def _run_synthesis(p: str) -> str:
        client = OpenAI(base_url=_OR_BASE, api_key=OPENROUTER_KEY, max_retries=0)
        sys_msg = "You are a real estate analyst. Respond with ONLY the formatted sections requested. Your first line must be '## Bottom-Line Recommendation'. Your second line must start with PURSUE, WATCHLIST, or PASS. No thinking. No reasoning steps. No meta-commentary. No preamble."
        msgs = [{"role": "system", "content": sys_msg}, {"role": "user", "content": p}]
        # Fallback chain: different providers so rate limits don't stack
        _models = [
            "meta-llama/llama-3.3-70b-instruct:free",  # Venice
            "google/gemma-4-31b-it:free",  # Google
            "meta-llama/llama-3.2-3b-instruct:free",  # smaller, different provider
        ]
        last_err = None
        for model in _models:
            try:
                stream = client.chat.completions.create(
                    model=model,
                    messages=msgs,
                    stream=True,
                    max_tokens=3000,
                    temperature=0,
                )
                text = ""
                for chunk in stream:
                    if chunk.choices:
                        text += chunk.choices[0].delta.content or ""
                log.info("  synthesis model used: %s", model)
                return text.strip()
            except Exception as e:
                if "429" in str(e) or "404" in str(e):
                    last_err = e
                    continue
                raise
        raise last_err

    try:
        loop = asyncio.get_running_loop()
        full_text = await asyncio.wait_for(
            loop.run_in_executor(None, _run_synthesis, prompt),
            timeout=200.0,
        )
        # Strip preamble: find "## Bottom-Line Recommendation" immediately followed
        # (within a line or two) by PURSUE/WATCHLIST/PASS — that's the real start.
        import re as _re

        real_start = _re.search(
            r"## Bottom-Line Recommendation\s*\n\s*(PURSUE|WATCHLIST|PASS)",
            full_text,
        )
        if real_start:
            full_text = full_text[real_start.start() :]
        else:
            # Fallback: any ## header that isn't at position 0
            for header in ("## Bottom-Line", "## Property Snapshot"):
                idx = full_text.find(header)
                if idx > 0:
                    full_text = full_text[idx:]
                    break
        # Try extracting verdict from text first
        upper = full_text.upper()
        for v in ("PURSUE", "WATCHLIST", "PASS"):
            if v in upper:
                verdict = v
                break
        # Fallback: fast free model via OpenRouter to extract verdict word
        if verdict == "UNKNOWN" and full_text:
            try:
                _vc = OpenAI(
                    base_url=_OR_BASE,
                    api_key=OPENROUTER_KEY,
                    timeout=15.0,
                    max_retries=0,
                )
                _vr = _vc.chat.completions.create(
                    model="meta-llama/llama-3.1-8b-instruct:free",
                    messages=[
                        {
                            "role": "user",
                            "content": f"Based on this real estate analysis, reply with exactly one word — PURSUE, WATCHLIST, or PASS:\n\n{full_text[:2000]}",
                        }
                    ],
                    max_tokens=5,
                    temperature=0,
                    stream=False,
                )
                word = (_vr.choices[0].message.content or "").strip().upper().split()[0]
                if word in ("PURSUE", "WATCHLIST", "PASS"):
                    verdict = word
            except Exception:
                pass
    except asyncio.TimeoutError:
        log.error("  ✗ synthesis timed out after 200s")
        full_text = "\n\n[Analysis timed out — model did not respond within 200s]"
    except Exception as e:
        log.error("  ✗ synthesis EXCEPTION: %s", e)
        full_text = f"\n\n[Synthesis error: {e}]"

    yield sse("synthesis_chunk", {"text": full_text})

    total = round(time.time() - pipeline_start, 1)
    log.info(
        "=== ANALYSIS DONE: verdict=%s confidence=%s total=%.1fs ===",
        verdict,
        confidence,
        total,
    )
    yield sse(
        "verdict",
        {
            "recommendation": verdict,
            "full_text": full_text,
            "data_quality": {
                "confidence": confidence,
                "sources_clean": score,
                "sources_total": len(QUALITY_SKILLS),
                "missing": missing,
            },
        },
    )
    asyncio.create_task(
        _log_run(
            address=ctx.get("address", filename),
            verdict=verdict,
            confidence=confidence,
            skill_results=skill_log,
            synthesis_chars=len(full_text),
            total_elapsed=total,
            pdf_filename=filename,
            all_data=all_data,
            ctx=ctx,
        )
    )
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


@app.post("/export")
async def export_analysis(body: dict):
    """Generate a PDF report from a completed analysis and optionally email it."""
    synthesis_text = body.get("synthesis_text", "")
    verdict = body.get("verdict", "UNKNOWN")
    all_data = body.get("all_data", {})
    data_quality = body.get("data_quality")
    recipient_email = body.get("recipient_email", "")
    property_address = (all_data.get("parse_om") or {}).get("address", "property")

    try:
        from reports.generate import build_om_context, render_pdf

        context = build_om_context(synthesis_text, verdict, all_data, data_quality)
        pdf_bytes = render_pdf("om_analysis.html", context)
    except ImportError:
        return Response(
            content=json.dumps(
                {
                    "error": "WeasyPrint not installed. Run: brew install cairo pango gdk-pixbuf && uv add weasyprint jinja2"
                }
            ),
            status_code=503,
            media_type="application/json",
        )
    except Exception as e:
        log.error("PDF generation error: %s", e)
        return Response(
            content=json.dumps({"error": str(e)}),
            status_code=500,
            media_type="application/json",
        )

    email_status = None
    if recipient_email:
        try:
            from reports.deliver import send_om_report

            email_id = send_om_report(recipient_email, pdf_bytes, property_address)
            log.info("OM report emailed to %s (id=%s)", recipient_email, email_id)
            email_status = {"sent": True, "id": email_id}
        except Exception as e:
            log.error("Email delivery error: %s", e)
            email_status = {"sent": False, "error": str(e)}

    safe = re.sub(r"[^\w]", "_", property_address)[:40]
    filename = f"Noor_Analysis_{safe}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if email_status:
        headers["X-Email-Status"] = json.dumps(email_status)
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@app.get("/health")
async def health_check():
    """Diagnostic endpoint: checks every API key and dependency. Green = ready, red = broken."""
    import httpx as _httpx

    checks: dict[str, dict] = {}

    # --- WeasyPrint ---
    try:
        from weasyprint import HTML as _WP  # noqa: F401

        checks["weasyprint"] = {"status": "ok", "detail": "importable"}
    except Exception as e:
        checks["weasyprint"] = {
            "status": "error",
            "detail": str(e),
            "fix": "brew install cairo pango gdk-pixbuf && uv add weasyprint",
        }

    # --- PDF templates ---
    from reports.generate import TEMPLATES_DIR

    for tmpl in ("om_analysis.html", "monthly_report.html"):
        key = f"template:{tmpl}"
        p = TEMPLATES_DIR / tmpl
        checks[key] = (
            {"status": "ok"}
            if p.exists()
            else {"status": "error", "detail": f"missing: {p}"}
        )

    # --- API keys (presence only — no live calls to avoid costs) ---
    key_checks = {
        "NVIDIA_API_KEY": {
            "fix": "Get from build.nvidia.com — required for parse_om and synthesis"
        },
        "OPENROUTER_API_KEY": {"fix": "Get from openrouter.ai"},
        "ATTOM_API_KEY": {"fix": "Get from api.gateway.attomdata.com"},
        "RESEND_API_KEY": {"fix": "Get from resend.com"},
        "BROWSERBASE_API_KEY": {"fix": "Get from browserbase.com"},
        "MODEL_API_KEY": {"fix": "OpenAI key for Stagehand browser agent"},
        "CENSUS_API_KEY": {"fix": "Free at api.census.gov/data/key_signup.html"},
        "SUPABASE_URL": {"fix": "Get from supabase.com project settings"},
        "SUPABASE_SERVICE_ROLE_KEY": {
            "fix": "Get from supabase.com project settings > API"
        },
    }
    for env_key, meta in key_checks.items():
        val = os.environ.get(env_key, "")
        if val:
            checks[f"env:{env_key}"] = {
                "status": "ok",
                "detail": f"set ({len(val)} chars)",
            }
        else:
            checks[f"env:{env_key}"] = {
                "status": "error",
                "detail": "NOT SET",
                "fix": meta["fix"],
            }

    # --- Resend domain live check ---
    resend_key = os.environ.get("RESEND_API_KEY", "")
    if resend_key:
        try:
            async with _httpx.AsyncClient() as client:
                r = await client.get(
                    "https://api.resend.com/domains",
                    headers={"Authorization": f"Bearer {resend_key}"},
                    timeout=5,
                )
            domains = r.json().get("data", [])
            verified = [d["name"] for d in domains if d.get("status") == "verified"]
            if verified:
                checks["resend:domain"] = {
                    "status": "ok",
                    "detail": f"verified domains: {', '.join(verified)}",
                }
            else:
                checks["resend:domain"] = {
                    "status": "error",
                    "detail": "No verified domains",
                    "fix": "Add domain at resend.com/domains",
                }
        except Exception as e:
            checks["resend:domain"] = {"status": "error", "detail": str(e)}

    # --- Supabase connectivity ---
    sb_url = os.environ.get("SUPABASE_URL", "")
    sb_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if sb_url and sb_key:
        try:
            async with _httpx.AsyncClient() as client:
                r = await client.get(
                    f"{sb_url}/rest/v1/pipeline_runs",
                    headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}"},
                    params={"select": "id", "limit": "1"},
                    timeout=5,
                )
            checks["supabase:pipeline_runs"] = {
                "status": "ok",
                "detail": f"HTTP {r.status_code}",
            }
        except Exception as e:
            checks["supabase:pipeline_runs"] = {"status": "error", "detail": str(e)}

    errors = [k for k, v in checks.items() if v["status"] == "error"]
    overall = "ok" if not errors else "degraded"

    return {
        "status": overall,
        "errors": errors,
        "checks": checks,
    }


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    import httpx as _httpx

    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    runs = []
    fetch_error = ""

    if supabase_url and supabase_key:
        try:
            async with _httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{supabase_url}/rest/v1/pipeline_runs",
                    headers={
                        "apikey": supabase_key,
                        "Authorization": f"Bearer {supabase_key}",
                    },
                    params={"select": "*", "order": "created_at.desc", "limit": "20"},
                    timeout=10,
                )
                resp.raise_for_status()
                runs = resp.json()
        except Exception as e:
            fetch_error = str(e)

    # Aggregate stats
    total = len(runs)
    successes = sum(
        1 for r in runs if r.get("verdict") in ("PURSUE", "WATCHLIST", "PASS")
    )
    success_rate = round(successes / total * 100, 1) if total else 0
    elapsed_vals = [
        r["total_elapsed_s"] for r in runs if r.get("total_elapsed_s") is not None
    ]
    avg_elapsed = round(sum(elapsed_vals) / len(elapsed_vals), 1) if elapsed_vals else 0

    # Per-skill reliability across all runs
    skill_stats: dict[str, dict] = {}
    for r in runs:
        for sk in r.get("skill_results") or []:
            name = sk.get("skill", "?")
            if name not in skill_stats:
                skill_stats[name] = {"total": 0, "ok": 0, "with_data": 0}
            skill_stats[name]["total"] += 1
            if sk.get("status") == "ok":
                skill_stats[name]["ok"] += 1
            if sk.get("has_data"):
                skill_stats[name]["with_data"] += 1

    def verdict_badge(v: str) -> str:
        colors = {"PURSUE": "#22c55e", "WATCHLIST": "#f59e0b", "PASS": "#ef4444"}
        bg = colors.get(v, "#64748b")
        return (
            f'<span style="background:{bg};color:#fff;padding:2px 8px;'
            f'border-radius:9999px;font-size:11px;font-weight:700;">{v or "—"}</span>'
        )

    def skill_dots(skill_results: list) -> str:
        if not skill_results:
            return "—"
        ok = sum(1 for s in skill_results if s.get("has_data"))
        total_sk = len(skill_results)
        pct = int(ok / total_sk * 100) if total_sk else 0
        color = "#22c55e" if pct >= 70 else "#f59e0b" if pct >= 40 else "#ef4444"
        return f'<span style="color:{color};font-weight:600;">{ok}/{total_sk}</span>'

    rows_html = ""
    for r in runs:
        ts = (r.get("created_at") or "")[:16].replace("T", " ")
        rows_html += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;font-size:13px;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
              title="{r.get("property_address", "")}">{r.get("property_address") or "—"}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:center;">{verdict_badge(r.get("verdict", ""))}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:center;font-size:13px;">{r.get("confidence") or "—"}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:center;font-size:13px;">{round(r["total_elapsed_s"], 1) if r.get("total_elapsed_s") else "—"}s</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:center;">{skill_dots(r.get("skill_results") or [])}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;font-size:12px;color:#64748b;">{r.get("type", "")}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;font-size:12px;color:#64748b;">{ts}</td>
        </tr>"""

    skill_rows_html = ""
    for sk_name, stats in skill_stats.items():
        pct = round(stats["ok"] / stats["total"] * 100, 0) if stats["total"] else 0
        data_pct = (
            round(stats["with_data"] / stats["total"] * 100, 0) if stats["total"] else 0
        )
        bar_color = "#22c55e" if pct >= 80 else "#f59e0b" if pct >= 50 else "#ef4444"
        skill_rows_html += f"""
        <tr>
          <td style="padding:7px 12px;border-bottom:1px solid #e2e8f0;font-size:13px;font-family:monospace;">{sk_name}</td>
          <td style="padding:7px 12px;border-bottom:1px solid #e2e8f0;text-align:center;font-size:13px;">{stats["total"]}</td>
          <td style="padding:7px 12px;border-bottom:1px solid #e2e8f0;">
            <div style="display:flex;align-items:center;gap:8px;">
              <div style="flex:1;background:#e2e8f0;border-radius:4px;height:8px;">
                <div style="width:{pct}%;background:{bar_color};border-radius:4px;height:8px;"></div>
              </div>
              <span style="font-size:12px;color:#334155;min-width:36px;">{int(pct)}%</span>
            </div>
          </td>
          <td style="padding:7px 12px;border-bottom:1px solid #e2e8f0;text-align:center;font-size:13px;">{int(data_pct)}%</td>
        </tr>"""

    error_banner = (
        f'<div style="background:#fef2f2;border:1px solid #fca5a5;color:#b91c1c;padding:10px 16px;'
        f'border-radius:6px;margin-bottom:16px;font-size:13px;">Supabase fetch error: {fetch_error}</div>'
        if fetch_error
        else ""
    )
    no_env_banner = (
        '<div style="background:#fffbeb;border:1px solid #fcd34d;color:#92400e;padding:10px 16px;'
        'border-radius:6px;margin-bottom:16px;font-size:13px;">SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY '
        "not configured — no data available.</div>"
        if not (supabase_url and supabase_key)
        else ""
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Sentinel — Pipeline Monitor</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f8fafc; color: #1e293b; }}
    .topbar {{ background: #0f172a; color: #fff; padding: 14px 32px;
               display: flex; align-items: center; gap: 12px; }}
    .topbar h1 {{ font-size: 18px; font-weight: 700; letter-spacing: -0.3px; }}
    .topbar .badge {{ background: #1e40af; font-size: 11px; padding: 2px 8px;
                      border-radius: 9999px; font-weight: 600; }}
    .container {{ max-width: 1100px; margin: 32px auto; padding: 0 24px; }}
    .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 32px; }}
    .stat {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
             padding: 20px 24px; }}
    .stat .label {{ font-size: 12px; color: #64748b; font-weight: 600;
                    text-transform: uppercase; letter-spacing: .5px; }}
    .stat .value {{ font-size: 32px; font-weight: 700; color: #0f172a; margin-top: 6px; }}
    .card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
             margin-bottom: 24px; overflow: hidden; }}
    .card-header {{ padding: 14px 20px; border-bottom: 1px solid #e2e8f0;
                    font-weight: 700; font-size: 14px; color: #0f172a;
                    background: #f8fafc; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ padding: 9px 12px; text-align: left; font-size: 11px; font-weight: 700;
          color: #64748b; text-transform: uppercase; letter-spacing: .5px;
          border-bottom: 2px solid #e2e8f0; background: #f8fafc; }}
    tr:hover td {{ background: #f8fafc; }}
  </style>
</head>
<body>
  <div class="topbar">
    <h1>Sentinel Pipeline Monitor</h1>
    <span class="badge">INTERNAL</span>
  </div>
  <div class="container">
    {no_env_banner}{error_banner}
    <div class="stats">
      <div class="stat">
        <div class="label">Total Runs (last 20)</div>
        <div class="value">{total}</div>
      </div>
      <div class="stat">
        <div class="label">Verdict Success Rate</div>
        <div class="value">{success_rate}%</div>
      </div>
      <div class="stat">
        <div class="label">Avg Pipeline Time</div>
        <div class="value">{avg_elapsed}s</div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">Recent Runs</div>
      <table>
        <thead>
          <tr>
            <th>Address</th>
            <th style="text-align:center">Verdict</th>
            <th style="text-align:center">Confidence</th>
            <th style="text-align:center">Elapsed</th>
            <th style="text-align:center">Skills OK</th>
            <th>Type</th>
            <th>Timestamp (UTC)</th>
          </tr>
        </thead>
        <tbody>{rows_html if rows_html else '<tr><td colspan="7" style="padding:24px;text-align:center;color:#94a3b8;">No runs recorded yet.</td></tr>'}</tbody>
      </table>
    </div>

    <div class="card">
      <div class="card-header">Skill Reliability</div>
      <table>
        <thead>
          <tr>
            <th>Skill</th>
            <th style="text-align:center">Runs</th>
            <th>Status OK Rate</th>
            <th style="text-align:center">Data Return Rate</th>
          </tr>
        </thead>
        <tbody>{skill_rows_html if skill_rows_html else '<tr><td colspan="4" style="padding:24px;text-align:center;color:#94a3b8;">No skill data yet.</td></tr>'}</tbody>
      </table>
    </div>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)


ui_dist = PROJECT / "ui" / "dist"
if ui_dist.exists():
    app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")
