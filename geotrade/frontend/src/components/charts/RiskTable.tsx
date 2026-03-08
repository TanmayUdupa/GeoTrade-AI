// frontend/src/components/charts/RiskTable.tsx
import type { CountryRiskScore, RiskLevel } from "../../types";

const BADGE = {
  LOW:      "bg-green-900/50 text-green-400 border-green-700",
  MODERATE: "bg-yellow-900/50 text-yellow-400 border-yellow-700",
  HIGH:     "bg-orange-900/50 text-orange-400 border-orange-700",
  CRITICAL: "bg-red-900/50 text-red-400 border-red-700",
};

interface Props {
  data: CountryRiskScore[];
  onSelect: (code: string) => void;
}

export function RiskTable({ data, onSelect }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="text-gray-500 border-b border-gray-800">
            {["CODE","COUNTRY","SCORE","LEVEL","TARIFF IDX","STABILITY Δ","SENTIMENT","CONFIDENCE","ENTITIES"].map(h => (
              <th key={h} className="text-left py-2 px-3 tracking-widest font-normal">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((r, i) => {
            const deltaColor = r.stability_delta > 0 ? "text-red-400" : r.stability_delta < 0 ? "text-green-400" : "text-gray-500";
            const sign = r.stability_delta > 0 ? "+" : "";
            return (
              <tr
                key={r.country_code}
                onClick={() => onSelect(r.country_code)}
                className="border-b border-gray-900 hover:bg-gray-800 cursor-pointer transition-colors"
              >
                <td className="py-2 px-3 text-gray-300 font-bold">{r.country_code}</td>
                <td className="py-2 px-3 text-gray-400">{r.country_name}</td>
                <td className="py-2 px-3 text-white font-bold">{r.risk_score.toFixed(1)}</td>
                <td className="py-2 px-3">
                  <span className={`px-2 py-0.5 rounded border text-[10px] ${BADGE[r.risk_level] || BADGE.MODERATE}`}>
                    {r.risk_level}
                  </span>
                </td>
                <td className="py-2 px-3 text-gray-300">{(r.tariff_index * 100).toFixed(0)}%</td>
                <td className={`py-2 px-3 font-bold ${deltaColor}`}>
                  {sign}{r.stability_delta.toFixed(1)}
                </td>
                <td className="py-2 px-3 text-gray-400">{r.sentiment_aggregate.toFixed(2)}</td>
                <td className="py-2 px-3 text-gray-400">{(r.confidence * 100).toFixed(0)}%</td>
                <td className="py-2 px-3 text-gray-500 max-w-xs truncate">
                  {r.top_entities?.slice(0, 3).join(", ")}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {data.length === 0 && (
        <div className="py-12 text-center text-gray-600 text-xs tracking-widest">
          NO RISK DATA AVAILABLE — RUN INGESTION PIPELINE
        </div>
      )}
    </div>
  );
}
