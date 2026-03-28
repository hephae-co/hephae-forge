/**
 * Pure function to compute suggestion chips based on app state.
 * Extracted from page.tsx useMemo for testability.
 */

import { SuggestionChip } from '@/components/Chatbot/types';

export interface ChipState {
  isCentered: boolean;
  isDiscovering: boolean;
  isTyping: boolean;
  businessName?: string;
  hasReport: boolean;
  hasForecast: boolean;
  hasSeoReport: boolean;
  hasCompetitiveReport: boolean;
  hasSocialAuditReport: boolean;
  hasCapabilities: boolean;
}

/**
 * Map of action chip text → capability ID.
 * Used by sendMessage to route action chips directly to executeCapability.
 */
export const ACTION_CHIP_MAP: Record<string, string> = {
  "Now forecast the foot traffic": "traffic",
  "How's their online presence?": "seo",
  "Now analyze the menu margins": "surgery",
  "Now scan the menu for profit leaks": "surgery",
  "How do they rank on Google?": "seo",
  "Run an SEO audit next": "seo",
  "Let's check the menu margins": "surgery",
  "Will rain hurt their traffic?": "traffic",
  "Analyze their social media": "marketing",
  "What's their social media like?": "marketing",
  "Analyze the competition": "competitive",
  "Audit their social media": "marketing",
  "Where is their money leaking?": "surgery",
};

export function computeSuggestionChips(state: ChipState): SuggestionChip[] {
  const {
    isCentered, isDiscovering, isTyping,
    businessName, hasReport, hasForecast,
    hasSeoReport, hasCompetitiveReport,
    hasSocialAuditReport, hasCapabilities,
  } = state;

  if (isCentered) {
    return [];
  }

  if (isDiscovering || isTyping) return [];

  const chips: SuggestionChip[] = [];
  const name = businessName || 'this business';

  if (hasReport) {
    chips.push({ text: "Which item is bleeding the most money?", category: 'insight' });
    if (!hasForecast) chips.push({ text: "Now forecast the foot traffic", category: 'action', capability: 'traffic' });
    if (!hasSeoReport) chips.push({ text: "How's their online presence?", category: 'action', capability: 'seo' });
  } else if (hasSeoReport) {
    chips.push({ text: "What's the biggest SEO red flag?", category: 'insight' });
    if (!hasReport) chips.push({ text: "Now analyze the menu margins", category: 'action', capability: 'surgery' });
    if (!hasForecast) chips.push({ text: "Will rain hurt their traffic?", category: 'action', capability: 'traffic' });
  } else if (hasForecast) {
    chips.push({ text: "When is the worst time to be short-staffed?", category: 'insight' });
    if (!hasReport) chips.push({ text: "Now scan the menu for profit leaks", category: 'action', capability: 'surgery' });
    if (!hasSeoReport) chips.push({ text: "How do they rank on Google?", category: 'action', capability: 'seo' });
  } else if (hasSocialAuditReport) {
    chips.push({ text: "Which platform needs the most work?", category: 'insight' });
    if (!hasReport) chips.push({ text: "Let's check the menu margins", category: 'action', capability: 'surgery' });
    if (!hasCompetitiveReport) chips.push({ text: "Analyze the competition", category: 'action', capability: 'competitive' });
  } else if (hasCompetitiveReport) {
    chips.push({ text: "Who's their biggest threat?", category: 'insight' });
    if (!hasReport) chips.push({ text: "Let's check the menu margins", category: 'action', capability: 'surgery' });
    if (!hasSocialAuditReport) chips.push({ text: "Audit their social media", category: 'action', capability: 'marketing' });
  } else if (hasCapabilities) {
    chips.push({ text: "Where is their money leaking?", category: 'action', capability: 'surgery' });
    chips.push({ text: "How do they rank on Google?", category: 'action', capability: 'seo' });
    chips.push({ text: "What's their social media like?", category: 'action', capability: 'marketing' });
  }

  return chips.slice(0, 4);
}
