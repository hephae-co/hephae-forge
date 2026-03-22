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
 * Hook that uses Google Maps JS API (client-side) for autocomplete.
 * Uses AutocompleteService for suggestions + PlacesService for details.
 * No server-side proxy needed.
 */
export function usePlacesAutocomplete() {
  const [predictions, setPredictions] = useState<PlacePrediction[]>([]);
  const [isReady, setIsReady] = useState(false);
  const serviceRef = useRef<google.maps.places.AutocompleteService | null>(null);
  const sessionTokenRef = useRef<google.maps.places.AutocompleteSessionToken | null>(null);
  const dummyDivRef = useRef<HTMLDivElement | null>(null);

  // Initialize when Google Maps API loads
  useEffect(() => {
    const init = () => {
      if (window.google?.maps?.places?.AutocompleteService) {
        serviceRef.current = new google.maps.places.AutocompleteService();
        sessionTokenRef.current = new google.maps.places.AutocompleteSessionToken();
        // Create a hidden div for PlacesService (it needs a DOM element)
        if (!dummyDivRef.current) {
          dummyDivRef.current = document.createElement('div');
        }
        setIsReady(true);
        return;
      }
      // Retry until API loads
      setTimeout(init, 500);
    };
    init();
  }, []);

  const fetchPredictions = useCallback((input: string) => {
    if (!serviceRef.current || input.trim().length < 3) {
      setPredictions([]);
      return;
    }

    serviceRef.current.getPlacePredictions(
      {
        input: input.trim(),
        componentRestrictions: { country: 'us' },
        sessionToken: sessionTokenRef.current!,
      },
      (results, status) => {
        if (status === google.maps.places.PlacesServiceStatus.OK && results) {
          setPredictions(
            results.slice(0, 5).map((r) => ({
              placeId: r.place_id,
              mainText: r.structured_formatting.main_text,
              secondaryText: r.structured_formatting.secondary_text || '',
              description: r.description,
            }))
          );
        } else {
          setPredictions([]);
        }
      }
    );
  }, []);

  const getPlaceDetails = useCallback(
    (placeId: string): Promise<PlaceDetails | null> => {
      return new Promise((resolve) => {
        if (!dummyDivRef.current) {
          resolve(null);
          return;
        }

        const service = new google.maps.places.PlacesService(dummyDivRef.current);
        service.getDetails(
          {
            placeId,
            fields: [
              'name',
              'formatted_address',
              'geometry',
              'address_components',
              'website',
              'international_phone_number',
              'rating',
            ],
            sessionToken: sessionTokenRef.current!,
          },
          (place, status) => {
            // Reset session token after details call (as per Google billing best practice)
            sessionTokenRef.current = new google.maps.places.AutocompleteSessionToken();

            if (status !== google.maps.places.PlacesServiceStatus.OK || !place) {
              resolve(null);
              return;
            }

            let zipCode: string | null = null;
            for (const comp of place.address_components || []) {
              if (comp.types?.includes('postal_code')) {
                zipCode = comp.short_name || comp.long_name || null;
                break;
              }
            }

            resolve({
              name: place.name || '',
              address: place.formatted_address || '',
              zipCode,
              coordinates: place.geometry?.location
                ? {
                    lat: place.geometry.location.lat(),
                    lng: place.geometry.location.lng(),
                  }
                : null,
              officialUrl: place.website || undefined,
              phone: place.international_phone_number || undefined,
              rating: place.rating || undefined,
            });
          }
        );
      });
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
