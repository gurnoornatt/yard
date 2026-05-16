import json
import os
import re
import sys

from browserbase import Browserbase
from playwright.sync_api import sync_playwright

BB_KEY = os.environ.get("BROWSERBASE_API_KEY", "")
BCAD_SEARCH = "https://bexar.trueautomation.com/clientdb/PropertySearch.aspx?cid=110"


def _parse_address(address: str) -> tuple[str, str]:
    """Split '4123 McCullough Ave' into ('4123', 'McCullough Ave')."""
    m = re.match(r"^(\d+)\s+(.+)$", address.strip())
    if m:
        return m.group(1), m.group(2)
    return "", address.strip()


def run(params: dict) -> dict:
    state = params.get("state", "").strip().upper()
    if state != "TX":
        return {
            "job": "owner_lookup",
            "status": "data_unavailable",
            "reason": "BCAD covers Bexar County, TX only",
            "data": None,
        }

    address = params.get("address", "")
    street_num, street_name = _parse_address(address)

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

            # Fill street number and name
            num_sel = "input[name*='StreetNum'], input[id*='StreetNum'], input[name*='streetnum']"
            name_sel = "input[name*='StreetName'], input[id*='StreetName'], input[name*='streetname']"

            if page.locator(num_sel).count():
                page.fill(num_sel, street_num)
            if page.locator(name_sel).count():
                page.fill(name_sel, street_name.split()[0])  # just the street name word

            # Submit search
            page.click("input[type='submit'], button[type='submit']")
            page.wait_for_load_state("networkidle")

            # Click first result in table
            first_link = page.locator("table a").first
            if first_link.count() == 0:
                browser.close()
                return {
                    "job": "owner_lookup",
                    "status": "data_unavailable",
                    "reason": "Property not found in BCAD",
                    "data": None,
                }

            # Extract prop_id from href before clicking
            href = first_link.get_attribute("href") or ""
            prop_id_match = re.search(r"prop_id=(\d+)", href)
            bcad_prop_id = prop_id_match.group(1) if prop_id_match else ""

            first_link.click()
            page.wait_for_load_state("networkidle")

            # Extract owner info from property detail page
            content = page.content()
            browser.close()

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(content, "lxml")

        def find_field(label: str) -> str:
            for el in soup.find_all(string=re.compile(label, re.I)):
                sib = el.find_parent().find_next_sibling()
                if sib:
                    return sib.get_text(strip=True)
            return ""

        owner_name = find_field(r"owner\s+name") or find_field(r"owner")
        owner_address = find_field(r"owner\s+address") or find_field(r"mailing")
        appraised = find_field(r"appraised\s+value") or find_field(r"total\s+value")

        # Detect out-of-state from owner address
        owner_state = ""
        state_match = re.search(r"\b([A-Z]{2})\s+\d{5}", owner_address)
        if state_match:
            owner_state = state_match.group(1)

        return {
            "job": "owner_lookup",
            "status": "ok",
            "data": {
                "owner_name": owner_name,
                "owner_address": owner_address,
                "owner_state": owner_state,
                "out_of_state": owner_state not in ("TX", ""),
                "appraised_value": appraised,
                "bcad_prop_id": bcad_prop_id,
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
