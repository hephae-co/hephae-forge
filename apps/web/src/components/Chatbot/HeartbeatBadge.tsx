import { Activity } from 'lucide-react';

interface HeartbeatBadgeProps {
  onClick?: () => void;
}

export function HeartbeatBadge({ onClick }: HeartbeatBadgeProps) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/15 transition-colors group"
      title="Heartbeat monitoring active"
    >
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
      </span>
      <span className="text-xs font-medium text-emerald-400 group-hover:text-emerald-300 transition-colors">
        Heartbeat active
      </span>
    </button>
  );
}
