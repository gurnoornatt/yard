---
name: portfolio_crawler
description: >
  Crawl the owner's full portfolio — all properties owned by the same LLC
  or principal. Call after owner_lookup when the owner is an LLC.
  Reveals portfolio pressure: a stressed owner selling one may be selling all.
---
# portfolio_crawler

## When to call
After owner_lookup, if owner is_entity is true. Needs {"property_id": "<id>"}.

## How to call
Run: `uv run python ${HERMES_SKILL_DIR}/run.py '{"property_id":"<id>"}'`

## Returns (exact shape)
{"job":"portfolio_crawler","status":"ok|data_unavailable",
 "property_id":"<id>","data":{...}|null}

data fields when ok:
  entity, principal, other_properties (list), total_units_in_portfolio,
  total_portfolio_value_approx
  each property: address, units, acquisition_date, appraised_value
