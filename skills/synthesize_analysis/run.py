import json
import sys
from pathlib import Path

REPORTS = Path(__file__).resolve().parents[2] / "reports"


def run(params: dict) -> dict:
    """Signal that all research is collected and synthesis can begin.

    server.py drives the actual Nemotron call using accumulated all_data.
    This skill exists in the pipeline to show progress in the UI.
    """
    REPORTS.mkdir(exist_ok=True)

    asset_class = params.get("asset_class", "unknown")
    non_mf_note = (
        f"Note: asset_class is '{asset_class}'. Sentinel is optimized for multifamily — "
        "analysis criteria and verdict should be interpreted accordingly."
        if asset_class not in ("multifamily", "unknown", "")
        else ""
    )

    return {
        "job": "synthesize_analysis",
        "status": "ok",
        "data": {
            "ready": True,
            "asset_class": asset_class,
            "non_multifamily_note": non_mf_note,
        },
    }


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
