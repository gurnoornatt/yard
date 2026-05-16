import json, os, sys
from pathlib import Path

DATA = Path(os.environ.get(
    "SENTINEL_DATA_DIR",
    str(Path(__file__).resolve().parents[2] / "data" / "demo_properties")
))
REPORTS = Path(os.environ.get(
    "SENTINEL_PROJECT_DIR",
    str(Path(__file__).resolve().parents[2])
)) / "reports"


def run(params: dict) -> dict:
    property_id = params.get("property_id")
    output_path = params.get("output_path",
                             str(REPORTS / f"{property_id}_analysis.md"))

    f = DATA / f"{property_id}.json"
    if not f.exists():
        return {"job": "synthesize_analysis", "status": "data_unavailable",
                "property_id": property_id, "data": None}

    full_record = json.loads(f.read_text())
    research_keys = [
        "parse_om", "owner_lookup", "deed_lookup", "permit_lookup",
        "tax_lookup", "violations_lookup", "comps_lookup",
        "portfolio_crawler", "maturity_estimator",
    ]
    research_data = {k: full_record.get(k) for k in research_keys}

    REPORTS.mkdir(exist_ok=True)

    return {
        "job": "synthesize_analysis",
        "status": "ok",
        "property_id": property_id,
        "data": {
            "research_data": research_data,
            "output_path": output_path,
            "synthesis_template": {
                "section_1": "Property Snapshot: address, units, year built, appraised value, asset class",
                "section_2": "Owner Motivation Profile: LLC chain, principal, hold period, portfolio size, intent signals",
                "section_3": "Loan Situation: lender, origination date, maturity date, CMBS vs regional bank, refinance assessment",
                "section_4": "Submarket Reality Check: recent comp addresses + prices, rent trajectory, vacancy, headwinds",
                "section_5": "Hidden Flags: code violations, tax delinquency, lawsuits — or 'No hidden flags detected in public records'",
                "section_6": "Bottom-Line Recommendation: exactly PURSUE / WATCHLIST / PASS with 3-5 sentences of reasoning tied to specific signals, plus next concrete move",
            },
            "instruction": (
                "Write each section 2-4 sentences. Be direct and factual. "
                "Cite specific numbers from research_data. No marketing language. "
                "The recommendation must be defensible from the evidence. "
                f"Save the completed report as markdown to: {output_path}"
            ),
        },
    }


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
