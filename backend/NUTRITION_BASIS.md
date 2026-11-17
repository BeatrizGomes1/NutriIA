# Nutrition reference (P0)

The existing API routes and five nutrient fields keep their names and units.
`nutrition` now also contains optional/defaulted metadata:

- `basis`: `per_100g`, `per_100ml`, `per_serving`, or `unknown` (default).
- `serving_quantity` and `serving_unit` (`g`/`ml`): supplied together when known.
  These describe the portion, even if the selected nutrient column is per 100.
  A per-serving column may have an unknown portion size.

Source adapters do not convert reference bases. The goal evaluation can derive
compatible serving facts separately; see NUTRITION_GOAL_CRITERIA.md. Sodium still uses mg.
Unknown reference must not support quantitative conclusions in the analysis prompt.
Zero is a known value; null is absent. Non-finite/negative nutrients and
nonpositive portions are rejected. Metadata alone is not nutrient content.

## Sources

Photo extraction selects one visible column, preserving its reference. It must
not infer reference from package size or mix columns. A valid model does not
prove an image transcription is correct; visual accuracy remains a limitation.

OFF `_100g` fields can refer to 100 g OR 100 ml:
https://github.com/openfoodfacts/openfoodfacts-server/blob/main/html/data-fields.txt
Consequently, ambiguous `nutrition_data_per=100g` remains unknown unless an explicit
serving column can be selected as described below, without guessing
from package or serving units. An explicit `100ml` is preserved. For `serving`,
only `_serving` values are read, without filling gaps from `_100g`. The raw
nutrition_data_per and serving description remain in serving_information.

## Persistence and existing data

No database migration is required. New writes use the existing nutrition_table
JSONB with `{"schema_version": 2, "values": {...}}`. Legacy flat tables and
legacy `per_100g` wrappers retain their numbers but are read as unknown because
the previous writer assigned that reference automatically. Reading does not
rewrite any existing rows. Completely absent nutrition remains null so an OFF
upsert does not replace a previous table with empty content.

Cache keys include nutrition schema version 2, basis and portion metadata.
Old cache entries are bypassed for new analysis requests. Existing historical
analysis texts are not rewritten or revalidated by this scoped change and can
still contain conclusions made before this fix.

Photo deduplication requires identical nutrition metadata/values and serving
information; otherwise it creates a new record rather than overwriting an old
capture's product. No frontend changes, migrations, commits or data backfill
are part of this implementation.

## Verification

Run from the repository root:
`backend/.venv/Scripts/python.exe -m pytest backend/tests -q -p no:cacheprovider`

Tests simulate OFF, Gemini and API service dependencies. Persistence adapters
are tested without a database. Live provider and PostgreSQL execution are not
part of these checks.


When the selected `_100g` reference is ambiguous, an explicit, valid serving size
and at least one valid `_serving` nutrient allow selecting that whole column as
per_serving. Missing serving nutrients remain null; no `_100g` fallback is applied
per nutrient. Without a valid portion/column the reference stays unknown.
Ninho 7891000325858: 6.3 g protein, 124 kcal, 0 g fibre per labelled 25 g serving.
New captures update the selected values and change the analysis cache key; no
existing row is blindly relabelled and historical analyses are not rewritten.
