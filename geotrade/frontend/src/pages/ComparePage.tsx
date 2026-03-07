// frontend/src/pages/ComparePage.tsx
import { useState } from "react";
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip } from "recharts";
import type { CountryRiskScore } from "../types";
import { useRiskStore } from "../store/riskStore";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8003";

const AVAILABLE = ["CN","US","RU","IN","EU","JP","DE","FR","AU","BR","VN","MX","CA","KR","SA","TR","ID"];

export function ComparePage() {
  const { risks } = useRiskStore();
  const [selected, setSelected] = useState<string[]>(["CN","US","IN"]);
  const [comparing, setComparing] = useState<CountryRiskScore[]>([]);
  const [loading, setLoading] = useState(false);

  const toggle = (code: string) => {
    setSelected(prev =>
      prev.includes(code)
        ? prev.filter(c => c !== code)
        : prev.length < 5 ? [...prev, code] : prev
    );
  };

  const runCompare = async () => {
    if (selected.length < 2) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/compare?codes=${selected.join(",")}`);
      const data = await res.json();
      setComparing(data.countries || []);
    } catch (e) {
      // fallback to store data
      setComparing(selected.map(c => risks[c]).filter(Boolean));
    }
    setLoading(false);
  };

  const radarData = [
    { metric: "Risk Score", ...Object.fromEntries(comparing.map(c => [c.country_code, c.risk_score])) },
    { metric: "Tariff %", ...Object.fromEntries(comparing.map(c => [c.country_code, c.tariff_index * 100])) },
    { metric: "Stability", ...Object.fromEntries(comparing.map(c => [c.country_code, Math.abs(c.stability_delta) * 10])) },
    { metric: "Confidence", ...Object.fromEntries(comparing.map(c => [c.country_code, c.confidence * 100])) },
  ];

  const COLORS = ["#ef4444","#3b82f6","#22c55e","#f59e0b","#a855f7"];

  return (
    <div className="p-6 max-w-screen-xl mx-auto font-mono">
      <h1 className="text-2xl font-bold text-green-400 tracking-widest mb-2">COUNTRY COMPARISON</h1>
      <p className="text-xs text-gray-500 mb-6">Select up to 5 countries to compare risk profiles</p>

      {/* Country selector */}
      <div className="flex flex-wrap gap-2 mb-4">
        {AVAILABLE.map(code => (
          <button
            key={code}
            onClick={() => toggle(code)}
            className={`px-3 py-1.5 text-xs rounded border transition-all ${
              selected.includes(code)
                ? "bg-green-900/30 border-green-600 text-green-400"
                : "bg-gray-900 border-gray-700 text-gray-400 hover:text-gray-200"
            }`}
          >
            {code}
          </button>
        ))}
        <button
          onClick={runCompare}
          disabled={selected.length < 2 || loading}
          className="ml-2 px-4 py-1.5 text-xs bg-green-700 hover:bg-green-600 disabled:opacity-50 text-white rounded transition-colors"
        >
          {loading ? "LOADING..." : "▶ COMPARE"}
        </button>
      </div>

      {comparing.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Radar Chart */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h2 className="text-xs text-gray-400 tracking-widest mb-4">RISK RADAR</h2>
            <ResponsiveContainer width="100%" height={280}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#374151" />
                <PolarAngleAxis dataKey="metric" tick={{ fill: "#6b7280", fontSize: 10 }} />
                {comparing.map((c, i) => (
                  <Radar
                    key={c.country_code}
                    name={c.country_code}
                    dataKey={c.country_code}
                    stroke={COLORS[i]}
                    fill={COLORS[i]}
                    fillOpacity={0.1}
                  />
                ))}
                <Tooltip contentStyle={{ background: "#111827", border: "1px solid #374151", fontSize: 10 }} />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          {/* Side-by-side stats */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h2 className="text-xs text-gray-400 tracking-widest mb-4">SCORE COMPARISON</h2>
            <div className="space-y-3">
              {comparing.map((c, i) => (
                <div key={c.country_code} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold" style={{ color: COLORS[i] }}>{c.country_code}</span>
                    <span className="text-gray-300">{c.country_name}</span>
                    <span className="text-white font-bold">{c.risk_score.toFixed(1)}</span>
                  </div>
                  <div className="w-full bg-gray-800 rounded-full h-1.5">
                    <div
                      className="h-1.5 rounded-full transition-all"
                      style={{ width: `${c.risk_score}%`, backgroundColor: COLORS[i] }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {comparing.length === 0 && (
        <div className="py-16 text-center text-gray-600 text-sm">
          SELECT 2–5 COUNTRIES AND CLICK COMPARE
        </div>
      )}
    </div>
  );
}
