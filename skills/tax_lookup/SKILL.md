---
name: tax_lookup
description: >
  Look up property tax status and delinquency for a multifamily property.
  Returns current/delinquent status, appraised value, annual taxes,
  and delinquency amount if applicable. Tax delinquency is a major red flag.
---
# tax_lookup

## When to call
During the hidden-flags research phase. Needs {"property_id": "<id>"}.

## How to call
Run: `uv run python ${HERMES_SKILL_DIR}/run.py '{"property_id":"<id>"}'`

## Returns (exact shape)
{"job":"tax_lookup","status":"ok|data_unavailable",
 "property_id":"<id>","data":{...}|null}

data fields when ok:
  status ("current"|"delinquent"), appraised_value, tax_year,
  annual_taxes, delinquent (bool), delinquency_amount, delinquency_years
