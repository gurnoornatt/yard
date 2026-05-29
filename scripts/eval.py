"""
Skill evaluator — run before claiming any skill "works".

Usage:
  python3 scripts/eval.py                  # all evaluations
  python3 scripts/eval.py parse_om         # just parse_om
  python3 scripts/eval.py deed_lookup      # just deed_lookup

Each evaluation reports actual field values, not just pass/fail.
A field returning None is explicitly flagged — not silently ignored.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Load .env before anything else
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    import os

    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def load_skill(name: str):
    path = ROOT / "skills" / name / "run.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
DIM = "\033[2m"


def ok(msg):
    print(f"  {GREEN}PASS{RESET}  {msg}")


def warn(msg):
    print(f"  {YELLOW}WARN{RESET}  {msg}")


def fail(msg):
    print(f"  {RED}FAIL{RESET}  {msg}")


def info(msg):
    print(f"  {DIM}NOTE{RESET}  {msg}")


def check_field(label: str, value, expect_null: bool = False):
    """Report a field value. Explicit about nulls — never silently passes."""
    if expect_null:
        if value is None:
            info(f"{label}: null (expected — not in source)")
        else:
            warn(f"{label}: {repr(value)} (expected null but got data — verify)")
    else:
        if value is None or value == "" or value == 0:
            fail(f"{label}: NULL — field not extracted")
        else:
            ok(f"{label}: {repr(value)}")


# ---------------------------------------------------------------------------
# parse_om evaluator
# ---------------------------------------------------------------------------

PARSE_OM_CASES = [
    {"name": "culebra_om", "path": "demo_oms/culebra_om.pdf"},
    {"name": "blanco_om", "path": "demo_oms/blanco_om.pdf"},
    {"name": "mccullough_om", "path": "demo_oms/mccullough_om.pdf"},
    {"name": "gerber_lake", "path": "OM/Gerber-Lake-Park-Offering-Memorandum.pdf"},
    {"name": "city_of_ink", "path": "OM/cityofinkom.pdf"},
    {"name": "sunnybrook", "path": "OM/sunnybrookom.pdf"},
    {"name": "business_circle", "path": "models/2223-business-circle_om_2026_v3.pdf"},
    {"name": "pasco_heights", "path": "models/Pasco-Heights-San-Antonio-FL-OM-PP.pdf"},
    {"name": "wloop_south", "path": "models/2300wloopsouthom-q82-ZlH.pdf"},
]

# Fields we MUST get from any OM
REQUIRED_FIELDS = ["address", "units", "year_built", "asking_price"]

# Loan fields — often absent from OMs. We check and report honestly.
LOAN_FIELDS = [
    "loan_type",
    "loan_original_balance",
    "loan_interest_rate",
    "loan_term_months",
    "offering_structure",
]


def eval_parse_om():
    print(f"\n{BOLD}=== parse_om ==={RESET}")
    mod = load_skill("parse_om")

    present_loan = 0
    total = 0

    for case in PARSE_OM_CASES:
        path = ROOT / case["path"]
        if not path.exists():
            print(f"\n  [{case['name']}] {YELLOW}SKIP — file not found{RESET}")
            continue

        print(f"\n  [{case['name']}]")
        try:
            result = mod.run({"pdf_path": str(path)})
        except Exception as e:
            fail(f"exception: {e}")
            continue

        if result.get("status") != "ok":
            fail(f"status={result.get('status')} reason={result.get('reason')}")
            continue

        data = result.get("data") or {}
        total += 1

        for field in REQUIRED_FIELDS:
            check_field(field, data.get(field))

        # Citation check (Mistral path only — legacy path has no citations)
        citations = data.get("citations", {})
        cited_count = sum(1 for v in citations.values() if v and v != "not found")
        if cited_count >= 3:
            ok(f"citations: {cited_count} fields sourced")
        elif cited_count > 0:
            warn(f"citations: only {cited_count} fields sourced (want ≥3)")
        else:
            info("citations: none (legacy path or Mistral key not set)")

        # Loan fields — check inside financials (where they actually live)
        financials = data.get("financials", {})
        loan_found = any(financials.get(f) for f in LOAN_FIELDS)
        if loan_found:
            present_loan += 1
            for f in LOAN_FIELDS:
                check_field(f"financials/{f}", financials.get(f), expect_null=(financials.get(f) is None))
        else:
            info(
                "loan fields: all null (loan terms not found in this OM — this is normal)"
            )

    if total > 0:
        pct = round(present_loan / total * 100)
        print(
            f"\n  {BOLD}Loan data found in {present_loan}/{total} OMs ({pct}%){RESET}"
        )
        print(f"  {DIM}— OMs without loan terms require external deed records{RESET}")


# ---------------------------------------------------------------------------
# deed_lookup evaluator
# ---------------------------------------------------------------------------

DEED_CASES = [
    {
        # Confirmed 5 results in manual testing (DEED, WAIVER, MEMORANDUM — no financial institution)
        # Records exist but no lender keyword found; mechanics lien present is a valid ok result
        "name": "100 Dolorosa (SA downtown — confirmed records exist)",
        "params": {
            "address": "100 Dolorosa",
            "city": "San Antonio",
            "state": "TX",
            "zip": "78205",
            "owner_name": "",
        },
        "required_fields": [],
        "optional_fields": ["lender", "origination_date", "loan_amount", "borrower"],
    },
    {
        # 14900 Nacogdoches Rd — UCC 3 REAL PROPERTY filed 10/14/2025 (ReadyCap)
        # NOTE: Assignments of Deed of Trust are NOT indexed by address in this clerk system.
        # Only mechanics liens, UCC filings, releases, and waivers appear in address search.
        "name": "14900 Nacogdoches Rd (View the Rio — confirmed UCC + mechanics liens)",
        "params": {
            "address": "14900 Nacogdoches Rd",
            "city": "San Antonio",
            "state": "TX",
            "zip": "78247",
            "owner_name": "",
        },
        "required_fields": ["lender", "origination_date"],
        "optional_fields": ["loan_amount", "borrower"],
    },
    {
        # Gerber Lake Park — a different SA multifamily, no prior knowledge of records
        # Tests that the fix works generically, not just for Nacogdoches
        "name": "7202 Blanco Rd (different SA multifamily — generic test)",
        "params": {
            "address": "7202 Blanco Rd",
            "city": "San Antonio",
            "state": "TX",
            "zip": "78216",
            "owner_name": "",
        },
        "required_fields": ["lender", "origination_date"],
        "optional_fields": ["loan_amount", "borrower"],
    },
    {
        # Out-of-state — should return data_unavailable immediately, not error
        "name": "non-TX address (should return data_unavailable, not error)",
        "params": {
            "address": "123 Main St",
            "city": "Los Angeles",
            "state": "CA",
            "zip": "90001",
            "owner_name": "",
        },
        "expect_unavailable": True,
        "required_fields": ["lender", "origination_date"],
        "optional_fields": ["loan_amount", "borrower"],
    },
]


def eval_deed_lookup():
    print(f"\n{BOLD}=== deed_lookup ==={RESET}")
    mod = load_skill("deed_lookup")

    passed = 0
    total = len(DEED_CASES)

    for case in DEED_CASES:
        print(f"\n  [{case['name']}]")
        try:
            result = mod.run(case["params"])
        except Exception as e:
            fail(f"exception: {e}")
            continue

        status = result.get("status")
        data = result.get("data") or {}

        if status == "error":
            fail(f"status=error reason={result.get('reason')}")
            continue

        if status == "data_unavailable":
            expected_unavailable = case.get("expect_unavailable", False)
            if expected_unavailable:
                ok(f"correctly returned data_unavailable: {result.get('reason')}")
                passed += 1
            else:
                warn(f"status=data_unavailable — {result.get('reason')}")
                info("No deed records found in county clerk for this address")
            continue

        if status == "ok":
            all_required = True
            for field in case["required_fields"]:
                val = data.get(field)
                if not val:
                    fail(f"{field}: NULL — required field missing")
                    all_required = False
                else:
                    ok(f"{field}: {repr(val)}")
            for field in case["optional_fields"]:
                val = data.get(field)
                if not val:
                    info(f"{field}: null (optional)")
                else:
                    ok(f"{field}: {repr(val)}")
            # Report assignment_count if present (address search won't find Assignments of DT)
            asgn_count = data.get("assignment_count", 0) or 0
            if asgn_count:
                info(f"assignment_count: {asgn_count}")
            distress = data.get("distress_signals", [])
            if distress:
                for sig in distress:
                    ok(f"distress_signal: {sig}")
            if all_required:
                passed += 1

    print(f"\n  {BOLD}deed_lookup: {passed}/{total} cases returned usable data{RESET}")


# ---------------------------------------------------------------------------
# owner_lookup evaluator
# ---------------------------------------------------------------------------

OWNER_CASES = [
    {
        # Confirmed: BCAD shows RIO @ 1604 LLC, market value $15,044,510
        "name": "14900 Nacogdoches Rd (View the Rio — confirmed: RIO @ 1604 LLC on BCAD)",
        "params": {
            "address": "14900 Nacogdoches Rd",
            "city": "San Antonio",
            "state": "TX",
            "zip": "78247",
        },
        "expected_owner_fragment": "RIO",  # must contain this substring (case-insensitive)
    },
    {
        # Out-of-state — should return data_unavailable immediately
        "name": "non-TX address (should return data_unavailable)",
        "params": {
            "address": "123 Main St",
            "city": "Los Angeles",
            "state": "CA",
            "zip": "90001",
        },
        "expect_unavailable": True,
    },
]


def eval_owner_lookup():
    print(f"\n{BOLD}=== owner_lookup ==={RESET}")
    mod = load_skill("owner_lookup")

    passed = 0
    total = len(OWNER_CASES)

    for case in OWNER_CASES:
        print(f"\n  [{case['name']}]")
        try:
            result = mod.run(case["params"])
        except Exception as e:
            fail(f"exception: {e}")
            continue

        status = result.get("status")
        data = result.get("data") or {}

        if status == "error":
            fail(f"status=error reason={result.get('reason')}")
            continue

        if case.get("expect_unavailable"):
            if status == "data_unavailable":
                ok("correctly returned data_unavailable")
                passed += 1
            else:
                fail(f"expected data_unavailable but got status={status}")
            continue

        if status == "data_unavailable":
            warn(f"status=data_unavailable — {result.get('reason')}")
            info("BCAD lookup failed — check stderr logs for debug details")
            continue

        if status == "ok":
            owner = data.get("owner_name", "")
            if owner:
                ok(f"owner_name: {repr(owner)}")
                fragment = case.get("expected_owner_fragment", "")
                if fragment and fragment.lower() not in owner.lower():
                    warn(
                        f"owner_name doesn't contain expected '{fragment}' — got: {owner}"
                    )
                else:
                    passed += 1
            else:
                fail("owner_name: NULL — extraction returned empty")
            for field in (
                "owner_address",
                "owner_state",
                "appraised_value",
                "bcad_prop_id",
            ):
                val = data.get(field)
                if val:
                    ok(f"{field}: {repr(val)}")
                else:
                    info(f"{field}: null")
            out_of_state = data.get("out_of_state")
            info(f"out_of_state: {out_of_state}")

    print(f"\n  {BOLD}owner_lookup: {passed}/{total} cases passed{RESET}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

EVALS = {
    "parse_om": eval_parse_om,
    "deed_lookup": eval_deed_lookup,
    "owner_lookup": eval_owner_lookup,
}

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None

    if target:
        if target not in EVALS:
            print(f"Unknown eval: {target}. Options: {list(EVALS.keys())}")
            sys.exit(1)
        EVALS[target]()
    else:
        for fn in EVALS.values():
            fn()

    print()
