
import { ChartPie, Search, Zap, LayoutTemplate, FileText } from 'lucide-react';

export const GEMINI_FLASH_MODEL = 'gemini-3.1-flash-lite-preview';
export const GEMINI_PRO_MODEL = 'gemini-3.0-flash-preview';

export const SCAN_CATEGORIES = [
  { id: 'technical', title: 'Technical SEO' },
  { id: 'content', title: 'Content Quality' },
  { id: 'ux', title: 'User Experience' },
  { id: 'performance', title: 'Performance' },
  { id: 'authority', title: 'Backlinks & Authority' }
];

export const CATEGORY_ICONS: Record<string, any> = {
  'Technical SEO': Zap,
  'Content Quality': FileText,
  'User Experience': LayoutTemplate,
  'Performance': ChartPie,
  'Backlinks & Authority': Search,
};

export const SEVERITY_COLORS = {
  'Critical': 'bg-red-100 text-red-800 border-red-200',
  'Warning': 'bg-yellow-100 text-yellow-800 border-yellow-200',
  'Info': 'bg-blue-100 text-blue-800 border-blue-200',
};

export const LOADING_THOUGHTS: Record<string, string[]> = {
  technical: [
    "Parsing DOM structure...",
    "Validating SSL/TLS certificate chain...",
    "Checking robots.txt directives...",
    "Analyzing sitemap.xml availability...",
    "Verifying canonical tag consistency...",
    "Inspecting schema.org structured data...",
    "Checking for broken links (404s)...",
    "Analyzing URL structure depths..."
  ],
  content: [
    "Evaluating H1-H6 heading hierarchy...",
    "Analyzing keyword density and distribution...",
    "Checking for duplicate content signatures...",
    "Assessing meta title and description lengths...",
    "Reading content for tone and readability...",
    "Identifying thin content pages...",
    "Checking image alt text coverage..."
  ],
  ux: [
    "Measuring Cumulative Layout Shift (CLS)...",
    "Checking tap target sizes for mobile...",
    "Analyzing navigation flow and depth...",
    "Checking color contrast ratios...",
    "Verifying mobile viewport configuration...",
    "Evaluating interstitial usage..."
  ],
  performance: [
    "Simulating First Contentful Paint (FCP)...",
    "Analyzing JavaScript bundle sizes...",
    "Checking image optimization (WebP/AVIF)...",
    "Evaluating server response time (TTFB)...",
    "Checking browser caching policies...",
    "Analyzing render-blocking resources..."
  ],
  authority: [
    "Querying knowledge graph signals...",
    "Analyzing external link profile...",
    "Checking social signal consistency...",
    "Verifying brand mentions on web...",
    "Evaluating domain age and history...",
    "Checking internal linking structure..."
  ],
  general: [
    "Initializing Gemini 3.1 Flash Lite model...",
    "Configuring thinking level...",
    "Connecting to Google Search grounding...",
    "Synthesizing audit findings...",
    "Generating actionable recommendations...",
    "Finalizing SEO report JSON..."
  ]
};
