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
  Download,
  ImageIcon,
  ExternalLink,
} from "lucide-react";

interface SocialSharePanelProps {
  reportUrl: string;
  reportType: string;
  businessName: string;
  summary: string;
  socialHandles?: { instagram?: string; facebook?: string; twitter?: string };
  headline?: string;
  subtitle?: string;
  highlight?: string;
  reportUrls?: Record<string, string>;
  onClose: () => void;
}

interface PostData {
  caption?: string;
  post?: string;
  tweet?: string;
  reportLink?: string;
  imageUrl?: string;
}

interface SocialPosts {
  instagram: PostData;
  facebook: PostData;
  twitter: PostData;
}

// X/Twitter logo SVG (the "𝕏" mark)
function XLogo({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  );
}

/** Renders a clickable report link badge below a post */
function ReportLinkBadge({ url, label }: { url: string; label?: string }) {
  if (!url) return null;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1.5 mt-2 px-3 py-1.5 rounded-lg bg-indigo-50 border border-indigo-100 text-xs font-semibold text-indigo-600 hover:bg-indigo-100 transition-colors"
    >
      <ExternalLink size={11} />
      {label || "View Full Report"}
    </a>
  );
}

/** Renders a social card image preview if available */
function CardPreview({ url }: { url?: string }) {
  if (!url) return null;
  return (
    <div className="mt-2 rounded-lg overflow-hidden border border-gray-200">
      <img
        src={url}
        alt="Social card"
        className="w-full h-auto"
        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
      />
    </div>
  );
}

