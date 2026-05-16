---
name: synthesize_analysis
description: >
  Final step. Call ONLY after all research tools have been run.
  Returns all gathered research data plus the 6-section synthesis template.
  After calling this, write the complete 6-section analysis and save it to the output_path.
  Do not call any more research tools after this.
---
# synthesize_analysis

## When to call
Last step, after owner_lookup, deed_lookup, portfolio_crawler, permit_lookup,
tax_lookup, violations_lookup, comps_lookup, and maturity_estimator are done.
Needs {"property_id": "<id>"}.

## How to call
Run: `uv run python ${HERMES_SKILL_DIR}/run.py '{"property_id":"<id>"}'`

## Returns (exact shape)
{"job":"synthesize_analysis","status":"ok|data_unavailable",
 "property_id":"<id>","data":{...}|null}

data fields when ok:
  research_data (all gathered data), output_path, synthesis_template (6 sections),
  instruction (what to write)

After receiving this, write the full 6-section analysis:
  1. Property Snapshot — address, units, year built, appraised value, asset class
  2. Owner Motivation Profile — LLC, principal, hold period, portfolio, intent signals
  3. Loan Situation — lender, origination, maturity, CMBS vs regional, refi assessment
  4. Submarket Reality Check — specific comp addresses + prices, rent trend, vacancy
  5. Hidden Flags — violations, tax delinquency; or "No hidden flags detected"
  6. Bottom-Line Recommendation — exactly PURSUE / WATCHLIST / PASS, 3-5 sentences
     citing specific numbers, plus next concrete move

Rules: cite specific numbers, no marketing language, save report to output_path.
