// frontend/src/components/RiskDashboard.tsx
import { useMemo } from "react";
import { useRiskStore } from "../store/riskStore";
import { RiskGauge } from "./charts/RiskGauge";
import { RiskTable } from "./charts/RiskTable";
import { RiskBarChart } from "./charts/RiskBarChart";
import type { RiskLevel } from "../types";

const RISK_COLORS: Record<RiskLevel, string> = {
  LOW: "#22c55e",
  MODERATE: "#f59e0b",
  HIGH: "#ef4444",
  CRITICAL: "#dc2626",
};

interface Props {
  onCountrySelect: (code: string) => void;
}

export function RiskDashboard({ onCountrySelect }: Props) {
  const { risks, loading } = useRiskStore();
  const sorted = useMemo(
    () => Object.values(risks).sort((a, b) => b.risk_score - a.risk_score),
    [risks]
  );

  const stats = useMemo(() => {
    const all = Object.values(risks);
    return {
      critical: all.filter(r => r.risk_level === "CRITICAL").length,
      high: all.filter(r => r.risk_level === "HIGH").length,
      moderate: all.filter(r => r.risk_level === "MODERATE").length,
      low: all.filter(r => r.risk_level === "LOW").length,
      avg: all.length ? all.reduce((s, r) => s + r.risk_score, 0) / all.length : 0,
    };
  }, [risks]);

  if (loading && sorted.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-green-400 animate-pulse font-mono text-sm">
          ▶ LOADING GEOPOLITICAL DATA...
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-screen-2xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-green-400 tracking-widest">
          GEOTRADE AI // RISK DASHBOARD
        </h1>
        <p className="text-gray-500 text-xs mt-1">
          Real-time geopolitical trade intelligence · {sorted.length} countries tracked
        </p>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        {[
          { label: "CRITICAL", value: stats.critical, color: "text-red-400 border-red-800" },
          { label: "HIGH", value: stats.high, color: "text-orange-400 border-orange-800" },
          { label: "MODERATE", value: stats.moderate, color: "text-yellow-400 border-yellow-800" },
          { label: "LOW", value: stats.low, color: "text-green-400 border-green-800" },
          { label: "AVG SCORE", value: stats.avg.toFixed(1), color: "text-blue-400 border-blue-800" },
        ].map(s => (
          <div
            key={s.label}
            className={`bg-gray-900 border rounded-lg p-4 text-center ${s.color}`}
          >
            <div className="text-3xl font-bold font-mono">{s.value}</div>
            <div className="text-xs text-gray-500 mt-1 tracking-widest">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top Risk Countries — Bar Chart */}
        <div className="lg:col-span-2 bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h2 className="text-xs text-gray-400 tracking-widest mb-4">TOP 15 RISK COUNTRIES</h2>
          <RiskBarChart
            data={sorted.slice(0, 15)}
            onSelect={onCountrySelect}
          />
        </div>

        {/* Risk Level Gauges */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h2 className="text-xs text-gray-400 tracking-widest mb-4">TOP RISK GAUGES</h2>
          <div className="space-y-3">
            {sorted.slice(0, 5).map(r => (
              <RiskGauge
                key={r.country_code}
                countryCode={r.country_code}
                countryName={r.country_name}
                score={r.risk_score}
                level={r.risk_level}
                delta={r.stability_delta}
                onClick={() => onCountrySelect(r.country_code)}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Full Country Table */}
      <div className="mt-6 bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h2 className="text-xs text-gray-400 tracking-widest mb-4">ALL COUNTRIES — RISK INTELLIGENCE</h2>
        <RiskTable data={sorted} onSelect={onCountrySelect} />
      </div>
    </div>
  );
}
