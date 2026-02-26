import React from 'react';

interface MarkdownRendererProps {
    content: string;
}

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
    // Simple regex-based parser for basic markdown
    const parseMarkdown = (text: string) => {
        const lines = text.split('\n');
        let inList = false;
        const elements: React.ReactNode[] = [];

        lines.forEach((line, index) => {
            // Headers
            if (line.startsWith('### ')) {
                elements.push(<h3 key={index} className="text-md font-bold text-gray-800 mt-3 mb-1">{parseInline(line.replace('### ', ''))}</h3>);
                return;
            }
            if (line.startsWith('## ')) {
                elements.push(<h2 key={index} className="text-lg font-bold text-gray-900 mt-4 mb-2">{parseInline(line.replace('## ', ''))}</h2>);
                return;
            }
            if (line.startsWith('**') && line.endsWith('**')) {
                elements.push(<p key={index} className="font-bold text-gray-800 mt-2 mb-1">{parseInline(line.replace(/\*\*/g, ''))}</p>);
                return;
            }

            // Lists
            if (line.trim().startsWith('* ') || line.trim().startsWith('- ')) {
                const content = line.trim().substring(2);
                if (!inList) {
                    inList = true;
                    elements.push(
                        <ul key={`list-${index}`} className="list-disc pl-5 space-y-1 mb-2 text-gray-700">
                            <li key={index}>{parseInline(content)}</li>
                        </ul>
                    );
                } else {
                    const lastElement = elements[elements.length - 1] as React.ReactElement;
                    if (lastElement && lastElement.type === 'ul') {
                        elements.push(
                            <ul key={`list-sub-${index}`} className="list-disc pl-5 space-y-1 text-gray-700">
                                <li key={index}>{parseInline(content)}</li>
                            </ul>
                        );
                    }
                }
                return;
            }
            inList = false;

            // Paragraphs
            if (line.trim() === '') {
                elements.push(<div key={index} className="h-2"></div>);
            } else {
                elements.push(<p key={index} className="text-gray-700 mb-1 leading-relaxed">{parseInline(line)}</p>);
            }
        });

        return elements;
    };

    const parseInline = (text: string) => {
        const parts = text.split(/(\*\*.*?\*\*)/g);
        return parts.map((part, i) => {
            if (part.startsWith('**') && part.endsWith('**')) {
                return <strong key={i} className="font-semibold text-gray-900">{part.slice(2, -2)}</strong>;
            }
            return part;
        });
    };

    return <div className="text-sm">{parseMarkdown(content)}</div>;
};

export default MarkdownRenderer;
