import asyncio
import json
import re
import sys
from datetime import date
from urllib.parse import quote_plus

from skills._stagehand import make_client, session_kwargs

MODEL = "openai/gpt-4o-mini"


def _parse_amount(s: str) -> float | None:
    if not s:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(s))
    try:
        val = float(cleaned)
        if val > 9_999_999_999 or val <= 0:
            return None
        return val
    except (ValueError, TypeError):
        return None


def _clean_dict(d: dict) -> dict:
    return {
        k: str(v).strip().strip('"')
        for k, v in d.items()
        if v and str(v).lower().strip().strip('"') not in ("null", "none", "n/a", "")
    }


def _extract_result(resp) -> dict:
    if not (resp and resp.data and resp.data.result):
        return {}
    r = resp.data.result
    if isinstance(r, dict) and "extraction" in r:
        # Freeform text blob — parse key: value lines
        result = {}
        for line in str(r["extraction"]).replace("\\n", "\n").split("\n"):
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip().lower().strip('"')
            val = val.strip().strip('"')
            if val.lower() in ("null", "none", "n/a", ""):
                continue
            if "grantor" in key or "lender_grantor" in key:
                result.setdefault("lender_grantor", val)
            elif "grantee" in key or "lender_grantee" in key:
                result.setdefault("lender_grantee", val)
            elif "date" in key or "lender_date" in key:
                result.setdefault("lender_date", val)
            elif "doc" in key or "type" in key:
                result.setdefault("lender_doc_type", val)
            elif "mechanics" in key or "lien_count" in key:
                try:
                    result["mechanics_lien_count"] = int(re.sub(r"[^\d]", "", val))
                except (ValueError, TypeError):
                    pass
            elif "assignment" in key:
                try:
                    result["assignment_count"] = int(re.sub(r"[^\d]", "", val))
                except (ValueError, TypeError):
                    pass
        return result
    if isinstance(r, dict):
        return _clean_dict(r)
    return {}


def _results_url(address: str) -> str:
    today = date.today().strftime("%Y%m%d")
    addr_encoded = quote_plus(address.upper())
    return (
        f"https://bexar.tx.publicsearch.us/results"
        f"?department=RP"
        f"&propertyAddress={addr_encoded}"
        f"&recordedDateRange=20100101,{today}"
        f"&searchType=advancedSearch"
    )


async def _navigate_and_wait(session, url: str, debug: list) -> None:
    # bexar.tx.publicsearch.us fires continuous analytics so networkidle never
    # resolves — navigate then sleep to let the React XHR finish.
    # 8s: more reliable than 5s, especially when running concurrently with other skills.
    await session.navigate(url=url)
    await asyncio.sleep(8)
    debug.append(f"navigated+sleep: {url[:80]}")


