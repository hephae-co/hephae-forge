import { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';

interface BlogPost {
  id: string;
  title: string;
  content: string;
  blogUrl: string;
  hashtags: string[];
  wordCount: number;
  chartCount: number;
  publishedAt: string;
}

async function fetchPost(slug: string): Promise<BlogPost | null> {
  const backendUrl = process.env.BACKEND_URL || 'http://localhost:8080';
  try {
    const res = await fetch(`${backendUrl}/api/blog/by-slug/${slug}`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

async function fetchBlogHtml(blogUrl: string): Promise<string> {
  try {
    const res = await fetch(blogUrl, { next: { revalidate: 300 } });
    if (!res.ok) return '';
    const fullHtml = await res.text();

    // Extract just the article content from the full HTML page
    // The blog HTML is wrapped in <article>...</article> inside the template
    const articleMatch = fullHtml.match(/<article[^>]*>([\s\S]*?)<\/article>/);
    if (articleMatch) return articleMatch[1];

    // Fallback: return between <body> tags
    const bodyMatch = fullHtml.match(/<body[^>]*>([\s\S]*?)<\/body>/);
    return bodyMatch?.[1] || fullHtml;
  } catch {
    return '';
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const post = await fetchPost(slug);
  if (!post) return { title: 'Blog | Hephae' };

  const description = `${post.title} — Data-driven analysis by Hephae Intelligence.`;

  return {
    title: `${post.title} | Hephae Blog`,
    description,
    openGraph: {
      title: post.title,
      description,
      type: 'article',
      url: `https://hephae.co/blog/${slug}`,
    },
    twitter: {
      card: 'summary_large_image',
      title: post.title,
      description,
    },
  };
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric', month: 'long', day: 'numeric',
    });
  } catch { return ''; }
}

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const post = await fetchPost(slug);
  if (!post) notFound();

  // Fetch the rendered blog HTML from CDN
  const articleHtml = post.content || await fetchBlogHtml(post.blogUrl);

  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/blog" className="flex items-center gap-2">
            <span className="text-xl font-bold text-slate-900">Hephae</span>
            <span className="text-amber-600 text-sm font-medium">Blog</span>
          </Link>
          <Link
            href="/blog"
            className="text-sm text-slate-500 hover:text-amber-600 transition-colors"
          >
            ← All Posts
          </Link>
        </div>
      </header>

      <article className="max-w-3xl mx-auto px-6 py-12">
        {/* Article meta */}
        <div className="mb-8">
          {post.publishedAt && (
            <time dateTime={post.publishedAt} className="text-sm text-slate-400">
              {formatDate(post.publishedAt)}
            </time>
          )}
          {post.hashtags?.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {post.hashtags.map((tag) => (
                <span
                  key={tag}
                  className="text-xs bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Article content */}
        <div
          className="prose prose-slate prose-lg max-w-none
            prose-headings:text-slate-900 prose-h1:text-3xl prose-h1:font-bold prose-h1:mb-4
            prose-h2:text-xl prose-h2:font-semibold prose-h2:mt-10 prose-h2:border-b-2 prose-h2:border-amber-500 prose-h2:pb-2
            prose-p:text-slate-600 prose-p:leading-relaxed
            prose-a:text-amber-600 prose-a:no-underline hover:prose-a:underline
            prose-strong:text-slate-800
            prose-blockquote:border-l-amber-500 prose-blockquote:bg-amber-50 prose-blockquote:text-amber-900 prose-blockquote:rounded-r-lg prose-blockquote:py-3
            prose-li:text-slate-600"
          dangerouslySetInnerHTML={{ __html: articleHtml }}
        />

        {/* Share */}
        <div className="border-t border-slate-200 mt-12 pt-6 flex items-center gap-4">
          <span className="text-sm text-slate-400">Share:</span>
          <a
            href={`https://twitter.com/intent/tweet?text=${encodeURIComponent(post.title)}&url=${encodeURIComponent(`https://hephae.co/blog/${slug}`)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm px-3 py-1.5 bg-sky-500 text-white rounded-md hover:bg-sky-600"
          >
            Twitter/X
          </a>
          <a
            href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(`https://hephae.co/blog/${slug}`)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm px-3 py-1.5 bg-blue-700 text-white rounded-md hover:bg-blue-800"
          >
            LinkedIn
          </a>
        </div>
      </article>

      {/* CTA */}
      <section className="bg-amber-50 border-t border-amber-200 py-12 text-center">
        <h2 className="text-2xl font-bold text-slate-900 mb-2">
          Want insights like this for your business?
        </h2>
        <p className="text-slate-500 mb-6">
          Hephae analyzes your local market using 15+ government data sources every week.
        </p>
        <Link
          href="/"
          className="inline-block bg-amber-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-amber-700 transition-colors"
        >
          Try Hephae Free →
        </Link>
      </section>

      {/* Chart.js CDN — needed if article contains charts */}
      <script
        src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"
        async
      />

      {/* Footer */}
      <footer className="border-t border-slate-200 py-8 text-center text-sm text-slate-400">
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
