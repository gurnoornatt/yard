"""
tax_lookup — Bexar County property tax delinquency check.

Uses Browserbase REST API directly (no Stagehand) to get a cloud browser CDP URL,
then Playwright with CSS selectors for deterministic form filling. No AI involved.
"""

import asyncio
import json
import os
import re
import sys

import httpx

BCAD_SEARCH = "https://bexar.trueautomation.com/clientdb/PropertySearch.aspx?cid=110"
BCAD_PROP = (
    "https://bexar.trueautomation.com/clientdb/property.aspx?cid=110&prop_id={prop_id}"
)
BB_CREATE = "https://api.browserbase.com/v1/sessions"

BB_KEY = os.environ.get("BROWSERBASE_API_KEY", "")
BB_PROJECT_ID = os.environ.get("BROWSERBASE_PROJECT_ID", "")


def _parse_tax_text(text: str) -> dict:
    # BCAD shows estimated taxes (appraised value × tax rate), not actual paid/delinquent status.
    # Extract the estimated annual tax burden and total tax rate from Taxing Jurisdiction section.

    # "Taxes w/Current Exemptions: $341,130.35" or similar
    total_match = re.search(
        r"Taxes w/Current Exemptions:\s*(\$[\d,]+(?:\.\d{2})?)", text
    )
    estimated_tax = total_match.group(1) if total_match else None

    # "Total Tax Rate: 2.267474"
    rate_match = re.search(r"Total Tax Rate:\s*([\d.]+)", text)
    tax_rate = float(rate_match.group(1)) if rate_match else None

    tax_year = re.search(r"\b(20\d{2})\b", text)
    tax_year = tax_year.group(1) if tax_year else None

    return {
        "delinquent": None,  # BCAD (appraisal district) does not report tax payment status
        "estimated_annual_tax": estimated_tax,
        "total_tax_rate": tax_rate,
        "tax_year": tax_year,
        "status": "data_from_bcad_appraisal_district",
    }


