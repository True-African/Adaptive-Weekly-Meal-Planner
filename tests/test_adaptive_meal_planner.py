import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from adaptive_meal_planner import (  # noqa: E402
    adult_equivalents,
    apply_discovery_signals,
    harmonise_market_rows,
    load_profile,
    plan_week,
)


class PlannerTests(unittest.TestCase):
    def test_household_scaling_is_transparent(self):
        self.assertEqual(adult_equivalents({"adult_man": 1, "adult_woman": 2, "child_2_5": 1}), 3.35)


    def test_market_harmonisation_keeps_currency_and_market_count(self):
        rows = [
            {"date": "2026-01-01", "market": f"m{i}", "commodity": "beans",
             "food_group": "legume", "unit": "kg", "price": str(1 + i / 10),
             "currency": "USD", "availability_score": "0.9"}
            for i in range(5)
        ]
        beans = harmonise_market_rows(rows)["beans"]
        self.assertEqual(beans.markets, 5)
        self.assertEqual(beans.currency, "USD")
        self.assertIsNotNone(beans.price)


    def test_plan_uses_profile_and_has_seven_days(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            profile_path = Path(directory) / "profile.json"
            profile_path.write_text(
                '{"location":"Test town","currency":"EUR","foods":{"staple":["bread"],'
                '"legume":["lentils"],"vegetable":["carrot"],"fruit":["apple"],'
                '"animal_protein":["egg"],"healthy_fat":["olive oil"]}}',
                encoding="utf-8",
            )
            plan = plan_week(load_profile(str(profile_path), "ignored"), {"adult_woman": 1}, [])
        self.assertEqual(len(plan["days"]), 7)
        self.assertEqual(plan["days"][0]["breakfast"], "bread with egg")

    def test_market_food_group_does_not_add_generic_foods(self):
        rows = [
            {"date": "2026-01-01", "market": f"m{i}", "commodity": "rice",
             "food_group": "staple", "unit": "kg", "price": "1.0",
             "currency": "USD", "availability_score": "0.9"}
            for i in range(5)
        ]
        plan = plan_week(load_profile(None, "Test town"), {"adult_woman": 1}, rows)
        self.assertTrue(all("rice" in day["breakfast"] for day in plan["days"]))

    def test_verified_discovery_signals_update_profile(self):
        profile = load_profile(None, "Test town")
        apply_discovery_signals(profile, {"food_signals": {"staple": ["bread"], "fruit": ["fruit"]}})
        self.assertEqual(profile.foods["staple"], ["bread"])
        self.assertEqual(profile.foods["fruit"], ["fruit"])
