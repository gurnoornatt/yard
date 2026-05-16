---
name: permit_lookup
description: >
  Look up building permit history for a multifamily property.
  Returns all recorded permits with type, date, value, and status.
  Useful for detecting deferred maintenance or recent capex.
---
# permit_lookup

## When to call
During the hidden-flags research phase. Needs {"property_id": "<id>"}.

## How to call
Run: `uv run python ${HERMES_SKILL_DIR}/run.py '{"property_id":"<id>"}'`

## Returns (exact shape)
{"job":"permit_lookup","status":"ok|data_unavailable",
 "property_id":"<id>","data":{...}|null}

data.permits is a list; each permit has:
  permit_number, type, date, value, status, is_new_construction