def _create_bb_session() -> str:
    """Create a Browserbase session and return the CDP connectUrl."""
    r = httpx.post(
        BB_CREATE,
        headers={"X-BB-API-Key": BB_KEY, "Content-Type": "application/json"},
        json={"projectId": BB_PROJECT_ID},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    connect_url = data.get("connectUrl") or data.get("connect_url")
    if not connect_url:
        raise RuntimeError(f"No connectUrl in Browserbase response: {data}")
    session_id = data.get("id", "unknown")
    print(
        f"[tax_lookup] BB session {session_id} | CDP: {connect_url[:60]}...",
        file=sys.stderr,
    )
    return connect_url


async def _scrape(address: str, bcad_prop_id: str = "") -> dict:
    from playwright.async_api import async_playwright

    m = re.match(r"^(\d+)\s+(.+)$", address.strip())
    street_num = m.group(1) if m else ""
    street_name = (m.group(2) if m else address).split()[0].upper()

    if BB_KEY and BB_PROJECT_ID:
        connect_url = _create_bb_session()
    else:
        connect_url = None  # local fallback

    async with async_playwright() as pw:
        if connect_url:
            browser = await pw.chromium.connect_over_cdp(connect_url)
            ctx = (
                browser.contexts[0] if browser.contexts else await browser.new_context()
            )
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        else:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()

        try:
            if bcad_prop_id:
                await page.goto(
                    BCAD_PROP.format(prop_id=bcad_prop_id),
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                await page.wait_for_timeout(2000)
                taxing = page.locator("text=Taxing Jurisdiction").first
                if await taxing.count() > 0:
                    await taxing.click()
                    await page.wait_for_timeout(1500)
                text = await page.inner_text("body")
                return _parse_tax_text(text)

            # Navigate to BCAD search
            await page.goto(BCAD_SEARCH, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            current_url = page.url
            print(f"[tax_lookup] URL: {current_url}", file=sys.stderr)
            if "customdisplay" in current_url:
                print(
                    "[tax_lookup] Error page — IP blocked even on cloud browser",
                    file=sys.stderr,
                )
                return {}

            # Click "Advanced >>" — triggers ASP.NET postback that reveals street fields
            async with page.expect_navigation(
                wait_until="domcontentloaded", timeout=15000
            ):
                await page.click("#propertySearchOptions_advanced")
            print(
                "[tax_lookup] Advanced >> clicked (postback complete)", file=sys.stderr
            )
            await page.wait_for_timeout(1000)

            # Fill street number and name — now visible in advanced mode
            await page.fill("#propertySearchOptions_streetNumber", street_num)
            print(f"[tax_lookup] filled street number: {street_num}", file=sys.stderr)

            await page.fill("#propertySearchOptions_streetName", street_name)
            print(f"[tax_lookup] filled street name: {street_name}", file=sys.stderr)

            # In advanced mode the search button ID changes to propertySearchOptions_searchAdv
            await page.click("#propertySearchOptions_searchAdv", timeout=10000)
            print("[tax_lookup] clicked search", file=sys.stderr)

            await page.wait_for_load_state("domcontentloaded", timeout=20000)
            await page.wait_for_timeout(2000)

            # Click first property result — href uses capital Property.aspx
            result_link = page.locator("a[href*='prop_id=']").first
            count = await result_link.count()
            print(f"[tax_lookup] property links found: {count}", file=sys.stderr)
            if count == 0:
                return {}

            link_text = await result_link.inner_text()
            print(f"[tax_lookup] clicking: {link_text[:60]}", file=sys.stderr)
            await result_link.click(timeout=10000)
            await page.wait_for_load_state("domcontentloaded", timeout=20000)
            await page.wait_for_timeout(2000)

            # Expand "Taxing Jurisdiction" section — BCAD uses collapsible JS sections
            taxing = page.locator("text=Taxing Jurisdiction").first
            if await taxing.count() > 0:
                await taxing.click()
                await page.wait_for_timeout(1500)

            text = await page.inner_text("body")
            print(f"[tax_lookup] page text length: {len(text)}", file=sys.stderr)
            return _parse_tax_text(text)

        finally:
            await browser.close()


ACTTAX_LIST = "https://bexar.acttax.com/act_webdev/bexar/showlist.jsp"
ACTTAX_DETAIL = "https://bexar.acttax.com/act_webdev/bexar/showdetail2.jsp"
ACTTAX_REFERER = "https://bexar.acttax.com/act_webdev/bexar/index.jsp"


def _parse_amount(s: str) -> float:
    try:
        return float(s.replace(",", "").replace("$", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def _acttax_delinquency(address: str) -> dict:
    """Check Bexar County Tax Assessor-Collector for actual delinquency status.

    Pure HTTP — no browser needed. Separate from BCAD (appraisal district).
    Delinquent = Prior Year(s) Amount Due > $0.
    """
    parts = address.strip().split()
    number = parts[0] if parts and parts[0].isdigit() else ""
    street_word = parts[1][:8].upper() if len(parts) > 1 else ""
    if not number or not street_word:
        return {}

    try:
        r = httpx.post(
            ACTTAX_LIST,
            data={"searchby": "6", "criteria": f"{number} {street_word}"},
            headers={
                "Referer": ACTTAX_REFERER,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=15,
            follow_redirects=True,
        )
        r.raise_for_status()
        cans = re.findall(r"can=(\d+)", r.text)
        if not cans:
            return {}

        for can in cans[:5]:
            dr = httpx.get(
                ACTTAX_DETAIL,
                params={"can": can, "ownerno": "0"},
                headers={"Referer": ACTTAX_LIST},
                timeout=15,
            )
            dr.raise_for_status()
            html = dr.text

            # Skip tangible property accounts (no real estate market value)
            mkt_m = re.search(r"Total Market Value:.*?\$([\d,]+)", html, re.DOTALL)
            if not mkt_m or _parse_amount(mkt_m.group(1)) < 10000:
                continue

            prior_m = re.search(r"Prior Year\(s\) Amount Due:.*?\$([\d,]+\.\d{2})", html, re.DOTALL)
            total_m = re.search(r"Total Amount Due:.*?\$([\d,]+\.\d{2})", html, re.DOTALL)
            levy_m = re.search(r"(20\d{2}) Year Tax Levy:.*?\$([\d,]+\.\d{2})", html, re.DOTALL)
            lawsuits_m = re.search(r"Active Lawsuits:.*?</label>\s*([^\n<]+)", html, re.DOTALL)
            judgments_m = re.search(r"Active Judgments:.*?</label>\s*([^\n<]+)", html, re.DOTALL)
            payment_m = re.search(r"Last Payment Amount Received:.*?\$([\d,]+\.\d{2})", html, re.DOTALL)

            prior_due = _parse_amount(prior_m.group(1)) if prior_m else 0.0
            total_due = _parse_amount(total_m.group(1)) if total_m else 0.0

            result = {
                "delinquent": prior_due > 0,
                "prior_year_amount_due": f"${prior_due:,.2f}",
                "total_amount_due": f"${total_due:,.2f}",
                "current_year_levy": f"${levy_m.group(2)}" if levy_m else None,
                "tax_year": levy_m.group(1) if levy_m else None,
                "active_lawsuits": lawsuits_m.group(1).strip() if lawsuits_m else None,
                "active_judgments": judgments_m.group(1).strip() if judgments_m else None,
                "last_payment_amount": f"${payment_m.group(1)}" if payment_m else None,
                "account_number": can,
            }
            print(
                f"[tax_lookup] acttax: delinquent={result['delinquent']} prior_due=${prior_due:,.2f} lawsuits={result['active_lawsuits']}",
                file=sys.stderr,
            )
            return result

    except Exception as e:
        print(f"[tax_lookup] acttax fetch failed (non-fatal): {e}", file=sys.stderr)

    return {}


def run(params: dict) -> dict:
    state = params.get("state", "").strip().upper()
    if state and state != "TX":
        return {
            "job": "tax_lookup",
            "status": "data_unavailable",
            "reason": "BCAD covers Bexar County, TX only",
            "data": None,
        }

    address = params.get("address", "")
    bcad_prop_id = params.get("bcad_prop_id", "")

    if not address and not bcad_prop_id:
        return {
            "job": "tax_lookup",
            "status": "data_unavailable",
            "reason": "No address provided",
            "data": None,
        }

    try:
        # BCAD: estimated annual tax + tax rate (Browserbase + Playwright)
        bcad_data = asyncio.run(_scrape(address=address, bcad_prop_id=bcad_prop_id))

        # Tax Assessor-Collector: actual delinquency status (pure HTTP, no browser)
        acttax_data = _acttax_delinquency(address) if address else {}

        if not bcad_data and not acttax_data:
            return {
                "job": "tax_lookup",
                "status": "data_unavailable",
                "reason": "No results found for this address in BCAD or Tax Assessor-Collector",
                "data": None,
            }

        # Merge: acttax delinquency fields override BCAD's null delinquent field
        data = bcad_data or {}
        if acttax_data:
            data["delinquent"] = acttax_data.get("delinquent")
            data["prior_year_amount_due"] = acttax_data.get("prior_year_amount_due")
            data["total_amount_due"] = acttax_data.get("total_amount_due")
            data["current_year_levy"] = acttax_data.get("current_year_levy")
            data["active_lawsuits"] = acttax_data.get("active_lawsuits")
            data["active_judgments"] = acttax_data.get("active_judgments")
            data["last_payment_amount"] = acttax_data.get("last_payment_amount")
            data["account_number"] = acttax_data.get("account_number")
            data["source"] = "BCAD (estimated tax) + Bexar County Tax Assessor-Collector (delinquency)"
        else:
            data["source"] = "BCAD (Bexar County Appraisal District)"

        return {"job": "tax_lookup", "status": "ok", "data": data}
    except Exception as e:
        return {"job": "tax_lookup", "status": "error", "reason": str(e), "data": None}


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
