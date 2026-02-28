import { AgentModels } from "../config";
import { LlmAgent, FunctionTool } from "@google/adk";
import { GoogleGenerativeAI } from "@google/generative-ai";
import { z } from "zod";

const SCAN_CATEGORIES = [
    { id: 'technical', title: 'Technical SEO' },
    { id: 'content', title: 'Content Quality' },
    { id: 'ux', title: 'User Experience' },
    { id: 'performance', title: 'Performance' },
    { id: 'authority', title: 'Backlinks & Authority' }
];

export const SeoAuditorAgent = new LlmAgent({
    name: 'seoAuditor',
    description: 'An elite Technical SEO Auditor capable of analyzing websites using Google Search and PageSpeed Insights to verify technical health, web vitals, content integrity, and authority metrics.',
    instruction: `You are an elite Technical SEO Auditor. Your task is to perform a comprehensive Deep Dive analysis on the provided URL.

    You must evaluate the website across all five core categories:
    ${SCAN_CATEGORIES.map(c => `- ID: "${c.id}" (Title: ${c.title})`).join('\n')}

    **PROTOCOL:**
    1. **PERFORMANCE AUDIT:** Call 'auditWebPerformance' with the target URL to get quantitative Lighthouse scores and Core Web Vitals. Use these numbers in Performance, Technical, and UX sections.
    2. **IF auditWebPerformance FAILS (e.g., 429 rate limit or any error):** Do NOT abort. Continue the audit using only 'googleSearch'. For Performance/Technical/UX sections: assign estimated scores based on common patterns for this type of site, and provide specific actionable recommendations (optimize images, reduce render-blocking JS, enable caching, etc.) based on what you can infer from a search of the site.
    3. **SEARCH:** Use 'googleSearch' for qualitative checks regardless of whether PageSpeed succeeded: "site:URL" for indexing, brand search for authority, competitor searches for Content and Authority sections. Always complete Content and Authority sections — they do not depend on PageSpeed.
    4. **NEVER RETURN ALL ZEROS:** If a tool fails, provide partial analysis and best-practice recommendations for that section. A partial report with estimated scores is always more useful than a blank report.
    5. **REPORT:** Once you have synthesized your research, yield a structured JSON payload encompassing:
       - 'overallScore' (0-100)
       - 'summary' (1-2 sentence overview)
       - 'sections' (An array mapping exactly to the 5 'id' categories provided above)

       For each section, you MUST provide 'id', 'title', 'score', 'description', detailed 'recommendations', and your internal 'methodology' showing precisely what checks were performed.

       OUTPUT STRICTLY VALID JSON! NO MARKDOWN. NO CODE BLOCKS.`,
    model: AgentModels.DEEP_ANALYST_MODEL,

    tools: [
        new FunctionTool({
            name: 'googleSearch',
            description: 'Execute a Google Search to analyze indexing, backlinks, content, or authority.',
            parameters: z.object({ query: z.string() }),
            execute: async ({ query }) => {
                try {
                    const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
                    const model = genAI.getGenerativeModel({
                        model: AgentModels.DEFAULT_FAST_MODEL,
                        tools: [{ googleSearch: {} } as any]
                    });
                    const result = await model.generateContent(`Search and summarize: ${query}`);
                    return { result: result.response.text() };
                } catch (e: any) {
                    return { error: `Search failed: ${e.message}` };
                }
            }
        }),
        new FunctionTool({
            name: 'auditWebPerformance',
            description: 'Run a PageSpeed Insights (Lighthouse) audit on a URL to get quantitative performance scores and Core Web Vitals. Call this first for any SEO audit.',
            parameters: z.object({ url: z.string().describe('The full URL to audit (e.g. https://example.com)') }),
            execute: async ({ url }) => {
                try {
                    const apiUrl = `https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=${encodeURIComponent(url)}&strategy=mobile`;
                    const res = await fetch(apiUrl);
                    if (!res.ok) {
                        return { error: `PageSpeed API returned ${res.status}` };
                    }
                    const data = await res.json();

                    const cats = data?.lighthouseResult?.categories ?? {};
                    const audits = data?.lighthouseResult?.audits ?? {};

                    const scores = {
                        performance: Math.round((cats.performance?.score ?? 0) * 100),
                        seo: Math.round((cats.seo?.score ?? 0) * 100),
                        accessibility: Math.round((cats.accessibility?.score ?? 0) * 100),
                        bestPractices: Math.round((cats['best-practices']?.score ?? 0) * 100),
                    };

                    const coreWebVitals = {
                        lcp: audits['largest-contentful-paint']?.displayValue ?? null,
                        cls: audits['cumulative-layout-shift']?.displayValue ?? null,
                        fcp: audits['first-contentful-paint']?.displayValue ?? null,
                        ttfb: audits['server-response-time']?.displayValue ?? null,
                        speedIndex: audits['speed-index']?.displayValue ?? null,
                        tbt: audits['total-blocking-time']?.displayValue ?? null,
                    };

                    // Top failing audits (score < 0.9)
                    const topIssues = Object.values(audits)
                        .filter((a: any) => a.score !== null && a.score < 0.9 && a.title)
                        .sort((a: any, b: any) => (a.score ?? 1) - (b.score ?? 1))
                        .slice(0, 8)
                        .map((a: any) => ({
                            id: a.id,
                            title: a.title,
                            description: a.description?.split('.')[0] ?? '',
                            score: a.score,
                            displayValue: a.displayValue ?? null,
                        }));

                    return { url, scores, coreWebVitals, topIssues, source: 'PageSpeed Insights (Lighthouse Mobile)' };
                } catch (e: any) {
                    return { error: `PageSpeed audit failed: ${e.message}` };
                }
            }
        })
    ]
});
