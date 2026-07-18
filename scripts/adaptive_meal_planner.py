"""Small, dependency-free location-adaptive weekly meal planner.

The module is deliberately conservative: market observations and an explicit
location profile are stronger evidence than a global food list.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from location_discovery import discover_location


GROUPS = ("staple", "legume", "vegetable", "fruit", "animal_protein", "healthy_fat")
WEEKLY_PURCHASE_UNITS_PER_AE = {
    "staple": 2.5,
    "legume": 0.8,
    "vegetable": 2.0,
    "fruit": 1.5,
    "animal_protein": 1.0,
    "healthy_fat": 0.25,
}
ADULT_EQUIVALENTS = {
    "adult_man": 1.1, "adult_woman": 0.9, "adolescent": 0.9,
    "child_2_5": 0.45, "child_6_13": 0.7, "older_adult": 0.85,
}
DEFAULT_PROFILE = {
    "staple": ["rice", "maize meal", "potato", "sweet potato"],
    "legume": ["beans", "peas", "lentils", "groundnuts"],
    "vegetable": ["cabbage", "tomato", "onion", "amaranth", "pumpkin"],
    "fruit": ["banana", "papaya", "orange", "mango"],
    "animal_protein": ["egg", "small fish", "milk", "chicken"],
    "healthy_fat": ["avocado", "groundnuts", "vegetable oil"],
}
ALIASES = {
    "maize": "staple", "maize meal": "staple", "cornmeal": "staple", "rice": "staple",
    "potato": "staple", "irish potato": "staple", "sweet potato": "staple", "cassava": "staple",
    "plantain": "staple", "banana plantain": "staple", "sorghum": "staple", "millet": "staple",
    "beans": "legume", "bean": "legume", "peas": "legume", "lentils": "legume",
    "chickpeas": "legume", "groundnuts": "legume", "peanuts": "legume", "soy": "legume",
    "cabbage": "vegetable", "tomato": "vegetable", "tomatoes": "vegetable", "onion": "vegetable",
    "amaranth": "vegetable", "dodo": "vegetable", "spinach": "vegetable", "kale": "vegetable",
    "carrot": "vegetable", "pumpkin": "vegetable", "eggplant": "vegetable", "okra": "vegetable",
    "banana": "fruit", "papaya": "fruit", "orange": "fruit", "mango": "fruit", "pineapple": "fruit",
    "avocado": "healthy_fat", "vegetable oil": "healthy_fat", "palm oil": "healthy_fat",
    "egg": "animal_protein", "eggs": "animal_protein", "fish": "animal_protein", "small fish": "animal_protein",
    "sardines": "animal_protein", "milk": "animal_protein", "chicken": "animal_protein", "beef": "animal_protein",
    "goat": "animal_protein", "meat": "animal_protein",
}


@dataclass
class Food:
    name: str
    group: str
    availability: float = 0.5
    price: Optional[float] = None
    currency: str = ""
    unit: str = "kg"
    markets: int = 0
    preferred: float = 0.5
    source: str = "profile fallback"


@dataclass
class LocationProfile:
    location: str
    country: str = ""
    currency: str = ""
    languages: List[str] = field(default_factory=lambda: ["English"])
    foods: Dict[str, List[str]] = field(default_factory=lambda: {g: list(v) for g, v in DEFAULT_PROFILE.items()})
    preferred_foods: List[str] = field(default_factory=list)
    local_names: Dict[str, str] = field(default_factory=dict)
    seasonal_notes: str = ""
    assumptions: List[str] = field(default_factory=list)


def normalize(value: str) -> str:
    return " ".join((value or "").lower().replace("_", " ").split())


def load_profile(path: Optional[str], location: str) -> LocationProfile:
    raw = {}
    if path:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    foods = {g: list(raw.get("foods", {}).get(g, DEFAULT_PROFILE[g] if path else [])) for g in GROUPS}
    return LocationProfile(
        location=raw.get("location", location), country=raw.get("country", ""),
        currency=raw.get("currency", ""), languages=list(raw.get("languages", ["English"])),
        foods=foods, preferred_foods=list(raw.get("preferred_foods", [])),
        local_names=dict(raw.get("local_names", {})), seasonal_notes=raw.get("seasonal_notes", ""),
        assumptions=[] if path else ["No local profile supplied; market observations are used for covered food groups."],
    )


def read_market_rows(path: Optional[str]) -> List[dict]:
    if not path:
        return []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def infer_group(name: str, explicit: str = "") -> Optional[str]:
    group = normalize(explicit)
    if group in GROUPS:
        return group
    return ALIASES.get(normalize(name))


def _latest(rows: Iterable[dict]) -> List[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[(normalize(row.get("commodity", "")), normalize(row.get("market", "")))].append(row)
    latest = []
    for entries in grouped.values():
        entries.sort(key=lambda r: r.get("date", ""), reverse=True)
        latest.append(entries[0])
    return latest


def harmonise_market_rows(rows: Sequence[dict]) -> Dict[str, Food]:
    latest = _latest(rows)
    grouped = defaultdict(list)
    for row in latest:
        name = normalize(row.get("commodity", ""))
        group = infer_group(name, row.get("food_group", ""))
        try:
            price = float(row.get("price", ""))
        except (TypeError, ValueError):
            price = None
        if name and group:
            grouped[name].append((row, price, group))
    result = {}
    for name, entries in grouped.items():
        prices = [p for _, p, _ in entries if p is not None and p >= 0]
        prices.sort()
        trim = prices[1:-1] if len(prices) >= 5 else prices
        typical = ((statistics.median(prices) + statistics.mean(trim)) / 2) if prices else None
        avail = [float(r.get("availability_score", 0.5) or 0.5) for r, _, _ in entries]
        row = entries[0][0]
        result[name] = Food(name, entries[0][2], min(1.0, statistics.mean(avail)), typical,
                            row.get("currency", ""), row.get("unit", "kg"), len(entries), 0.5,
                            row.get("source", "market data"))
    return result


def resolve_foods(profile: LocationProfile, market_foods: Mapping[str, Food]) -> Dict[str, List[Food]]:
    by_group = {g: [] for g in GROUPS}
    seen = set()
    for food in market_foods.values():
        by_group[food.group].append(food)
        seen.add(food.name)
    for group, names in profile.foods.items():
        if not names and by_group[group]:
            continue
        if not names:
            names = DEFAULT_PROFILE[group]
        for name in names:
            key = normalize(name)
            if key not in seen:
                by_group[group].append(Food(name, group, 0.5, None, profile.currency, "kg", 0,
                                            0.9 if key in {normalize(x) for x in profile.preferred_foods} else 0.5))
    for group in GROUPS:
        by_group[group].sort(key=lambda f: (0.35 * f.availability + 0.2 * f.preferred + (0.3 / (1 + f.price) if f.price is not None else 0.0)), reverse=True)
    return by_group


def adult_equivalents(household: Mapping[str, int]) -> float:
    return max(0.45, sum(ADULT_EQUIVALENTS.get(k, 0.9) * int(v) for k, v in household.items()))


def apply_discovery_signals(profile: LocationProfile, discovery: Mapping[str, object]) -> LocationProfile:
    """Add user-accepted OSM food signals to the active location profile."""
    signals = discovery.get("food_signals", {})
    for group, names in signals.items():
        if group in GROUPS and isinstance(names, list) and names:
            profile.foods[group] = [str(name) for name in names]
    return profile


def apply_confirmed_foods(profile: LocationProfile, values: Sequence[str]) -> LocationProfile:
    """Apply checkpoint entries formatted as group=item1,item2."""
    for value in values:
        if "=" not in value:
            continue
        group, names = value.split("=", 1)
        group = normalize(group)
        if group in GROUPS:
            profile.foods[group] = [name.strip() for name in names.split(",") if name.strip()]
    return profile


def collect_local_confirmation(profile: LocationProfile, missing_groups: Sequence[str], interactive: bool) -> List[str]:
    """Ask a user to consult a local person when discovery data is incomplete."""
    if not missing_groups or not interactive:
        return list(missing_groups)
    print("Ask a trusted local person what foods are normally available in this location.")
    print("Enter foods by group, separated by commas. Press Enter if the group is still unknown.")
    for group in missing_groups:
        value = input(f"Local foods for {group}: ").strip()
        if value:
            profile.foods[group] = [name.strip() for name in value.split(",") if name.strip()]
    return [group for group in GROUPS if not profile.foods[group]]


def _purchase_quantity(group: str, unit: str, adult_equivalents_value: float) -> float:
    base = WEEKLY_PURCHASE_UNITS_PER_AE[group] * adult_equivalents_value
    normalized_unit = normalize(unit)
    if normalized_unit in {"g", "gram", "grams"}:
        return round(base * 1000, 2)
    if normalized_unit in {"dozen", "dozens"}:
        return round(1.0 * adult_equivalents_value if group == "animal_protein" else base, 2)
    if normalized_unit in {"each", "piece", "pieces"}:
        return round(14.0 * adult_equivalents_value if group in {"animal_protein", "fruit"} else base, 2)
    return round(base, 2)


def estimate_budget(market_foods: Mapping[str, Food], adult_equivalents_value: float) -> dict:
    """Estimate weekly food cost using observed prices and transparent purchase heuristics."""
    line_items = []
    totals = defaultdict(float)
    for food in market_foods.values():
        if food.price is None or not food.currency:
            continue
        quantity = _purchase_quantity(food.group, food.unit, adult_equivalents_value)
        estimated_cost = round(food.price * quantity, 2)
        totals[food.currency] += estimated_cost
        line_items.append({
            "commodity": food.name,
            "food_group": food.group,
            "quantity": quantity,
            "unit": food.unit,
            "unit_price": food.price,
            "currency": food.currency,
            "estimated_cost": estimated_cost,
            "markets": food.markets,
            "provisional": food.markets < 5,
            "availability": round(food.availability, 2),
        })
    priced_commodities = {item["commodity"] for item in line_items}
    return {
        "adult_equivalents": round(adult_equivalents_value, 2),
        "line_items": line_items,
        "totals_by_currency": {currency: round(total, 2) for currency, total in totals.items()},
        "priced_commodities": len(priced_commodities),
        "price_coverage": (
            "unavailable" if not market_foods
            else "complete" if len(priced_commodities) >= len(market_foods)
            else "partial"
        ),
        "method_note": "Rough weekly purchasing estimate; verify local serving sizes, package sizes, and current prices before spending.",
    }


def plan_week(profile: LocationProfile, household: Mapping[str, int], rows: Sequence[dict]) -> dict:
    market_foods = harmonise_market_rows(rows)
    foods = resolve_foods(profile, market_foods)
    ae = adult_equivalents(household)
    market_groups = sorted({food.group for food in market_foods.values()})
    fallback_groups = [group for group in GROUPS if not any(food.markets for food in foods[group])]
    assumptions = list(profile.assumptions)
    if fallback_groups:
        assumptions.append("No market observations supplied for: " + ", ".join(fallback_groups) + "; generic or profile foods are used for those groups.")
    currency = profile.currency or next((food.currency for food in market_foods.values() if food.currency), "")
    market_prices = {
        food.name: {
            "price": food.price,
            "currency": food.currency,
            "unit": food.unit,
            "markets": food.markets,
            "provisional": food.markets < 5,
            "availability": round(food.availability, 2),
            "source": food.source,
        }
        for food in market_foods.values()
    }
    days = []
    for day_index in range(7):
        staple = foods["staple"][day_index % len(foods["staple"])]
        legume = foods["legume"][day_index % len(foods["legume"])]
        vegetable = foods["vegetable"][day_index % len(foods["vegetable"])]
        fruit = foods["fruit"][day_index % len(foods["fruit"])]
        protein = foods["animal_protein"][day_index % len(foods["animal_protein"])]
        fat = foods["healthy_fat"][day_index % len(foods["healthy_fat"])]
        days.append({
            "day": day_index + 1,
            "breakfast": f"{staple.name} with {protein.name}",
            "lunch": f"{staple.name}, {legume.name}, and {vegetable.name}",
            "dinner": f"{staple.name} with {protein.name} and {vegetable.name}",
            "snack": fruit.name,
            "fat": fat.name,
            "water": "Offer safe water throughout the day.",
            "portion_factor_adult_equivalents": round(ae, 2),
            "rationale": "Combines an energy food, protein, and produce; rotate foods to support dietary diversity.",
            "substitutions": [f"Replace {vegetable.name} with another affordable vegetable.", f"Replace {protein.name} with another protein food."],
        })
    return {"location": profile.location, "country": profile.country, "currency": currency,
            "adult_equivalents": round(ae, 2), "assumptions": assumptions,
            "data_coverage": {"market_food_groups": market_groups, "fallback_food_groups": fallback_groups,
                              "market_commodities": sorted(market_foods)},
            "market_prices": market_prices,
            "budget_estimate": estimate_budget(market_foods, ae),
            "seasonal_notes": profile.seasonal_notes, "days": days}


def verification_checkpoint(profile: LocationProfile, discovery: Mapping[str, object]) -> dict:
    signals = discovery.get("food_signals", {})
    return {
        group: {
            "discovered_signals": list(signals.get(group, [])),
            "confirmed_foods": list(profile.foods.get(group, [])),
            "status": "confirmed" if profile.foods.get(group) else "needs_confirmation",
        }
        for group in GROUPS
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a location-adaptive weekly meal plan")
    parser.add_argument("--location", help="City, district, or address to search")
    parser.add_argument("--profile")
    parser.add_argument("--market-data")
    parser.add_argument("--offline", action="store_true", help="Do not query OpenStreetMap")
    parser.add_argument("--radius-km", type=float, default=5.0)
    parser.add_argument("--confirm-discovery", action="store_true", help="Accept the displayed OSM checkpoint")
    parser.add_argument("--confirmed-foods", action="append", default=[], help="Checkpoint input: group=item1,item2")
    parser.add_argument("--household", nargs="*", default=["adult_man:1", "adult_woman:1", "child_2_5:1"])
    args = parser.parse_args()
    location = args.location or input("Enter your location: ").strip()
    if not location:
        parser.error("A location is required")
    household = {item.split(":", 1)[0]: int(item.split(":", 1)[1]) for item in args.household if ":" in item}
    discovery = None
    plan_status = "market_data_or_profile"
    if not args.offline and not args.market_data:
        search_radii = [args.radius_km]
        if args.radius_km < 25:
            search_radii.append(25.0)
        for search_radius in search_radii:
            discovery = discover_location(location, radius_km=search_radius)
            if discovery.get("provider_errors") or discovery.get("nearby_food_places"):
                break
        print(json.dumps({
            "resolved_location": discovery["resolved_location"],
            "search_radius_km": discovery["radius_km"],
            "search_attempts_km": search_radii,
            "nearby_food_places": discovery["nearby_food_places"][:20],
            "food_signals": discovery["food_signals"],
            "country": discovery["country"],
            "country_code": discovery["country_code"],
            "currencies": discovery["currencies"],
            "provider_errors": discovery["provider_errors"],
            "limitations": discovery["limitations"],
            "attribution": discovery["attribution"],
        }, indent=2, ensure_ascii=False))
        if discovery.get("provider_errors"):
            print("Location was resolved, but the nearby-place provider is temporarily unavailable.")
            print("The planner will continue with local confirmation or clearly labelled fallback foods.")
            plan_status = "provider_unavailable"
        if not discovery.get("nearby_food_places"):
            print("No mapped food-access places were found within the searched area.")
            print("The planner will continue after asking for local food confirmation.")
            plan_status = "no_mapped_food_places"
        elif not discovery.get("provider_errors"):
            confirmed = args.confirm_discovery or input("Verify these nearby food sources and continue? [y/N] ").strip().lower() in {"y", "yes"}
            if not confirmed:
                print("Discovery was not confirmed; the planner will use local confirmation or clearly labelled fallback foods.")
                plan_status = "discovery_not_confirmed"
    profile = load_profile(args.profile, location)
    if not discovery and not args.market_data:
        plan_status = "profile_fallback" if args.profile else "generic_fallback"
    if discovery:
        profile.country = discovery.get("country", "") or profile.country
        currencies = discovery.get("currencies", [])
        if not profile.currency and len(currencies) == 1:
            profile.currency = currencies[0]
        profile = apply_discovery_signals(profile, discovery)
        profile = apply_confirmed_foods(profile, args.confirmed_foods)
        missing_groups = [group for group in GROUPS if not profile.foods[group]]
        missing_groups = collect_local_confirmation(profile, missing_groups, sys.stdin.isatty())
        if missing_groups:
            plan_status = "partial_local_confirmation_fallback"
        else:
            plan_status = "locally_confirmed"
    rows = read_market_rows(args.market_data)
    result = plan_week(profile, household, rows)
    result["plan_status"] = plan_status
    if plan_status == "partial_local_confirmation_fallback":
        result["assumptions"].append("Some food groups were not confirmed by a local person; fallback foods are included and should be verified before purchase.")
    if discovery:
        result["location_discovery"] = discovery
        result["verification_checkpoint"] = verification_checkpoint(profile, discovery)
        result["assumptions"].append("Food availability signals were discovered from OpenStreetMap and accepted at the user checkpoint; confirm inventory locally.")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
