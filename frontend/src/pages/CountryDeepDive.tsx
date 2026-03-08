// frontend/src/pages/CountryDeepDive.tsx
import { useState } from "react";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine
} from "recharts";
import type { CountryRiskScore } from "../types";
import { useRiskStore } from "../store/riskStore";
import { usePrediction } from "../hooks/usePrediction";
import { Alternative, AlternativesResponse } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8003";

interface Props {
  countryCode: string;
  onBack: () => void;
}

export function CountryDeepDive({ countryCode, onBack }: Props) {
  const { risks } = useRiskStore();
  const { prediction, loading: predLoading } = usePrediction(countryCode);
  const [alternatives, setAlternatives] = useState<AlternativesResponse | null>(null);

  const risk = risks[countryCode] || null;
  const loading = !risk || predLoading;

  // Optional: Fetch /recommend for alternatives
  // useEffect(() => {
  //   if (!countryCode) return;
  //   fetch(`${API_BASE}/recommend?country_code=${countryCode}`)
  //     .then(r => r.json())
  //     .then(setAlternatives)
  //     .catch(() => setAlternatives(null));
  // }, [countryCode]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-green-400 animate-pulse font-mono text-sm">▶ LOADING {countryCode}...</div>
      </div>
    );
  }

  const scoreColor = !risk ? "text-gray-400"
    : risk.risk_level === "CRITICAL" ? "text-red-400"
    : risk.risk_level === "HIGH" ? "text-orange-400"
    : risk.risk_level === "MODERATE" ? "text-yellow-400"
    : "text-green-400";

  return (
    <div className="p-6 max-w-screen-xl mx-auto font-mono">
      {/* Back */}
      <button onClick={onBack} className="text-xs text-gray-500 hover:text-gray-300 mb-6 tracking-widest">
        ← BACK TO DASHBOARD
      </button>

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white">
            {risk?.country_name || countryCode}
          </h1>
          <p className="text-gray-500 text-xs mt-1">ISO: {countryCode} · Last updated: {risk?.last_updated?.slice(0,19).replace("T"," ")} UTC</p>
        </div>
        <div className="text-right">
          <div className={`text-5xl font-bold ${scoreColor}`}>{risk?.risk_score?.toFixed(1)}</div>
          <div className="text-xs text-gray-500 tracking-widest">{risk?.risk_level} RISK</div>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {[
          { label: "TARIFF INDEX", value: `${((risk?.tariff_index || 0) * 100).toFixed(0)}%` },
          { label: "STABILITY Δ", value: `${risk?.stability_delta && risk.stability_delta > 0 ? "+" : ""}${risk?.stability_delta?.toFixed(1) ?? "—"}` },
          { label: "SENTIMENT", value: risk?.sentiment_aggregate?.toFixed(2) ?? "—" },
          { label: "CONFIDENCE", value: `${((risk?.confidence || 0) * 100).toFixed(0)}%` },
        ].map(s => (
          <div key={s.label} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="text-2xl font-bold text-white">{s.value}</div>
            <div className="text-xs text-gray-500 mt-1 tracking-widest">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Forecast Chart */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xs text-gray-400 tracking-widest">RISK FORECAST</h2>
          {prediction?.model_confidence && (
            <span className="text-xs text-gray-500">Confidence: {(prediction.model_confidence * 100).toFixed(0)}%</span>
          )}
        </div>
        {prediction && prediction.historical_scores && prediction.historical_scores.length > 0 ? (
          <>
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={prediction.historical_scores} margin={{ top: 5, right: 10, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#6b7280", fontSize: 9 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v) => v.slice(5)}
                  interval={Math.floor((prediction.historical_scores.length || 1) / 6)}
                />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fill: "#6b7280", fontSize: 9 }}
                  axisLine={false}
                  tickLine={false}
                  width={28}
                />
                <Tooltip
                  contentStyle={{ background: "#111827", border: "1px solid #374151", fontSize: 10, fontFamily: "monospace" }}
                  formatter={(val: number) => [val.toFixed(1), "Risk Score"]}
                />
                <ReferenceLine y={75} stroke="#dc2626" strokeDasharray="3 3" />
                <ReferenceLine y={55} stroke="#ef4444" strokeDasharray="3 3" />
                <Area
                  type="monotone"
                  dataKey="score"
                  stroke="#ef4444"
                  strokeWidth={2}
                  fill="url(#riskGrad)"
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
            <div className="mt-2 text-xs text-gray-600">
              Data points used: {prediction.data_points_used} · Confidence: {(prediction.model_confidence * 100).toFixed(0)}%
            </div>
          </>
        ) : (
          <div className="py-8 text-center text-gray-600 text-xs">FORECAST UNAVAILABLE - INSUFFICIENT DATA</div>
        )}
      </div>

      {/* Supply Chain Alternatives */}
      {alternatives && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h2 className="text-xs text-gray-400 tracking-widest mb-4">
            SUPPLY CHAIN ALTERNATIVES · DISRUPTION PROB: {(alternatives.disruption_probability * 100).toFixed(0)}%
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {alternatives.alternatives.map((alt: Alternative) => (
              <div key={alt.country_code} className="bg-gray-950 border border-gray-800 rounded p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-bold text-white">{alt.country_name}</span>
                  <span className="text-xs text-green-400 font-bold">{(alt.alt_score * 100).toFixed(0)}%</span>
                </div>
                <div className="w-full bg-gray-800 rounded-full h-1 mb-2">
                  <div
                    className="h-1 rounded-full bg-green-500"
                    style={{ width: `${alt.alt_score * 100}%` }}
                  />
                </div>
                <ul className="text-xs text-gray-500 space-y-0.5">
                  {alt.reasons.map((r: string) => <li key={r}>▸ {r}</li>)}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
