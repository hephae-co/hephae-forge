"""OpenStreetMap business discovery via Nominatim geocoding + Overpass API."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_USER_AGENT = "hephae-admin/1.0 (business-discovery)"
_SEARCH_RADIUS_M = 2000

_nominatim_lock = asyncio.Lock()


@dataclass
class OsmBusiness:
    name: str
    category: str
    address: str
    phone: str
    website: str


_CATEGORY_TO_OSM: dict[str, tuple[str, str]] = {
    # amenity-based
    "restaurant": ("amenity", "restaurant"),
    "restaurants": ("amenity", "restaurant"),
    "cafe": ("amenity", "cafe"),
    "coffee shop": ("amenity", "cafe"),
    "coffee shops": ("amenity", "cafe"),
    "bar": ("amenity", "bar"),
    "pharmacy": ("amenity", "pharmacy"),
    "dentist": ("amenity", "dentist"),
    "dentists": ("amenity", "dentist"),
    "bakery": ("amenity", "bakery"),
    "bakeries": ("amenity", "bakery"),
    "gym": ("amenity", "gym"),
    "gyms": ("amenity", "gym"),
    "auto repair": ("shop", "car_repair"),
    "spa": ("amenity", "spa"),
    "spas": ("amenity", "spa"),
    # shop-based
    "salon": ("shop", "hairdresser"),
    "hair salon": ("shop", "hairdresser"),
    "hair salons": ("shop", "hairdresser"),
    "barbershop": ("shop", "hairdresser"),
    "barbershops": ("shop", "hairdresser"),
    "nail salon": ("shop", "beauty"),
    "nail salons": ("shop", "beauty"),
    "boutique": ("shop", "boutique"),
    "supermarket": ("shop", "supermarket"),
    "florist": ("shop", "florist"),
    "florists": ("shop", "florist"),
    "pet groomer": ("shop", "pet_grooming"),
    "pet groomers": ("shop", "pet_grooming"),
    "dry cleaner": ("shop", "dry_cleaning"),
    "dry cleaners": ("shop", "dry_cleaning"),
    "deli": ("shop", "deli"),
    "delis": ("shop", "deli"),
    "pizza shop": ("amenity", "restaurant"),
    "pizza shops": ("amenity", "restaurant"),
}


def _build_overpass_query(lat: float, lng: float, category: str | None = None, radius: int = _SEARCH_RADIUS_M) -> str:
    if category:
        cat = category.lower().strip()
        osm_mapping = _CATEGORY_TO_OSM.get(cat)
        if osm_mapping:
            osm_key, osm_val = osm_mapping
            query_filter = f'["{osm_key}"="{osm_val}"]'
        else:
            # Fallback: fuzzy name match
            query_filter = f'["name"~"{cat}",i]'
            
        return f"""
[out:json][timeout:25];
(
  node["name"]{query_filter}(around:{radius},{lat},{lng});
  way["name"]{query_filter}(around:{radius},{lat},{lng});
);
out center tags 50;
"""

    return f"""
[out:json][timeout:25];
(
  node["name"]["amenity"~"restaurant|cafe|bar|fast_food|pharmacy|bank|dentist|veterinary|clinic|doctors|pub|cinema|library|fuel|car_repair|car_wash"](around:{radius},{lat},{lng});
  node["name"]["shop"](around:{radius},{lat},{lng});
  node["name"]["craft"](around:{radius},{lat},{lng});
  node["name"]["office"](around:{radius},{lat},{lng});
  way["name"]["amenity"~"restaurant|cafe|bar|fast_food|pharmacy|bank|dentist|veterinary|clinic|doctors|pub|cinema|library|fuel|car_repair|car_wash"](around:{radius},{lat},{lng});
  way["name"]["shop"](around:{radius},{lat},{lng});
);
out center tags 50;
"""


def _parse_address(tags: dict[str, str]) -> str:
    parts = []
    housenumber = tags.get("addr:housenumber", "")
    street = tags.get("addr:street", "")
    if housenumber and street:
        parts.append(f"{housenumber} {street}")
    elif street:
        parts.append(street)
    city = tags.get("addr:city", "")
    if city:
        parts.append(city)
    state = tags.get("addr:state", "")
    if state:
        parts.append(state)
    postcode = tags.get("addr:postcode", "")
    if postcode:
        parts.append(postcode)
    return ", ".join(parts)


def _parse_category(tags: dict[str, str]) -> str:
    for key in ("amenity", "shop", "craft", "office"):
        val = tags.get(key)
        if val:
            return val.replace("_", " ")
    return "business"


async def _geocode_zipcode(zip_code: str, client: httpx.AsyncClient) -> tuple[float, float] | None:
    async with _nominatim_lock:
        resp = await client.get(
            _NOMINATIM_URL,
            params={
                "q": f"{zip_code}, United States",
                "format": "json",
                "limit": 1,
                "countrycodes": "us",
            },
            headers={"User-Agent": _USER_AGENT},
        )
    if resp.status_code != 200:
        return None
    data = resp.json()
    if not data:
        return None
    return float(data[0]["lat"]), float(data[0]["lon"])


async def _query_overpass(lat: float, lng: float, client: httpx.AsyncClient, category: str | None = None) -> list[dict]:
    query = _build_overpass_query(lat, lng, category=category)
    resp = await client.post(
        _OVERPASS_URL,
        data={"data": query},
        headers={"User-Agent": _USER_AGENT},
    )
    if resp.status_code != 200:
        return []
    return resp.json().get("elements", [])


async def discover_businesses(zip_code: str, category: str | None = None) -> list[OsmBusiness]:
    """Discover businesses in a zip code via OpenStreetMap."""
    async with httpx.AsyncClient(timeout=30) as client:
        coords = await _geocode_zipcode(zip_code, client)
        if not coords:
            return []

        lat, lng = coords
        logger.info(f"[OSM] Geocoded {zip_code} → ({lat:.4f}, {lng:.4f}), querying Overpass ({category or 'all'})...")
        elements = await _query_overpass(lat, lng, client, category=category)

    results: list[OsmBusiness] = []
    seen_names: set[str] = set()

    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name", "").strip()
        if not name:
            continue
        name_key = name.lower()
        if name_key in seen_names:
            continue
        seen_names.add(name_key)

        results.append(
            OsmBusiness(
                name=name,
                category=_parse_category(tags),
                address=_parse_address(tags),
                phone=tags.get("phone", ""),
                website=tags.get("website", ""),
            )
        )

    logger.info(f"[OSM] Found {len(results)} businesses in {zip_code}")
    return results
