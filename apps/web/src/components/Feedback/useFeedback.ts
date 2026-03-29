"use client";

import { useCallback, useRef } from "react";

export type FeedbackDataType =
  | "pulse_insight"
  | "business_overview"
  | "ai_tool"
  | "margin_item"
  | "traffic_slot"
  | "seo_item"
  | "competitive_item"
  | "event"
  | "community_buzz";

export interface FeedbackPayload {
  sessionId: string;
  businessSlug: string;
  dataType: FeedbackDataType;
  itemId: string;
  itemLabel: string;
  rating: "up" | "down";
  zipCode?: string;
  vertical?: string;
  tags?: string[];
  comment?: string;
}

function getSessionId(): string {
  if (typeof window === "undefined") return "ssr";
  const key = "hephae_session_id";
  let id = sessionStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(key, id);
  }
  return id;
}

export function useFeedback(
  businessSlug: string,
  zipCode?: string,
  vertical?: string
) {
  // Track submitted item IDs to avoid duplicate votes in a session
  const submitted = useRef<Set<string>>(new Set());

  const submitFeedback = useCallback(
    async (
      dataType: FeedbackDataType,
      itemId: string,
      itemLabel: string,
      rating: "up" | "down",
      tags?: string[],
      comment?: string
    ) => {
      const dedupeKey = `${businessSlug}:${dataType}:${itemId}`;
      if (submitted.current.has(dedupeKey)) return;

      const payload: FeedbackPayload = {
        sessionId: getSessionId(),
        businessSlug,
        dataType,
        itemId,
        itemLabel: itemLabel.slice(0, 60),
        rating,
        zipCode,
        vertical,
        tags: tags ?? [],
        comment,
      };

      // Fire-and-forget — swallow errors silently
      try {
        await fetch("/api/feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        submitted.current.add(dedupeKey);
      } catch {
        // Silent — feedback failure should never surface to user
      }
    },
    [businessSlug, zipCode, vertical]
  );

  return { submitFeedback };
}
