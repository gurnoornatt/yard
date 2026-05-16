import json, sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data" / "demo_properties"

DEMO_MAP = {
    "mccullough": "4123_mccullough",
    "blanco": "7821_blanco",
    "culebra": "2455_culebra",
}


def _parse_live(pdf_path: str) -> dict | None:
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
        return {"raw_text": text[:2000], "note": "live parse — property_id unknown, use cached data for full research"}
    except Exception as e:
        return None


def run(params: dict) -> dict:
    pdf_path = params.get("pdf_path", "")
    path_lower = str(pdf_path).lower()

    for keyword, property_id in DEMO_MAP.items():
        if keyword in path_lower:
            f = DATA / f"{property_id}.json"
            if f.exists():
                record = json.loads(f.read_text()).get("parse_om")
                if record:
                    record["property_id"] = property_id
                    return {"job": "parse_om", "status": "ok",
                            "property_id": property_id, "data": record}

    live = _parse_live(pdf_path)
    if live:
        return {"job": "parse_om", "status": "ok",
                "property_id": "unknown", "data": live}

    return {"job": "parse_om", "status": "data_unavailable",
            "property_id": "unknown", "data": None}


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
