"use client";

/**
 * HephaeLogo — uses the official Hephae brand logo image.
 *
 * The PNG is the canonical brand asset from hephae.co.
 * For the `white` variant (e.g. on the dark blue header), a CSS
 * filter inverts the blue mark to white.
 *
 * Props:
 *   size    – 'xs' | 'sm' | 'md' | 'lg'  (default: 'md')
 *   variant – 'color' | 'white'           (default: 'color')
 *   className – extra Tailwind classes
 */

const LOGO_URL = 'https://insights.ai.hephae.co/hephae_logo_blue.png';

interface HephaeLogoProps {
  size?: 'xs' | 'sm' | 'md' | 'lg';
  variant?: 'color' | 'white';
  className?: string;
  /** Kept for API compatibility — logo image already contains the wordmark */
  showWordmark?: boolean;
}

const heightMap = {
  xs: 16,
  sm: 22,
  md: 32,
  lg: 48,
};

export default function HephaeLogo({
  size = 'md',
  variant = 'color',
  className = '',
}: HephaeLogoProps) {
  const h = heightMap[size];
  const isWhite = variant === 'white';

  return (
    <img
      src={LOGO_URL}
      alt="Hephae"
      height={h}
      style={{
        height: h,
        width: 'auto',
        display: 'inline-block',
        flexShrink: 0,
        ...(isWhite
          ? { filter: 'brightness(0) invert(1)' }
          : {}),
      }}
      className={className}
    />
  );
}
