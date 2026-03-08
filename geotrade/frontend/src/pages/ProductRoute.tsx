import { useState, useEffect } from "react";
import { useStrategy } from "../hooks/useStrategy";

interface Props {
  onBack: () => void;
}

const INDUSTRIES = [
  "General Trade",
  "Electronics",
  "Automotive",
  "Pharmaceuticals",
  "Textile",
  "Agriculture",
  "Energy",
  "Chemicals",
  "Machinery",
  "Metals",
];

const COUNTRIES = [
  "USA",
  "CHN",
  "DEU",
  "IND",
  "RUS",
  "GBR",
  "JPN",
  "KOR",
  "MEX",
  "BRA",
  "VNM",
  "SGP",
  "FRA",
  "AUS",
  "CAN",
];

export function ProductRoute({ onBack }: Props) {
  const [product, setProduct] = useState("semiconductors");
  const [origin, setOrigin] = useState("USA");
  const [targetMarket, setTargetMarket] = useState("DEU");
  const [industry, setIndustry] = useState("Electronics");
  const [budget, setBudget] = useState("500000");

  const { strategy, loading, error, fetchStrategy } = useStrategy({
    product,
    origin,
    target_market: targetMarket,
    industry,
    budget: parseInt(budget) || 100000,
  });

  useEffect(() => {
    // Auto-fetch on mount with default values
    fetchStrategy();
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchStrategy();
  };

  return (
    <div className="p-6 max-w-screen-2xl mx-auto font-mono">
      {/* Back */}
      <button onClick={onBack} className="text-xs text-gray-500 hover:text-gray-300 mb-6 tracking-widest">
        ← BACK TO DASHBOARD
      </button>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-green-400 tracking-widest">TRADE STRATEGY GENERATOR</h1>
        <p className="text-gray-500 text-xs mt-1">AI-powered route optimization and risk mitigation planning</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Input Form */}
        <div className="lg:col-span-1">
          <form onSubmit={handleSubmit} className="bg-gray-900 border border-gray-800 rounded-lg p-6 space-y-4">
            <h2 className="text-xs text-gray-400 tracking-widest mb-4">SUPPLY CHAIN PARAMETERS</h2>

            {/* Product */}
            <div>
              <label className="text-xs text-gray-500 tracking-widest block mb-2">PRODUCT</label>
              <input
                type="text"
                value={product}
                onChange={(e) => setProduct(e.target.value)}
                className="w-full bg-gray-950 border border-gray-700 rounded px-3 py-2 text-xs text-gray-100 placeholder-gray-600 focus:outline-none focus:border-green-600"
                placeholder="e.g., semiconductors"
              />
            </div>

            {/* Origin */}
            <div>
              <label className="text-xs text-gray-500 tracking-widest block mb-2">ORIGIN COUNTRY</label>
              <select
                value={origin}
                onChange={(e) => setOrigin(e.target.value)}
                className="w-full bg-gray-950 border border-gray-700 rounded px-3 py-2 text-xs text-gray-100 focus:outline-none focus:border-green-600"
              >
                {COUNTRIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            {/* Target Market */}
            <div>
              <label className="text-xs text-gray-500 tracking-widest block mb-2">TARGET MARKET</label>
              <select
                value={targetMarket}
                onChange={(e) => setTargetMarket(e.target.value)}
                className="w-full bg-gray-950 border border-gray-700 rounded px-3 py-2 text-xs text-gray-100 focus:outline-none focus:border-green-600"
              >
                {COUNTRIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            {/* Industry */}
            <div>
              <label className="text-xs text-gray-500 tracking-widest block mb-2">INDUSTRY</label>
              <select
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                className="w-full bg-gray-950 border border-gray-700 rounded px-3 py-2 text-xs text-gray-100 focus:outline-none focus:border-green-600"
              >
                {INDUSTRIES.map((ind) => (
                  <option key={ind} value={ind}>
                    {ind}
                  </option>
                ))}
              </select>
            </div>

            {/* Budget */}
            <div>
              <label className="text-xs text-gray-500 tracking-widest block mb-2">BUDGET (USD)</label>
              <input
                type="number"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                className="w-full bg-gray-950 border border-gray-700 rounded px-3 py-2 text-xs text-gray-100 focus:outline-none focus:border-green-600"
                placeholder="100000"
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full mt-6 px-4 py-2 bg-green-700 hover:bg-green-600 disabled:opacity-50 text-white text-xs rounded transition-colors tracking-widest font-bold"
            >
              {loading ? "▶ GENERATING..." : "▶ GENERATE STRATEGY"}
            </button>

            {error && <div className="text-xs text-red-400 bg-red-900/20 border border-red-800 rounded p-2 mt-2">{error}</div>}
          </form>
        </div>

        {/* Strategy Results */}
        <div className="lg:col-span-2 space-y-4">
          {loading && (
            <div className="flex items-center justify-center h-96">
              <div className="text-green-400 animate-pulse font-mono text-sm">▶ ANALYZING TRADE ROUTES...</div>
            </div>
          )}

          {strategy && !loading && (
            <>
              {/* Executive Summary */}
              <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
                <h3 className="text-xs text-gray-400 tracking-widest mb-3">EXECUTIVE SUMMARY</h3>
                <p className="text-sm text-gray-300 leading-relaxed">{strategy.strategy?.executive_summary}</p>
              </div>

              {/* Primary Route */}
              {strategy.strategy?.primary_route && (
                <div className="bg-gray-900 border border-green-800/50 rounded-lg p-6">
                  <h3 className="text-xs text-green-400 tracking-widest mb-3">RECOMMENDED PRIMARY ROUTE</h3>
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-500">Origin:</span>
                      <span className="text-gray-300 font-bold">{strategy.strategy.primary_route.origin}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-500">Destination:</span>
                      <span className="text-gray-300 font-bold">{strategy.strategy.primary_route.destination}</span>
                    </div>
                    {strategy.strategy.primary_route.via_countries?.length > 0 && (
                      <div className="flex justify-between text-xs">
                        <span className="text-gray-500">Via:</span>
                        <span className="text-gray-300 font-bold">{strategy.strategy.primary_route.via_countries.join(", ")}</span>
                      </div>
                    )}
                    <div className="mt-3 pt-3 border-t border-gray-700">
                      <p className="text-xs text-gray-400">{strategy.strategy.primary_route.rationale}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Backup Route */}
              {strategy.strategy?.backup_route && (
                <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
                  <h3 className="text-xs text-gray-400 tracking-widest mb-3">RECOMMENDED BACKUP ROUTE</h3>
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-500">Origin:</span>
                      <span className="text-gray-300 font-bold">{strategy.strategy.backup_route.origin}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-500">Destination:</span>
                      <span className="text-gray-300 font-bold">{strategy.strategy.backup_route.destination}</span>
                    </div>
                    <div className="mt-3 pt-3 border-t border-gray-700">
                      <p className="text-xs text-gray-400">{strategy.strategy.backup_route.rationale}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Timeline */}
              {strategy.strategy?.timeline && (
                <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
                  <h3 className="text-xs text-gray-400 tracking-widest mb-4">ACTION TIMELINE</h3>
                  <div className="space-y-3">
                    {Object.entries(strategy.strategy.timeline).map(([phase, actions]) => (
                      <div key={phase}>
                        <h4 className="text-xs text-green-400 font-bold tracking-widest mb-1">{phase.toUpperCase()}</h4>
                        <p className="text-xs text-gray-400 leading-relaxed">{String(actions)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Risk Mitigation */}
              {strategy.strategy?.risk_mitigation && strategy.strategy.risk_mitigation.length > 0 && (
                <div className="bg-gray-900 border border-red-800/30 rounded-lg p-6">
                  <h3 className="text-xs text-red-400 tracking-widest mb-3">RISK MITIGATION</h3>
                  <ul className="space-y-2">
                    {strategy.strategy.risk_mitigation.map((item, i) => (
                      <li key={i} className="text-xs text-gray-400 flex gap-2">
                        <span className="text-red-400 flex-shrink-0">▸</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Cost Optimization */}
              {strategy.strategy?.cost_optimization && strategy.strategy.cost_optimization.length > 0 && (
                <div className="bg-gray-900 border border-blue-800/30 rounded-lg p-6">
                  <h3 className="text-xs text-blue-400 tracking-widest mb-3">COST OPTIMIZATION</h3>
                  <ul className="space-y-2">
                    {strategy.strategy.cost_optimization.map((item, i) => (
                      <li key={i} className="text-xs text-gray-400 flex gap-2">
                        <span className="text-blue-400 flex-shrink-0">▸</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* KPI Targets */}
              {strategy.strategy?.kpi_targets && (
                <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
                  <h3 className="text-xs text-gray-400 tracking-widest mb-4">KPI TARGETS</h3>
                  <div className="grid grid-cols-2 gap-4">
                    {Object.entries(strategy.strategy.kpi_targets).map(([key, value]) => (
                      <div key={key}>
                        <div className="text-xs text-gray-500 tracking-widest mb-1">{key.toUpperCase()}</div>
                        <div className="text-lg font-bold text-green-400">{String(value)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Warnings */}
              {strategy.strategy?.warnings && strategy.strategy.warnings.length > 0 && (
                <div className="bg-gray-900 border border-orange-800/50 rounded-lg p-6">
                  <h3 className="text-xs text-orange-400 tracking-widest mb-3">⚠ WARNINGS</h3>
                  <ul className="space-y-2">
                    {strategy.strategy.warnings.map((warning, i) => (
                      <li key={i} className="text-xs text-gray-400 flex gap-2">
                        <span className="text-orange-400 flex-shrink-0">⚠</span>
                        <span>{warning}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Confidence & Generated Date */}
              <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-gray-500">Model Confidence:</span>
                  <span className="text-gray-300 font-bold">{((strategy.strategy?.confidence || 0) * 100).toFixed(0)}%</span>
                </div>
                <div className="flex items-center justify-between text-xs mt-2">
                  <span className="text-gray-500">Generated:</span>
                  <span className="text-gray-300 font-bold">{new Date(strategy.generated_date).toLocaleString()}</span>
                </div>
              </div>
            </>
          )}

          {!strategy && !loading && (
            <div className="flex items-center justify-center h-96">
              <div className="text-gray-600 text-sm">Submit parameters to generate strategy</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
