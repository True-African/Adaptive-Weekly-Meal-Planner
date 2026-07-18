# Adaptive Weekly Meal Planner Skill

Reusable Codex skill and reference implementation for generating affordable, culturally appropriate weekly meal plans from the foods that are grown, sold, and affordable in a specified location.

The planner is location-first and globally configurable. A new country, city, language, currency, or food system can be configured with a small JSON profile and local market observations.

## Package contents

- `skills/adaptive-weekly-meal-planner/SKILL.md`: reusable Codex instructions.
- `scripts/adaptive_meal_planner.py`: dependency-free reference engine for profiles, market ranking, portion scaling, substitutions, and seven-day plans.
- `examples/market_prices_schema.csv`: portable market data schema with local currency and food-group fields.
- `examples/location_profile.json`: example configuration showing how to add a location without changing the algorithm.

## Quick test

```text
python scripts/adaptive_meal_planner.py \
  --location "Example city" \
  --market-data examples/market_prices_schema.csv \
  --household adult_man:1 adult_woman:2 child_2_5:1
```

The engine uses local market rows first. If a food is unavailable from the market data, it falls back to the configured location profile, then to a generic food-group template. Every fallback is labelled in the output.

## Adaptation model

1. Parse the location and optional local profile.
2. Read market observations, food groups, prices, seasonality, and availability.
3. Harmonise each commodity across markets using the median and trimmed mean.
4. Rank foods within each food group by availability, affordability, local preference, and recentness.
5. Assemble meals using the pattern staple + protein + vegetable/fruit + small healthy fat where available.
6. Rotate foods across seven days to protect dietary diversity.
7. Scale quantities and estimated cost with adult-equivalent household members.
8. Provide local substitutions when a top-ranked food is missing or too expensive.

The output is a planning and budgeting aid, not a clinical diet prescription.
