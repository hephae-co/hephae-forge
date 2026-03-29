'use client';

import { MapPin } from 'lucide-react';
import { LockedCard } from './LockedCard';
import type { DashBusiness } from './types';

export function MapCard({ business }: { business: DashBusiness | null }) {
  if (!business?.lat || !business?.lng) {
    return <LockedCard title="Location Map" icon={MapPin} action="Load Business" className="h-full" />;
  }
  const query = business.address
    ? `${business.name}, ${business.address}`
    : `${business.lat},${business.lng}`;
  const src = `https://www.google.com/maps?q=${encodeURIComponent(query)}&z=15&output=embed`;

  return (
    <div className="relative w-full h-full rounded-2xl overflow-hidden shadow-sm shadow-purple-900/5 min-h-[260px]">
      <iframe
        key={src}
        src={src}
        className="absolute inset-0 w-full h-full border-0"
        title="Business location"
        loading="lazy"
        referrerPolicy="no-referrer-when-downgrade"
      />
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-4">
        <p className="text-white font-bold text-sm truncate">{business.name}</p>
        {business.address && (
          <p className="text-white/70 text-xs truncate mt-0.5">{business.address}</p>
        )}
      </div>
    </div>
  );
}
