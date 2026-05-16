---
name: violations_lookup
description: >
  Look up code violations filed against a multifamily property.
  Returns all violations with type, date, status, and fine.
  Open violations are a red flag; closed violations show resolution pattern.
---
# violations_lookup

## When to call
During the hidden-flags research phase. Needs {"property_id": "<id>"}.

## How to call
Run: `uv run python ${HERMES_SKILL_DIR}/run.py '{"property_id":"<id>"}'`

## Returns (exact shape)
{"job":"violations_lookup","status":"ok|data_unavailable",
 "property_id":"<id>","data":{...}|null}

data fields when ok:
  violations (list), open_violations (int), total_violations (int)
  each violation: case_number, type, date_filed, status, resolution_date, fine
