import { Metadata } from 'next';
import { notFound } from 'next/navigation';
import BusinessProfileClient from './client';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8080';

async function fetchProfile(slug: string) {
    try {
        const res = await fetch(`${BACKEND_URL}/api/b/${slug}/public`, {
            cache: 'no-store',
        });
        if (!res.ok) return null;
        return res.json();
    } catch {
        return null;
    }
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
    const { slug } = await params;
    const profile = await fetchProfile(slug);

    if (!profile) {
        return { title: 'Business Profile | Hephae' };
    }

    const name = profile.name || 'Business';
    const address = profile.address || '';
    const snapshot = profile.snapshot || {};
    const overview = snapshot.overview || {};
    const bs = overview.businessSnapshot || {};
    const dash = overview.dashboard || {};

    const ratingText = bs.rating ? `${bs.rating}/5 (${bs.reviewCount || '?'} reviews)` : '';
    const competitorText = dash.stats?.competitorCount ? `${dash.stats.competitorCount} competitors nearby` : '';
    const description = [
        `AI-powered business intelligence for ${name}${address ? ` in ${address}` : ''}.`,
        ratingText,
        competitorText,
        dash.topInsights?.[0]?.title || '',
    ].filter(Boolean).join(' · ');

    return {
        title: `${name} — Business Intelligence | Hephae`,
        description,
        openGraph: {
            title: `${name} — AI Business Intelligence`,
            description,
            type: 'article',
            url: `https://hephae.co/b/${slug}`,
        },
        twitter: {
            card: 'summary_large_image',
            title: `${name} — AI Business Intelligence`,
            description,
        },
    };
}

export default async function BusinessProfilePage({ params }: { params: Promise<{ slug: string }> }) {
    const { slug } = await params;
    const profile = await fetchProfile(slug);

    // Pass to client component which handles both public view and authenticated redirect
    return <BusinessProfileClient slug={slug} publicProfile={profile} />;
}
