export default function BlobBackground({ className = '' }: { className?: string }) {
  return (
    <div className={`absolute inset-0 overflow-hidden pointer-events-none ${className}`}>
      <div className="animate-blob absolute top-1/4 -left-10 w-80 h-80 rounded-full
                      bg-gradient-to-r from-[#0052CC]/50 to-[#00C2FF]/40 blur-3xl" />
      <div className="animate-blob animation-delay-2000 absolute top-1/3 right-0 w-72 h-72 rounded-full
                      bg-gradient-to-r from-[#7c3aed]/35 to-[#0052CC]/25 blur-3xl" />
      <div className="animate-blob animation-delay-4000 absolute bottom-1/4 left-1/4 w-64 h-64 rounded-full
                      bg-gradient-to-r from-[#00C2FF]/35 to-[#7c3aed]/25 blur-3xl" />
    </div>
  );
}
