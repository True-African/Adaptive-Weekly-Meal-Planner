# Adaptive Weekly Meal Planner

This repository contains a globally configurable weekly meal-planning system. It helps households, schools, workers, and community programmes create affordable meal plans from foods that are locally grown, sold, in season, and affordable.

The system does not assume a particular country, food list, language, currency, or market. At runtime it can discover a typed location through OpenStreetMap, show nearby food-access places for user verification, and combine confirmed discovery signals with market observations.

## Get started

### 1. Install Python

Use Python 3.10 or newer. No third-party Python packages are required for the reference engine.

```bash
python --version
```

### 2. Download the repository

```bash
git clone https://github.com/True-African/Adaptive-Weekly-Meal-Planner.git
cd Adaptive-Weekly-Meal-Planner
```

### 3. Choose online discovery or offline data

The reference engine supports two location modes.

Online discovery mode is the simplest first run. Type a city, district, or address. The engine geocodes it, searches nearby OpenStreetMap food markets and shops, prints the results, and pauses at a verification checkpoint.

```bash
python scripts/adaptive_meal_planner.py \
  --location "Your city or district" \
  --household adult_man:1 adult_woman:2 child_2_5:1
```

You can omit `--location` and be prompted interactively:

```bash
python scripts/adaptive_meal_planner.py
```

The checkpoint is important. OpenStreetMap can identify nearby food-related places and some explicit shop types, but it does not prove what is currently in stock, the price, or the full food inventory. Confirm the places and signals before continuing.

Market-data mode is useful when you have a local market feed or survey. Provide a CSV with commodity names, food groups, prices, currencies, units, dates, and availability scores. It avoids an online discovery request and uses the supplied observations directly.

```bash
python scripts/adaptive_meal_planner.py \
  --location "Your city or district" \
  --market-data path/to/local_market_prices.csv \
  --household adult_man:1 adult_woman:2 child_2_5:1
```

Use `--offline` to prevent online discovery. Use `--radius-km 10` to search a larger area. Use `--confirm-discovery` to run non-interactively after your application has displayed and verified the discovery checkpoint.

If discovery finds no food places, or cannot identify enough food groups, the planner stops instead of producing a generic local-looking plan. Recover by widening the search area, supplying local market data, adding a profile, or confirming foods explicitly:

```bash
python scripts/adaptive_meal_planner.py \
  --location "Kamwenge, Uganda" \
  --confirm-discovery \
  --confirmed-foods staple=maize meal,sweet potato \
  --confirmed-foods legume=beans,groundnuts \
  --confirmed-foods vegetable=greens,tomato \
  --confirmed-foods fruit=banana,papaya \
  --confirmed-foods animal_protein=eggs,small fish \
  --confirmed-foods healthy_fat=avocado,vegetable oil
```

Curated profile mode remains available when a local implementer wants to add local names, preferred foods, seasonal notes, or foods commonly grown but not captured in market data. Copy `examples/location_profile.json` and pass it with `--profile`. It is optional.

Important: entering only a city name does not automatically discover local foods. A reliable local data source, such as a market feed, survey, agricultural dataset, or curated profile, is required to make location claims.

### 4. Prepare market data when available

Use `examples/market_prices_schema.csv` as the template. The checked-in values are illustrative only; replace them with observations from the target location. Each row should contain:

`date, market, administrative area, commodity, food group, unit, price, currency, availability score, source`

Use the same currency and unit when comparing markets. Include several markets for each important commodity. Results based on fewer than five markets are treated as provisional.

The `food_group` value must be one of:

`staple`, `legume`, `vegetable`, `fruit`, `animal_protein`, or `healthy_fat`.

Availability scores range from `0` to `1`, where `1` means readily available. Do not enter a price without its currency and unit. The generated output reports which food groups came from market data and which groups still use fallback foods.

### 5. Generate a weekly plan

Run the reference engine with a location and household composition. Online discovery will pause before generation so the user can verify the result:

```bash
python scripts/adaptive_meal_planner.py \
  --location "Your city or district" \
  --household adult_man:1 adult_woman:2 child_2_5:1
```

