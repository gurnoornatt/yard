import asyncio
import json
import os
import re
import sys

from stagehand import AsyncStagehand

BB_KEY = os.environ.get("BROWSERBASE_API_KEY", "")
MODEL_KEY = os.environ.get("MODEL_API_KEY", "")
BCAD_PROP = (
    "https://bexar.trueautomation.com/clientdb/property.aspx?cid=110&prop_id={prop_id}"
)
BCAD_SEARCH = "https://bexar.trueautomation.com/clientdb/PropertySearch.aspx?cid=110"
MODEL = "openai/gpt-4o-mini"


def _parse_tax_blob(blob: str) -> dict:
    import datetime

    text = str(blob).lower()
    current_year = datetime.date.today().year
    # Only flag delinquent on explicit past-due language; "unpaid" alone can mean
    # current-year taxes not yet billed, which is normal and not a red flag.
    delinquent = bool(re.search(r"delinquent|past due|overdue", text))
    amount = re.search(r"\$[\d,]+(?:\.\d{2})?", blob)
    year_match = re.search(r"\b(20\d{2})\b", blob)
    tax_year = year_match.group(1) if year_match else None
    # Suppress delinquency flag if the only year mentioned is current or future
    if delinquent and tax_year and int(tax_year) >= current_year:
        delinquent = False
    return {
        "delinquent": delinquent,
        "total_due": amount.group(0) if amount else None,
        "tax_year": tax_year,
        "status": "delinquent" if delinquent else "current",
    }


def _parse_extraction(result: dict | str | None) -> dict:
    import datetime

    if not result:
        return {}
    if isinstance(result, dict):
        if "delinquent" in result:
            # Apply year-check: suppress delinquency if tax_year >= current year
            parsed = dict(result)
            tax_year = parsed.get("tax_year")
            if parsed.get("delinquent") and tax_year:
                try:
                    if int(tax_year) >= datetime.date.today().year:
                        parsed["delinquent"] = False
                        parsed["status"] = "current"
                except (ValueError, TypeError):
                    pass
            return parsed
        blob = result.get("extraction", "")
    else:
        blob = str(result)
    return _parse_tax_blob(blob)


async def _scrape_tax(bcad_prop_id: str = "", address: str = "") -> dict:
    async with AsyncStagehand(
        browserbase_api_key=BB_KEY,
        model_api_key=MODEL_KEY,
    ) as client:
        session = await client.sessions.start(model_name=MODEL)
        try:
            if bcad_prop_id:
                await session.navigate(url=BCAD_PROP.format(prop_id=bcad_prop_id))
                await session.act(input="Click the Taxes tab or Taxes link.")
            else:
                m = re.match(r"^(\d+)\s+(.+)$", address.strip())
                street_num = m.group(1) if m else ""
                street_name = m.group(2) if m else address
                search_term = f"{street_num} {street_name.split()[0]}"
                await session.navigate(url=BCAD_SEARCH)
                await session.execute(
                    execute_options={
                        "instruction": (
                            f"Type '{search_term}' in the 'Property Search:' box and click Search."
                        ),
                        "max_steps": 6,
                    },
                    agent_config={"model": MODEL},
                    timeout=60.0,
                )
                await session.execute(
                    execute_options={
                        "instruction": "Click the first property link in results, then click the Taxes tab.",
                        "max_steps": 6,
                    },
                    agent_config={"model": MODEL},
                    timeout=45.0,
                )

            resp = await session.extract(
                instruction=(
                    "From the taxes section extract: whether any PRIOR YEAR taxes are delinquent "
                    "or past due (true/false — current-year taxes not yet billed or not yet due "
                    "should be false), total delinquent amount owed if any, most recent tax year "
                    "shown, and status (current or delinquent)."
                ),
                schema={
                    "type": "object",
                    "properties": {
                        "delinquent": {"type": "boolean"},
                        "total_due": {"type": "string"},
                        "tax_year": {"type": "string"},
                        "status": {"type": "string"},
                    },
                    "required": ["delinquent", "status"],
                },
                options={"model": MODEL},
            )

            raw = resp.data.result if resp and resp.data else None
            return _parse_extraction(raw)
        finally:
            await session.end()


def run(params: dict) -> dict:
    state = params.get("state", "").strip().upper()
    if state and state != "TX":
        return {
            "job": "tax_lookup",
            "status": "data_unavailable",
            "reason": "BCAD covers Bexar County, TX only",
            "data": None,
        }

    try:
        data = asyncio.run(
            _scrape_tax(
                bcad_prop_id=params.get("bcad_prop_id", ""),
                address=params.get("address", ""),
            )
        )
        data["source"] = "BCAD (Bexar County Appraisal District)"
        return {"job": "tax_lookup", "status": "ok", "data": data}
    except Exception as e:
        return {"job": "tax_lookup", "status": "error", "reason": str(e), "data": None}


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
