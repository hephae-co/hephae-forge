import { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8080';

async function fetchCaseStudy(slug: string) {
  try {
    // Fetch from case studies API endpoint
    const res = await fetch(`${BACKEND_URL}/api/case-studies/${slug}`, {
      cache: 'no-store',
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;

  const profile = await fetchCaseStudy(slug);

  if (!profile) {
    return { title: 'Case Study | Hephae' };
  }

  const name = profile.name || 'Business';
  const address = profile.address || '';
  const overview = profile.snapshot?.overview || {};
  const bs = overview.businessSnapshot || {};
  const dash = overview.dashboard || {};
  const topInsight = dash.topInsights?.[0]?.title || '';

  const title = `${name} Case Study — AI Business Intelligence | Hephae`;
  const description = [
    `How ${name}${address ? ` in ${address}` : ''} leveraged Hephae to uncover hidden business opportunities.`,
    `Rating: ${bs.rating}/5. ${topInsight}`,
  ]
    .filter(Boolean)
    .join(' ');

  return {
    title,
    description,
    keywords: [
      'case study',
      'business intelligence',
      'AI analysis',
      'SEO optimization',
      'margin analysis',
      name,
    ],
    openGraph: {
      title: `${name} Case Study — Hephae`,
      description,
      type: 'article',
      url: `https://hephae.co/case-studies/${slug}`,
      siteName: 'Hephae',
    },
    twitter: {
      card: 'summary_large_image',
      title: `${name} Case Study — Hephae`,
      description,
    },
    alternates: {
      canonical: `https://hephae.co/case-studies/${slug}`,
    },
  };
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  } catch {
    return '';
  }
}

export default async function CaseStudyPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;

  const profile = await fetchCaseStudy(slug);

  if (!profile) {
    notFound();
  }

  const name = profile.name || 'Business';
  const address = profile.address || '';
  const snapshot = profile.snapshot || {};
  const overview = snapshot.overview || {};
  const bs = overview.businessSnapshot || {};
  const mp = overview.marketPosition || {};
  const dash = overview.dashboard || {};
  const seoReport = snapshot.seoReport || {};
  const marginReport = snapshot.marginReport || {};

  return (
    <main className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <span className="text-lg font-bold text-slate-900">Hephae</span>
          </Link>
          <Link
            href="/case-studies"
            className="text-sm text-slate-500 hover:text-amber-600 transition-colors"
          >
            ← Back to Case Studies
          </Link>
        </div>
      </header>

      <article className="max-w-3xl mx-auto px-6 py-12">
        {/* Hero Section */}
        <header className="mb-12">
          <div className="mb-4">
            <span className="inline-block px-3 py-1 bg-amber-50 text-amber-700 text-xs font-semibold rounded-full">
              Case Study
            </span>
          </div>

          <h1 className="text-5xl font-bold text-slate-900 mb-4 leading-tight">
            {name}
          </h1>

          <div className="flex items-center gap-6 text-slate-600 mb-8">
            <span className="flex items-center gap-2">
              📍 {address}
            </span>
            {bs.publishedAt && (
              <time dateTime={bs.publishedAt} className="text-slate-500">
                {formatDate(bs.publishedAt)}
              </time>
            )}
          </div>

          {/* Key Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8">
            {bs.rating && (
              <div className="bg-slate-50 rounded-lg p-4">
                <div className="text-sm text-slate-500 mb-1">Rating</div>
                <div className="text-2xl font-bold text-slate-900">
                  {bs.rating}/5
                </div>
                <div className="text-xs text-slate-400">
                  {bs.reviewCount || '?'} reviews
                </div>
              </div>
            )}
            {seoReport?.overallScore !== undefined && (
              <div className="bg-slate-50 rounded-lg p-4">
                <div className="text-sm text-slate-500 mb-1">SEO Score</div>
                <div className="text-2xl font-bold text-amber-600">
                  {seoReport.overallScore}/100
                </div>
              </div>
            )}
            {mp.competitorCount && (
              <div className="bg-slate-50 rounded-lg p-4">
                <div className="text-sm text-slate-500 mb-1">Competitors</div>
                <div className="text-2xl font-bold text-slate-900">
                  {mp.competitorCount}
                </div>
              </div>
            )}
          </div>
        </header>

        {/* Key Findings */}
        {dash.topInsights && dash.topInsights.length > 0 && (
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-slate-900 mb-6">Key Findings</h2>
            <div className="space-y-4">
              {dash.topInsights.slice(0, 3).map((insight: any, idx: number) => (
                <div
                  key={idx}
                  className="border-l-4 border-amber-500 bg-amber-50 p-4 rounded"
                >
                  <h3 className="font-semibold text-slate-900 mb-2">
                    {insight.title}
                  </h3>
                  <p className="text-slate-600">{insight.recommendation}</p>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* SEO Analysis */}
        {seoReport?.overallScore !== undefined && (
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-slate-900 mb-6">SEO Analysis</h2>
            <div className="bg-slate-50 rounded-lg p-8">
              <div className="grid grid-cols-2 gap-6 mb-6">
                <div>
                  <div className="text-sm text-slate-500 mb-1">Overall Score</div>
                  <div className="text-4xl font-bold text-amber-600">
                    {seoReport.overallScore}
                  </div>
                </div>
                {seoReport.mobileFriendly !== undefined && (
                  <div>
                    <div className="text-sm text-slate-500 mb-1">Mobile Friendly</div>
                    <div className="text-lg font-semibold text-slate-900">
                      {seoReport.mobileFriendly ? '✓ Yes' : '✗ No'}
                    </div>
                  </div>
                )}
              </div>

              {seoReport.recommendations && (
                <div>
                  <h3 className="font-semibold text-slate-900 mb-4">
                    Top Recommendations
                  </h3>
                  <ul className="space-y-2">
                    {seoReport.recommendations.slice(0, 5).map(
                      (rec: string, idx: number) => (
                        <li key={idx} className="flex gap-2 text-slate-600">
                          <span className="text-amber-600 font-bold">•</span>
                          {rec}
                        </li>
                      )
                    )}
                  </ul>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Margin Analysis */}
        {marginReport?.overall_score !== undefined && (
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-slate-900 mb-6">
              Margin Analysis
            </h2>
            <div className="bg-slate-50 rounded-lg p-8">
              <div className="mb-6">
                <div className="text-sm text-slate-500 mb-1">Profitability Score</div>
                <div className="text-4xl font-bold text-amber-600">
                  {marginReport.overall_score}/100
                </div>
              </div>

              {marginReport.opportunities && (
                <div>
                  <h3 className="font-semibold text-slate-900 mb-4">
                    Identified Opportunities
                  </h3>
                  <ul className="space-y-3">
                    {marginReport.opportunities.slice(0, 4).map(
                      (opp: any, idx: number) => (
                        <li key={idx} className="border-l-2 border-amber-300 pl-4">
                          <div className="font-semibold text-slate-900">
                            {opp.title || opp.category}
                          </div>
                          <p className="text-sm text-slate-600">
                            {opp.description || opp.detail}
                          </p>
                        </li>
                      )
                    )}
                  </ul>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Market Position */}
        {mp.saturationLevel && (
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-slate-900 mb-6">
              Market Position
            </h2>
            <div className="grid grid-cols-2 gap-6">
              <div className="bg-slate-50 rounded-lg p-6">
                <div className="text-sm text-slate-500 mb-2">Market Saturation</div>
                <div className="text-xl font-bold text-slate-900">
                  {mp.saturationLevel}
                </div>
              </div>
              {mp.marketShare && (
                <div className="bg-slate-50 rounded-lg p-6">
                  <div className="text-sm text-slate-500 mb-2">Market Share</div>
                  <div className="text-xl font-bold text-slate-900">
                    {mp.marketShare}
                  </div>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Recommendations */}
        <section className="mb-12 bg-amber-50 border border-amber-200 rounded-lg p-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Recommended Next Steps
          </h2>
          <ol className="space-y-3 list-decimal list-inside text-slate-600">
            <li>Implement SEO recommendations to improve search visibility</li>
            <li>Analyze pricing strategy against competitor benchmarks</li>
            <li>Review operational efficiency for cost reduction opportunities</li>
            <li>Monitor competitive landscape changes quarterly</li>
          </ol>
        </section>

        {/* CTA */}
        <section className="text-center py-8 border-t border-slate-200">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Ready to Get Intelligence for Your Business?
          </h2>
          <Link
            href="/"
            className="inline-block px-8 py-3 bg-amber-600 text-white font-semibold rounded-lg hover:bg-amber-700 transition-colors"
          >
            Start Your Analysis
          </Link>
        </section>
      </article>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-slate-50 py-8 text-center text-sm text-slate-400 mt-16">
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
