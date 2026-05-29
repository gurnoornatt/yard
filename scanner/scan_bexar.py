"""
Motivated seller scanner for Bexar County multifamily.

Data source: Bexar County ArcGIS parcel service (free, no API key needed).
Replaces ATTOM bulk query which 504s on our plan tier.

Workflow:
  1. ArcGIS parcel query — all multifamily PropUse codes in Bexar County
  2. Score each property by seller pressure signals
  3. Top N → mini-pipeline: deed_lookup + tax_lookup + violations_lookup
  4. Generate PDF → deliver to all active subscribers

Usage:
  python3 scanner/scan_bexar.py [--dry-run] [--top N] [--no-email]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import sys
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

# Bexar County ArcGIS parcel service — free, no auth required
ARCGIS_URL = "https://maps.bexar.org/arcgis/rest/services/Parcels/MapServer/0/query"

# BCAD PropUse codes for multifamily (5+ units)
# 800 = market rate apartments (754 props)
# 801 = apartment complexes (20 props)
# 810 = medium multifamily (256 props)
# 814 = mid-size apartments (54 props)
# 815 = residential apartments (29 props)
# 817 = workforce/affordable market (48 props)
# 820 = large apartment complexes (12 props)
# 8100 = large apartment complexes (46 props)
# 8105 = luxury apartments (51 props)
MULTIFAMILY_CODES = ["800", "801", "810", "814", "815", "817", "820", "8100", "8105"]

ARCGIS_FIELDS = "PropID,Situs,Owner,YrBlt,TotVal,LandVal,ImprVal,Zip,PropUse,AddrSt,AddrCity"


def _build_where() -> str:
    return " OR ".join(f"PropUse='{c}'" for c in MULTIFAMILY_CODES)


def fetch_multifamily_parcels() -> list[dict]:
    """Fetch all multifamily parcels from Bexar County ArcGIS. Free, no key needed."""
    results: list[dict] = []
    where = _build_where()
    offset = 0
    page_size = 1000

    while True:
        try:
            r = httpx.get(
                ARCGIS_URL,
                params={
                    "where": where,
                    "outFields": ARCGIS_FIELDS,
                    "returnGeometry": "false",
                    "f": "json",
                    "resultRecordCount": page_size,
                    "resultOffset": offset,
                },
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            features = data.get("features", [])
            if not features:
                break
            batch = [f["attributes"] for f in features]
            results.extend(batch)
            log.info("  ArcGIS page offset=%d → %d records", offset, len(batch))
            if not data.get("exceededTransferLimit"):
                break
            offset += page_size
            time.sleep(0.3)  # polite pacing — free public service
        except Exception as e:
            log.warning("ArcGIS fetch error at offset=%d: %s", offset, e)
            break

    return results


def normalize_arcgis(feat: dict) -> dict:
    """Convert ArcGIS parcel attributes to score.py-compatible format.

    Preserves raw ArcGIS data under '_arcgis' key so mini-pipeline can access PropID.
    Maps to the nested ATTOM-like structure that score_property() reads.

    NOTE: Zip/AddrCity/AddrSt are the OWNER's mailing address, not the property address.
    Property ZIP is not in the ArcGIS export — Situs has street only.
    """
    situs = (feat.get("Situs") or "").strip()

    # Owner mailing address fields (not property address)
    owner_state = (feat.get("AddrSt") or "").strip().upper()
    # Property ZIP: not in ArcGIS data; derive from Situs if embedded, else leave blank
    # Skills work with just street + city=San Antonio, state=TX
    full_address = f"{situs}, San Antonio, TX" if situs else "Unknown"

    return {
        # score.py compat fields
        "address": {"oneLine": full_address, "_situs": situs},
        "summary": {"yearbuilt": feat.get("YrBlt")},
        "assessment": {
            "assessed": {"assdttlvalue": feat.get("TotVal")},
            "land": {"landval": feat.get("LandVal")},
            "impr": {"imprval": feat.get("ImprVal")},
        },
        "owner": {"mailingState": owner_state, "ownerName": feat.get("Owner", "")},
        "identifier": {"Id": str(int(feat.get("PropID") or 0))},
        "_arcgis": feat,  # raw ArcGIS record — Zip here is owner mailing ZIP, not property ZIP
    }


def _load_skill(name: str):
    path = ROOT / "skills" / name / "run.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_mini_pipeline(prop: ScoredProperty) -> dict:
    """Run deed_lookup + tax_lookup + violations_lookup for a top-scored property."""
    arcgis = prop.raw.get("_arcgis", {})
    situs = arcgis.get("Situs", prop.address).strip()
    zip_code = prop.zip_code
    bcad_prop_id = str(int(arcgis.get("PropID") or 0)) if arcgis.get("PropID") else ""

    # Strip house number for street name (tax_lookup needs both separately)
    params = {
        "address": situs,
        "city": "San Antonio",
        "state": "TX",
        "zip": zip_code,
        "bcad_prop_id": bcad_prop_id,
    }

    enriched = {
        "address": prop.address,
        "units": prop.units,
        "year_built": prop.year_built,
        "appraised_value": prop.appraised_value,
        "zip_code": prop.zip_code,
        "owner_name": arcgis.get("Owner"),
        "owner_state": arcgis.get("AddrSt", ""),
        "prop_use": arcgis.get("PropUse", ""),
        "bcad_prop_id": bcad_prop_id,
        "signals": prop.signals,
        "score": prop.score,
        "liens": [],
        "open_violations": 0,
        "tax_annual": None,
        "market": {},
    }

    # deed_lookup — mechanics liens from Bexar County Clerk
    try:
        deed_mod = _load_skill("deed_lookup")
        deed_result = deed_mod.run(params)
        deed_data = deed_result.get("data") or {}
        liens = deed_data.get("mechanics_liens") or []
        enriched["liens"] = liens
        if liens and "Mechanics liens" not in " ".join(enriched["signals"]):
            enriched["signals"] = enriched["signals"] + [f"{len(liens)} mechanics lien(s)"]
        log.info("    deed_lookup: %d liens", len(liens))
    except Exception as e:
        log.warning("    deed_lookup failed: %s", e)

    # tax_lookup — BCAD estimated annual tax (uses PropID directly if available)
    try:
        tax_mod = _load_skill("tax_lookup")
        tax_result = tax_mod.run(params)
        tax_data = tax_result.get("data") or {}
        enriched["tax_annual"] = tax_data.get("estimated_annual_tax")
        log.info("    tax_lookup: %s", enriched["tax_annual"] or "—")
    except Exception as e:
        log.warning("    tax_lookup failed: %s", e)

    # violations_lookup — SA Open Data code violations
    try:
        viol_mod = _load_skill("violations_lookup")
        viol_result = viol_mod.run(params)
        viol_data = viol_result.get("data") or {}
        violations = viol_data.get("violations") or []
        open_viols = [v for v in violations if str(v.get("status", "")).lower() in ("open", "active")]
        enriched["open_violations"] = len(open_viols)
        if open_viols and "Open violations" not in " ".join(enriched["signals"]):
            enriched["signals"] = enriched["signals"] + [f"{len(open_viols)} open violation(s)"]
        log.info("    violations_lookup: %d open", len(open_viols))
    except Exception as e:
        log.warning("    violations_lookup failed: %s", e)

    # comps_lookup — Census ACS market rents for context
    try:
        comps_mod = _load_skill("comps_lookup")
        comps_result = comps_mod.run(params)
        comps_data = comps_result.get("data") or {}
        enriched["market"] = comps_data.get("market") or {}
    except Exception as e:
        log.warning("    comps_lookup failed: %s", e)

    return enriched


def main() -> None:
    parser = argparse.ArgumentParser(description="Bexar County motivated seller scanner")
    parser.add_argument("--dry-run", action="store_true",
                        help="Score only — skip mini-pipeline and email")
    parser.add_argument("--top", type=int, default=20,
                        help="Properties in report (default 20)")
    parser.add_argument("--no-email", action="store_true",
                        help="Generate PDF but do not email")
    parser.add_argument("--output", default="", help="Save PDF to this path (optional)")
    args = parser.parse_args()

    log.info("=== Bexar County Multifamily Scanner (ArcGIS) ===")
    log.info("Fetching multifamily parcels from Bexar County parcel service...")
    raw_features = fetch_multifamily_parcels()
    log.info("Fetched %d multifamily parcels", len(raw_features))

    if not raw_features:
        log.error("No parcels returned from ArcGIS. Check URL or service availability.")
        sys.exit(1)

    # Normalize to score.py format
    normalized = [normalize_arcgis(f) for f in raw_features]

    # Score all properties
    scored = [score_property(p) for p in normalized]
    scored.sort(key=lambda x: x.score, reverse=True)

    log.info("Top %d by score:", min(10, len(scored)))
    for i, p in enumerate(scored[:10], 1):
        log.info("  %d. %s (score=%d) — %s", i, p.address[:60], p.score, "; ".join(p.signals) or "no signals")

    if args.dry_run:
        log.info("Dry run — skipping mini-pipeline and report generation.")
        output = [
            {
                "rank": i + 1,
                "address": p.address,
                "owner": p.raw.get("owner", {}).get("ownerName", ""),
                "owner_state": p.raw.get("owner", {}).get("mailingState", ""),
                "year_built": p.year_built,
                "appraised_value": p.appraised_value,
                "zip_code": p.zip_code,
                "score": p.score,
                "signals": p.signals,
                "bcad_prop_id": p.raw.get("identifier", {}).get("Id", ""),
            }
            for i, p in enumerate(scored[: args.top])
        ]
        print(json.dumps(output, indent=2, default=str))
        return

    # Full run: mini-pipeline on top N
    top_n = scored[: args.top]
    log.info("Running mini-pipeline on top %d properties...", len(top_n))
    enriched = []
    for i, prop in enumerate(top_n, 1):
        log.info("[%d/%d] %s", i, len(top_n), prop.address[:60])
        data = run_mini_pipeline(prop)
        enriched.append(data)

    # Generate PDF report
    try:
        from reports.generate import build_monthly_context, render_pdf

        context = build_monthly_context(enriched)
        pdf_bytes = render_pdf("monthly_report.html", context)
        log.info("PDF generated (%d bytes)", len(pdf_bytes))
    except ImportError as e:
        log.error("WeasyPrint not installed: %s", e)
        sys.exit(1)

    if args.output:
        Path(args.output).write_bytes(pdf_bytes)
        log.info("Saved PDF to %s", args.output)

    # Log to Supabase
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
            log.warning("SUPABASE credentials not set — skipping email delivery")
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
