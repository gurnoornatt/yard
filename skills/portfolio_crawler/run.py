import asyncio
import json
import re
import sys

from skills._stagehand import make_client, session_kwargs

BCAD_SEARCH = "https://bexar.trueautomation.com/clientdb/PropertySearch.aspx?cid=110"
MODEL = "openai/gpt-4o-mini"


def _parse_portfolio_blob(blob: str) -> list[dict]:
    """Parse freeform extraction text into a list of property dicts."""
    properties = []
    lines = str(blob).replace("\\n", "\n").split("\n")
    for line in lines:
        line = line.strip(" -•*")
        if not line or len(line) < 5:
            continue
        # Each line is typically "Address — type — $value" or just an address
        props: dict = {"address": line, "property_type": "", "appraised_value": ""}
        amt = re.search(r"\$[\d,]+(?:\.\d{2})?", line)
        if amt:
            props["appraised_value"] = amt.group(0)
            props["address"] = line[: amt.start()].strip(" —-|")
        properties.append(props)
    return properties[:20]


async def _scrape_portfolio(owner_name: str) -> dict:
    search_term = owner_name.split()[0]
    async with make_client() as client:
        session = await client.sessions.start(**session_kwargs(MODEL))
        try:
            await session.navigate(url=BCAD_SEARCH)
            await session.execute(
                execute_options={
                    "instruction": (
                        "Click the 'Advanced >>' button to expand advanced search options. "
                        f"Find the Owner Name field and type '{search_term}'. "
                        "Click the Search button. Wait for results."
                    ),
                    "max_steps": 8,
                },
                agent_config={"model": MODEL},
                timeout=60.0,
            )

            resp = await session.extract(
                instruction=(
                    f"List all property addresses shown in the search results that belong to owner '{owner_name}' "
                    "or similar name. Include address, property type, and appraised value for each row, up to 20."
                ),
                schema={
                    "type": "object",
                    "properties": {
                        "properties": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "address": {"type": "string"},
                                    "property_type": {"type": "string"},
                                    "appraised_value": {"type": "string"},
                                },
                            },
                        },
                    },
                    "required": ["properties"],
                },
                options={"model": MODEL},
            )

            raw = resp.data.result if resp and resp.data else None
            if isinstance(raw, dict):
                if "properties" in raw and isinstance(raw["properties"], list):
                    return {"properties": raw["properties"]}
                if "extraction" in raw:
                    return {"properties": _parse_portfolio_blob(str(raw["extraction"]))}
            return {"properties": []}
        finally:
            await session.end()


def run(params: dict) -> dict:
    state = params.get("state", "").strip().upper()
    if state and state != "TX":
        return {
            "job": "portfolio_crawler",
            "status": "data_unavailable",
            "reason": "BCAD covers Bexar County, TX only",
            "data": None,
        }

    owner_name = params.get("owner_name", "").strip()
    if not owner_name:
        return {
            "job": "portfolio_crawler",
            "status": "data_unavailable",
            "reason": "No owner name from owner_lookup",
            "data": None,
        }

    try:
        data = asyncio.run(_scrape_portfolio(owner_name))
        properties = data.get("properties", [])
        return {
            "job": "portfolio_crawler",
            "status": "ok",
            "data": {
                "owner_name": owner_name,
                "properties": properties,
                "property_count": len(properties),
                "source": "BCAD (Bexar County Appraisal District)",
            },
        }
    except Exception as e:
        return {
            "job": "portfolio_crawler",
            "status": "error",
            "reason": str(e),
            "data": None,
        }


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
