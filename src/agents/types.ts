export interface Coordinates {
    lat: number;
    lng: number;
}

export interface BaseIdentity {
    name: string;
    address?: string;
    coordinates?: Coordinates;
    officialUrl: string;
}

export interface EnrichedProfile extends BaseIdentity {
    primaryColor?: string;
    secondaryColor?: string;
    logoUrl?: string;
    persona?: string;
    menuScreenshotBase64?: string;
    socialLinks?: {
        instagram?: string;
        facebook?: string;
        twitter?: string;
    };
    googleMapsUrl?: string;
    competitors?: {
        name: string;
        url: string;
        reason?: string;
    }[];
    _debugError?: string;
}
