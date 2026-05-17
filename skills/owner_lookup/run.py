import asyncio
import json
import os
import re
import sys

from stagehand import AsyncStagehand

BB_KEY = os.environ.get("BROWSERBASE_API_KEY", "")
MODEL_KEY = os.environ.get("MODEL_API_KEY", "")
BCAD_SEARCH = "https://bexar.trueautomation.com/clientdb/PropertySearch.aspx?cid=110"
MODEL = "openai/gpt-4o-mini"


def _parse_address(address: str) -> tuple[str, str]:
    m = re.match(r"^(\d+)\s+(.+)$", address.strip())
    return (m.group(1), m.group(2)) if m else ("", address.strip())


def _parse_extraction_blob(blob: str, current_url: str = "") -> dict:
    """Parse the freeform extraction string Stagehand returns into structured fields."""
    result = {}
    lines = blob.replace("\\n", "\n").split("\n")
    for line in lines:
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if val.lower() in ("null", "none", "n/a", ""):
            val = ""
        if "owner name" in key:
            result["owner_name"] = val
        elif "owner" in key and "address" in key or "mailing" in key:
            result["owner_address"] = val
        elif "appraised" in key or "market value" in key or "total value" in key:
            result["appraised_value"] = val
        elif "property id" in key or "prop_id" in key or "id" == key:
            result["bcad_prop_id"] = val

    # Pull prop_id from URL if not found in text
    if not result.get("bcad_prop_id") and current_url:
        m = re.search(r"prop_id=(\d+)", current_url)
        if m:
            result["bcad_prop_id"] = m.group(1)

    return result


async def _scrape(street_num: str, street_name: str) -> dict:
    async with AsyncStagehand(
        browserbase_api_key=BB_KEY,
        model_api_key=MODEL_KEY,
    ) as client:
        session = await client.sessions.start(model_name=MODEL)
        try:
            await session.navigate(url=BCAD_SEARCH)

            # Single search box — type "236 Deerwood" and submit
            search_term = f"{street_num} {street_name.split()[0]}"
            await session.execute(
                execute_options={
                    "instruction": (
                        f"The page has one search box labeled 'Property Search:'. "
                        f"Type '{search_term}' in it and click the 'Search' button."
                    ),
                    "max_steps": 6,
                },
                agent_config={"model": MODEL},
                timeout=60.0,
            )

            # Click first result
            await session.execute(
                execute_options={
                    "instruction": "Click the first property link in the results list to open the property detail page.",
                    "max_steps": 4,
                },
                agent_config={"model": MODEL},
                timeout=45.0,
            )

            # Non-streaming extract — returns SessionExtractResponse
            resp = await session.extract(
                instruction=(
                    "Extract from this property detail page: "
                    "Owner Name, Owner Mailing Address, Total Appraised Value, Property ID from the URL."
                ),
                schema={
                    "type": "object",
                    "properties": {
                        "owner_name": {"type": "string"},
                        "owner_address": {"type": "string"},
                        "appraised_value": {"type": "string"},
                        "bcad_prop_id": {"type": "string"},
                    },
                    "required": ["owner_name"],
                },
                options={"model": MODEL},
            )

            raw = {}
            if resp and resp.data and resp.data.result:
                r = resp.data.result
                # If schema was applied, r has keys directly
                if isinstance(r, dict) and "owner_name" in r:
                    raw = r
                # Otherwise parse the extraction blob
                elif isinstance(r, dict) and "extraction" in r:
                    raw = _parse_extraction_blob(str(r["extraction"]))
                elif isinstance(r, str):
                    raw = _parse_extraction_blob(r)

            return raw
        finally:
            await session.end()


def run(params: dict) -> dict:
    state = params.get("state", "").strip().upper()
    if state and state != "TX":
        return {
            "job": "owner_lookup",
            "status": "data_unavailable",
            "reason": "BCAD covers Bexar County, TX only",
            "data": None,
        }

    address = params.get("address", "")
    if not address:
        return {
            "job": "owner_lookup",
            "status": "data_unavailable",
            "reason": "No address provided",
            "data": None,
        }

    street_num, street_name = _parse_address(address)

    try:
        data = asyncio.run(_scrape(street_num, street_name))
        owner_name = data.get("owner_name", "")
        owner_address = data.get("owner_address", "")
        bcad_prop_id = data.get("bcad_prop_id", "")
        owner_state = ""
        m = re.search(r"\b([A-Z]{2})\s+\d{5}", owner_address)
        if m:
            owner_state = m.group(1)
        return {
            "job": "owner_lookup",
            "status": "ok",
            "data": {
                "owner_name": owner_name,
                "owner_address": owner_address,
                "owner_state": owner_state,
                "out_of_state": owner_state not in ("TX", ""),
                "appraised_value": data.get("appraised_value", ""),
                "bcad_prop_id": bcad_prop_id,
                "source": "BCAD (Bexar County Appraisal District)",
            },
        }
    except Exception as e:
        return {
            "job": "owner_lookup",
            "status": "error",
            "reason": str(e),
            "data": None,
        }


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
