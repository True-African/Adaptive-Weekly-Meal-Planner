---
name: adaptive-weekly-meal-planner
description: Generate and implement location-adaptive weekly meal planners that use local food availability, market prices, seasonality, household composition, cultural preferences, and language settings. Use for households, schools, workers, and community centres in any country, including low-bandwidth and offline deployments.
---

# Adaptive Weekly Meal Planner

Treat the location as a configuration, not as a fixed food list. Never assume a country, currency, language, market, or food list unless the user specifies it or the data indicates it.

## Required intake

Collect or label assumptions for:

- country, city, district, and neighbourhood;
- household members and age groups;
- budget and currency;
- meals per day and cooking equipment;
- foods commonly grown, sold, or stored locally;
- foods to avoid for allergy, religion, culture, dislike, or clinical advice;
- preferred language and literacy level;
- goal and shopping frequency;
- recent market observations, if available.

## Location adaptation workflow

Use the following order of evidence:

1. User-supplied foods, restrictions, culture, and preferences.
2. Local market observations with commodity, food group, price, unit, market, date, and availability.
3. A country/city profile supplied by the implementer.
4. A generic food-group fallback, clearly labelled as an assumption.

Do not treat an international food database as proof that a food is locally available. Unknown foods should be excluded or shown as "needs local confirmation" until a user, health worker, market survey, or trusted local dataset confirms them.

## Planning algorithm

For each meal, target:

`staple or other energy food + protein food + vegetable or fruit + small healthy fat + safe water`

Rank candidate foods within each group using:

`availability 35% + affordability 30% + local preference 20% + seasonal fit 10% + observed-data freshness 5%`

If weights or scores are unavailable, use transparent defaults and label them. Harmonise a commodity across markets with the median and a trimmed mean; average those two values, retain the number of markets, and flag fewer than five markets as provisional. Never silently convert currencies or units.

Rotate candidates over seven days so the plan does not repeat one staple, legume, vegetable, or fruit unnecessarily. Use substitutions from the same food group when a food is unavailable or exceeds the household budget.

## Household quantities

Use adult-equivalent eaters only as a purchasing and cooking estimate:

- adult man: 1.1
- adult woman: 0.9
- child 2-5: 0.45
- child 6-13: 0.7
- adolescent 14-17: 0.9
- older adult 65+: 0.85

State that these are rough planning factors, not clinical portion prescriptions. Keep child, pregnancy, lactation, diabetes, kidney disease, allergy, severe malnutrition, and growth concerns within professional referral boundaries.

## Evidence rules

Apply WHO healthy-diet principles and FAO dietary-diversity logic as global guardrails. Add country-specific nutrition-sensitive agriculture or food-balance guidance only when a reliable local source or implementer profile is available. Separate evidence rules from local food availability data in the implementation.

## Presentation

Present the result in this order for a local person:

1. Today's meals with local food names and simple quantities.
2. What to buy, grouped by food type.
3. What to substitute if unavailable or expensive.
4. A batch-cooking and fuel-saving suggestion.
5. SMS, voice, and icon/text cues in the selected language.
6. A short safety and referral note.

Do not lead with nutrient terminology, a long evidence explanation, or a technical score. Preserve a PDF-ready appendix for health workers and implementers.

## Safety boundary

Do not diagnose disease, prescribe therapeutic diets, recommend starvation, detoxes, unsafe supplements, or replace clinical care. Refer people with diabetes, kidney disease, pregnancy complications, severe malnutrition, food allergy, serious illness, swallowing difficulty, or child growth concerns to a qualified health professional.

## Reference implementation

Use `scripts/adaptive_meal_planner.py` for deterministic profile resolution, market harmonisation, food ranking, household scaling, and plan generation. Read `examples/location_profile.json` before adding a new location.
