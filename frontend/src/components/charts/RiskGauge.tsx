// frontend/src/components/charts/RiskGauge.tsx
import type { RiskLevel } from "../../types";

const LEVEL_CONFIG = {
  LOW:      { color: "bg-green-500",  text: "text-green-400",  border: "border-green-800" },
  MODERATE: { color: "bg-yellow-500", text: "text-yellow-400", border: "border-yellow-800" },
  HIGH:     { color: "bg-orange-500", text: "text-orange-400", border: "border-orange-800" },
  CRITICAL: { color: "bg-red-600",    text: "text-red-400",    border: "border-red-800" },
};

interface Props {
  countryCode: string;
  countryName: string;
  score: number;
  level: RiskLevel;
  delta: number;
  onClick: () => void;
}

export function RiskGauge({ countryCode, countryName, score, level, delta, onClick }: Props) {
  const cfg = LEVEL_CONFIG[level] || LEVEL_CONFIG.MODERATE;
  const pct = Math.round(score);
  const deltaSign = delta > 0 ? "+" : "";
  const deltaColor = delta > 0 ? "text-red-400" : delta < 0 ? "text-green-400" : "text-gray-500";

  return (
    <button
      onClick={onClick}
      className={`w-full text-left bg-gray-950 border rounded p-3 hover:bg-gray-800 transition-colors ${cfg.border}`}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-bold font-mono text-gray-200">
          {countryCode} <span className="text-gray-500 font-normal">{countryName}</span>
        </span>
        <div className="flex items-center gap-2">
          <span className={`text-xs font-mono ${deltaColor}`}>
            {deltaSign}{delta.toFixed(1)}
          </span>
          <span className={`text-xs font-mono font-bold ${cfg.text}`}>{pct}</span>
        </div>
      </div>
      <div className="w-full bg-gray-800 rounded-full h-1.5">
        <div
          className={`h-1.5 rounded-full transition-all duration-500 ${cfg.color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </button>
  );
}
