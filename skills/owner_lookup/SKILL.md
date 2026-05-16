---
name: owner_lookup
description: >
  Look up the legal owner of a multifamily property. CALL THIS FIRST
  after parse_om for any OM analysis. Returns owner LLC, principal,
  mailing address, acquisition date, and hold-period years.
---
# owner_lookup

## When to call
First research step after parsing the OM. Needs {"property_id": "<id>"}.

## How to call
Run: `uv run python ${HERMES_SKILL_DIR}/run.py '{"property_id":"<id>"}'`

## Returns (exact shape)
{"job":"owner_lookup","status":"ok|data_unavailable",
 "property_id":"<id>","data":{...}|null}

data fields when ok:
  llc_name, principal, mailing_address, acquisition_date,
  hold_period_years, is_entity, owner_state
