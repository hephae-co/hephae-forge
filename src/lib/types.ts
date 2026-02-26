export interface BusinessIdentity {
    primaryColor: string;
    secondaryColor: string;
    logoUrl?: string;
    persona: string; // e.g., "Old School Jersey Diner", "Modern Cafe"
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
    source_url: string; // Grounding citation requirement
    distance_miles?: number;
}

export interface CommodityTrend {
    ingredient: string; // e.g., "Eggs", "Bacon"
    inflation_rate_12mo: number; // percentage
    trend_description: string;
}

export interface MenuAnalysisItem extends MenuItem {
    competitor_benchmark: number; // Median of competitors
    commodity_factor: number; // Inflation impact
    recommended_price: number;
    price_leakage: number; // The "loss" per sale
    confidence_score: number; // 0-100
    rationale: string;
}

export interface SurgicalReport {
    identity: BusinessIdentity;
    menu_items: MenuAnalysisItem[];
    strategic_advice: string[]; // From Advisor Agent
    overall_score: number;
    generated_at: string;
}

// --- SEO AUDITOR TYPES ---

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
}

export interface AuditSection {
    id: string; // Added ID for reliable selection
    title: string;
    score: number;
    description?: string; // Brief summary from quick scan
    recommendations: Recommendation[];
    methodology?: Methodology; // New field for transparency
    isAnalyzed?: boolean; // Track if this section got the deep dive
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
