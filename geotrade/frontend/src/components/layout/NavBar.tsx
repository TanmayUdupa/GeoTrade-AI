// frontend/src/components/layout/NavBar.tsx
interface Props {
  page: string;
  onNavigate: (p: any) => void;
  wsConnected: boolean;
  alertCount: number;
}

const PAGES = [
  { id: "dashboard", label: "DASHBOARD" },
  { id: "map", label: "WORLD MAP" },
  { id: "compare", label: "COMPARE" },
];

export function NavBar({ page, onNavigate, wsConnected, alertCount }: Props) {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-gray-950/95 backdrop-blur border-b border-gray-800 h-16 flex items-center px-6 font-mono">
      {/* Logo */}
      <div className="flex items-center gap-3 mr-8">
        <div className="w-6 h-6 bg-green-500 rounded-sm flex items-center justify-center">
          <span className="text-black text-xs font-black">G</span>
        </div>
        <span className="text-sm font-bold text-white tracking-widest">GEOTRADE AI</span>
        <span className="text-xs text-gray-600 hidden md:block">// RISK INTELLIGENCE</span>
      </div>

      {/* Navigation */}
      <div className="flex gap-1">
        {PAGES.map(p => (
          <button
            key={p.id}
            onClick={() => onNavigate(p.id)}
            className={`px-3 py-1.5 text-xs rounded transition-colors tracking-widest ${
              page === p.id
                ? "bg-green-900/30 text-green-400 border border-green-800"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Status Indicators */}
      <div className="flex items-center gap-4 text-xs">
        {alertCount > 0 && (
          <span className="bg-red-900/40 text-red-400 border border-red-800 rounded px-2 py-1 animate-pulse">
            ⚠ {alertCount} CRITICAL
          </span>
        )}
        <div className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${wsConnected ? "bg-green-500" : "bg-red-500"}`} />
          <span className={wsConnected ? "text-green-500" : "text-red-500"}>
            {wsConnected ? "LIVE" : "OFFLINE"}
          </span>
        </div>
      </div>
    </nav>
  );
}
