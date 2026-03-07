// frontend/src/components/map/WorldRiskMap.tsx
import { useRiskStore } from "../../store/riskStore";

const RISK_COLORS = {
  LOW: "#22c55e",
  MODERATE: "#f59e0b",
  HIGH: "#ef4444",
  CRITICAL: "#dc2626",
};

interface Props {
  onCountrySelect: (code: string) => void;
}

export function WorldRiskMap({ onCountrySelect }: Props) {
  const { risks } = useRiskStore();
  const sorted = Object.values(risks).sort((a, b) => b.risk_score - a.risk_score);

  return (
    <div className="p-6 max-w-screen-xl mx-auto font-mono">
      <h1 className="text-2xl font-bold text-green-400 tracking-widest mb-2">
        WORLD RISK MAP
      </h1>
      <p className="text-xs text-gray-500 mb-6">
        Click a country to view detailed risk intelligence
      </p>

      {/* Risk Legend */}
      <div className="flex gap-4 mb-6 text-xs">
        {Object.entries(RISK_COLORS).map(([level, color]) => (
          <div key={level} className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full inline-block" style={{ background: color }} />
            <span className="text-gray-400">{level}</span>
          </div>
        ))}
      </div>

      {/* Country Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {sorted.map((r) => {
          const color = RISK_COLORS[r.risk_level] || "#6b7280";
          return (
            <button
              key={r.country_code}
              onClick={() => onCountrySelect(r.country_code)}
              className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-left hover:bg-gray-800 transition-all hover:scale-105"
              style={{ borderLeftColor: color, borderLeftWidth: 3 }}
            >
              <div className="text-lg font-bold text-white">{r.country_code}</div>
              <div className="text-xs text-gray-500 truncate mb-2">{r.country_name}</div>
              <div className="text-xl font-bold" style={{ color }}>
                {r.risk_score.toFixed(0)}
              </div>
              <div className="text-[10px] tracking-widest mt-1" style={{ color }}>
                {r.risk_level}
              </div>
              <div className="w-full bg-gray-800 rounded-full h-1 mt-2">
                <div
                  className="h-1 rounded-full transition-all"
                  style={{ width: `${r.risk_score}%`, background: color }}
                />
              </div>
            </button>
          );
        })}
      </div>

      {sorted.length === 0 && (
        <div className="py-24 text-center text-gray-600 text-sm">
          NO DATA — START BACKEND SERVICES AND TRIGGER INGESTION
        </div>
      )}
    </div>
  );
}
