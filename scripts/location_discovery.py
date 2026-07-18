"""End-user location discovery through OpenStreetMap public services.

OSM places are evidence of nearby food access, not a complete inventory or
price feed. The caller must show the returned places to the user for review.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_FALLBACK_URL = "https://overpass.kumi.systems/api/interpreter"
OSM_ATTRIBUTION = "OpenStreetMap contributors, ODbL 1.0"

SHOP_SIGNALS = {
    "bakery": {"staple": ["bread"]},
    "butcher": {"animal_protein": ["meat"]},
    "seafood": {"animal_protein": ["fish"]},
    "dairy": {"animal_protein": ["milk"]},
    "greengrocer": {"vegetable": ["vegetables"], "fruit": ["fruit"]},
    "farm": {"vegetable": ["seasonal farm produce"], "fruit": ["seasonal farm produce"]},
}


def _request_json(url: str, params: Dict[str, str], user_agent: str) -> dict:
    request = Request(
        f"{url}?{urlencode(params)}",
        headers={"User-Agent": user_agent, "Accept": "application/json"},
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _cache_file(location: str, radius_km: float, cache_dir: Optional[str]) -> Optional[Path]:
    if not cache_dir:
        return None
    key = hashlib.sha256((f"v3:{location.strip().lower()}:{radius_km}").encode("utf-8")).hexdigest()[:20]
    path = Path(cache_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{key}.json"


def _overpass_query(lat: str, lon: str, radius_m: int) -> str:
    return f"""[out:json][timeout:25];
(
  nwr(around:{radius_m},{lat},{lon})[amenity=marketplace];
  nwr(around:{radius_m},{lat},{lon})[shop~\"^(food|supermarket|greengrocer|farm|seafood|butcher|dairy|bakery)$\"];
  nwr(around:{radius_m},{lat},{lon})[amenity~\"^(market|food_court)$\"];
);
out center tags;"""


def _place_from_element(element: dict, origin_lat: float, origin_lon: float) -> dict:
    tags = element.get("tags", {})
    center = element.get("center", {})
    latitude = element.get("lat", center.get("lat"))
    longitude = element.get("lon", center.get("lon"))
    distance_km = None
    if latitude is not None and longitude is not None:
        lat1, lon1, lat2, lon2 = map(math.radians, [origin_lat, origin_lon, float(latitude), float(longitude)])
        delta_lat = lat2 - lat1
        delta_lon = lon2 - lon1
        haversine = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
        distance_km = round(6371.0 * 2 * math.asin(math.sqrt(haversine)), 2)
    return {
        "name": tags.get("name") or tags.get("shop") or tags.get("amenity") or "Unnamed food place",
        "type": tags.get("shop") or tags.get("amenity") or "food place",
        "latitude": latitude,
        "longitude": longitude,
        "distance_km": distance_km,
        "opening_hours": tags.get("opening_hours", ""),
        "website": tags.get("website") or tags.get("contact:website", ""),
        "source": "OpenStreetMap",
        "last_checked": datetime.now(timezone.utc).isoformat(),
        "confidence": "place_access_only",
        "inventory_status": "unknown",
        "price_status": "unknown",
        "seasonal_status": "unknown",
    }


def _signals(elements: List[dict]) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    for element in elements:
        tags = element.get("tags", {})
        shop_type = tags.get("shop", "")
        for group, foods in SHOP_SIGNALS.get(shop_type, {}).items():
            result.setdefault(group, [])
            for food in foods:
                if food not in result[group]:
                    result[group].append(food)
    return result


def lookup_currencies(country_code: str, user_agent: str) -> List[str]:
    """Look up ISO currency codes for a resolved country; return [] on failure."""
    if not country_code:
        return []
    sources = (
        (f"https://restcountries.com/v3.1/alpha/{country_code.lower()}", {"fields": "currencies"}),
        (f"https://countries.dev/alpha/{country_code.upper()}", {}),
    )
    for endpoint, params in sources:
        try:
            data = _request_json(endpoint, params, user_agent)
            record = data[0] if isinstance(data, list) else data
            currencies = record.get("currencies") or {}
            if isinstance(currencies, dict) and currencies:
                return sorted(currencies.keys())
            if isinstance(currencies, list) and currencies:
                return sorted(item.get("code", "") for item in currencies if item.get("code"))
        except Exception:
            continue
    return []


def discover_location(
    location: str,
    radius_km: float = 5.0,
    user_agent: str = "AdaptiveWeeklyMealPlanner/0.1 (location discovery)",
    cache_dir: Optional[str] = ".cache/osm",
) -> dict:
    """Resolve a location and discover nearby food-access signals.

    The request is intended for direct end-user searches, not bulk geocoding.
    Cache results and provide a way to replace the public services in deployed
    applications.
    """
    cache = _cache_file(location, radius_km, cache_dir)
    if cache and cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))

    geocoded = _request_json(
        NOMINATIM_URL,
        {"q": location, "format": "jsonv2", "limit": "1", "addressdetails": "1"},
        user_agent,
    )
    if not geocoded:
        raise ValueError(f"Location not found: {location}")
    match = geocoded[0]
    time.sleep(1.0)
    query = _overpass_query(match["lat"], match["lon"], int(radius_km * 1000))
    errors = []
    elements = []
    for endpoint in (OVERPASS_URL, OVERPASS_FALLBACK_URL):
        try:
            overpass = _request_json(endpoint, {"data": query}, user_agent)
            elements = overpass.get("elements", [])
            break
        except Exception as exc:
            errors.append(f"{endpoint}: {exc}")
    result = {
        "query": location,
        "resolved_location": match.get("display_name", location),
        "latitude": float(match["lat"]),
        "longitude": float(match["lon"]),
        "address": match.get("address", {}),
        "country": match.get("address", {}).get("country", ""),
        "country_code": match.get("address", {}).get("country_code", "").upper(),
        "currencies": lookup_currencies(match.get("address", {}).get("country_code", ""), user_agent),
        "radius_km": radius_km,
        "nearby_food_places": [_place_from_element(element, float(match["lat"]), float(match["lon"])) for element in elements],
        "food_signals": _signals(elements),
        "provider_errors": errors if not elements else [],
        "verification_required": True,
        "limitations": [
            "OpenStreetMap place tags do not prove current inventory, prices, or seasonal availability.",
            "Food signals are generated only from explicit shop tags and require user confirmation.",
        ],
        "attribution": OSM_ATTRIBUTION,
    }
    if cache:
        cache.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result
