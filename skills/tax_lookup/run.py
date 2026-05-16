import json
import os
import re
import sys

from browserbase import Browserbase
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

BB_KEY = os.environ.get("BROWSERBASE_API_KEY", "")
BCAD_PROP = (
    "https://bexar.trueautomation.com/clientdb/property.aspx?cid=110&prop_id={prop_id}"
)
BCAD_SEARCH = "https://bexar.trueautomation.com/clientdb/PropertySearch.aspx?cid=110"


def _parse_address(address: str) -> tuple[str, str]:
    m = re.match(r"^(\d+)\s+(.+)$", address.strip())
    if m:
        return m.group(1), m.group(2)
    return "", address.strip()


def _extract_tax(content: str) -> dict:
    soup = BeautifulSoup(content, "lxml")
    text = soup.get_text(" ", strip=True)

    delinquent = bool(re.search(r"delinquent|past\s+due|overdue", text, re.I))
    amount_match = re.search(r"\$[\d,]+(?:\.\d{2})?", text)
    total_due = amount_match.group(0) if amount_match else None

    year_match = re.search(r"(20\d{2})", text)
    tax_year = year_match.group(1) if year_match else None

    return {
        "delinquent": delinquent,
        "total_due": total_due,
        "tax_year": tax_year,
        "status": "delinquent" if delinquent else "current",
    }


def run(params: dict) -> dict:
    state = params.get("state", "").strip().upper()
    if state != "TX":
        return {
            "job": "tax_lookup",
            "status": "data_unavailable",
            "reason": "BCAD covers Bexar County, TX only",
            "data": None,
        }

    bcad_prop_id = params.get("bcad_prop_id", "")
    address = params.get("address", "")

    try:
        bb = Browserbase(api_key=BB_KEY)
        with sync_playwright() as p:
            session = bb.sessions.create()
            browser = p.chromium.connect_over_cdp(session.connect_url)
            context = browser.contexts[0]
            page = context.pages[0]
            page.set_default_timeout(20000)

            if bcad_prop_id:
                page.goto(BCAD_PROP.format(prop_id=bcad_prop_id))
            else:
                # Re-search by address
                street_num, street_name = _parse_address(address)
                page.goto(BCAD_SEARCH)
                page.wait_for_load_state("networkidle")
                num_sel = "input[name*='StreetNum'], input[id*='StreetNum']"
                name_sel = "input[name*='StreetName'], input[id*='StreetName']"
                if page.locator(num_sel).count():
                    page.fill(num_sel, street_num)
                if page.locator(name_sel).count():
                    page.fill(name_sel, street_name.split()[0])
                page.click("input[type='submit'], button[type='submit']")
                page.wait_for_load_state("networkidle")
                first = page.locator("table a").first
                if first.count():
                    first.click()
                    page.wait_for_load_state("networkidle")

            # Navigate to tax tab
            tax_tab = page.locator("a:has-text('Tax'), a:has-text('Taxes')")
            if tax_tab.count():
                tax_tab.first.click()
                page.wait_for_load_state("networkidle")

            content = page.content()
            browser.close()

        tax_data = _extract_tax(content)
        return {"job": "tax_lookup", "status": "ok", "data": tax_data}

    except Exception as e:
        return {"job": "tax_lookup", "status": "error", "reason": str(e), "data": None}


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
