import { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Blog | Hephae',
  description: 'Data-driven insights for local businesses — powered by BLS, Census, and AI analysis.',
};

interface BlogPost {
  id: string;
  title: string;
  blogUrl: string;
  hashtags: string[];
  wordCount: number;
  chartCount: number;
  publishedAt: string;
  slug?: string;
}

async function fetchPosts(): Promise<BlogPost[]> {
  const backendUrl = process.env.BACKEND_URL || 'http://localhost:8080';
  try {
    const res = await fetch(`${backendUrl}/api/blog/posts?limit=20`, {
      next: { revalidate: 300 }, // revalidate every 5 minutes
    });
    if (!res.ok) return [];
    const data = await res.json();
    return (data || [])
      .filter((p: any) => p.status === 'published' && p.blogUrl)
      .map((p: any) => ({
        id: p.id,
        title: p.title || 'Untitled',
        blogUrl: p.blogUrl,
        hashtags: p.hashtags || [],
        wordCount: p.wordCount || 0,
        chartCount: p.chartCount || 0,
        publishedAt: p.publishedAt || '',
        slug: extractSlug(p.blogUrl),
      }));
  } catch {
    return [];
  }
}

function extractSlug(blogUrl: string): string {
  // https://cdn.hephae.co/reports/nutley-restaurants-march-2026/blog-123.html → nutley-restaurants-march-2026
  const match = blogUrl.match(/\/reports\/([^/]+)\//);
  return match?.[1] || '';
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
  } catch {
    return '';
  }
}

function estimateReadTime(wordCount: number): string {
  const minutes = Math.max(1, Math.ceil(wordCount / 250));
  return `${minutes} min read`;
}

export default async function BlogListPage() {
  const posts = await fetchPosts();

  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <span className="text-xl font-bold text-slate-900">Hephae</span>
            <span className="text-amber-600 text-sm font-medium">Blog</span>
          </Link>
          <Link
            href="/"
            className="text-sm text-slate-500 hover:text-amber-600 transition-colors"
          >
            ← Back to Hephae
          </Link>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-12">
        <h1 className="text-4xl font-bold text-slate-900 mb-2">
          Intelligence for Local Businesses
        </h1>
        <p className="text-lg text-slate-500 mb-10">
          Data-driven analysis powered by BLS, Census, FDA, and 12+ government data sources.
        </p>

        {posts.length === 0 ? (
          <div className="text-center py-20 text-slate-400">
            <p className="text-lg">No posts yet — check back soon.</p>
          </div>
        ) : (
          <div className="space-y-8">
            {posts.map((post) => (
              <article
                key={post.id}
                className="group border border-slate-200 rounded-xl p-6 hover:border-amber-300 hover:shadow-md transition-all bg-white"
              >
                <Link href={`/blog/${post.slug}`} className="block">
                  <h2 className="text-xl font-semibold text-slate-900 group-hover:text-amber-700 transition-colors mb-2">
                    {post.title}
                  </h2>
                  <div className="flex items-center gap-4 text-sm text-slate-400 mb-3">
                    {post.publishedAt && (
                      <time dateTime={post.publishedAt}>
                        {formatDate(post.publishedAt)}
                      </time>
                    )}
                    {post.wordCount > 0 && <span>{estimateReadTime(post.wordCount)}</span>}
                    {post.chartCount > 0 && (
                      <span className="flex items-center gap-1">
                        📊 {post.chartCount} charts
                      </span>
                    )}
                  </div>
                  {post.hashtags.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {post.hashtags.slice(0, 5).map((tag) => (
                        <span
                          key={tag}
                          className="text-xs bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </Link>
              </article>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="border-t border-slate-200 mt-16 py-8 text-center text-sm text-slate-400">
        <p>
          © {new Date().getFullYear()} Hephae Intelligence ·{' '}
          <Link href="/" className="text-amber-600 hover:underline">
            hephae.co
          </Link>
        </p>
      </footer>
    </main>
  );
}
