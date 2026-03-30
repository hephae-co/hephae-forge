import { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Case Studies | Hephae — AI Business Intelligence',
  description: 'Real-world examples of how local businesses use Hephae to uncover hidden opportunities in SEO, margins, and competitive positioning.',
  keywords: ['case studies', 'local business', 'AI analysis', 'SMB intelligence', 'business growth'],
  openGraph: {
    title: 'Hephae Case Studies — Real Business Intelligence Stories',
    description: 'Discover how local businesses leverage AI-driven insights to grow revenue and reduce costs.',
    type: 'website',
    url: 'https://hephae.co/case-studies',
    siteName: 'Hephae',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Hephae Case Studies',
    description: 'Real-world AI business intelligence for local companies.',
  },
  alternates: {
    canonical: 'https://hephae.co/case-studies',
  },
};

interface CaseStudy {
  id: string;
  slug: string;
  businessName: string;
  location: string;
  industry: string;
  publishedAt: string;
  excerpt: string;
  metrics: {
    seoScore?: number;
    marginOpportunity?: string;
    competitorCount?: number;
  };
}

// Mock case studies — in production, fetch from API
async function fetchCaseStudies(): Promise<CaseStudy[]> {
  return [
    {
      id: 'meal-07110',
      slug: 'meal-restaurant-newark-07110',
      businessName: 'Meal Restaurant',
      location: 'Newark, NJ 07110',
      industry: 'Food & Beverage',
      publishedAt: '2026-03-29',
      excerpt:
        'A local restaurant leveraged AI-driven SEO optimization and competitive analysis to identify $50K+ in annual margin recovery opportunities across menu pricing and operational efficiency.',
      metrics: {
        seoScore: 62,
        marginOpportunity: '$50K+ annually',
        competitorCount: 12,
      },
    },
  ];
}

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

export default async function CaseStudiesPage() {
  const caseStudies = await fetchCaseStudies();

  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <span className="text-xl font-bold text-slate-900">Hephae</span>
            <span className="text-amber-600 text-sm font-medium">Case Studies</span>
          </Link>
          <Link
            href="/"
            className="text-sm text-slate-500 hover:text-amber-600 transition-colors"
          >
            ← Back to Hephae
          </Link>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-16">
        {/* Hero */}
        <section className="mb-16">
          <h1 className="text-5xl font-bold text-slate-900 mb-4 leading-tight">
            Real Businesses, Real Results
          </h1>
          <p className="text-xl text-slate-600 mb-2">
            See how local companies discover hidden opportunities using Hephae's AI-driven intelligence.
          </p>
          <p className="text-lg text-slate-500">
            From SEO gaps to margin leaks — data-backed insights that drive growth.
          </p>
        </section>

        {/* Case Studies Grid */}
        {caseStudies.length === 0 ? (
          <div className="text-center py-20 text-slate-400">
            <p className="text-lg">Case studies coming soon.</p>
          </div>
        ) : (
          <div className="space-y-6">
            {caseStudies.map((study) => (
              <Link key={study.id} href={`/case-studies/${study.slug}`}>
                <article className="group border border-slate-200 rounded-2xl p-8 hover:border-amber-300 hover:shadow-lg transition-all bg-white cursor-pointer">
                  {/* Meta */}
                  <div className="flex items-center gap-3 mb-4">
                    <span className="inline-block px-3 py-1 bg-amber-50 text-amber-700 text-xs font-semibold rounded-full">
                      {study.industry}
                    </span>
                    <time dateTime={study.publishedAt} className="text-sm text-slate-400">
                      {formatDate(study.publishedAt)}
                    </time>
                  </div>

                  {/* Title & Location */}
                  <h2 className="text-2xl font-bold text-slate-900 group-hover:text-amber-700 transition-colors mb-2">
                    {study.businessName}
                  </h2>
                  <p className="text-slate-500 mb-4">{study.location}</p>

                  {/* Excerpt */}
                  <p className="text-slate-600 text-lg mb-6 line-clamp-2">
                    {study.excerpt}
                  </p>

                  {/* Metrics */}
                  <div className="grid grid-cols-3 gap-4">
                    {study.metrics.seoScore && (
                      <div className="bg-slate-50 rounded-lg p-4">
                        <div className="text-sm text-slate-500 mb-1">SEO Score</div>
                        <div className="text-2xl font-bold text-amber-600">
                          {study.metrics.seoScore}/100
                        </div>
                      </div>
                    )}
                    {study.metrics.marginOpportunity && (
                      <div className="bg-slate-50 rounded-lg p-4">
                        <div className="text-sm text-slate-500 mb-1">Margin Opportunity</div>
                        <div className="text-xl font-bold text-slate-900">
                          {study.metrics.marginOpportunity}
                        </div>
                      </div>
                    )}
                    {study.metrics.competitorCount && (
                      <div className="bg-slate-50 rounded-lg p-4">
                        <div className="text-sm text-slate-500 mb-1">Competitors</div>
                        <div className="text-2xl font-bold text-slate-900">
                          {study.metrics.competitorCount}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* CTA */}
                  <div className="mt-6 text-amber-600 font-semibold group-hover:gap-2 transition-all flex items-center gap-1">
                    Read Case Study →
                  </div>
                </article>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="border-t border-slate-200 mt-20 py-8 text-center text-sm text-slate-400">
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
