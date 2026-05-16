---
name: maturity_estimator
description: >
  Estimate loan maturity pressure for a multifamily property.
  Call after deed_lookup. Calculates months to maturity, flags past-due loans,
  and returns a refi pressure level (high/medium/low). High pressure = forced seller signal.
---
# maturity_estimator

## When to call
After deed_lookup, to assess refinance/exit pressure. Needs {"property_id": "<id>"}.

## How to call
Run: `uv run python ${HERMES_SKILL_DIR}/run.py '{"property_id":"<id>"}'`

## Returns (exact shape)
{"job":"maturity_estimator","status":"ok|data_unavailable",
 "property_id":"<id>","data":{...}|null}

data fields when ok:
  loan_maturity, months_to_maturity (negative = past due),
  maturity_status ("past_due"|"near_term"|"healthy"),
  refi_pressure ("high"|"medium"|"low"), note
