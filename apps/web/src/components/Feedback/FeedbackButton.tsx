"use client";

import { ThumbsUp, ThumbsDown } from "lucide-react";
import { useState } from "react";
import { useFeedback, FeedbackDataType } from "./useFeedback";

interface FeedbackButtonProps {
  businessSlug: string;
  dataType: FeedbackDataType;
  itemId: string;
  itemLabel: string;
  zipCode?: string;
  vertical?: string;
  className?: string;
}

export default function FeedbackButton({
  businessSlug,
  dataType,
  itemId,
  itemLabel,
  zipCode,
  vertical,
  className = "",
}: FeedbackButtonProps) {
  const { submitFeedback } = useFeedback(businessSlug, zipCode, vertical);
  const [rating, setRating] = useState<"up" | "down" | null>(null);

  const handle = async (r: "up" | "down") => {
    if (rating) return;
    setRating(r);
    await submitFeedback(dataType, itemId, itemLabel, r);
  };

  return (
    <div className={`inline-flex items-center gap-0.5 ${className}`}>
      {rating !== "down" && (
        <button
          onClick={() => handle("up")}
          disabled={!!rating}
          className={`w-5 h-5 rounded flex items-center justify-center transition-colors ${
            rating === "up"
              ? "text-emerald-500"
              : "text-slate-300 hover:text-emerald-400"
          }`}
          aria-label="Mark as helpful"
        >
          <ThumbsUp className={`w-3 h-3 ${rating === "up" ? "fill-current" : ""}`} />
        </button>
      )}
      {rating !== "up" && (
        <button
          onClick={() => handle("down")}
          disabled={!!rating}
          className={`w-5 h-5 rounded flex items-center justify-center transition-colors ${
            rating === "down"
              ? "text-slate-400"
              : "text-slate-300 hover:text-red-400"
          }`}
          aria-label="Mark as not helpful"
        >
          <ThumbsDown className={`w-3 h-3 ${rating === "down" ? "fill-current" : ""}`} />
        </button>
      )}
    </div>
  );
}
