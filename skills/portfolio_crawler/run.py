import json
import os
import sys

from browserbase import Browserbase
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

BB_KEY = os.environ.get("BROWSERBASE_API_KEY", "")
BCAD_SEARCH = "https://bexar.trueautomation.com/clientdb/PropertySearch.aspx?cid=110"


def run(params: dict) -> dict:
    state = params.get("state", "").strip().upper()
    owner_name = params.get("owner_name", "").strip()

    if state != "TX":
        return {
            "job": "portfolio_crawler",
            "status": "data_unavailable",
            "reason": "BCAD covers Bexar County, TX only",
            "data": None,
        }

    if not owner_name:
        return {
            "job": "portfolio_crawler",
            "status": "data_unavailable",
            "reason": "No owner name available from owner_lookup",
            "data": None,
        }

    try:
        bb = Browserbase(api_key=BB_KEY)
        with sync_playwright() as p:
            session = bb.sessions.create()
            browser = p.chromium.connect_over_cdp(session.connect_url)
            context = browser.contexts[0]
            page = context.pages[0]
            page.set_default_timeout(20000)

            page.goto(BCAD_SEARCH)
            page.wait_for_load_state("networkidle")

            # Search by owner name
            owner_sel = "input[name*='Owner'], input[id*='Owner'], input[name*='owner']"
            if page.locator(owner_sel).count():
                # Use first word of LLC name for broader match
                search_term = owner_name.split()[0] if owner_name else owner_name
                page.fill(owner_sel, search_term)
                page.click("input[type='submit'], button[type='submit']")
                page.wait_for_load_state("networkidle")

            content = page.content()
            browser.close()

        soup = BeautifulSoup(content, "lxml")
        rows = soup.select("table tr")[1:21]  # skip header, max 20

        properties = []
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                properties.append(
                    {
                        "address": cells[0].get_text(strip=True),
                        "property_type": cells[1].get_text(strip=True)
                        if len(cells) > 1
                        else "",
                        "appraised_value": cells[2].get_text(strip=True)
                        if len(cells) > 2
                        else "",
                    }
                )

        return {
            "job": "portfolio_crawler",
            "status": "ok",
            "data": {
                "owner_name": owner_name,
                "properties": properties,
                "property_count": len(properties),
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
