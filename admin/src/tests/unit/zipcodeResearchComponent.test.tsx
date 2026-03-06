import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import ZipcodeResearch from '@/components/ZipcodeResearch';

const mockReport = {
    summary: 'A vibrant neighborhood in northern New Jersey.',
    zip_code: '07110',
    sections: {
        geography: {
            title: 'Geography & Location',
            content: 'Located in Essex County, NJ.',
            key_facts: ['Essex County', 'Suburban area'],
        },
        demographics: {
            title: 'Demographics',
            content: 'Population of approximately 40,000.',
            key_facts: ['Pop: 40,000', 'Median age: 37'],
        },
        trending: {
            title: 'Google Trends & Search Interest',
            content: 'Pizza delivery searches are surging.',
            key_facts: ['pizza delivery +500%', 'home renovation +200%'],
        },
    },
    sources: [
        { short_id: 'src-1', title: 'Census Bureau', url: 'https://census.gov', domain: 'census.gov' },
        { short_id: 'src-2', title: 'Wikipedia', url: 'https://en.wikipedia.org', domain: 'wikipedia.org' },
    ],
    source_count: 2,
};

describe('ZipcodeResearch Component', () => {
    let mockFetch: ReturnType<typeof vi.fn>;
    const originalFetch = global.fetch;

    beforeEach(() => {
        mockFetch = vi.fn();
        global.fetch = mockFetch as typeof fetch;
    });

    afterEach(() => {
        global.fetch = originalFetch;
        vi.restoreAllMocks();
    });

    describe('Loading state', () => {
        it('shows checking state on mount', () => {
            // Never resolve the fetch — keep in loading state
            mockFetch.mockReturnValue(new Promise(() => {}));

            render(<ZipcodeResearch zipCode="07110" />);

            expect(screen.getByText(/checking for existing research/i)).toBeInTheDocument();
        });
    });

    describe('No cached report', () => {
        beforeEach(() => {
            mockFetch.mockResolvedValue({
                ok: true,
                json: async () => ({ success: false, report: null, cached: false }),
            });
        });

        it('shows research prompt when no cache exists', async () => {
            render(<ZipcodeResearch zipCode="07110" />);

            await waitFor(() => {
                expect(screen.getByText(/area research for 07110/i)).toBeInTheDocument();
            });

            expect(screen.getByText(/run deep research/i)).toBeInTheDocument();
            expect(screen.getByText(/deep research pipeline/i)).toBeInTheDocument();
        });

        it('shows loading state when research button is clicked', async () => {
            render(<ZipcodeResearch zipCode="07110" />);

            await waitFor(() => {
                expect(screen.getByText(/run deep research/i)).toBeInTheDocument();
            });

            // Mock the POST request to hang
            mockFetch.mockReturnValueOnce(new Promise(() => {}));

            await act(async () => {
                fireEvent.click(screen.getByText(/run deep research/i));
            });

            expect(screen.getByText(/researching\.\.\./i)).toBeInTheDocument();
            expect(screen.getByText(/Trends/)).toBeInTheDocument(); // Pipeline step label
        });

        it('displays report after successful research', async () => {
            render(<ZipcodeResearch zipCode="07110" />);

            await waitFor(() => {
                expect(screen.getByText(/run deep research/i)).toBeInTheDocument();
            });

            // Mock the POST response
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ success: true, report: mockReport }),
            });

            await act(async () => {
                fireEvent.click(screen.getByText(/run deep research/i));
            });

            await waitFor(() => {
                expect(screen.getByText(/area research: 07110/i)).toBeInTheDocument();
            });

            expect(screen.getByText('A vibrant neighborhood in northern New Jersey.')).toBeInTheDocument();
        });

        it('shows error on failed research', async () => {
            render(<ZipcodeResearch zipCode="07110" />);

            await waitFor(() => {
                expect(screen.getByText(/run deep research/i)).toBeInTheDocument();
            });

            mockFetch.mockResolvedValueOnce({
                ok: false,
                json: async () => ({ error: 'Pipeline timeout' }),
            });

            await act(async () => {
                fireEvent.click(screen.getByText(/run deep research/i));
            });

            await waitFor(() => {
                expect(screen.getByText(/pipeline timeout/i)).toBeInTheDocument();
            });
        });
    });

    describe('Cached report display', () => {
        beforeEach(() => {
            mockFetch.mockResolvedValue({
                ok: true,
                json: async () => ({ success: true, report: mockReport, cached: true }),
            });
        });

        it('renders report header with badges', async () => {
            render(<ZipcodeResearch zipCode="07110" />);

            await waitFor(() => {
                expect(screen.getByText(/area research: 07110/i)).toBeInTheDocument();
            });

            expect(screen.getByText('3 sections')).toBeInTheDocument();
            expect(screen.getByText('2 sources')).toBeInTheDocument();
        });

        it('renders summary card', async () => {
            render(<ZipcodeResearch zipCode="07110" />);

            await waitFor(() => {
                expect(screen.getByText('A vibrant neighborhood in northern New Jersey.')).toBeInTheDocument();
            });
        });

        it('renders all section titles', async () => {
            render(<ZipcodeResearch zipCode="07110" />);

            await waitFor(() => {
                expect(screen.getByText('Geography & Location')).toBeInTheDocument();
            });

            expect(screen.getByText('Demographics')).toBeInTheDocument();
            expect(screen.getByText('Google Trends & Search Interest')).toBeInTheDocument();
        });

        it('shows fact counts on collapsed sections', async () => {
            render(<ZipcodeResearch zipCode="07110" />);

            await waitFor(() => {
                expect(screen.getByText('Geography & Location')).toBeInTheDocument();
            });

            // Geography has 2 facts
            expect(screen.getAllByText('2 facts').length).toBeGreaterThanOrEqual(2);
        });

        it('expands section on click to show content', async () => {
            render(<ZipcodeResearch zipCode="07110" />);

            await waitFor(() => {
                expect(screen.getByText('Geography & Location')).toBeInTheDocument();
            });

            // Content should not be visible before expansion
            expect(screen.queryByText('Located in Essex County, NJ.')).not.toBeInTheDocument();

            // Click to expand
            await act(async () => {
                fireEvent.click(screen.getByText('Geography & Location'));
            });

            expect(screen.getByText('Located in Essex County, NJ.')).toBeInTheDocument();
            expect(screen.getByText('Essex County')).toBeInTheDocument();
            expect(screen.getByText('Suburban area')).toBeInTheDocument();
        });

        it('collapses section on second click', async () => {
            render(<ZipcodeResearch zipCode="07110" />);

            await waitFor(() => {
                expect(screen.getByText('Geography & Location')).toBeInTheDocument();
            });

            // Expand
            await act(async () => {
                fireEvent.click(screen.getByText('Geography & Location'));
            });
            expect(screen.getByText('Located in Essex County, NJ.')).toBeInTheDocument();

            // Collapse
            await act(async () => {
                fireEvent.click(screen.getByText('Geography & Location'));
            });
            expect(screen.queryByText('Located in Essex County, NJ.')).not.toBeInTheDocument();
        });

        it('expand all / collapse all toggles all sections', async () => {
            render(<ZipcodeResearch zipCode="07110" />);

            await waitFor(() => {
                expect(screen.getByText('Expand All')).toBeInTheDocument();
            });

            // Expand All
            await act(async () => {
                fireEvent.click(screen.getByText('Expand All'));
            });

            expect(screen.getByText('Located in Essex County, NJ.')).toBeInTheDocument();
            expect(screen.getByText('Population of approximately 40,000.')).toBeInTheDocument();
            expect(screen.getByText('Pizza delivery searches are surging.')).toBeInTheDocument();
            expect(screen.getByText('Collapse All')).toBeInTheDocument();

            // Collapse All
            await act(async () => {
                fireEvent.click(screen.getByText('Collapse All'));
            });

            expect(screen.queryByText('Located in Essex County, NJ.')).not.toBeInTheDocument();
            expect(screen.getByText('Expand All')).toBeInTheDocument();
        });

        it('shows re-research button', async () => {
            render(<ZipcodeResearch zipCode="07110" />);

            await waitFor(() => {
                expect(screen.getByText('Re-research')).toBeInTheDocument();
            });
        });
    });

    describe('Zip code changes', () => {
        it('resets report and checks cache for new zip', async () => {
            mockFetch.mockResolvedValue({
                ok: true,
                json: async () => ({ success: true, report: mockReport, cached: true }),
            });

            const { rerender } = render(<ZipcodeResearch zipCode="07110" />);

            await waitFor(() => {
                expect(screen.getByText(/area research: 07110/i)).toBeInTheDocument();
            });

            // Change zip — should fetch again for new zip
            mockFetch.mockResolvedValue({
                ok: true,
                json: async () => ({ success: false, report: null, cached: false }),
            });

            rerender(<ZipcodeResearch zipCode="10001" />);

            await waitFor(() => {
                expect(screen.getByText(/area research for 10001/i)).toBeInTheDocument();
            });
        });
    });
});
