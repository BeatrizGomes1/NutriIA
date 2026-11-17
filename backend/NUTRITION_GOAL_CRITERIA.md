# Quantitative product evaluation by dietary goal

Version: goal-composition-v1. This evaluates product composition, not a complete
diet, clinical suitability, protein quality/bioavailability or a body-weight result.
No quantities to consume, daily targets, or patient prescriptions are generated.

## References and scope

European Commission nutrition claim composition conditions (EC 1924/2006 Annex):
https://food.ec.europa.eu/food-safety/labelling-and-nutrition/nutrition-and-health-claims/nutrition-claims_en

Energy factor for protein: 4 kcal/g; fibre: 2 kcal/g (EU 1169/2011 Annex XIV):
https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:02011R1169-20250401

These are documented composition benchmarks, NOT a statement of compliance with
Brazilian labelling law or a claim that a product causes muscle gain/weight loss.

## Inputs

Existing: calories_kcal, protein_g, sugars_g, carbohydrates_g, sodium_mg,
basis, serving_quantity and serving_unit. Added optional fiber_g (g on the SAME
reference as other nutrients), from OFF fiber_<selected suffix> or visible label.
Missing fibre stays null. No schema migration: existing JSONB persists it.
Quantities must be finite, nonnegative JSON numbers, not booleans/numeric strings.

## Muscle gain

Primary criterion: share of declared energy supplied by protein = protein_g * 4 /
calories_kcal * 100, only on a known common reference, with positive energy.
At least 20% reaches the high protein proportion benchmark; at least 12% reaches
the source benchmark; below 12% does not reach that particular benchmark.
Those categories are product characteristics, NOT a verdict about the whole diet.
A high fraction can coexist with a small absolute protein amount; source amounts
and serving facts remain available so the fraction is never an intake prescription.

## Weight loss

Primary criteria: energy density and available fibre, without an arbitrary
high/low calorie cutoff. Energy is reported per 100 g OR per 100 ml; never mix
mass and volume or assume a mass/volume conversion. Lower energy per equal
quantity means less energy on that same reference, not guaranteed weight loss.

Fibre benchmarks: source >=3 g/100 g OR >=1.5 g/100 kcal;
high >=6 g/100 g OR >=3 g/100 kcal. Only computable references are evaluated.
A positive alternative can establish the corresponding benchmark; missing
alternatives never become evidence of absence. Other cases say not established.
This describes fibre composition and does not promise satiety or weight loss.

## Portions, validity and traceability

Serving facts use the labelled portion only. Convert per-100 to per-serving only
with quantity and matching unit; convert per-serving to per-100 only with a known
portion size and unit. Ratios from a per-serving column can be computed without
its mass/volume because the shared serving cancels. Its density cannot.
No guessed portions or inferred units. Original values are never overwritten.

Unknown basis: no numeric goal metrics/comparisons, while verified qualitative
observations remain. Missing nutrients are listed. Protein/fibre implying more
energy than the declared total, sugars above carbohydrates, or mass-based
macronutrients exceeding the reference mass block calculations conservatively.
This is a partial consistency check, not a complete calorimetric validation;
rounding discrepancies can require label review rather than an invented tolerance.
Threshold comparisons use Decimal and unrounded values; display is approximate.

GoalAssessment exposes metrics, findings, missing data, state and reference
internally. The observation catalogue publishes only backend-validated results;
Gemini cannot change formulas, values or thresholds. Safety evaluation is separate
and confirmed allergies still force not_recommended, even for high protein food.
No overall beneficial diet score is inferred from a single characteristic.
For these goals, a positive benchmark alone does not produce recommended: the
existing aggregate status remains attention unless a safety/invalid-data guard
requires not_recommended/insufficient_information.

## Compatibility and tests

Public response keys/statuses remain; fiber_g is additive and nullable. Quantitative
reasons use existing summary/reasons/evidence persistence. The cache personalization
version includes the goal-rule version; old records are not rewritten. New capture
or reanalysis is necessary for an existing historical entry to use the new policy.
Android only recognizes new reason prefixes; its two-sentence summary, two normal
reasons, critical alerts, ingredients and optional details are retained.

Tests cover boundary values, different compositions/goals, known and unknown
references, equivalent servings, missing/invalid/inconsistent inputs, allergies,
source extraction, JSONB roundtrip, and HTTP/PostgreSQL history after goal change.
Integration uses only nutriIA_test with identity guards and outer rollback.
OFF/Gemini are simulated; no migrations or production writes are required.
