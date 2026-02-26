import React, { useState, useMemo } from 'react';
import { SeoReport } from '@/lib/types';
import RadialScore from './RadialScore';
import RecommendationCard from './RecommendationCard';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Globe, ExternalLink, ChevronDown, ChevronUp, Download, BookOpen, BrainCircuit, Search as SearchIcon } from 'lucide-react';
import jsPDF from 'jspdf';

interface ResultsDashboardProps {
  report: SeoReport;
  groundingChunks: any[];
}

const ResultsDashboard: React.FC<ResultsDashboardProps> = ({ report, groundingChunks }) => {
  // Ensure Core Web Vitals are present in Technical SEO and Meta Descriptions in Content Quality if analyzed
  const displayReport = useMemo(() => {
    // Create a deep copy to avoid mutating props
    const newReport = JSON.parse(JSON.stringify(report)) as SeoReport;

    // 1. Technical SEO: Core Web Vitals Check
    const techSection = newReport.sections.find(s =>
      s.title.toLowerCase().includes('technical') || s.id === 'technical'
    );

    if (techSection && techSection.isAnalyzed) {
      const hasCWV = techSection.recommendations.some(r =>
        /core web vitals|lcp|cls|inp|fid/i.test(r.title + r.description)
      );

      if (!hasCWV) {
        techSection.recommendations.unshift({
          severity: 'Critical',
          title: 'Optimize Core Web Vitals (LCP, INP, CLS)',
          description: 'Core Web Vitals are crucial ranking factors. No explicit data was found in the initial scan, so it is critical to measure and optimize these metrics (LCP, INP, CLS) to ensure a good page experience.',
          action: 'Use PageSpeed Insights to measure LCP (<2.5s), INP (<200ms), and CLS (<0.1). Optimize images (WebP), defer non-critical JS, and ensure layout stability.'
        });
      }
    }

    // 2. Content Quality: Meta Description Check
    const contentSection = newReport.sections.find(s =>
      s.title.toLowerCase().includes('content') || s.id === 'content'
    );

    if (contentSection && contentSection.isAnalyzed) {
      const hasMeta = contentSection.recommendations.some(r =>
        /meta description|description tag|snippet/i.test(r.title + r.description)
      );

      if (!hasMeta) {
        contentSection.recommendations.push({
          severity: 'Warning',
          title: 'Optimize Meta Descriptions (Length & Uniqueness)',
          description: 'Well-optimized meta descriptions improve click-through rates. Ensure they are between 150-160 characters; too short and they are uninformative, too long and they get truncated.',
          action: 'Audit all pages for missing, duplicate, short (<50 chars), or long (>160 chars) meta descriptions. Rewrite them to be compelling, unique summaries containing target keywords.'
        });
      }
    }

    return newReport;
  }, [report]);

  const [expandedSection, setExpandedSection] = useState<string | null>(displayReport.sections[0]?.title || null);
  const [methodologyOpen, setMethodologyOpen] = useState<Record<string, boolean>>({});

  const toggleSection = (title: string) => {
    setExpandedSection(expandedSection === title ? null : title);
  };

  const toggleMethodology = (sectionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setMethodologyOpen(prev => ({
      ...prev,
      [sectionId]: !prev[sectionId]
    }));
  };

  const handleDownloadPdf = () => {
    const doc = new jsPDF();
    const pageWidth = doc.internal.pageSize.getWidth();
    const margin = 20;
    const maxLineWidth = pageWidth - margin * 2;
    let yPos = 20;

    // Helper to check page bounds
    const checkPageBreak = (heightNeeded: number) => {
      if (yPos + heightNeeded > 280) {
        doc.addPage();
        yPos = 20;
        return true;
      }
      return false;
    };

    // Header
    doc.setFontSize(22);
    doc.setTextColor(30, 41, 59); // Slate 800
    doc.text("SEO Audit Report", margin, yPos);
    yPos += 10;

    doc.setFontSize(12);
    doc.setTextColor(100);
    doc.text(displayReport.url, margin, yPos);
    doc.text(`Date: ${new Date().toLocaleDateString()}`, pageWidth - margin - 30, yPos);
    yPos += 15;

    // Overall Score
    doc.setFontSize(14);
    doc.setTextColor(0);
    doc.text(`Overall Score: ${displayReport.overallScore}/100`, margin, yPos);
    yPos += 10;

    // Summary
    doc.setFontSize(11);
    doc.setTextColor(60);
    const summaryLines = doc.splitTextToSize(displayReport.summary, maxLineWidth);
    doc.text(summaryLines, margin, yPos);
    yPos += (summaryLines.length * 5) + 15;

    // Sections
    displayReport.sections.forEach(section => {
      if (!section.isAnalyzed && section.recommendations.length === 0) return; // Skip empty non-analyzed sections in PDF

      checkPageBreak(30);

      doc.setFontSize(16);
      doc.setTextColor(30, 41, 59);
      doc.setFont("helvetica", "bold");
      doc.text(`${section.title} (${section.score}/100)`, margin, yPos);
      doc.setFont("helvetica", "normal");
      yPos += 10;

      // Draw a line under section title
      doc.setDrawColor(200);
      doc.line(margin, yPos - 3, pageWidth - margin, yPos - 3);

      section.recommendations.forEach(rec => {
        // Calculate estimated height for this item
        const descLines = doc.splitTextToSize(rec.description, maxLineWidth);
        const actionLines = doc.splitTextToSize(rec.action, maxLineWidth - 10);
        const estimatedHeight = 15 + (descLines.length * 5) + (actionLines.length * 5);

        checkPageBreak(estimatedHeight);

        // Severity Badge (Text representation)
        doc.setFontSize(10);
        doc.setFont("helvetica", "bold");
        if (rec.severity === 'Critical') doc.setTextColor(220, 38, 38);
        else if (rec.severity === 'Warning') doc.setTextColor(202, 138, 4);
        else doc.setTextColor(37, 99, 235);

        doc.text(`[${rec.severity.toUpperCase()}] ${rec.title}`, margin, yPos);
        yPos += 5;

        // Description
        doc.setFontSize(10);
        doc.setFont("helvetica", "normal");
        doc.setTextColor(60);
        doc.text(descLines, margin, yPos);
        yPos += (descLines.length * 5) + 2;

        // Fix Action
        doc.setTextColor(30);
        doc.setFont("helvetica", "bold");
        doc.text("Fix:", margin, yPos);
        doc.setFont("helvetica", "normal");
        doc.text(actionLines, margin + 8, yPos); // Indent action
        yPos += (actionLines.length * 5) + 8;
      });

      yPos += 5; // Spacing between sections
    });

    doc.save(`seo-report-${new URL(displayReport.url).hostname}.pdf`);
  };

  // Prepare chart data
  const chartData = displayReport.sections.map(section => ({
    name: section.title,
    score: section.score,
  }));

  const getBarColor = (score: number) => {
    if (score >= 90) return '#22c55e';
    if (score >= 70) return '#eab308';
    return '#ef4444';
  };

  return (
    <div className="animate-fade-in space-y-8">
      {/* Header Summary */}
      <div className="bg-white rounded-2xl shadow-xl border border-slate-100 overflow-hidden">
        <div className="p-8 md:p-10 flex flex-col md:flex-row gap-10 items-center">
          <div className="shrink-0">
            <RadialScore score={displayReport.overallScore} size={220} label="Overall Health" />
          </div>
          <div className="flex-1 space-y-4 w-full">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3 overflow-hidden">
                <Globe className="w-6 h-6 text-indigo-600 shrink-0" />
                <h2 className="text-2xl font-bold text-gray-900 truncate" title={displayReport.url}>
                  {displayReport.url}
                </h2>
              </div>
              <button
                onClick={handleDownloadPdf}
                className="flex items-center gap-2 px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-sm font-medium transition-colors shadow-sm shrink-0"
              >
                <Download className="w-4 h-4" />
                Export PDF
              </button>
            </div>

            <p className="text-gray-600 leading-relaxed text-lg">
              {displayReport.summary}
            </p>

            {groundingChunks.length > 0 && (
              <div className="mt-8 pt-8 border-t border-slate-200">
                <h4 className="flex items-center gap-2 text-sm font-bold text-slate-900 uppercase tracking-widest mb-6">
                  <div className="bg-indigo-100 p-1.5 rounded text-indigo-600">
                    <BookOpen className="w-4 h-4" />
                  </div>
                  Verified Grounding Sources
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {groundingChunks.map((chunk, i) => {
                    if (!chunk.web?.uri) return null;
                    const uri = chunk.web.uri;
                    const urlObj = new URL(uri);
                    const hostname = urlObj.hostname;
                    const title = chunk.web.title || hostname;

                    // Try to find a snippet or fallback to path
                    const snippet = (chunk.web as any).snippet || (chunk.web as any).content;

                    return (
                      <a
                        key={i}
                        href={uri}
                        target="_blank"
                        rel="noreferrer"
                        className="group relative flex flex-col p-5 bg-white border border-slate-200 rounded-xl hover:border-indigo-400 hover:shadow-lg hover:-translate-y-1 transition-all duration-300 h-full"
                      >
                        {/* Header: Favicon & Hostname */}
                        <div className="flex items-center gap-3 mb-3">
                          <div className="w-8 h-8 rounded-full bg-slate-50 border border-slate-100 flex items-center justify-center shrink-0 overflow-hidden group-hover:border-indigo-200 transition-colors">
                            <img
                              src={`https://www.google.com/s2/favicons?domain=${hostname}&sz=64`}
                              alt={hostname}
                              className="w-5 h-5 object-contain"
                              onError={(e) => {
                                e.currentTarget.style.display = 'none';
                                const next = e.currentTarget.nextSibling as HTMLElement;
                                if (next) next.style.display = 'block';
                              }}
                            />
                            <Globe className="w-4 h-4 text-slate-400 hidden" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-bold text-slate-500 uppercase tracking-wider truncate group-hover:text-indigo-600 transition-colors">
                              {hostname}
                            </p>
                          </div>
                          <ExternalLink className="w-3 h-3 text-slate-300 group-hover:text-indigo-400 transition-colors shrink-0" />
                        </div>

                        {/* Content */}
                        <h5 className="font-bold text-slate-800 leading-snug mb-2 line-clamp-2 group-hover:text-indigo-700 transition-colors">
                          {title}
                        </h5>

                        {snippet ? (
                          <p className="text-xs text-slate-500 leading-relaxed line-clamp-3 mt-auto">
                            {snippet}
                          </p>
                        ) : (
                          <p className="text-xs text-slate-400 font-mono truncate mt-auto opacity-70 group-hover:opacity-100 transition-opacity">
                            {urlObj.pathname === '/' ? '/' : urlObj.pathname}
                          </p>
                        )}

                        {/* Tooltip on Hover */}
                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-3 w-64 p-3 bg-slate-800 text-white text-xs rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 pointer-events-none transform translate-y-2 group-hover:translate-y-0 text-center">
                          <span className="font-semibold block mb-1 text-slate-300 border-b border-slate-700 pb-1">Full URL</span>
                          <span className="font-mono break-all text-slate-400 leading-tight">{uri}</span>
                          {/* Arrow */}
                          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px border-4 border-transparent border-t-slate-800"></div>
                        </div>
                      </a>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Breakdown Chart */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-3 bg-white p-6 rounded-xl shadow-sm border border-slate-100">
          <h3 className="text-lg font-bold text-gray-800 mb-6">Score Breakdown</h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
                <XAxis type="number" domain={[0, 100]} hide />
                <YAxis dataKey="name" type="category" width={100} tick={{ fontSize: 12, fill: '#64748b' }} />
                <Tooltip
                  cursor={{ fill: '#f1f5f9' }}
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                />
                <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={32}>
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={getBarColor(entry.score)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Detailed Sections */}
      <div className="space-y-4">
        <h3 className="text-xl font-bold text-gray-900 mb-4 px-1">Detailed Recommendations</h3>
        {displayReport.sections.map((section, idx) => (
          <div key={idx} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <button
              onClick={() => toggleSection(section.title)}
              className="w-full flex items-center justify-between p-6 hover:bg-slate-50 transition-colors focus:outline-none"
            >
              <div className="flex items-center gap-4">
                <div
                  className={`w-12 h-12 rounded-full flex items-center justify-center font-bold text-lg ${section.score >= 90 ? 'bg-green-100 text-green-700' :
                    section.score >= 70 ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'
                    }`}
                >
                  {section.score}
                </div>
                <div className="text-left">
                  <h4 className="font-bold text-lg text-gray-900">{section.title}</h4>
                  <div className="flex gap-2">
                    {section.isAnalyzed ? (
                      <p className="text-sm text-gray-500">{section.recommendations.length} recommendations</p>
                    ) : (
                      <p className="text-sm text-gray-400 italic">Skipped deep dive</p>
                    )}
                  </div>
                </div>
              </div>
              {expandedSection === section.title ? (
                <ChevronUp className="w-5 h-5 text-gray-400" />
              ) : (
                <ChevronDown className="w-5 h-5 text-gray-400" />
              )}
            </button>

            {expandedSection === section.title && (
              <div className="p-6 pt-0 bg-slate-50/50 border-t border-slate-100">
                {/* Methodology / Logic Toggle */}
                {section.isAnalyzed && section.methodology && (
                  <div className="mb-6 mt-4">
                    <button
                      onClick={(e) => toggleMethodology(section.id, e)}
                      className="flex items-center gap-2 text-indigo-600 font-medium text-sm hover:text-indigo-700 transition-colors focus:outline-none px-3 py-1.5 rounded-lg hover:bg-indigo-50 border border-transparent hover:border-indigo-100"
                    >
                      <BrainCircuit className="w-4 h-4" />
                      {methodologyOpen[section.id] ? "Hide Analysis Logic" : "View AI Analysis Logic"}
                      {methodologyOpen[section.id] ? <ChevronUp className="w-3 h-3 ml-1" /> : <ChevronDown className="w-3 h-3 ml-1" />}
                    </button>

                    {methodologyOpen[section.id] && (
                      <div className="mt-3 bg-slate-800 rounded-lg p-5 text-slate-300 animate-fade-in shadow-inner border border-slate-700">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                          <div>
                            <h5 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                              <BrainCircuit className="w-3 h-3" />
                              Reasoning Steps
                            </h5>
                            <ul className="space-y-2">
                              {section.methodology.reasoningSteps.map((step, i) => (
                                <li key={i} className="flex items-start gap-2 text-sm leading-relaxed">
                                  <span className="text-indigo-400 mt-1.5 w-1.5 h-1.5 bg-indigo-500 rounded-full shrink-0"></span>
                                  {step}
                                </li>
                              ))}
                            </ul>
                          </div>
                          <div className="space-y-6">
                            <div>
                              <h5 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                                <SearchIcon className="w-3 h-3" />
                                Tools & Sources
                              </h5>
                              <div className="flex flex-wrap gap-2">
                                {section.methodology.toolsUsed.map((tool, i) => (
                                  <span key={i} className="px-2 py-1 bg-slate-700 text-slate-200 text-xs rounded border border-slate-600 font-mono">
                                    {tool}
                                  </span>
                                ))}
                              </div>
                            </div>
                            {section.methodology.searchQueries && section.methodology.searchQueries.length > 0 && (
                              <div>
                                <h5 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Search Queries</h5>
                                <ul className="space-y-1">
                                  {section.methodology.searchQueries.map((q, i) => (
                                    <li key={i} className="text-xs font-mono text-slate-400 italic truncate">
                                      "{q}"
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <div className="grid gap-4 mt-2">
                  {section.recommendations.map((rec, recIdx) => (
                    <RecommendationCard key={recIdx} item={rec} />
                  ))}
                  {section.recommendations.length === 0 && (
                    <p className="text-gray-500 italic text-center py-4">
                      {section.isAnalyzed
                        ? "No critical issues found in this section. Great job!"
                        : "Deep dive analysis was not selected for this category."}
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default ResultsDashboard;