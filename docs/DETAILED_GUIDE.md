# Detailed Guide

This guide contains the implementation details for the Adaptive Weekly Meal Planner. Start with the [main README](../README.md) if you want to open the browser dashboard quickly.

## Command-line engine

The reference engine requires Python 3.10 or newer and no third-party Python packages.

```bash
python scripts/adaptive_meal_planner.py \
  --location "Your city or district" \
  --household adult_man:1 adult_woman:2 child_2_5:1
```

You can omit `--location` and enter it interactively. The online mode geocodes the location, searches nearby OpenStreetMap food-access places, and pauses for a verification checkpoint. Map listings indicate food access only; they do not prove current inventory, prices, or seasonality.

When the default 5 km search is empty, the engine retries at 25 km. Provider timeouts are reported separately from genuine empty results. The planner still returns a seven-day plan: interactive users can ask a trusted local person about missing food groups, while non-interactive runs use clearly labelled fallback foods.

Supply local confirmation directly when needed:

```bash
python scripts/adaptive_meal_planner.py \
  --location "Example city" \
  --confirmed-foods staple=rice,maize \
  --confirmed-foods legume=beans,lentils \
  --confirmed-foods vegetable=greens,cabbage \
  --confirmed-foods fruit=banana,mango \
  --confirmed-foods animal_protein=eggs,fish \
  --confirmed-foods healthy_fat=avocado,groundnuts
```

Use `--offline` to prevent online discovery. Use `--profile examples/location_profile.json` for a curated local profile.

## Market data and budget estimates

Use `examples/market_prices_schema.csv` as the template for local observations. Replace the illustrative values before making decisions. Each row should include:

`date, market, administrative area, commodity, food group, unit, price, currency, availability score, source`

Valid food groups are `staple`, `legume`, `vegetable`, `fruit`, `animal_protein`, and `healthy_fat`. Use the same currency and unit when comparing markets. Five or more markets are preferred; fewer than five are marked provisional.

```bash
python scripts/adaptive_meal_planner.py \
  --location "Your city or district" \
  --market-data path/to/local_market_prices.csv \
  --household adult_man:1 adult_woman:2 child_2_5:1
```

The JSON output contains seven meals per day, assumptions, substitutions, household adult-equivalent factors, `market_prices`, and `budget_estimate`. The budget includes household-scaled purchase quantities, line items, totals by currency, and `price_coverage`. It is a rough planning estimate, not a guarantee of what a household will spend.

The browser dashboard resolves a location's currency through location discovery. Currency identification and price collection are separate steps: OpenStreetMap and country metadata can identify a currency, but they do not provide current commodity prices. The dashboard therefore refuses to present USD demonstration prices as local currency. Supply market observations with the detected currency to obtain local cost estimates.

Supported household factors are:

| Member type | Factor |
|---|---:|
| `adult_man` | 1.10 |
| `adult_woman` | 0.90 |
| `adolescent` | 0.90 |
| `child_2_5` | 0.45 |
| `child_6_13` | 0.70 |
| `older_adult` | 0.85 |

These are purchasing and cooking estimates, not clinical portion prescriptions.

## How adaptation works

The planner uses evidence in this order:

1. User restrictions, preferences, culture, and local confirmation.
2. Local market observations and availability scores.
3. User-verified map discovery signals.
4. A curated location profile.
5. Generic food-group fallback, clearly labelled as an assumption.

Each main meal targets an energy food, protein food, vegetable or fruit, small healthy fat, and safe water. Foods rotate across the week and substitutions remain within the same food group.

The output includes `plan_status` and, when discovery is requested, `verification_checkpoint`. These fields tell an implementer whether the result used market data, local confirmation, map signals, or fallback logic.

## OpenStreetMap usage

The discovery adapter uses a user-triggered Nominatim request and an Overpass place query. Keep requests cached, use a clear application `User-Agent`, respect public service limits, and keep the provider replaceable. Display:

`OpenStreetMap contributors, ODbL 1.0`

For larger deployments, place a hosted or self-managed geocoder and place-search service behind the same adapter interface.

## Updating and deployment

Refresh the market CSV whenever new observations arrive, then rerun the planner. Keep the last valid market file on an offline device and show its observation date. For automation, validate dates, currencies, units, and food groups; merge approved observations; write a versioned CSV; run the planner; and publish the JSON to an app, dashboard, SMS service, or community-health-worker tool.

The browser dashboard can be hosted behind a production WSGI/ASGI server or adapted to Gradio/Hugging Face Spaces by calling `build_plan()` from `web_app.py`. For public deployment, use HTTPS, authentication where needed, rate limiting, and a production server rather than the development server.

## Safety

This is a general planning and budgeting aid. It does not diagnose disease or replace clinical nutrition care. Refer users to qualified professionals for diabetes, kidney disease, pregnancy complications, severe malnutrition, food allergy, serious illness, swallowing difficulty, or child growth concerns. Do not generate starvation diets, detox diets, unsafe supplement plans, or therapeutic diets without professional oversight.

## Testing

```bash
python -m py_compile scripts/adaptive_meal_planner.py web_app.py
python -m unittest discover -s tests -p "test_*.py"
```
