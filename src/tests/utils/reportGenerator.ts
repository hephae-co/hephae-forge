import fs from 'fs';
import path from 'path';

export async function generateMarkdownReport(results: any[]) {
    console.log("📝 Compiling pass/fail matrices into Markdown Report...");

    let md = `# Hephae Hub - Agentic Integration Test Report\n\n`;
    md += `**Date:** ${new Date().toISOString().split('T')[0]}\n`;
    md += `**Target:** 5 Geographically Diverse US Restaurants\n`;
    md += `**Evaluator:** \`gemini-2.5-flash\` ("LLM-as-a-Judge" Evals Pattern)\n\n`;

    md += `## Pass/Fail Matrix\n\n`;
    md += `| Restaurant | Stage | Score (/100) | Pass | Justification |\n`;
    md += `| :--- | :--- | :---: | :---: | :--- |\n`;

    let passes = 0;

    for (const res of results) {
        const passIcon = res.pass ? "✅" : "❌";
        if (res.pass) passes++;
        md += `| **${res.restaurant}** | ${res.stage} | ${res.score} | ${passIcon} | ${res.justification} |\n`;
    }

    md += `\n**Final Capability Pass Rate:** ${passes} / ${results.length} (${Math.round((passes / results.length) * 100)}%)\n`;

    const outputPath = path.resolve(process.cwd(), 'src/tests/report.md');
    fs.writeFileSync(outputPath, md);
    console.log(`✅ Report saved to: ${outputPath}`);
}
