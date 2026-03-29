/** Shared types for Amethyst Insight dashboard cards. */

export interface AiTool { tool: string; capability: string; url?: string | null; actionForOwner?: string; }
export interface Insight { title: string; recommendation: string; }
export interface DashEvent { what: string; when: string; }
export interface Competitor { name: string; category: string; cuisine: string; distanceM: number; }

export interface DashboardData {
  pulseHeadline?: string | null;
  isNational?: boolean;
  keyMetrics?: Record<string, number>;
  topInsights?: Insight[];
  communityBuzz?: string | null;
  events?: DashEvent[];
  stats?: {
    population?: string | null;
    medianIncome?: string | null;
    city?: string | null;
    state?: string | null;
    competitorCount?: number;
    saturationLevel?: string | null;
    deliveryAdoption?: string | null;
    eventCount?: number;
    weatherOutlook?: string | null;
    confirmedSources?: number;
    county?: string | null;
  };
  aiTools?: AiTool[];
  competitors?: Competitor[];
  confirmedSources?: number;
  /** Rich local signals from IRS, weather, CDC, census data_cache */
  localIntel?: Record<string, string>;
  /** Specific discovered facts — the real value */
  localFacts?: string[];
}

export interface MarginCardData {
  overall_score?: number;
  annual_leakage?: number;
  top_opportunity?: string;
  categories?: Record<string, { margin_pct?: number; cost_pct?: number; label?: string }>;
}

export interface SeoCardData {
  overallScore?: number;
  findings?: { title: string; severity: string }[];
}

export interface TrafficCardData {
  weeklyScore: number;
  peakDay: string;
  peakHour: string;
  forecast: string;
  byDay: { day: string; score: number }[];
  hourly: { hour: string; score: number }[];
}

export interface DashBusiness {
  name: string;
  address?: string;
  officialUrl?: string;
  lat?: number;
  lng?: number;
  persona?: string;
  logoUrl?: string;
  favicon?: string;
  primaryColor?: string;
}
