import React from 'react';

interface MarkdownRendererProps {
    content: string;
}

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
    const parseMarkdown = (text: string) => {
        const lines = text.split('\n');
        const elements: React.ReactNode[] = [];
        let listItems: React.ReactNode[] = [];

        const flushList = (key: string) => {
            if (listItems.length) {
                elements.push(
                    <ul key={key} className="list-none pl-0 space-y-1 mb-3">
                        {listItems}
                    </ul>
                );
                listItems = [];
            }
        };

        lines.forEach((line, index) => {
            // H2
            if (line.startsWith('## ')) {
                flushList(`fl-${index}`);
                elements.push(
                    <h2 key={index} className="text-base font-bold text-gray-900 mt-4 mb-1.5 tracking-tight">
                        {parseInline(line.slice(3))}
                    </h2>
                );
                return;
            }
            // H3
            if (line.startsWith('### ')) {
                flushList(`fl-${index}`);
                elements.push(
                    <h3 key={index} className="text-sm font-semibold text-gray-800 mt-3 mb-1">
                        {parseInline(line.slice(4))}
                    </h3>
                );
                return;
            }
            // Standalone bold line
            if (/^\*\*[^*]+\*\*$/.test(line.trim())) {
                flushList(`fl-${index}`);
                elements.push(
                    <p key={index} className="font-semibold text-gray-900 mt-2 mb-0.5 text-sm">
                        {line.trim().slice(2, -2)}
                    </p>
                );
                return;
            }
            // Horizontal rule
            if (line.trim() === '---') {
                flushList(`fl-${index}`);
                elements.push(<hr key={index} className="border-gray-100 my-3" />);
                return;
            }
            // List items (• or * or -)
            if (/^[•*-] /.test(line.trim())) {
                const itemContent = line.trim().slice(2);
                listItems.push(
                    <li key={index} className="flex items-start gap-2 text-sm text-gray-700 leading-relaxed">
                        <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-indigo-400 flex-shrink-0" />
                        <span>{parseInline(itemContent)}</span>
                    </li>
                );
                return;
            }
            // Empty line
            if (line.trim() === '') {
                flushList(`fl-${index}`);
                elements.push(<div key={index} className="h-1.5" />);
                return;
            }
            // Paragraph
            flushList(`fl-${index}`);
            elements.push(
                <p key={index} className="text-sm text-gray-700 leading-relaxed mb-1">
                    {parseInline(line)}
                </p>
            );
        });

        flushList('final');
        return elements;
    };

    const parseInline = (text: string): React.ReactNode[] => {
        // Split on links [text](url), bold **text**, italic *text*, and inline code `text`
        const pattern = /(\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`)/g;
        const nodes: React.ReactNode[] = [];
        let last = 0;
        let match: RegExpExecArray | null;

        while ((match = pattern.exec(text)) !== null) {
            // Push preceding plain text
            if (match.index > last) {
                nodes.push(text.slice(last, match.index));
            }
            const full = match[0];
            if (full.startsWith('[')) {
                // Link
                nodes.push(
                    <a
                        key={match.index}
                        href={match[3]}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-indigo-600 font-medium hover:text-indigo-800 hover:underline underline-offset-2 transition-colors"
                    >
                        {match[2]}
                    </a>
                );
            } else if (full.startsWith('**')) {
                nodes.push(
                    <strong key={match.index} className="font-semibold text-gray-900">
                        {match[4]}
                    </strong>
                );
            } else if (full.startsWith('*')) {
                nodes.push(
                    <em key={match.index} className="italic text-gray-600">
                        {match[5]}
                    </em>
                );
            } else if (full.startsWith('`')) {
                nodes.push(
                    <code key={match.index} className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-100">
                        {match[6]}
                    </code>
                );
            }
            last = match.index + full.length;
        }
        if (last < text.length) nodes.push(text.slice(last));
        return nodes;
    };

    return <div className="text-sm space-y-0">{parseMarkdown(content)}</div>;
};

export default MarkdownRenderer;