async def _scrape(address: str) -> dict:
    # Full results URL — no docTypes filter.
    # The docTypes=DT filter returns "No Results Found" because Deeds of Trust
    # are not indexed by property address in this clerk system. The full search
    # returns UCC filings (which name the lender), mechanics liens, and lien
    # releases — all extractable distress signals.
    url = _results_url(address)
    debug: list[str] = []

    async with make_client() as client:
        session = await client.sessions.start(**session_kwargs(MODEL))
        try:
            await _navigate_and_wait(session, url, debug)

            # Get raw accessibility tree — no LLM, just the page text.
            # Counts are mechanical tasks; regex is more reliable than gpt-4o-mini schema calls.
            # Retry once if page returns 0 cells (XHR not finished yet).
            page_text = ""
            for attempt in range(2):
                resp_raw = await session.extract()
                if resp_raw and resp_raw.data and resp_raw.data.result:
                    r = resp_raw.data.result
                    page_text = r.get("pageText", "") if isinstance(r, dict) else str(r)
                cell_values_check = re.findall(r"cell: ([^\n\\]+)", page_text)
                if cell_values_check:
                    break
                if attempt == 0:
                    debug.append("0 cells on first extract — waiting 5s and retrying")
                    await asyncio.sleep(5)
            debug.append(f"page_text_length: {len(page_text)}")

            # Extract all cell values in order: each row is checkbox, menu, status,
            # grantor, grantee, doc_type, recorded_date, doc_number, ...
            cell_values = re.findall(r"cell: ([^\n\\]+)", page_text)
            debug.append(f"total_cells: {len(cell_values)}")

            # Parse rows: groups of 14 cells per result row
            rows = []
            i = 0
            while i + 13 < len(cell_values):
                chunk = cell_values[i : i + 14]
                # Row structure: [checkbox_label, menu, status, grantor, grantee, doc_type, date, ...]
                if len(chunk) >= 7 and re.search(r"\d{1,2}/\d{1,2}/\d{4}", chunk[6]):
                    rows.append(
                        {
                            "grantor": chunk[3].strip(),
                            "grantee": chunk[4].strip(),
                            "doc_type": chunk[5].strip(),
                            "date": chunk[6].strip(),
                        }
                    )
                    i += 14
                else:
                    i += 1  # re-sync if row boundary is off

            debug.append(f"parsed_rows: {len(rows)}")

            # Count distress signal document types
            lien_types = {"MECHANICS LIEN", "LIEN"}
            asgn_types = {"ASSIGNMENT", "ASGN"}
            mechanics_lien_count = sum(
                1
                for r in rows
                if r["doc_type"].upper() in lien_types
                or "MECHANICS LIEN" in r["doc_type"].upper()
            )
            assignment_count = sum(
                1 for r in rows if any(t in r["doc_type"].upper() for t in asgn_types)
            )

            # Find most recent row where grantor or grantee looks like a financial institution
            _fin_keywords = (
                "CAPITAL",
                "BANK",
                "MORTGAGE",
                "FINANCIAL",
                "CREDIT",
                "LENDING",
            )
            lender_row = None
            for row in reversed(
                rows
            ):  # reversed = most recent last → check all, take last match
                combined = f"{row['grantor']} {row['grantee']}".upper()
                if any(kw in combined for kw in _fin_keywords):
                    lender_row = row
            if lender_row:
                # Determine which party is the financial institution
                g1 = lender_row["grantor"].upper()
                if any(kw in g1 for kw in _fin_keywords):
                    lender_name = lender_row["grantor"]
                    borrower_name = lender_row["grantee"]
                else:
                    lender_name = lender_row["grantee"]
                    borrower_name = lender_row["grantor"]
                lender_date = lender_row["date"]
                lender_doc_type = lender_row["doc_type"]
            else:
                lender_name = borrower_name = lender_date = lender_doc_type = ""

            raw = {
                "lender_name": lender_name,
                "borrower_name": borrower_name,
                "lender_date": lender_date,
                "lender_doc_type": lender_doc_type,
                "mechanics_lien_count": mechanics_lien_count,
                "assignment_count": assignment_count,
            }
            debug.append(f"doc_types: {sorted(set(r['doc_type'] for r in rows))}")
            debug.append(f"extraction: {raw}")

            lender_name = raw.get("lender_name", "")
            borrower_name = raw.get("borrower_name", "")
            lender_date = raw.get("lender_date", "")
            lender_doc_type = raw.get("lender_doc_type", "")
            mechanics_lien_count = raw.get("mechanics_lien_count", 0) or 0
            assignment_count = raw.get("assignment_count", 0) or 0

            try:
                mechanics_lien_count = int(mechanics_lien_count)
            except (TypeError, ValueError):
                mechanics_lien_count = 0
            try:
                assignment_count = int(assignment_count)
            except (TypeError, ValueError):
                assignment_count = 0

            debug.append(
                f"lender={lender_name}, liens={mechanics_lien_count}, assignments={assignment_count}"
            )

            return {
                "lender_name": lender_name,
                "borrower_name": borrower_name,
                "lender_date": lender_date,
                "lender_doc_type": lender_doc_type,
                "mechanics_lien_count": mechanics_lien_count,
                "assignment_count": assignment_count,
                "debug": debug,
            }

        finally:
            await session.end()


def run(params: dict) -> dict:
    state = params.get("state", "").strip().upper()
    if state and state != "TX":
        return {
            "job": "deed_lookup",
            "status": "data_unavailable",
            "reason": "Bexar County Clerk covers TX only",
            "data": None,
        }

    address = params.get("address", "").strip()
    if not address:
        return {
            "job": "deed_lookup",
            "status": "data_unavailable",
            "reason": "No address provided",
            "data": None,
        }

    try:
        raw = asyncio.run(_scrape(address=address))
        debug = raw.get("debug", [])
        for line in debug:
            print(f"[deed_lookup] {line}", file=sys.stderr)

        lender = raw.get("lender_name", "")
        borrower = raw.get("borrower_name", "")
        lender_date = raw.get("lender_date", "")
        lender_doc_type = raw.get("lender_doc_type", "")
        mechanics_lien_count = raw.get("mechanics_lien_count", 0)
        assignment_count = raw.get("assignment_count", 0)

        distress_signals = []
        if mechanics_lien_count >= 2:
            distress_signals.append(
                f"{mechanics_lien_count} mechanics liens — unpaid contractors, cash flow distress signal"
            )
        if assignment_count >= 2:
            distress_signals.append(
                f"Loan assigned {assignment_count} times — possible special servicing"
            )

        if not lender and mechanics_lien_count == 0 and assignment_count == 0:
            return {
                "job": "deed_lookup",
                "status": "data_unavailable",
                "reason": "No lender records found in Bexar County Clerk for this address",
                "data": None,
            }

        return {
            "job": "deed_lookup",
            "status": "ok",
            "data": {
                "lender": lender,
                "borrower": borrower,
                "origination_date": lender_date,
                "doc_type": lender_doc_type,
                "loan_amount": None,
                "mechanics_lien_count": mechanics_lien_count,
                "assignment_count": assignment_count,
                "distress_signals": distress_signals,
                "source": "Bexar County Clerk (bexar.tx.publicsearch.us)",
            },
        }
    except Exception as e:
        print(f"[deed_lookup] EXCEPTION: {e}", file=sys.stderr)
        return {
            "job": "deed_lookup",
            "status": "error",
            "reason": str(e),
            "data": None,
        }


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