export default function SocialSharePanel({
  reportUrl,
  reportType,
  businessName,
  summary,
  socialHandles,
  headline,
  subtitle,
  highlight,
  reportUrls,
  onClose,
}: SocialSharePanelProps) {
  const [posts, setPosts] = useState<SocialPosts | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [cardImageUrl, setCardImageUrl] = useState<string | null>(null);
  const [cardLoading, setCardLoading] = useState(true);

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
          reportUrls: reportUrls || {},
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

  const fetchCard = async () => {
    setCardLoading(true);
    try {
      const res = await fetch("/api/social-card", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          businessName,
          reportType,
          headline: headline || "",
          subtitle: subtitle || "",
          highlight: highlight || "",
        }),
      });
      if (res.ok) {
        const blob = await res.blob();
        setCardImageUrl(URL.createObjectURL(blob));
      }
    } catch {
      /* ignore — image is optional */
    } finally {
      setCardLoading(false);
    }
  };

  useEffect(() => {
    fetchPosts();
    fetchCard();
    return () => {
      if (cardImageUrl) URL.revokeObjectURL(cardImageUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const copyText = (text: string, field: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
    });
  };

  const downloadCard = () => {
    if (!cardImageUrl) return;
    const a = document.createElement("a");
    a.href = cardImageUrl;
    a.download = `Hephae-${businessName.replace(/\s+/g, "-")}.png`;
    a.click();
  };

  const shareOnInstagram = () => {
    if (posts?.instagram?.caption) {
      const fullText = posts.instagram.caption + (posts.instagram.reportLink ? `\n\n${posts.instagram.reportLink}` : '');
      navigator.clipboard.writeText(fullText);
    }
    downloadCard();
    setCopiedField("instagram-share");
    setTimeout(() => setCopiedField(null), 3000);
  };

  const shareOnFacebook = () => {
    const shareUrl = posts?.facebook?.reportLink || reportUrl;
    const text = posts?.facebook?.post
      ? encodeURIComponent(posts.facebook.post)
      : "";
    window.open(
      `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}&quote=${text}`,
      "_blank",
      "width=600,height=400"
    );
  };

  const shareOnTwitter = () => {
    const shareUrl = posts?.twitter?.reportLink || reportUrl;
    const text = posts?.twitter?.tweet
      ? encodeURIComponent(posts.twitter.tweet)
      : "";
    window.open(
      `https://twitter.com/intent/tweet?text=${text}&url=${encodeURIComponent(shareUrl)}`,
      "_blank",
      "width=600,height=400"
    );
  };

  const REPORT_LABELS: Record<string, string> = {
    margin: "Price Optimization",
    traffic: "Foot Traffic Forecast",
    seo: "Google Presence Check",
    competitive: "Competitive Analysis",
    marketing: "Social Media Health Check",
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
      <div className="relative w-full max-w-lg mx-4 mb-4 sm:mb-0 bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden animate-slide-in-up">
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
        <div className="px-5 py-4 max-h-[70vh] overflow-y-auto space-y-5">
          {/* Social Card Image Preview */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <ImageIcon className="w-4 h-4 text-gray-500" />
              <span className="text-xs font-bold text-gray-700 uppercase tracking-wide">
                Share Image
              </span>
            </div>
            {cardLoading ? (
              <div className="w-full aspect-[1200/630] bg-gray-100 rounded-xl animate-pulse flex items-center justify-center">
                <Loader2 className="w-5 h-5 text-gray-300 animate-spin" />
              </div>
            ) : cardImageUrl ? (
              <div className="relative group">
                <img
                  src={cardImageUrl}
                  alt="Social card preview"
                  className="w-full rounded-xl border border-gray-200 shadow-sm"
                />
                <button
                  onClick={downloadCard}
                  className="absolute bottom-2 right-2 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/90 backdrop-blur-sm text-xs font-semibold text-gray-700 border border-gray-200 shadow-sm opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <Download size={12} />
                  Download
                </button>
              </div>
            ) : null}
          </div>

          {loading && (
            <div className="flex flex-col items-center justify-center py-6 gap-3">
              <Loader2 className="w-6 h-6 text-indigo-500 animate-spin" />
              <p className="text-sm text-gray-500 font-medium">
                Crafting your social posts...
              </p>
            </div>
          )}

          {error && !loading && (
            <div className="flex flex-col items-center justify-center py-6 gap-3">
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
                  <ReportLinkBadge url={posts.instagram.reportLink || ""} />
                  <CardPreview url={posts.instagram.imageUrl} />
                </div>
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => {
                      const full = (posts.instagram.caption || '') + (posts.instagram.reportLink ? `\n\n${posts.instagram.reportLink}` : '');
                      copyText(full, "instagram");
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gradient-to-r from-purple-50 to-pink-50 border border-purple-100 text-xs font-semibold text-purple-700 hover:from-purple-100 hover:to-pink-100 transition-all"
                  >
                    {copiedField === "instagram" ? (
                      <>
                        <Check size={12} className="text-green-600" />
                        Copied!
                      </>
                    ) : (
                      <>
                        <Copy size={12} />
                        Copy Caption + Link
                      </>
                    )}
                  </button>
                  <button
                    onClick={shareOnInstagram}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gradient-to-r from-purple-500 via-pink-500 to-orange-400 text-xs font-semibold text-white hover:opacity-90 transition-all"
                  >
                    {copiedField === "instagram-share" ? (
                      <>
                        <Check size={12} />
                        Caption copied & image downloaded!
                      </>
                    ) : (
                      <>
                        <Instagram size={12} />
                        Share on Instagram
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* X / Twitter */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-6 h-6 rounded-lg bg-black flex items-center justify-center">
                    <XLogo size={13} />
                  </div>
                  <span className="text-xs font-bold text-gray-700 uppercase tracking-wide">
                    X / Twitter
                  </span>
                </div>
                <div className="bg-gray-50 rounded-xl border border-gray-100 p-3.5">
                  <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                    {posts.twitter.tweet}
                  </p>
                  <span className="text-[11px] text-gray-400 mt-1.5 block">
                    {(posts.twitter.tweet || '').length}/280 characters
                  </span>
                  {posts.twitter.reportLink && (
                    <div className="mt-2 p-2.5 rounded-lg border border-gray-200 bg-white">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded bg-indigo-100 flex items-center justify-center flex-shrink-0">
                          <Link2 size={14} className="text-indigo-500" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-[11px] font-semibold text-gray-800 truncate">Hephae Report</p>
                          <p className="text-[10px] text-gray-400 truncate">{posts.twitter.reportLink}</p>
                        </div>
                      </div>
                    </div>
                  )}
                  <CardPreview url={posts.twitter.imageUrl} />
                </div>
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() =>
                      copyText(posts.twitter.tweet || '', "twitter")
                    }
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gray-50 border border-gray-200 text-xs font-semibold text-gray-700 hover:bg-gray-100 transition-all"
                  >
                    {copiedField === "twitter" ? (
                      <>
                        <Check size={12} className="text-green-600" />
                        Copied!
                      </>
                    ) : (
                      <>
                        <Copy size={12} />
                        Copy Tweet
                      </>
                    )}
                  </button>
                  <button
                    onClick={shareOnTwitter}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-black text-xs font-semibold text-white hover:bg-gray-800 transition-all"
                  >
                    <XLogo size={12} />
                    Share on X
                  </button>
                </div>
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
                  <ReportLinkBadge url={posts.facebook.reportLink || ""} />
                  <CardPreview url={posts.facebook.imageUrl} />
                </div>
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => {
                      const full = (posts.facebook.post || '') + (posts.facebook.reportLink ? `\n\n${posts.facebook.reportLink}` : '');
                      copyText(full, "facebook");
                    }}
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
                        Copy Post + Link
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
