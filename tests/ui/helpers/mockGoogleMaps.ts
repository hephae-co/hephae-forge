import { Page } from '@playwright/test';

/**
 * Inject a mock PlaceAutocompleteElement before the page loads.
 * This replaces the Google Maps Web Component so tests can trigger
 * place selection without a real Google Maps API key.
 *
 * Usage:
 *   await mockGoogleMaps(page);
 *   await page.goto('/');
 *   await triggerPlaceSelect(page, { name: 'Arturo\'s Tavern', ... });
 */
export async function mockGoogleMaps(page: Page) {
  await page.addInitScript(() => {
    // Build a minimal mock of google.maps.places.PlaceAutocompleteElement
    class MockPlaceAutocompleteElement extends HTMLElement {
      private _listeners: Map<string, Set<EventListener>> = new Map();

      connectedCallback() {
        this.style.display = 'block';
        this.style.width = '100%';
        // Render a visible text input so tests can interact if needed
        const input = document.createElement('input');
        input.style.cssText = 'width:100%;border:none;outline:none;font-size:inherit;background:transparent;';
        input.placeholder = this.getAttribute('placeholder') || 'Search for a business...';
        this.appendChild(input);
      }

      addEventListener(type: string, listener: EventListener) {
        if (!this._listeners.has(type)) {
          this._listeners.set(type, new Set());
        }
        this._listeners.get(type)!.add(listener);

        // Expose gmp-select listener for test harness
        if (type === 'gmp-select') {
          (window as any).__gmpSelectListeners = (window as any).__gmpSelectListeners || [];
          (window as any).__gmpSelectListeners.push(listener);
        }
      }

      removeEventListener(type: string, listener: EventListener) {
        this._listeners.get(type)?.delete(listener);
      }

      setAttribute(name: string, value: string) {
        super.setAttribute(name, value);
      }
    }

    customElements.define('gmp-place-autocomplete', MockPlaceAutocompleteElement);

    // Expose google.maps.places namespace
    (window as any).google = (window as any).google || {};
    (window as any).google.maps = (window as any).google.maps || {};
    (window as any).google.maps.places = (window as any).google.maps.places || {};
    (window as any).google.maps.places.PlaceAutocompleteElement = MockPlaceAutocompleteElement;

    /**
     * window.__triggerPlaceSelect({ name, address, zipCode, lat, lng, phone?, rating? })
     *
     * Call this from tests to simulate the user picking a place from the autocomplete.
     */
    (window as any).__triggerPlaceSelect = function(placeData: {
      name: string;
      address: string;
      zipCode: string | null;
      lat?: number;
      lng?: number;
      phone?: string;
      rating?: number;
    }) {
      const listeners: EventListener[] = (window as any).__gmpSelectListeners || [];

      // Build a fake gmp-select event matching what PlacesAutocomplete.tsx expects
      const mockPlace = {
        displayName: placeData.name,
        formattedAddress: placeData.address,
        location: placeData.lat != null ? {
          lat: () => placeData.lat!,
          lng: () => placeData.lng!,
        } : null,
        addressComponents: placeData.zipCode ? [
          { types: ['postal_code'], shortText: placeData.zipCode }
        ] : [],
        websiteURI: undefined,
        internationalPhoneNumber: placeData.phone,
        rating: placeData.rating,
        fetchFields: async () => { /* no-op — fields already populated */ },
      };

      const fakeEvent = new Event('gmp-select') as any;
      fakeEvent.placePrediction = {
        toPlace: () => mockPlace,
      };

      listeners.forEach(fn => fn(fakeEvent));
    };
  });
}

/**
 * Trigger place selection from a test. Must be called after page.goto().
 */
export async function triggerPlaceSelect(page: Page, placeData: {
  name: string;
  address: string;
  zipCode: string | null;
  lat?: number;
  lng?: number;
  phone?: string;
  rating?: number;
}) {
  await page.evaluate((data) => {
    (window as any).__triggerPlaceSelect(data);
  }, placeData);
}
