---
name: comps_lookup
description: >
  Pull recent comparable sales in the submarket for a multifamily property.
  Returns comp transactions with specific addresses, sale prices, price-per-unit,
  and submarket vacancy/trend. Use to reality-check the asking price.
---
# comps_lookup

## When to call
After owner and loan research, to assess pricing. Needs {"property_id": "<id>"}.

## How to call
Run: `uv run python ${HERMES_SKILL_DIR}/run.py '{"property_id":"<id>"}'`

## Returns (exact shape)
{"job":"comps_lookup","status":"ok|data_unavailable",
 "property_id":"<id>","data":{...}|null}

data fields when ok:
  submarket, comps (list), avg_price_per_unit, rent_trend, submarket_vacancy
  each comp: address, units, sale_date, sale_price, price_per_unit, year_built
