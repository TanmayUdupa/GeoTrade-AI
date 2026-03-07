// frontend/src/components/alerts/AlertFeed.tsx
import { useState } from "react";
import type { TradeAlert } from "../../types";

const SEVERITY_STYLE = {
  INFO:     "border-blue-700 bg-blue-900/20 text-blue-400",
  WARNING:  "border-yellow-700 bg-yellow-900/20 text-yellow-400",
  CRITICAL: "border-red-700 bg-red-900/30 text-red-400 animate-pulse",
};

interface Props {
  alerts: TradeAlert[];
}

export function AlertFeed({ alerts }: Props) {
  const [open, setOpen] = useState(false);
  const critical = alerts.filter(a => a.severity === "CRITICAL").length;

  return (
    <div className="fixed bottom-4 right-4 z-50 font-mono">
      {/* Toggle Button */}
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 bg-gray-900 border border-gray-700 rounded-full px-4 py-2 text-xs text-gray-300 hover:text-white hover:border-gray-500 transition-all shadow-xl"
      >
        <span className={`w-2 h-2 rounded-full ${critical > 0 ? "bg-red-500 animate-ping" : "bg-green-500"}`} />
        ALERTS
        {alerts.length > 0 && (
          <span className="bg-gray-700 text-gray-200 rounded-full px-2 py-0.5 text-[10px]">
            {alerts.length}
          </span>
        )}
        {critical > 0 && (
          <span className="bg-red-900 text-red-400 border border-red-700 rounded-full px-2 py-0.5 text-[10px]">
            {critical} CRITICAL
          </span>
        )}
      </button>

      {/* Panel */}
      {open && (
        <div className="absolute bottom-12 right-0 w-80 max-h-96 overflow-y-auto bg-gray-950 border border-gray-800 rounded-lg shadow-2xl">
          <div className="sticky top-0 bg-gray-950 border-b border-gray-800 px-3 py-2 text-xs text-gray-500 tracking-widest">
            LIVE ALERTS · {alerts.length} EVENTS
          </div>
          {alerts.length === 0 ? (
            <div className="py-8 text-center text-gray-600 text-xs">
              NO ALERTS · MONITORING ACTIVE
            </div>
          ) : (
            <div className="divide-y divide-gray-900">
              {alerts.map(a => (
                <div
                  key={a.alert_id}
                  className={`p-3 border-l-2 ${SEVERITY_STYLE[a.severity]}`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-bold tracking-widest">{a.severity}</span>
                    <span className="text-[10px] text-gray-600">{a.country_code}</span>
                  </div>
                  <div className="text-xs text-gray-200 leading-relaxed">{a.title}</div>
                  <div className="text-[10px] text-gray-600 mt-1">
                    Δ {a.risk_delta > 0 ? "+" : ""}{a.risk_delta?.toFixed(1)} pts
                    · {a.created_at?.slice(11, 19)} UTC
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
