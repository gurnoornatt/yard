---
name: parse_om
description: >
  Parse a broker offering memorandum PDF to extract property basics.
  CALL THIS FIRST before any other research. Returns address, units,
  asking price, year built, asset class, and broker narrative.
---
# parse_om

## When to call
First step for any OM analysis. Call with the PDF file path.

## How to call
Run: `uv run python ${HERMES_SKILL_DIR}/run.py '{"pdf_path":"<path>"}'`

Demo shortcut: if the path contains "mccullough", "blanco", or "culebra",
returns pre-cached data and also sets property_id for downstream calls.

## Returns (exact shape)
{"job":"parse_om","status":"ok|data_unavailable",
 "property_id":"<id>","data":{...}|null}

data fields when ok:
  address, units, year_built, asking_price, price_per_unit,
  asset_class, broker, broker_narrative, property_id
