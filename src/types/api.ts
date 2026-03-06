/**
 * Shared type definitions for the frontend.
 * These mirror the Pydantic models in backend/types.py.
 * The backend is the source of truth — keep these in sync.
 */

// --- Identity types (from src/agents/types.ts) ---

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

export interface NewsItem {
    title: string;
    url: string;
    source: string;
    date?: string;
    snippet?: string;
}

export interface ValidationReport {
    totalUrlsChecked: number;
    valid: number;
    invalid: number;
    corrected: number;
}

export interface EnrichedProfile extends BaseIdentity {
    primaryColor?: string;
    secondaryColor?: string;
    logoUrl?: string;
    favicon?: string;
    persona?: string;
    menuUrl?: string;
    menuScreenshotBase64?: string;
    menuScreenshotUrl?: string;
    menuHtmlUrl?: string;
    socialLinks?: {
        instagram?: string;
        facebook?: string;
        twitter?: string;
        yelp?: string;
        tiktok?: string;
        grubhub?: string;
        doordash?: string;
        ubereats?: string;
        seamless?: string;
        toasttab?: string;
    };
    phone?: string;
    email?: string;
    hours?: string;
    googleMapsUrl?: string;
    competitors?: {
        name: string;
        url: string;
        reason?: string;
    }[];
    news?: NewsItem[];
    socialProfileMetrics?: SocialProfileMetrics;
    aiOverview?: AIOverview;
    validationReport?: ValidationReport;
    reportUrl?: string;
    _debugError?: string;
}

// --- Social Profile Metrics types ---

export interface SocialPlatformMetrics {
    url?: string;
    username?: string;
    pageName?: string;
    followerCount?: number;
    followingCount?: number;
    postCount?: number;
    videoCount?: number;
    likeCount?: number;
    rating?: number;
    reviewCount?: number;
    priceRange?: string;
    categories?: string[];
    bio?: string;
    isVerified?: boolean;
    claimedByOwner?: boolean;
    lastPostRecency?: string;
    engagementIndicator?: 'high' | 'moderate' | 'low' | 'unknown';
    error?: string | null;
}

export interface SocialProfileSummary {
    totalFollowers: number;
    strongestPlatform: string;
    weakestPlatform: string;
    overallPresenceScore: number;
    postingFrequency: string;
    recommendation: string;
}

export interface SocialProfileMetrics {
    instagram?: SocialPlatformMetrics | null;
    facebook?: SocialPlatformMetrics | null;
    twitter?: SocialPlatformMetrics | null;
    tiktok?: SocialPlatformMetrics | null;
    yelp?: SocialPlatformMetrics | null;
    summary?: SocialProfileSummary;
}

// --- AI Overview types ---

export interface AIOverview {
    summary: string;
    highlights: string[];
    business_type?: string;
    price_range?: string;
    established?: string;
    notable_mentions?: string[];
    reputation_signals?: 'positive' | 'mixed' | 'negative' | 'unknown';
    sources?: { url: string; title: string }[];
}

// --- Report types (from src/lib/types.ts) ---

export interface BusinessIdentity {
    primaryColor: string;
    secondaryColor: string;
    logoUrl?: string;
    persona: string;
    name: string;
    menuScreenshotBase64?: string;
}

export interface MenuItem {
    item_name: string;
    current_price: number;
    category: string;
    description?: string;
}

export interface CompetitorPrice {
    competitor_name: string;
    item_match: string;
    price: number;
    source_url: string;
    distance_miles?: number;
}

export interface CommodityTrend {
    ingredient: string;
    inflation_rate_12mo: number;
    trend_description: string;
}

export interface MenuAnalysisItem extends MenuItem {
    competitor_benchmark: number;
    commodity_factor: number;
    recommended_price: number;
    price_leakage: number;
    confidence_score: number;
    rationale: string;
}

export interface SurgicalReport {
    identity: BusinessIdentity;
    menu_items: MenuAnalysisItem[];
    strategic_advice: string[];
    overall_score: number;
    generated_at: string;
}

// --- SEO Auditor types ---

export interface Recommendation {
    severity: 'Critical' | 'Warning' | 'Info';
    title: string;
    description: string;
    action: string;
}

export interface Methodology {
    reasoningSteps: string[];
    toolsUsed: string[];
    searchQueries?: string[];
    sourcesUsed?: { url: string; title: string }[];
}

export interface AuditSection {
    id: string;
    title: string;
    score: number;
    description?: string;
    recommendations: Recommendation[];
    methodology?: Methodology;
    isAnalyzed?: boolean;
}

export interface SeoReport {
    overallScore: number;
    summary: string;
    url: string;
    sections: AuditSection[];
}

export interface QuickScanResult {
    url: string;
    overallScore: number;
    summary: string;
    categories: {
        id: string;
        title: string;
        score: number;
        description: string;
    }[];
}
