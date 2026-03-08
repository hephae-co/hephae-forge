"""GET /api/places/autocomplete + /api/places/details — Google Places API proxy."""

from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/places/autocomplete")
async def places_autocomplete(input: str = Query(...), sessiontoken: str = Query("")):
    try:
        api_key = os.environ.get("NEXT_PUBLIC_GOOGLE_MAPS_API_KEY") or os.environ.get("GOOGLE_MAPS_API_KEY")
        if not api_key:
            return JSONResponse({"error": "Google Maps API key not configured"}, status_code=500)

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(
                "https://places.googleapis.com/v1/places:autocomplete",
                json={
                    "input": input,
                    "includedPrimaryTypes": ["restaurant", "cafe", "bakery", "bar", "meal_takeaway"],
                    "includedRegionCodes": ["us"],
                    "sessionToken": sessiontoken,
                },
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": api_key,
                },
            )

        if res.status_code != 200:
            return JSONResponse({"error": f"Places API error: {res.status_code}"}, status_code=res.status_code)

        data = res.json()
        suggestions = []
        for s in (data.get("suggestions") or [])[:5]:
            pred = s.get("placePrediction", {})
            structured = pred.get("structuredFormat", {})
            suggestions.append({
                "mainText": structured.get("mainText", {}).get("text", ""),
                "secondaryText": structured.get("secondaryText", {}).get("text", ""),
                "placeId": pred.get("placeId", ""),
            })

        return JSONResponse({"suggestions": suggestions})

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
