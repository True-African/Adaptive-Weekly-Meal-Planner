"""Small browser interface for the adaptive weekly meal planner.

Run with: python web_app.py
Then open http://127.0.0.1:8000 in a browser on the same computer.
"""

from __future__ import annotations

import json
import argparse
import socket
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

from adaptive_meal_planner import (  # noqa: E402
    GROUPS,
    apply_discovery_signals,
    load_profile,
    plan_week,
    read_market_rows,
    verification_checkpoint,
)
from location_discovery import discover_location  # noqa: E402


HOUSEHOLD_KEYS = (
    "adult_man",
    "adult_woman",
    "adolescent",
    "child_2_5",
    "child_6_13",
    "older_adult",
)
EXCHANGE_CACHE: dict[tuple[str, str], dict] = {}


def _food_lists(raw_foods: object) -> dict[str, list[str]]:
    if not isinstance(raw_foods, dict):
        return {}
    foods: dict[str, list[str]] = {}
    for group in GROUPS:
        value = raw_foods.get(group, "")
        if isinstance(value, list):
            names = [str(item).strip() for item in value]
        else:
            names = [item.strip() for item in str(value).split(",")]
        foods[group] = [name for name in names if name]
    return foods


def build_plan(payload: dict) -> dict:
    location = str(payload.get("location", "")).strip()
    if not location:
        raise ValueError("Enter a location before generating a plan.")

    household = {
        key: max(0, int(payload.get("household", {}).get(key, 0)))
        for key in HOUSEHOLD_KEYS
    }
    if not any(household.values()):
        household["adult_woman"] = 1

    profile = load_profile(None, location)
    profile.foods.update(_food_lists(payload.get("local_foods")))
    profile.country = str(payload.get("country", "")).strip()
    profile.currency = str(payload.get("currency", "")).strip()
    discovery = None
    plan_status = "generic_fallback"

    if payload.get("discover"):
        radius = float(payload.get("radius_km", 5) or 5)
        discovery = discover_location(location, radius_km=radius)
        profile.country = discovery.get("country", "") or profile.country
        currencies = discovery.get("currencies", [])
        if not profile.currency and len(currencies) == 1:
            profile.currency = currencies[0]
        apply_discovery_signals(profile, discovery)
        plan_status = "locally_confirmed" if all(profile.foods[group] for group in GROUPS) else "partial_local_confirmation_fallback"
    elif any(profile.foods.values()):
        plan_status = "locally_confirmed" if all(profile.foods[group] for group in GROUPS) else "partial_local_confirmation_fallback"

    market_path = payload.get("market_data_path")
    rows = read_market_rows(str(market_path)) if market_path else []
    if payload.get("use_sample_market"):
        rows = read_market_rows(str(ROOT / "examples" / "market_prices_schema.csv"))
        plan_status = "market_data_or_profile"

    result = plan_week(profile, household, rows)
    result["plan_status"] = plan_status
    result["local_currency"] = profile.currency
    market_currencies = {str(row.get("currency", "")).strip() for row in rows if str(row.get("currency", "")).strip()}
    if payload.get("use_sample_market"):
        result["currency_status"] = "demo_prices_not_local"
        result["assumptions"].append("Demonstration prices remain in their source currency and were not converted into the detected local currency.")
    elif profile.currency and market_currencies and profile.currency not in market_currencies:
        result["currency_status"] = "price_currency_mismatch"
        result["assumptions"].append("Market prices use a currency different from the detected local currency; replace them with local observations before budgeting.")
    elif profile.currency:
        result["currency_status"] = "local_currency_identified"
    else:
        result["currency_status"] = "local_currency_unknown"
    result["web_inputs"] = {
        "location": location,
        "household": household,
        "local_foods": profile.foods,
        "used_sample_market": bool(payload.get("use_sample_market")),
    }
    if discovery:
        result["location_discovery"] = discovery
        result["verification_checkpoint"] = verification_checkpoint(profile, discovery)
    return result


def get_exchange_rate(base: str, quote: str) -> dict:
    base = base.upper().strip()
    quote = quote.upper().strip()
    if not base or not quote or len(base) != 3 or len(quote) != 3:
        raise ValueError("Currency codes must be three letters.")
    if base == quote:
        return {"base": base, "quote": quote, "rate": 1.0, "date": None, "source": "same currency"}
    key = (base, quote)
    if key in EXCHANGE_CACHE:
        return EXCHANGE_CACHE[key]
    query = urlencode({"base": base, "quotes": quote})
    request = Request(
        f"https://api.frankfurter.dev/v2/rates?{query}",
        headers={"User-Agent": "AdaptiveWeeklyMealPlanner/1.0"},
    )
    with urlopen(request, timeout=8) as response:
        rates = json.loads(response.read().decode("utf-8"))
    if not rates or not isinstance(rates, list) or "rate" not in rates[0]:
        raise ValueError(f"No exchange rate was returned for {base} to {quote}.")
    result = {"base": base, "quote": quote, "rate": float(rates[0]["rate"]), "date": rates[0].get("date"), "source": "Frankfurter"}
    EXCHANGE_CACHE[key] = result
    return result


class PlannerHandler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            body = (ROOT / "web" / "index.html").read_bytes()
            self._send(200, body, "text/html; charset=utf-8")
            return
        if path == "/health":
            self._send(200, b'{"status":"ok"}', "application/json")
            return
        if path == "/api/exchange":
            params = parse_qs(urlparse(self.path).query)
            rate = get_exchange_rate(params.get("base", [""])[0], params.get("quote", [""])[0])
            self._send(200, json.dumps(rate).encode("utf-8"), "application/json")
            return
        self._send(404, b'{"error":"Not found"}', "application/json")

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/plan":
            self._send(404, b'{"error":"Not found"}', "application/json")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            result = build_plan(payload)
            self._send(200, json.dumps(result, ensure_ascii=False).encode("utf-8"), "application/json")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send(400, json.dumps({"error": str(exc)}).encode("utf-8"), "application/json")
        except Exception as exc:  # Keep implementation errors visible to the UI without a traceback response.
            self._send(500, json.dumps({"error": f"Planner error: {exc}"}).encode("utf-8"), "application/json")

    def log_message(self, format: str, *args: object) -> None:
        print(f"[web] {format % args}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the meal planner browser dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address; use 0.0.0.0 for a trusted local network")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), PlannerHandler)
    display_host = "127.0.0.1" if args.host == "0.0.0.0" else args.host
    print(f"Meal planner dashboard: http://{display_host}:{args.port}")
    if args.host == "0.0.0.0":
        print("Open one of these addresses on another device:")
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if not address.startswith("127."):
                print(f"  http://{address}:{args.port}")
    threading.Timer(0.8, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}")).start()
    print("Press Ctrl+C to stop the local server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()
