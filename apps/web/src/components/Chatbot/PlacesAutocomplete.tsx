"use client";

import React, { useRef, useEffect, useCallback } from 'react';

interface PlaceResult {
  name: string;
  address: string;
  zipCode: string | null;
  coordinates: { lat: number; lng: number } | null;
  officialUrl?: string;
  phone?: string;
  rating?: number;
}

interface PlacesAutocompleteProps {
  onPlaceSelect: (place: PlaceResult) => void;
  onInputChange?: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  isCentered?: boolean;
}

/**
 * Google Maps PlaceAutocompleteElement wrapper for React.
 * Uses the new Places API (not legacy) per:
 * https://developers.google.com/maps/documentation/javascript/legacy/places-migration-ac-widget
 */
export default function PlacesAutocomplete({
  onPlaceSelect,
  onInputChange,
  placeholder = "Search for a business by name or city...",
  disabled = false,
  className = "",
  isCentered = false,
}: PlacesAutocompleteProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const elementRef = useRef<google.maps.places.PlaceAutocompleteElement | null>(null);
  const initRef = useRef(false);

  const handleSelect = useCallback(async (e: Event) => {
    // The gmp-select event has placePrediction on it but types may lag behind
    const event = e as any;
    const place = event.placePrediction?.toPlace?.();
    if (!place) return;

    try {
      await place.fetchFields({
        fields: ['displayName', 'formattedAddress', 'location', 'addressComponents', 'websiteURI', 'internationalPhoneNumber', 'rating'],
      });

      let zipCode: string | null = null;
      for (const comp of place.addressComponents || []) {
        if (comp.types?.includes('postal_code')) {
          zipCode = comp.shortText || comp.longText || null;
          break;
        }
      }

      onPlaceSelect({
        name: place.displayName || '',
        address: place.formattedAddress || '',
        zipCode,
        coordinates: place.location
          ? { lat: place.location.lat(), lng: place.location.lng() }
          : null,
        officialUrl: (place as any).websiteURI || undefined,
        phone: (place as any).internationalPhoneNumber || undefined,
        rating: place.rating || undefined,
      });
    } catch (err) {
      console.error('[PlacesAutocomplete] fetchFields failed:', err);
    }
  }, [onPlaceSelect]);

  useEffect(() => {
    if (initRef.current) return;

    const init = async () => {
      // Wait for Google Maps API to load
      if (!window.google?.maps?.places) {
        // Retry after a short delay
        const timer = setTimeout(init, 500);
        return () => clearTimeout(timer);
      }

      initRef.current = true;

      const autocomplete = new (google.maps.places as any).PlaceAutocompleteElement({
        includedRegionCodes: ['us'],
        includedPrimaryTypes: [
          'restaurant', 'cafe', 'bakery', 'bar', 'meal_takeaway',
        ],
      });

      // Style the inner input to match our design
      autocomplete.setAttribute('style', `
        width: 100%;
        --gmpx-color-surface: transparent;
        --gmpx-color-on-surface: #111827;
        --gmpx-color-on-surface-variant: #9ca3af;
        --gmpx-color-primary: #6366f1;
        --gmpx-font-family-base: inherit;
        --gmpx-font-family-headings: inherit;
        --gmpx-font-size-base: ${isCentered ? '1.125rem' : '0.875rem'};
      `);

      autocomplete.addEventListener('gmp-select', handleSelect);

      if (containerRef.current) {
        containerRef.current.innerHTML = '';
        containerRef.current.appendChild(autocomplete);
      }

      elementRef.current = autocomplete;
    };

    init();

    return () => {
      if (elementRef.current) {
        elementRef.current.removeEventListener('gmp-select', handleSelect);
      }
    };
  }, [handleSelect, isCentered]);

  // Handle disabled state
  useEffect(() => {
    if (elementRef.current) {
      if (disabled) {
        elementRef.current.setAttribute('disabled', '');
      } else {
        elementRef.current.removeAttribute('disabled');
      }
    }
  }, [disabled]);

  return (
    <div
      ref={containerRef}
      className={`places-autocomplete-container ${className}`}
    />
  );
}
