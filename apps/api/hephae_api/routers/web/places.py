"""GET /api/places/autocomplete + /api/places/details + /api/places/validate-zipcode — Google Places API proxy."""

from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from hephae_db.firestore.registered_zipcodes import get_registered_zipcode

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/places/autocomplete")
async def places_autocomplete(input: str = Query(...), sessiontoken: str = Query("")):
    try:
        api_key = os.environ.get("NEXT_PUBLIC_GOOGLE_MAPS_API_KEY") or os.environ.get("GOOGLE_MAPS_API_KEY")
        if not api_key:
            return JSONResponse({"error": "Google Maps API key not configured"}, status_code=500)

        async with httpx.AsyncClient(timeout=10.0) as client:
            body: dict = {
                    "input": input,
                    "includedPrimaryTypes": [
                        "restaurant", "cafe", "bakery", "bar", "meal_takeaway",
                        "meal_delivery", "grocery_store", "supermarket",
                        "liquor_store", "convenience_store",
                    ],
                    "includedRegionCodes": ["us"],
                }
            if sessiontoken:
                body["sessionToken"] = sessiontoken

            res = await client.post(
                "https://places.googleapis.com/v1/places:autocomplete",
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": api_key,
                },
            )

        if res.status_code != 200:
            logger.warning(f"[API/Places] Autocomplete {res.status_code}: {res.text[:300]}")
            return JSONResponse({"error": f"Places API error: {res.status_code}"}, status_code=res.status_code)

        data = res.json()
        predictions = []
        for s in (data.get("suggestions") or [])[:5]:
            pred = s.get("placePrediction", {})
            structured = pred.get("structuredFormat", {})
            main = structured.get("mainText", {}).get("text", "")
            secondary = structured.get("secondaryText", {}).get("text", "")
            predictions.append({
                "mainText": main,
                "secondaryText": secondary,
                "description": f"{main}, {secondary}" if secondary else main,
                "placeId": pred.get("placeId", ""),
            })

        return JSONResponse({"predictions": predictions})

    except Exception as e:
        logger.error(f"[API/Places] Autocomplete failed: {e}")
        return JSONResponse({"error": "Internal Server Error"}, status_code=500)


@router.get("/places/details")
async def places_details(placeId: str = Query(...), sessiontoken: str = Query("")):
    try:
        api_key = os.environ.get("NEXT_PUBLIC_GOOGLE_MAPS_API_KEY") or os.environ.get("GOOGLE_MAPS_API_KEY")
        if not api_key:
            return JSONResponse({"error": "Google Maps API key not configured"}, status_code=500)

        fields = "id,displayName,formattedAddress,location,addressComponents,internationalPhoneNumber,regularOpeningHours,rating,websiteUri"

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                f"https://places.googleapis.com/v1/places/{placeId}",
                params={"sessionToken": sessiontoken},
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": api_key,
                    "X-Goog-FieldMask": fields,
                },
            )

        if res.status_code != 200:
            return JSONResponse({"error": f"Places API error: {res.status_code}"}, status_code=res.status_code)

        data = res.json()
        address_components = data.get("addressComponents") or []
        zip_code = None
        for comp in address_components:
            types = comp.get("types") or []
            if "postal_code" in types:
                zip_code = comp.get("shortText") or comp.get("longText")
                break

        location = data.get("location") or {}

        return JSONResponse({
            "name": (data.get("displayName") or {}).get("text", ""),
            "address": data.get("formattedAddress", ""),
            "officialUrl": data.get("websiteUri"),
            "coordinates": {"lat": location.get("latitude"), "lng": location.get("longitude")},
            "zipCode": zip_code,
            "phone": data.get("internationalPhoneNumber"),
            "hours": data.get("regularOpeningHours"),
            "rating": data.get("rating"),
        })

    except Exception as e:
        logger.error(f"[API/Places] Details failed: {e}")
        return JSONResponse({"error": "Internal Server Error"}, status_code=500)


@router.get("/places/validate-zipcode")
async def validate_zipcode(zipCode: str = Query(...)):
    """Check zipcode coverage tier.

    All valid US zip codes are supported (national industry data available for all).
    Zips in registered_zipcodes with status=active additionally have ultralocal
    weekly pulse data (hyperlocal events, competitors, neighborhood intelligence).
    """
    import re as _re
    if not _re.match(r"^\d{5}$", zipCode):
        return JSONResponse({"supported": False, "ultralocal": False})

    try:
        doc = await get_registered_zipcode(zipCode)
        ultralocal = bool(doc and doc.get("status") == "active")
        city = doc.get("city", "") if doc else ""
        state = doc.get("state", "") if doc else ""
        last_headline = doc.get("lastPulseHeadline") if doc else None

        return JSONResponse({
            "supported": True,
            "ultralocal": ultralocal,
            "city": city,
            "state": state,
            "lastPulseHeadline": last_headline,
        })
    except Exception as e:
        logger.error(f"[API/Places] Validate zipcode failed: {e}")
        # Fail open — always supported, just not ultralocal
        return JSONResponse({"supported": True, "ultralocal": False})
