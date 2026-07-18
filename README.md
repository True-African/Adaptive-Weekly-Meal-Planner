# Adaptive Weekly Meal Planner

This repository contains a globally configurable weekly meal-planning system. It helps households, schools, workers, and community programmes create affordable meal plans from foods that are locally grown, sold, in season, and affordable.

The system does not assume a particular country, food list, language, currency, or market. Local information is supplied through a location profile and market observations.

## Get started

### 1. Install Python

Use Python 3.10 or newer. No third-party Python packages are required for the reference engine.

```bash
python --version
```

### 2. Download the repository

```bash
git clone https://github.com/True-African/AdaptiveWeeklyMealPlanner.git
cd AdaptiveWeeklyMealPlanner
```

### 3. Describe your location

Copy `examples/location_profile.json` and edit it for the target setting. Add:

- location and country name;
- local currency and preferred languages;
- staple foods;
- legumes and other protein foods;
- vegetables and fruits;
- animal-source foods where appropriate;
- locally used names;
- preferred foods and seasonal notes.

The profile is a fallback. Recent market observations take priority over it.

### 4. Prepare market data

Use `examples/market_prices_schema.csv` as the template. Each row should contain:

`date, market, administrative area, commodity, food group, unit, price, currency, availability score, source`

Use the same currency and unit when comparing markets. Include several markets for each important commodity. Results based on fewer than five markets are treated as provisional.

The `food_group` value must be one of:

`staple`, `legume`, `vegetable`, `fruit`, `animal_protein`, or `healthy_fat`.

Availability scores range from `0` to `1`, where `1` means readily available. Do not enter a price without its currency and unit.

### 5. Generate a weekly plan

Run the reference engine with a location, profile, market file, and household composition:

```bash
python scripts/adaptive_meal_planner.py \
  --location "Example city" \
  --profile examples/location_profile.json \
  --market-data examples/market_prices_schema.csv \
  --household adult_man:1 adult_woman:2 child_2_5:1
```

The result is JSON containing seven days of breakfasts, lunches, dinners, snacks, water reminders, nutrition rationales, substitutions, assumptions, and the household adult-equivalent factor.

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

Refresh the market CSV whenever new observations arrive, then rerun the same command. This supports weekly or daily updates without changing the algorithm.

For an automated deployment, schedule a data-ingestion job that:

1. validates dates, currencies, units, and food groups;
2. merges observations from local markets or approved data providers;
3. writes a versioned market CSV;
4. runs the planner;
5. publishes the JSON to an offline app, dashboard, SMS service, or community-health-worker tool.

Keep the last valid market file on the device for offline fallback. Mark stale data with its observation date instead of presenting it as current.

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
- `skills/adaptive-weekly-meal-planner/SKILL.md`: reusable Codex skill.
- `examples/location_profile.json`: editable location configuration.
- `examples/market_prices_schema.csv`: portable market data template.
- `tests/`: regression tests.
- `.github/workflows/test.yml`: automated GitHub checks.
