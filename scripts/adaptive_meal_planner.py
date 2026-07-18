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
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence


GROUPS = ("staple", "legume", "vegetable", "fruit", "animal_protein", "healthy_fat")
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
    foods = {g: list(raw.get("foods", {}).get(g, DEFAULT_PROFILE[g])) for g in GROUPS}
    return LocationProfile(
        location=raw.get("location", location), country=raw.get("country", ""),
        currency=raw.get("currency", ""), languages=list(raw.get("languages", ["English"])),
        foods=foods, preferred_foods=list(raw.get("preferred_foods", [])),
        local_names=dict(raw.get("local_names", {})), seasonal_notes=raw.get("seasonal_notes", ""),
        assumptions=[] if path else ["No local profile supplied; generic food-group defaults are being used."],
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


def plan_week(profile: LocationProfile, household: Mapping[str, int], rows: Sequence[dict]) -> dict:
    market_foods = harmonise_market_rows(rows)
    foods = resolve_foods(profile, market_foods)
    ae = adult_equivalents(household)
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
    return {"location": profile.location, "country": profile.country, "currency": profile.currency,
            "adult_equivalents": round(ae, 2), "assumptions": profile.assumptions,
            "seasonal_notes": profile.seasonal_notes, "days": days}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a location-adaptive weekly meal plan")
    parser.add_argument("--location", required=True)
    parser.add_argument("--profile")
    parser.add_argument("--market-data")
    parser.add_argument("--household", nargs="*", default=["adult_man:1", "adult_woman:1", "child_2_5:1"])
    args = parser.parse_args()
    household = {item.split(":", 1)[0]: int(item.split(":", 1)[1]) for item in args.household if ":" in item}
    profile = load_profile(args.profile, args.location)
    print(json.dumps(plan_week(profile, household, read_market_rows(args.market_data)), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
