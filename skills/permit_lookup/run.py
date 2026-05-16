import json, sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data" / "demo_properties"


def run(params: dict) -> dict:
    property_id = params.get("property_id")
    f = DATA / f"{property_id}.json"
    if not f.exists():
        return {"job": "permit_lookup", "status": "data_unavailable",
                "property_id": property_id, "data": None}
    record = json.loads(f.read_text()).get("permit_lookup")
    return {"job": "permit_lookup",
            "status": "ok" if record else "data_unavailable",
            "property_id": property_id, "data": record}


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
