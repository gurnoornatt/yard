import json, os, sys
from pathlib import Path

DATA = Path(os.environ.get(
    "SENTINEL_DATA_DIR",
    str(Path(__file__).resolve().parents[2] / "data" / "demo_properties")
))

DEMO_MAP = {
    "mccullough": "4123_mccullough",
    "blanco": "7821_blanco",
    "culebra": "2455_culebra",
}

# Also match by address text found in a live-parsed PDF
ADDRESS_MAP = {
    "4123 mccullough": "4123_mccullough",
    "7821 blanco": "7821_blanco",
    "2455 culebra": "2455_culebra",
}


def _parse_live(pdf_path: str) -> tuple[str | None, dict | None]:
    """Returns (property_id_or_None, parsed_data_or_None)."""
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
        text_lower = text.lower()
        for addr_key, pid in ADDRESS_MAP.items():
            if addr_key in text_lower:
                return pid, None  # identified — use cached data
        return None, {"raw_text": text[:2000],
                      "note": "live parse — property_id unknown"}
    except Exception:
        return None, None


def run(params: dict) -> dict:
    pdf_path = params.get("pdf_path", "")
    path_lower = str(pdf_path).lower()

    # Fast path: keyword in filename/path
    for keyword, property_id in DEMO_MAP.items():
        if keyword in path_lower:
            f = DATA / f"{property_id}.json"
            if f.exists():
                record = json.loads(f.read_text()).get("parse_om")
                if record:
                    record["property_id"] = property_id
                    return {"job": "parse_om", "status": "ok",
                            "property_id": property_id, "data": record}

    # Slow path: read the PDF and match by address
    pid_from_text, live_data = _parse_live(pdf_path)
    if pid_from_text:
        f = DATA / f"{pid_from_text}.json"
        if f.exists():
            record = json.loads(f.read_text()).get("parse_om")
            if record:
                record["property_id"] = pid_from_text
                return {"job": "parse_om", "status": "ok",
                        "property_id": pid_from_text, "data": record}

    if live_data:
        return {"job": "parse_om", "status": "ok",
                "property_id": "unknown", "data": live_data}

    return {"job": "parse_om", "status": "data_unavailable",
            "property_id": "unknown", "data": None}


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
