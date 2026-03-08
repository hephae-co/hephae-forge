'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Loader2, Trash2, Send, ChevronDown, ChevronRight,
  Twitter, Instagram, Facebook, FileText, RefreshCw, X,
  Sparkles,
} from 'lucide-react';

type Platform = 'x' | 'instagram' | 'facebook' | 'blog';
type ContentStatus = 'draft' | 'published' | 'failed';
type SourceType = 'zipcode_research' | 'area_research' | 'combined_context';

interface ContentPost {
  id: string;
  type: string;
  platform: Platform;
  status: ContentStatus;
  sourceType: SourceType;
  sourceId: string;
  sourceLabel: string;
  content: string;
  title: string | null;
  hashtags: string[];
  publishedAt: string | null;
  createdAt: string;
  updatedAt: string;
  platformPostId: string | null;
  error: string | null;
}

interface SourceOption {
  id: string;
  label: string;
  type: SourceType;
}

const PLATFORM_CONFIG: Record<Platform, { label: string; icon: typeof Twitter; color: string; bg: string; border: string; maxLength: number | null }> = {
  x: { label: 'X', icon: Twitter, color: 'text-gray-900', bg: 'bg-gray-100', border: 'border-gray-300', maxLength: 280 },
  instagram: { label: 'Instagram', icon: Instagram, color: 'text-pink-600', bg: 'bg-pink-50', border: 'border-pink-200', maxLength: 2200 },
  facebook: { label: 'Facebook', icon: Facebook, color: 'text-blue-600', bg: 'bg-blue-50', border: 'border-blue-200', maxLength: 63206 },
  blog: { label: 'Blog', icon: FileText, color: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-200', maxLength: null },
};

const STATUS_STYLES: Record<ContentStatus, string> = {
  draft: 'bg-gray-100 text-gray-600',
  published: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
};

function PlatformIcon({ platform, className }: { platform: Platform; className?: string }) {
  const cfg = PLATFORM_CONFIG[platform];
  const Icon = cfg.icon;
  return <Icon className={className || 'w-4 h-4'} />;
}

export default function ContentStudio() {
  // Creator state
  const [platform, setPlatform] = useState<Platform>('x');
  const [sources, setSources] = useState<SourceOption[]>([]);
  const [selectedSource, setSelectedSource] = useState('');
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);

  // Draft preview state
  const [draft, setDraft] = useState<ContentPost | null>(null);
  const [editContent, setEditContent] = useState('');
  const [editTitle, setEditTitle] = useState('');
  const [editHashtags, setEditHashtags] = useState('');
  const [publishing, setPublishing] = useState(false);
  const [saving, setSaving] = useState(false);

  // History state
  const [posts, setPosts] = useState<ContentPost[]>([]);
  const [loadingPosts, setLoadingPosts] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Load research sources
  useEffect(() => {
    const load = async () => {
      const opts: SourceOption[] = [];
      try {
        const [zipRes, areaRes, ctxRes] = await Promise.allSettled([
          fetch('/api/zipcode-research/runs?limit=20'),
          fetch('/api/area-research?limit=20'),
          fetch('/api/combined-context?limit=10'),
        ]);
        if (zipRes.status === 'fulfilled' && zipRes.value.ok) {
          const data = await zipRes.value.json();
          for (const r of data) {
            opts.push({ id: r.id, label: `Zip ${r.zipCode}`, type: 'zipcode_research' });
          }
        }
        if (areaRes.status === 'fulfilled' && areaRes.value.ok) {
          const data = await areaRes.value.json();
          for (const r of data) {
            opts.push({ id: r.id, label: `${r.area} (${r.businessType})`, type: 'area_research' });
          }
        }
        if (ctxRes.status === 'fulfilled' && ctxRes.value.ok) {
          const data = await ctxRes.value.json();
          for (const r of data) {
            const zips = r.sourceZipCodes?.join(', ') || r.id.slice(0, 8);
            opts.push({ id: r.id, label: `Combined: ${zips}`, type: 'combined_context' });
          }
        }
      } catch { /* silent */ }
      setSources(opts);
    };
    load();
  }, []);

  const fetchPosts = useCallback(async () => {
    setLoadingPosts(true);
    try {
      const res = await fetch('/api/content?limit=50');
      if (res.ok) setPosts(await res.json());
    } catch { /* silent */ }
    finally { setLoadingPosts(false); }
  }, []);

  useEffect(() => { fetchPosts(); }, [fetchPosts]);

  // Generate content
  const handleGenerate = async () => {
    if (!selectedSource) return;
    const src = sources.find(s => `${s.type}:${s.id}` === selectedSource);
    if (!src) return;

    setGenerating(true);
    setGenError(null);
    setDraft(null);
    try {
      const res = await fetch('/api/content/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          platform,
          sourceType: src.type,
          sourceId: src.id,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Generation failed' }));
        throw new Error(err.detail || 'Generation failed');
      }
      const data = await res.json();
      const post = data.post as ContentPost;
      setDraft(post);
      setEditContent(post.content);
      setEditTitle(post.title || '');
      setEditHashtags(post.hashtags.join(', '));
      fetchPosts();
    } catch (e: any) {
      setGenError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  // Save draft edits
  const handleSaveDraft = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      const hashtags = editHashtags
        .split(',')
        .map(h => h.trim())
        .filter(Boolean);
      await fetch(`/api/content/${draft.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: editContent,
          title: editTitle || null,
          hashtags,
        }),
      });
      setDraft(prev => prev ? { ...prev, content: editContent, title: editTitle, hashtags } : null);
    } catch { /* silent */ }
    finally { setSaving(false); }
  };

  // Publish
  const handlePublish = async () => {
    if (!draft) return;
    // Save first if changed
    await handleSaveDraft();
    setPublishing(true);
    try {
      const res = await fetch(`/api/content/${draft.id}/publish`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setDraft(null);
        fetchPosts();
      } else {
        setGenError(data.error || 'Publish failed');
        fetchPosts();
      }
    } catch (e: any) {
      setGenError(e.message);
    } finally {
      setPublishing(false);
    }
  };

  // Discard draft
  const handleDiscard = async () => {
    if (!draft) return;
    try {
      await fetch(`/api/content/${draft.id}`, { method: 'DELETE' });
    } catch { /* silent */ }
    setDraft(null);
    fetchPosts();
  };

  // Delete from history
  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      const res = await fetch(`/api/content/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setPosts(prev => prev.filter(p => p.id !== id));
        if (expandedId === id) setExpandedId(null);
      }
    } catch { /* silent */ }
    finally { setDeletingId(null); setConfirmingId(null); }
  };

  const platformCfg = PLATFORM_CONFIG[platform];
  const charCount = editContent.length;
  const maxLen = platformCfg.maxLength;
  const overLimit = maxLen !== null && charCount > maxLen;

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-8">
      {/* Section A: Content Creator */}
      <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
        <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-indigo-500" />
          Content Creator
        </h3>

        {/* Platform selector */}
        <div className="mb-5">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 block">Platform</label>
          <div className="flex gap-2">
            {(Object.keys(PLATFORM_CONFIG) as Platform[]).map(p => {
              const cfg = PLATFORM_CONFIG[p];
              const Icon = cfg.icon;
              const active = platform === p;
              return (
                <button
                  key={p}
                  onClick={() => setPlatform(p)}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold border transition-all ${
                    active
                      ? `${cfg.bg} ${cfg.color} ${cfg.border} shadow-sm`
                      : 'bg-white text-gray-400 border-gray-200 hover:border-gray-300 hover:text-gray-600'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {cfg.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Research source selector */}
        <div className="mb-5">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 block">Research Source</label>
          <select
            value={selectedSource}
            onChange={e => setSelectedSource(e.target.value)}
            className="w-full px-4 py-2.5 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
          >
            <option value="">Select research data...</option>
            {sources.filter(s => s.type === 'zipcode_research').length > 0 && (
              <optgroup label="Zip Code Research">
                {sources.filter(s => s.type === 'zipcode_research').map(s => (
                  <option key={s.id} value={`${s.type}:${s.id}`}>{s.label}</option>
                ))}
              </optgroup>
            )}
            {sources.filter(s => s.type === 'area_research').length > 0 && (
              <optgroup label="Area Research">
                {sources.filter(s => s.type === 'area_research').map(s => (
                  <option key={s.id} value={`${s.type}:${s.id}`}>{s.label}</option>
                ))}
              </optgroup>
            )}
            {sources.filter(s => s.type === 'combined_context').length > 0 && (
              <optgroup label="Combined Contexts">
                {sources.filter(s => s.type === 'combined_context').map(s => (
                  <option key={s.id} value={`${s.type}:${s.id}`}>{s.label}</option>
                ))}
              </optgroup>
            )}
          </select>
        </div>

        {/* Generate button */}
        <button
          onClick={handleGenerate}
          disabled={!selectedSource || generating}
          className="px-6 py-2.5 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2 shadow-md"
        >
          {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          {generating ? 'Generating...' : 'Generate'}
        </button>

        {genError && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
            {genError}
          </div>
        )}
      </div>

      {/* Section B: Draft Preview */}
      {draft && (
        <div className="bg-white border border-indigo-200 rounded-xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
              <PlatformIcon platform={draft.platform} className="w-5 h-5" />
              Draft Preview
              <span className="text-xs font-normal text-gray-400">({PLATFORM_CONFIG[draft.platform].label})</span>
            </h3>
            <span className="text-xs bg-gray-100 text-gray-500 px-2 py-1 rounded">{draft.sourceLabel}</span>
          </div>

          {/* Title (blog only) */}
          {draft.platform === 'blog' && (
            <div className="mb-4">
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1 block">Title</label>
              <input
                type="text"
                value={editTitle}
                onChange={e => setEditTitle(e.target.value)}
                className="w-full px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
                placeholder="Blog title..."
              />
            </div>
          )}

          {/* Content textarea */}
          <div className="mb-4">
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Content</label>
              {maxLen !== null && (
                <span className={`text-xs font-mono ${overLimit ? 'text-red-500 font-bold' : 'text-gray-400'}`}>
                  {charCount}/{maxLen}
                </span>
              )}
            </div>
            <textarea
              value={editContent}
              onChange={e => setEditContent(e.target.value)}
              rows={draft.platform === 'blog' ? 12 : 5}
              className={`w-full px-4 py-3 bg-gray-50 border rounded-lg text-sm font-mono leading-relaxed resize-y focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 ${
                overLimit ? 'border-red-300 bg-red-50' : 'border-gray-200'
              }`}
            />
          </div>

          {/* Hashtags */}
          <div className="mb-6">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1 block">Hashtags</label>
            <div className="flex items-center gap-2 flex-wrap mb-2">
              {editHashtags.split(',').filter(h => h.trim()).map((h, i) => (
                <span key={i} className="text-xs bg-indigo-50 text-indigo-600 px-2 py-1 rounded-full border border-indigo-200">
                  #{h.trim().replace(/^#/, '')}
                </span>
              ))}
            </div>
            <input
              type="text"
              value={editHashtags}
              onChange={e => setEditHashtags(e.target.value)}
              className="w-full px-4 py-2 bg-white border border-gray-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
              placeholder="Comma-separated hashtags..."
            />
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3">
            <button
              onClick={handlePublish}
              disabled={publishing || overLimit}
              className="px-5 py-2.5 bg-emerald-600 text-white font-semibold rounded-lg hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2 shadow-md"
            >
              {publishing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              {publishing ? 'Publishing...' : 'Publish'}
            </button>
            <button
              onClick={handleSaveDraft}
              disabled={saving}
              className="px-4 py-2.5 bg-white text-gray-600 font-semibold rounded-lg border border-gray-200 hover:border-gray-300 hover:text-gray-800 transition-all flex items-center gap-2"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              Save Draft
            </button>
            <button
              onClick={handleDiscard}
              className="px-4 py-2.5 text-gray-400 hover:text-red-500 font-semibold rounded-lg transition-colors flex items-center gap-2"
            >
              <X className="w-4 h-4" />
              Discard
            </button>
          </div>
        </div>
      )}

      {/* Section C: Content History */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <FileText className="w-5 h-5 text-indigo-500" />
            Content History
          </h3>
          <button
            onClick={fetchPosts}
            className="text-xs text-gray-500 hover:text-gray-700 px-3 py-1.5 rounded border border-gray-200 hover:border-gray-300 transition-colors flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" /> Refresh
          </button>
        </div>

        {loadingPosts && (
          <div className="text-center py-8">
            <Loader2 className="w-5 h-5 animate-spin mx-auto text-gray-400" />
          </div>
        )}

        {!loadingPosts && posts.length === 0 && (
          <div className="text-center py-16 border border-dashed border-gray-300 rounded-xl text-gray-400">
            <FileText className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p>No content yet. Generate your first post above.</p>
          </div>
        )}

        {!loadingPosts && posts.length > 0 && (
          <div className="space-y-2">
            {posts.map(post => {
              const isExpanded = expandedId === post.id;
              const isConfirming = confirmingId === post.id;
              const isDeleting = deletingId === post.id;
              const cfg = PLATFORM_CONFIG[post.platform];

              return (
                <div
                  key={post.id}
                  className={`relative bg-white border rounded-lg transition-all ${
                    isConfirming ? 'border-red-200 bg-red-50' : 'border-gray-200 hover:shadow-md hover:border-gray-300'
                  }`}
                >
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : post.id)}
                    className="w-full text-left p-4"
                    disabled={isConfirming || isDeleting}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {isExpanded
                          ? <ChevronDown className="w-4 h-4 text-gray-400" />
                          : <ChevronRight className="w-4 h-4 text-gray-400" />
                        }
                        <span className={`p-1.5 rounded ${cfg.bg}`}>
                          <PlatformIcon platform={post.platform} className={`w-3.5 h-3.5 ${cfg.color}`} />
                        </span>
                        <span className="text-sm font-medium text-gray-700 truncate max-w-xs">
                          {post.title || post.content.slice(0, 60) + (post.content.length > 60 ? '...' : '')}
                        </span>
                        <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${STATUS_STYLES[post.status]}`}>
                          {post.status}
                        </span>
                      </div>
                      <span className="text-xs text-gray-400 whitespace-nowrap ml-4">
                        {new Date(post.createdAt).toLocaleDateString()} {new Date(post.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  </button>

                  {/* Delete button */}
                  {post.status !== 'published' && !isConfirming && !isDeleting && (
                    <button
                      onClick={(e) => { e.stopPropagation(); setConfirmingId(post.id); }}
                      className="absolute top-4 right-4 p-1.5 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}

                  {isConfirming && !isDeleting && (
                    <div className="mx-4 mb-4 flex items-center gap-3 pt-3 border-t border-red-200">
                      <span className="text-xs text-red-500">Delete this post?</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(post.id); }}
                        className="px-3 py-1 text-xs font-semibold bg-red-600 text-white rounded hover:bg-red-500 transition-colors"
                      >
                        Confirm
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); setConfirmingId(null); }}
                        className="px-3 py-1 text-xs text-gray-500 hover:text-gray-700 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  )}

                  {isDeleting && (
                    <div className="mx-4 mb-4 flex items-center gap-2 pt-3 border-t border-red-200">
                      <Loader2 className="w-3 h-3 animate-spin text-red-500" />
                      <span className="text-xs text-red-500">Deleting...</span>
                    </div>
                  )}

                  {/* Expanded content */}
                  {isExpanded && (
                    <div className="px-4 pb-4 border-t border-gray-100 space-y-3 mt-1">
                      <div className="text-xs text-gray-400 mt-3">
                        Source: {post.sourceLabel}
                      </div>
                      {post.title && (
                        <h4 className="text-base font-bold text-gray-800">{post.title}</h4>
                      )}
                      <div className="p-3 bg-gray-50 border border-gray-100 rounded-lg">
                        <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{post.content}</p>
                      </div>
                      {post.hashtags.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {post.hashtags.map((h, i) => (
                            <span key={i} className="text-xs bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full border border-indigo-200">
                              #{h.replace(/^#/, '')}
                            </span>
                          ))}
                        </div>
                      )}
                      {post.error && (
                        <div className="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-600">
                          {post.error}
                        </div>
                      )}
                      {post.platformPostId && (
                        <div className="text-xs text-gray-400">
                          Platform Post ID: <span className="font-mono">{post.platformPostId}</span>
                        </div>
                      )}
                      {post.publishedAt && (
                        <div className="text-xs text-gray-400">
                          Published: {new Date(post.publishedAt).toLocaleString()}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
