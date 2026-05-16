---
name: deed_lookup
description: >
  Look up deed-of-trust filings and loan history for a multifamily property.
  Call after owner_lookup. Returns lender, loan amount, origination date,
  estimated maturity, and CMBS flag for each recorded loan.
---
# deed_lookup

## When to call
After owner_lookup, to understand the debt structure. Needs {"property_id": "<id>"}.

## How to call
Run: `uv run python ${HERMES_SKILL_DIR}/run.py '{"property_id":"<id>"}'`

## Returns (exact shape)
{"job":"deed_lookup","status":"ok|data_unavailable",
 "property_id":"<id>","data":{...}|null}

data.loans is a list; each loan has:
  lender, origination_date, loan_amount, estimated_maturity,
  is_cmbs, lender_type, interest_rate_type, note
