export interface ChatMessage {
    id: string;
    role: 'user' | 'model';
    text: string;
}

export enum TrafficLevel {
    LOW = 'Low',
    MEDIUM = 'Medium',
    HIGH = 'High',
    VERY_HIGH = 'Very High',
    CLOSED = 'Closed'
}

export interface TimeSlot {
    label: string; // e.g., "Morning", "Lunch", "Afternoon", "Evening"
    score: number; // 0-100
    level: TrafficLevel;
    reason: string;
}

export interface DailyForecast {
    date: string; // YYYY-MM-DD
    dayOfWeek: string;
    localEvents: string[];
    weatherNote: string;
    slots: TimeSlot[];
}

export interface POI {
    name: string;
    lat: number;
    lng: number;
    type: string; // e.g. "School", "Competitor", "Transit"
}

export interface BusinessDetails {
    name: string;
    address: string;
    coordinates: {
        lat: number;
        lng: number;
    };
    type: string;
    nearbyPOIs: POI[];
}

export interface ForecastResponse {
    business: BusinessDetails;
    forecast: DailyForecast[];
    summary: string;
}