Add `--profile examples/location_profile.json` when using curated profile mode or combining a profile with market data. Add `--market-data examples/market_prices_schema.csv` only to exercise the offline sample data.

The result is JSON containing seven days of breakfasts, lunches, dinners, snacks, water reminders, nutrition rationales, substitutions, assumptions, and the household adult-equivalent factor.

Online discovery fills the resolved country from the geocoder and looks up the country currency code through a country-metadata provider. If more than one currency is returned, or a provider is unavailable, keep the currency as a user-verifiable field before showing costs.

Supported household labels include:

| Member type | Planning factor |
|---|---:|
| `adult_man` | 1.10 |
| `adult_woman` | 0.90 |
| `adolescent` | 0.90 |
| `child_2_5` | 0.45 |
| `child_6_13` | 0.70 |
| `older_adult` | 0.85 |

These factors estimate purchasing and cooking quantities. They are not clinical portion prescriptions.

## How the system adapts

The planner uses evidence in this order:

1. User restrictions, preferences, and cultural context.
2. Local market observations and availability scores.
3. The location profile.
4. Generic food-group defaults, clearly labelled as assumptions.

For each food, the engine ranks availability, affordability, local preference, seasonal fit, and data freshness. It harmonises prices across markets using the median and trimmed mean, then rotates foods across the week and proposes substitutions within the same food group.

Each main meal follows the practical pattern:

`energy food + protein food + vegetable or fruit + small healthy fat + safe water`

## Updating the plan

Refresh the market CSV whenever new observations arrive, then rerun the same command. Online discovery results are cached under `.cache/osm/` and should be refreshed according to your deployment's data policy. Do not treat cached place listings as current inventory.

For an automated deployment, schedule a data-ingestion job that:

1. validates dates, currencies, units, and food groups;
2. merges observations from local markets or approved data providers;
3. writes a versioned market CSV;
4. runs the planner;
5. publishes the JSON to an offline app, dashboard, SMS service, or community-health-worker tool.

Keep the last valid market file on the device for offline fallback. Mark stale data with its observation date instead of presenting it as current.

## OpenStreetMap usage and attribution

The discovery adapter uses a user-triggered Nominatim geocoding request and an Overpass place query. Set a clear application `User-Agent`, cache results, keep the service replaceable, and do not use the public Nominatim endpoint for autocomplete, bulk geocoding, or systematic area harvesting. Display OpenStreetMap attribution in the application:

`OpenStreetMap contributors, ODbL 1.0`

For a larger deployment, configure a hosted or self-managed geocoder and place-search service behind the same adapter interface.

## Using the output with an app

The reference engine is intentionally dependency-free so it can be embedded in:

- an offline Android application;
- a Gradio or Hugging Face demo;
- a community health-worker tablet workflow;
- an SMS or voice-message service;
- a school or workplace meal-planning dashboard.

For local users, present today's meals first, followed by what to buy, substitutions, batch-cooking guidance, and simple language or icon cues. Keep technical evidence and scoring in an appendix or implementer view.

## Testing

Run the checks before publishing changes:

```bash
python -m py_compile scripts/adaptive_meal_planner.py
python -m unittest discover -s tests -p "test_*.py"
```

GitHub Actions runs the same checks on pushes and pull requests.

## Safety and scope

This is a general planning and budgeting aid. It does not diagnose disease or replace clinical nutrition care. Seek qualified professional advice for diabetes, kidney disease, pregnancy complications, severe malnutrition, food allergy, serious illness, swallowing difficulty, or child growth concerns. Do not use it to generate starvation diets, detox diets, unsafe supplement plans, or therapeutic diets without professional oversight.

## Package contents

- `scripts/adaptive_meal_planner.py`: dependency-free reference engine.
- `scripts/location_discovery.py`: Nominatim and Overpass discovery adapter with caching and OSM attribution.
- `skills/adaptive-weekly-meal-planner/SKILL.md`: reusable Codex skill.
- `examples/location_profile.json`: editable location configuration.
- `examples/market_prices_schema.csv`: portable market data template.
- `tests/`: regression tests.
- `.github/workflows/test.yml`: automated GitHub checks.
