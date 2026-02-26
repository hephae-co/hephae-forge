import { LlmAgent, FunctionTool } from "@google/adk";
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
    description: 'An elite Technical SEO Auditor capable of analyzing websites using Google Search capabilities to verify technical health, web vitals, content integrity, and authority metrics.',
    instruction: `You are an elite Technical SEO Auditor. Your task is to perform a comprehensive Deep Dive analysis on the provided URL.
    
    You must evaluate the website across all five core categories:
    ${SCAN_CATEGORIES.map(c => `- ID: "${c.id}" (Title: ${c.title})`).join('\n')}
    
    **PROTOCOL:**
    1. **SEARCH:** Use your 'googleSearch' tool to validate claims (e.g., "site:URL" for indexing status, "link:URL" or brand search for authority). 
    2. **THINK:** Evaluate specific checks for all 5 categories.
    3. **REPORT:** Once you have synthesized your research, yield a structured JSON payload encompassing:
       - 'overallScore' (0-100)
       - 'summary' (1-2 sentence overview)
       - 'sections' (An array mapping exactly to the 5 'id' categories provided above)
       
       For each section, you MUST provide 'id', 'title', 'score', 'description', detailed 'recommendations', and your internal 'methodology' showing precisely what checks were performed.
       
       OUTPUT STRICTLY VALID JSON! NO MARKDOWN. NO CODE BLOCKS.`,
    model: 'gemini-2.5-pro',
    temperature: 0.2,
    tools: [
        new FunctionTool({
            name: 'googleSearch',
            description: 'Execute a Google Search to analyze indexing, web vitals, backlinks, or content.',
            parameters: z.object({ query: z.string() }),
            execute: async ({ query }) => {
                return { result: `Search executed for ${query}.` };
            }
        })
    ]
});
