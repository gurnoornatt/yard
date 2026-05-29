"""
Motivated seller scanner for Bexar County multifamily.

Workflow:
  1. ATTOM bulk query — all multifamily within 20mi of SA center
  2. Score each property by seller pressure signals
  3. Top 30 → mini-pipeline: owner_lookup + tax_lookup + comps_lookup
  4. Generate PDF → deliver to all active subscribers

Usage:
  python3 scanner/scan_bexar.py [--dry-run] [--top N] [--no-email]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import json
import logging
import os
import re
import sys
import threading
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from scanner.score import ScoredProperty, score_property  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scanner")

ATTOM_KEY = os.environ.get("ATTOM_API_KEY", "")
ATTOM_BASE = "https://api.gateway.attomdata.com/propertyapi/v1.0.0"

# Bexar County FIPS geoid — kept for reference; county-level snapshot queries time out
BEXAR_GEOID = "CO48029"

# All Bexar County ZIP codes that contain multifamily stock
BEXAR_ZIPS = [
    "78201",
    "78202",
    "78203",
    "78204",
    "78205",
    "78206",
    "78207",
    "78208",
    "78209",
    "78210",
    "78211",
    "78212",
    "78213",
    "78214",
    "78215",
    "78216",
    "78217",
    "78218",
    "78219",
    "78220",
    "78221",
    "78222",
    "78223",
    "78224",
    "78225",
    "78226",
    "78227",
    "78228",
    "78229",
    "78230",
    "78231",
    "78232",
    "78233",
    "78237",
    "78238",
    "78239",
    "78240",
    "78241",
    "78242",
    "78244",
    "78245",
    "78247",
    "78248",
    "78249",
    "78250",
    "78251",
    "78252",
    "78253",
    "78254",
    "78255",
    "78256",
    "78257",
    "78258",
    "78259",
    "78260",
    "78261",
    "78263",
    "78264",
    "78266",
]


class _RateLimiter:
    """Token-bucket rate limiter. Thread-safe, shared across all workers."""

    def __init__(self, max_per_minute: int):
        self._lock = threading.Lock()
        self._calls: list[float] = []
        self._max = max_per_minute

    def acquire(self) -> None:
        with self._lock:
            now = time.time()
            self._calls = [t for t in self._calls if now - t < 60]
            if len(self._calls) >= self._max:
                sleep_for = 60 - (now - self._calls[0]) + 0.05
                time.sleep(sleep_for)
                now = time.time()
                self._calls = [t for t in self._calls if now - t < 60]
            self._calls.append(now)


# Stay well under ATTOM's 150 req/min limit — leaves headroom for /analyze calls
_attom_limiter = _RateLimiter(max_per_minute=100)


def _attom_headers() -> dict:
    return {"APIKey": ATTOM_KEY, "Accept": "application/json"}


def _fetch_zip_multifamily(zip_code: str) -> list[dict]:
    """Fetch all multifamily properties for one ZIP code, paginating as needed."""
    results = []
    page = 1
    while True:
        try:
            _attom_limiter.acquire()
            r = httpx.get(
                f"{ATTOM_BASE}/assessment/snapshot",
                params={
                    "postalcode": zip_code,
                    "propertytype": "MULTI FAMILY DWELLING",
                    "pageSize": 100,
                    "page": page,
                },
                headers=_attom_headers(),
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            properties = data.get("property") or []
            if not properties:
                break
            results.extend(properties)
            if len(properties) < 100:
                break
            page += 1
        except Exception as e:
            log.warning("ATTOM fetch error zip=%s page=%d: %s", zip_code, page, e)
            break
    return results


def fetch_all_multifamily() -> list[dict]:
    """Fetch all Bexar County multifamily via parallel ZIP-code queries.

    County-geoid snapshot queries time out — ZIP-level queries are fast and reliable.
    Runs up to 6 ZIPs concurrently; deduplicates by attomId.
    """
    all_results: list[dict] = []
    seen_ids: set[str] = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(_fetch_zip_multifamily, z): z for z in BEXAR_ZIPS}
        for future in concurrent.futures.as_completed(futures):
            z = futures[future]
            props = future.result()
            new_props = []
            for p in props:
                aid = str(
                    p.get("identifier", {}).get("attomId")
                    or p.get("identifier", {}).get("Id")
                    or ""
                )
                if aid and aid in seen_ids:
                    continue
                if aid:
                    seen_ids.add(aid)
                new_props.append(p)
            if new_props:
                log.info("  ZIP %s — %d properties", z, len(new_props))
                all_results.extend(new_props)
    return all_results


def _parse_state_from_address(mailing: str) -> str:
    """Extract 2-letter state code from ATTOM mailing address: '123 ST, CITY, TX 12345'."""
    m = re.search(r",\s+([A-Z]{2})\s+\d{5}", mailing)
    return m.group(1) if m else ""


def _fetch_one_expanded(aid: str) -> tuple[str, dict]:
    try:
        _attom_limiter.acquire()
        r = httpx.get(
            f"{ATTOM_BASE}/property/expandedprofile",
            params={"attomId": aid},
            headers=_attom_headers(),
            timeout=20,
        )
        if r.status_code == 200:
            props = r.json().get("property") or []
            if props:
                return aid, props[0]
    except Exception as e:
        log.warning("  expandedprofile fetch failed for %s: %s", aid, e)
    return aid, {}


def fetch_sale_dates(attom_ids: list[str]) -> dict[str, dict]:
    """Fetch expandedprofile for top-N shortlist, parallelized across 8 workers.

    Returns dict keyed by attomId with the full expandedprofile property dict,
    which includes sale date, mortgage origination, and owner mailing address.
    """
    result: dict[str, dict] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for aid, expanded in ex.map(_fetch_one_expanded, attom_ids):
            if expanded:
                result[aid] = expanded
    return result


def _merge_expanded(raw: dict, expanded: dict) -> dict:
    """Merge expandedprofile fields into snapshot dict in the format score.py expects.

    score.py looks for: p['mortgage']['FirstMortgageDate'], p['owner']['mailingState'],
    p['sale']['saleTransDate']. Expandedprofile buries these under assessment.*
    """
    merged = dict(raw)
    fc = expanded.get("assessment", {}).get("mortgage", {}).get("FirstConcurrent", {})
    if fc.get("date"):
        merged["mortgage"] = {"FirstMortgageDate": fc["date"]}
    owner = expanded.get("assessment", {}).get("owner", {})
    mailing = owner.get("mailingAddressOneLine", "")
    state = _parse_state_from_address(mailing)
    if state:
        merged["owner"] = {"mailingState": state}
    if expanded.get("sale"):
        merged["sale"] = expanded["sale"]
    return merged


def _load_skill(name: str):
    path = ROOT / "skills" / name / "run.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_mini_pipeline(prop: ScoredProperty) -> dict:
    """Run owner_lookup + tax_lookup + comps_lookup for a single property."""
    addr_parts = prop.address.split(",")
    street = addr_parts[0].strip() if addr_parts else prop.address
    city_part = addr_parts[1].strip() if len(addr_parts) > 1 else "San Antonio"
    params = {
        "address": street,
        "city": city_part,
        "state": "TX",
        "zip": prop.zip_code,
        "bcad_prop_id": "",
    }
    enriched = {
        "address": prop.address,
        "units": prop.units,
        "year_built": prop.year_built,
        "appraised_value": prop.appraised_value,
        "zip_code": prop.zip_code,
        "signals": prop.signals,
        "score": prop.score,
        "owner_name": None,
        "tax_delinquent": None,
        "tax_status": None,
        "market": {},
    }

    # Owner lookup (Stagehand — may be slow)
    try:
        owner_mod = _load_skill("owner_lookup")
        owner_result = owner_mod.run(params)
        owner_data = owner_result.get("data") or {}
        enriched["owner_name"] = owner_data.get("owner_name")
        if owner_data.get("bcad_prop_id"):
            params["bcad_prop_id"] = owner_data["bcad_prop_id"]
        log.info("    owner_lookup: %s", enriched["owner_name"] or "—")
    except Exception as e:
        log.warning("    owner_lookup failed: %s", e)

    # Tax lookup (Stagehand — may be slow)
    try:
        tax_mod = _load_skill("tax_lookup")
        tax_result = tax_mod.run(params)
        tax_data = tax_result.get("data") or {}
        enriched["tax_delinquent"] = tax_data.get("delinquent", False)
        enriched["tax_status"] = tax_data.get("status", "")
        if enriched["tax_delinquent"] and "Tax delinquency" not in " ".join(
            enriched["signals"]
        ):
            enriched["signals"] = enriched["signals"] + ["Tax delinquency"]
        log.info("    tax_lookup: %s", enriched["tax_status"] or "—")
    except Exception as e:
        log.warning("    tax_lookup failed: %s", e)

    # Comps lookup (ATTOM + Census — fast)
    try:
        comps_mod = _load_skill("comps_lookup")
        comps_result = comps_mod.run(params)
        comps_data = comps_result.get("data") or {}
        enriched["market"] = comps_data.get("market") or {}
        log.info(
            "    comps_lookup: median_rent=%s",
            enriched["market"].get("median_rent", "—"),
        )
    except Exception as e:
        log.warning("    comps_lookup failed: %s", e)

    return enriched


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bexar County motivated seller scanner"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip mini-pipeline and email, just score",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of properties in report (default 20)",
    )
    parser.add_argument(
        "--no-email", action="store_true", help="Generate PDF but do not email"
    )
    parser.add_argument(
        "--no-sale-dates",
        action="store_true",
        help="Skip sale-date enrichment (fastest dry run, score from snapshot only)",
    )
    parser.add_argument("--output", default="", help="Save PDF to this path (optional)")
    args = parser.parse_args()

    log.info("=== Bexar County Multifamily Scanner ===")
    log.info("Fetching apartments from ATTOM (Bexar County geoid=%s)...", BEXAR_GEOID)
    raw_properties = fetch_all_multifamily()
    log.info("Fetched %d properties", len(raw_properties))

    if not raw_properties:
        log.error("No properties returned from ATTOM. Check API key and quota.")
        sys.exit(1)

    # Score all (first pass — no sale dates yet)
    scored = [score_property(p) for p in raw_properties]
    scored.sort(key=lambda x: x.score, reverse=True)

    # Enrich top 2×N candidates with expandedprofile before final sort
    # expandedprofile adds: mortgage origination date, owner state, sale date
    candidate_ids = [p.attom_id for p in scored[: args.top * 2] if p.attom_id]
    if candidate_ids and not args.no_sale_dates:
        log.info(
            "Fetching expanded profiles for top %d candidates (parallel)...",
            len(candidate_ids),
        )
        expanded_map = fetch_sale_dates(candidate_ids)
        enriched_raws = []
        for p in scored[: args.top * 2]:
            raw = dict(p.raw)
            if p.attom_id in expanded_map:
                raw = _merge_expanded(raw, expanded_map[p.attom_id])
            enriched_raws.append(raw)
        rescored = [score_property(r) for r in enriched_raws]
        rescored.sort(key=lambda x: x.score, reverse=True)
        top_n = rescored[: args.top]
    else:
        top_n = scored[: args.top]

    log.info("Top %d by score:", len(top_n))
    for i, p in enumerate(top_n[:10], 1):
        log.info(
            "  %d. %s (score=%d) — %s", i, p.address, p.score, "; ".join(p.signals)
        )

    if args.dry_run:
        log.info("Dry run — skipping mini-pipeline and report generation.")
        print(json.dumps([p._asdict() for p in top_n[:5]], indent=2, default=str))
        return

    # Enrich top N via mini-pipeline
    log.info("Running mini-pipeline on top %d properties...", len(top_n))
    enriched = []
    for i, prop in enumerate(top_n, 1):
        log.info("[%d/%d] %s", i, len(top_n), prop.address)
        data = run_mini_pipeline(prop)
        enriched.append(data)

    # Generate PDF
    try:
        from reports.generate import build_monthly_context, render_pdf

        context = build_monthly_context(enriched)
        pdf_bytes = render_pdf("monthly_report.html", context)
        log.info("PDF generated (%d bytes)", len(pdf_bytes))
    except ImportError as e:
        log.error("WeasyPrint not installed: %s", e)
        log.error(
            "Run: brew install cairo pango gdk-pixbuf && uv add weasyprint jinja2"
        )
        sys.exit(1)

    if args.output:
        Path(args.output).write_bytes(pdf_bytes)
        log.info("Saved PDF to %s", args.output)

    # Log scanner run to pipeline_runs
    try:
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if supabase_url and supabase_key:
            httpx.post(
                f"{supabase_url}/rest/v1/pipeline_runs",
                headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json={
                    "type": "scanner",
                    "property_address": f"Bexar County — {len(enriched)} properties",
                    "pdf_generated": True,
                },
                timeout=5,
            )
    except Exception:
        pass

    if args.no_email:
        log.info("--no-email set, skipping delivery.")
        return

    # Deliver to subscribers
    try:
        import datetime
        from reports.deliver import send_monthly_report
        from supabase import create_client

        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not supabase_url or not supabase_key:
            log.warning(
                "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set — skipping email delivery"
            )
            return

        sb = create_client(supabase_url, supabase_key)
        resp = sb.table("subscribers").select("email").eq("active", True).execute()
        subscribers = resp.data or []
        month_label = datetime.date.today().strftime("%B %Y")

        log.info("Sending to %d subscribers...", len(subscribers))
        for sub in subscribers:
            email = sub.get("email", "")
            if not email:
                continue
            send_monthly_report(email, pdf_bytes, month_label)
            log.info("  Sent to %s", email)

    except Exception as e:
        log.error("Email delivery failed: %s", e)


if __name__ == "__main__":
    main()
