/**
 * Loading experience configuration — pipeline stages, quotes, and bubble game settings.
 */

export type CapabilityId = "discovery" | "surgery" | "traffic" | "seo" | "competitive" | "marketing";

export interface PipelineStage {
  id: string;
  label: string;
  icon: string; // lucide-react icon name
  durationPercent: number; // sums to 100 across stages
}

export interface CapabilityConfig {
  id: CapabilityId;
  label: string;
  accentHex: string;
  estimatedDurationMs: number;
  stages: PipelineStage[];
  quotes: string[];
}

// ─── Pipeline stage definitions per capability ──────────────────────────────

const DISCOVERY_CONFIG: CapabilityConfig = {
  id: "discovery",
  label: "Deep Discovery",
  accentHex: "#0052CC",
  estimatedDurationMs: 45_000,
  stages: [
    { id: "crawl", label: "Crawling business website", icon: "Globe", durationPercent: 25 },
    { id: "agents", label: "Running 7 research agents", icon: "Users", durationPercent: 30 },
    { id: "social", label: "Profiling social media", icon: "Camera", durationPercent: 25 },
    { id: "validate", label: "Validating & cross-referencing", icon: "CheckCircle", durationPercent: 20 },
  ],
  quotes: [
    "We crawl deeper than a Yelp reviewer on a mission.",
    "7 AI agents researching your business simultaneously \u2014 like a team of interns, but faster.",
    "Finding every detail about your business across the web.",
    "Good discovery is the foundation of great strategy.",
    "Scanning menus, reviews, social profiles, and more\u2026",
    "Our bots are checking your Instagram so you don\u2019t have to.",
    "Building your digital twin \u2014 one data point at a time.",
    "The more we know, the sharper our recommendations.",
  ],
};

const SURGERY_CONFIG: CapabilityConfig = {
  id: "surgery",
  label: "Price Optimization",
  accentHex: "#6366f1",
  estimatedDurationMs: 90_000,
  stages: [
    { id: "vision", label: "Scanning menu screenshot", icon: "ScanEye", durationPercent: 20 },
    { id: "benchmark", label: "Benchmarking competitor prices", icon: "Scale", durationPercent: 25 },
    { id: "commodity", label: "Tracking commodity costs", icon: "TrendingUp", durationPercent: 20 },
    { id: "surgeon", label: "Calculating optimal pricing", icon: "Scissors", durationPercent: 25 },
    { id: "advisor", label: "Generating strategic advice", icon: "Lightbulb", durationPercent: 10 },
  ],
  quotes: [
    "A 1% drop in food costs has 3x the profit impact of a 1% revenue increase.",
    "The top 20% of menu items typically drive 70% of a restaurant's revenue.",
    "Egg prices surged 60%+ in two years \u2014 we track that live against your menu.",
    "Restaurants that price-optimize see 10\u201315% margin improvement on average.",
    "Our AI doesn\u2019t eat, but it has very strong opinions about your pricing.",
    "If this analysis were a dish, it would be the chef\u2019s tasting menu \u2014 thorough.",
    "Running more calculations than a waiter splitting a 12-top check.",
    "No menus were harmed in the making of this report.",
  ],
};

const TRAFFIC_CONFIG: CapabilityConfig = {
  id: "traffic",
  label: "Foot Traffic Forecast",
  accentHex: "#10b981",
  estimatedDurationMs: 60_000,
  stages: [
    { id: "weather", label: "Gathering local weather data", icon: "CloudSun", durationPercent: 25 },
    { id: "events", label: "Analyzing nearby events & holidays", icon: "Calendar", durationPercent: 25 },
    { id: "models", label: "Computing traffic models", icon: "BarChart3", durationPercent: 30 },
    { id: "forecast", label: "Generating 3-day forecast", icon: "MapPin", durationPercent: 20 },
  ],
  quotes: [
    "Heavy rain can drop foot traffic by up to 40% \u2014 we factor weather into forecasts.",
    "Friday and Saturday evenings drive 35% of weekly restaurant revenue.",
    "Local events can boost walk-in traffic by 25% or more.",
    "The best time to staff up? Right before the rush \u2014 we\u2019ll tell you when.",
    "Weather, events, and history \u2014 three ingredients for a perfect forecast.",
    "Predicting foot traffic more accurately than your weather app predicts rain.",
    "Crunching numbers harder than a Friday night kitchen rush\u2026",
    "Hold tight \u2014 genius takes a minute. Mediocrity is instant.",
  ],
};

