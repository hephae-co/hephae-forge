"use client";

import { useState, useRef, useCallback, useEffect } from 'react';

export interface PlacePrediction {
  placeId: string;
  mainText: string;
  secondaryText: string;
  description: string;
}

export interface PlaceDetails {
  name: string;
  address: string;
  zipCode: string | null;
  coordinates: { lat: number; lng: number } | null;
  officialUrl?: string;
  phone?: string;
  rating?: number;
}

/**
 * Hook that uses the NEW Google Places API (not legacy) for autocomplete.
 * Uses AutocompleteSuggestion.fetchAutocompleteSuggestions() + Place.fetchFields().
 */
export function usePlacesAutocomplete() {
  const [predictions, setPredictions] = useState<PlacePrediction[]>([]);
  const [isReady, setIsReady] = useState(false);
  const sessionTokenRef = useRef<any>(null);

  // Wait for Google Maps API to load
  useEffect(() => {
    const init = () => {
      if (window.google?.maps?.places) {
        sessionTokenRef.current = new (google.maps.places as any).AutocompleteSessionToken();
        setIsReady(true);
        return;
      }
      setTimeout(init, 500);
    };
    init();
  }, []);

  const fetchPredictions = useCallback(async (input: string) => {
    if (!isReady || input.trim().length < 3) {
      setPredictions([]);
      return;
    }

    try {
      const request: any = {
        input: input.trim(),
        includedRegionCodes: ['us'],
        sessionToken: sessionTokenRef.current,
      };

      const { suggestions } = await (google.maps.places as any).AutocompleteSuggestion.fetchAutocompleteSuggestions(request);

      const preds: PlacePrediction[] = (suggestions || [])
        .slice(0, 5)
        .map((s: any) => {
          const pred = s.placePrediction;
          if (!pred) return null;
          const main = pred.mainText?.text || pred.text?.text || '';
          const secondary = pred.secondaryText?.text || '';
          return {
            placeId: pred.placeId || pred.place || '',
            mainText: main,
            secondaryText: secondary,
            description: secondary ? `${main}, ${secondary}` : main,
          };
        })
        .filter(Boolean) as PlacePrediction[];

      setPredictions(preds);
    } catch (err) {
      console.error('[PlacesAutocomplete] fetchAutocompleteSuggestions failed:', err);
      setPredictions([]);
    }
  }, [isReady]);

  const getPlaceDetails = useCallback(
    async (placeId: string): Promise<PlaceDetails | null> => {
      try {
        const place = new (google.maps.places as any).Place({ id: placeId });

        await place.fetchFields({
          fields: ['displayName', 'formattedAddress', 'location', 'addressComponents', 'websiteURI', 'internationalPhoneNumber', 'rating'],
        });

        // Reset session token after details fetch (billing best practice)
        sessionTokenRef.current = new (google.maps.places as any).AutocompleteSessionToken();

        let zipCode: string | null = null;
        for (const comp of place.addressComponents || []) {
          if (comp.types?.includes('postal_code')) {
            zipCode = comp.shortText || comp.longText || null;
            break;
          }
        }

        return {
          name: place.displayName || '',
          address: place.formattedAddress || '',
          zipCode,
          coordinates: place.location
            ? { lat: place.location.lat(), lng: place.location.lng() }
            : null,
          officialUrl: place.websiteURI || undefined,
          phone: place.internationalPhoneNumber || undefined,
          rating: place.rating || undefined,
        };
      } catch (err) {
        console.error('[PlacesAutocomplete] Place.fetchFields failed:', err);
        return null;
      }
    },
    []
  );

  const clearPredictions = useCallback(() => setPredictions([]), []);

  return {
    predictions,
    fetchPredictions,
    getPlaceDetails,
    clearPredictions,
    isReady,
  };
}
