import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Providers from "./Providers";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export const metadata: Metadata = {
  title: "Hephae: Big AI for small businesses",
  description: "Find where your restaurant is losing money and fix it. Margin analysis, SEO audits, foot traffic forecasting, and competitive intel — all powered by AI agents.",
  icons: {
    icon: "/favicon.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        {process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY && (
          <script
            async
            src={`https://maps.googleapis.com/maps/api/js?key=${process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY}&libraries=places&loading=async`}
          />
        )}
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <Providers>{children}</Providers>
        {/* Footer */}
        <footer className="border-t border-slate-200 bg-slate-50 py-6 px-6">
          <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between text-sm text-slate-600">
            <div>© {new Date().getFullYear()} Hephae Intelligence. All rights reserved.</div>
            <div className="flex gap-6 mt-4 md:mt-0">
              <a href="/" className="hover:text-amber-600 transition-colors">Home</a>
              <a href="/case-studies" className="hover:text-amber-600 transition-colors">Case Studies</a>
              <a href="/blog" className="hover:text-amber-600 transition-colors">Blog</a>
              <a href="https://hephae.co/privacy" target="_blank" rel="noopener noreferrer" className="hover:text-amber-600 transition-colors">Privacy</a>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
