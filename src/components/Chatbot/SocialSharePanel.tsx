"use client";

import React, { useEffect, useState } from "react";
import {
  X,
  Instagram,
  Facebook,
  Copy,
  Check,
  Link2,
  Loader2,
  RefreshCw,
} from "lucide-react";

interface SocialSharePanelProps {
  reportUrl: string;
  reportType: string;
  businessName: string;
  summary: string;
  socialHandles?: { instagram?: string; facebook?: string };
  onClose: () => void;
}

interface SocialPosts {
  instagram: { caption: string };
  facebook: { post: string };
}

export default function SocialSharePanel({
  reportUrl,
  reportType,
  businessName,
  summary,
  socialHandles,
  onClose,
}: SocialSharePanelProps) {
  const [posts, setPosts] = useState<SocialPosts | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const fetchPosts = async () => {
    setLoading(true);
    setError(false);
    try {
      const res = await fetch("/api/social-posts/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          businessName,
          reportType,
          summary,
          reportUrl,
          socialHandles,
        }),
      });
      if (!res.ok) throw new Error("Failed");
      const data = await res.json();
      setPosts(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPosts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const copyText = (text: string, field: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
    });
  };

  const shareOnFacebook = () => {
    const text = posts?.facebook?.post
      ? encodeURIComponent(posts.facebook.post)
      : "";
    window.open(
      `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(reportUrl)}&quote=${text}`,
      "_blank",
      "width=600,height=400"
    );
  };

  const REPORT_LABELS: Record<string, string> = {
    margin: "Margin Surgery",
    traffic: "Traffic Forecast",
    seo: "SEO Deep Audit",
    competitive: "Competitive Analysis",
    marketing: "Social Media Insights",
    profile: "Business Profile",
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="relative w-full max-w-md mx-4 mb-4 sm:mb-0 bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden animate-slide-in-up">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 bg-gradient-to-r from-indigo-50 to-purple-50">
          <div>
            <h3 className="text-sm font-bold text-gray-900">
              Share This Report
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              {REPORT_LABELS[reportType] || reportType} for {businessName}
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full hover:bg-white/80 flex items-center justify-center text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="px-5 py-4 max-h-[60vh] overflow-y-auto space-y-4">
          {loading && (
            <div className="flex flex-col items-center justify-center py-8 gap-3">
              <Loader2 className="w-6 h-6 text-indigo-500 animate-spin" />
              <p className="text-sm text-gray-500 font-medium">
                Crafting your social posts...
              </p>
            </div>
          )}

          {error && !loading && (
            <div className="flex flex-col items-center justify-center py-8 gap-3">
              <p className="text-sm text-gray-500">
                Failed to generate posts.
              </p>
              <button
                onClick={fetchPosts}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-indigo-50 text-indigo-600 text-sm font-medium hover:bg-indigo-100 transition-colors"
              >
                <RefreshCw size={14} />
                Retry
              </button>
            </div>
          )}

          {posts && !loading && (
            <>
              {/* Instagram */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-purple-500 via-pink-500 to-orange-400 flex items-center justify-center">
                    <Instagram className="w-3.5 h-3.5 text-white" />
                  </div>
                  <span className="text-xs font-bold text-gray-700 uppercase tracking-wide">
                    Instagram
                  </span>
                </div>
                <div className="bg-gray-50 rounded-xl border border-gray-100 p-3.5">
                  <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                    {posts.instagram.caption}
                  </p>
                </div>
                <button
                  onClick={() =>
                    copyText(posts.instagram.caption, "instagram")
                  }
                  className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gradient-to-r from-purple-50 to-pink-50 border border-purple-100 text-xs font-semibold text-purple-700 hover:from-purple-100 hover:to-pink-100 transition-all"
                >
                  {copiedField === "instagram" ? (
                    <>
                      <Check size={12} className="text-green-600" />
                      Copied!
                    </>
                  ) : (
                    <>
                      <Copy size={12} />
                      Copy Caption
                    </>
                  )}
                </button>
              </div>

              {/* Facebook */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-6 h-6 rounded-lg bg-[#1877F2] flex items-center justify-center">
                    <Facebook className="w-3.5 h-3.5 text-white" />
                  </div>
                  <span className="text-xs font-bold text-gray-700 uppercase tracking-wide">
                    Facebook
                  </span>
                </div>
                <div className="bg-gray-50 rounded-xl border border-gray-100 p-3.5">
                  <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                    {posts.facebook.post}
                  </p>
                </div>
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() =>
                      copyText(posts.facebook.post, "facebook")
                    }
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-blue-50 border border-blue-100 text-xs font-semibold text-blue-700 hover:bg-blue-100 transition-all"
                  >
                    {copiedField === "facebook" ? (
                      <>
                        <Check size={12} className="text-green-600" />
                        Copied!
                      </>
                    ) : (
                      <>
                        <Copy size={12} />
                        Copy Post
                      </>
                    )}
                  </button>
                  <button
                    onClick={shareOnFacebook}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#1877F2] text-xs font-semibold text-white hover:bg-[#166FE5] transition-all"
                  >
                    <Facebook size={12} />
                    Share on Facebook
                  </button>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer: Quick actions */}
        <div className="px-5 py-3 border-t border-gray-100 bg-gray-50/50 flex items-center gap-2">
          <button
            onClick={() => copyText(reportUrl, "link")}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white border border-gray-200 text-xs font-semibold text-gray-600 hover:bg-gray-100 transition-all"
          >
            {copiedField === "link" ? (
              <>
                <Check size={12} className="text-green-600" />
                Copied!
              </>
            ) : (
              <>
                <Link2 size={12} />
                Copy Report Link
              </>
            )}
          </button>
          <button
            onClick={() => {
              fetchPosts();
            }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white border border-gray-200 text-xs font-semibold text-gray-600 hover:bg-gray-100 transition-all"
          >
            <RefreshCw size={12} />
            Regenerate
          </button>
        </div>
      </div>
    </div>
  );
}