const SEO_CONFIG: CapabilityConfig = {
  id: "seo",
  label: "Google Presence Check",
  accentHex: "#8b5cf6",
  estimatedDurationMs: 75_000,
  stages: [
    { id: "crawl", label: "Crawling website structure", icon: "Globe", durationPercent: 25 },
    { id: "pagespeed", label: "Running PageSpeed analysis", icon: "Gauge", durationPercent: 25 },
    { id: "content", label: "Evaluating content & metadata", icon: "FileText", durationPercent: 30 },
    { id: "score", label: "Scoring SEO performance", icon: "Award", durationPercent: 20 },
  ],
  quotes: [
    "73% of diners check a restaurant online before walking in.",
    "Page load speed is the #1 factor in mobile search ranking.",
    "Restaurants with complete Google Business profiles get 7x more clicks.",
    "The first 5 organic results capture 67% of all clicks.",
    "Scanning the web faster than a foodie doom-scrolling Yelp reviews.",
    "Your website is your 24/7 hostess \u2014 let\u2019s make sure she\u2019s on point.",
    "Doing the math your accountant wishes they could do this fast.",
    "Teaching our AI to appreciate the fine art of SEO engineering\u2026",
  ],
};

const COMPETITIVE_CONFIG: CapabilityConfig = {
  id: "competitive",
  label: "Competitive Analysis",
  accentHex: "#f97316",
  estimatedDurationMs: 80_000,
  stages: [
    { id: "profile", label: "Profiling your business position", icon: "Building2", durationPercent: 20 },
    { id: "research", label: "Researching local competitors", icon: "Search", durationPercent: 30 },
    { id: "threat", label: "Analyzing threat levels", icon: "Shield", durationPercent: 30 },
    { id: "advantages", label: "Crafting strategic advantages", icon: "Target", durationPercent: 20 },
  ],
  quotes: [
    "Know thy enemy \u2014 Sun Tzu probably ran a restaurant.",
    "The average restaurant competes with 12 others within a 1-mile radius.",
    "Differentiation is the #1 driver of long-term restaurant success.",
    "Your competitors\u2019 weakness is your opportunity \u2014 we\u2019ll find it.",
    "Spying on the competition \u2014 legally, of course.",
    "If you can\u2019t beat them, at least know exactly why they\u2019re winning.",
    "Mapping the competitive landscape one rival at a time\u2026",
    "Strategy without intelligence is noise. Intelligence without strategy is wasted.",
  ],
};

const MARKETING_CONFIG: CapabilityConfig = {
  id: "marketing",
  label: "Social Media Health Check",
  accentHex: "#ec4899",
  estimatedDurationMs: 90_000,
  stages: [
    { id: "research", label: "Researching social platforms", icon: "Search", durationPercent: 30 },
    { id: "analyze", label: "Analyzing presence & engagement", icon: "Share2", durationPercent: 25 },
    { id: "benchmark", label: "Benchmarking competitors", icon: "Users", durationPercent: 20 },
    { id: "strategy", label: "Building strategy recommendations", icon: "Target", durationPercent: 25 },
  ],
  quotes: [
    "Posts with food photos get 120% more engagement than text-only updates.",
    "Instagram Reels now drive 40% of new restaurant discovery.",
    "Consistency beats virality \u2014 but we\u2019ll aim for both.",
    "Your social media is your digital curb appeal.",
    "Auditing their presence across every platform\u2026",
    "Searching for followers, posts, and engagement signals\u2026",
    "73% of diners check social media before visiting a new restaurant.",
    "A strong social presence can boost revenue by 20-30%.",
  ],
};

export const CAPABILITY_CONFIGS: Record<string, CapabilityConfig> = {
  discovery: DISCOVERY_CONFIG,
  surgery: SURGERY_CONFIG,
  traffic: TRAFFIC_CONFIG,
  seo: SEO_CONFIG,
  competitive: COMPETITIVE_CONFIG,
  marketing: MARKETING_CONFIG,
};

export const GENERIC_QUOTES = [
  "A 1% drop in food costs has 3x the profit impact of a 1% revenue increase.",
  "The top 20% of menu items typically drive 70% of a restaurant's revenue.",
  "73% of diners check a restaurant online before walking in.",
  "Crunching numbers harder than a Friday night kitchen rush\u2026",
  "Our AI doesn\u2019t eat, but it has very strong opinions about your pricing.",
  "Hold tight \u2014 genius takes a minute. Mediocrity is instant.",
  "Doing the math your accountant wishes they could do this fast.",
  "No menus were harmed in the making of this report.",
];

// ─── Bubble game config ─────────────────────────────────────────────────────

export const BUBBLE_CONFIG = {
  spawnIntervalMs: 1100,
  maxBubbles: 12,
  minRadius: 24,
  maxRadius: 48,
  riseSpeed: { min: 0.25, max: 0.6 },
  wobbleAmplitude: 0.5,
  popDurationMs: 300,
  symbols: [
    "\u{1F374}", // fork and knife
    "\u{2615}",  // coffee
    "\u{1F355}", // pizza
    "\u{2B50}",  // star
    "\u{1F4B0}", // money bag
    "\u{1F4C8}", // chart up
    "\u{2764}\u{FE0F}", // heart
    "\u{26A1}",  // lightning
    "\u{1F525}", // fire
    "\u{1F3AF}", // target
    "\u{1F680}", // rocket
    "\u{2728}",  // sparkles
  ],
  colors: [
    "#0052CC", // Hephae blue
    "#00C2FF", // Hephae cyan
    "#7c3aed", // purple
    "#10b981", // emerald
    "#f59e0b", // amber
    "#ec4899", // pink
  ],
};
