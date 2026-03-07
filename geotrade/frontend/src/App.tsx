// frontend/src/App.tsx
import { useState, useEffect, useCallback } from "react";
import { WorldRiskMap } from "./components/map/WorldRiskMap";
import { RiskDashboard } from "./components/RiskDashboard";
import { AlertFeed } from "./components/alerts/AlertFeed";
import { CountryDeepDive } from "./pages/CountryDeepDive";
import { ComparePage } from "./pages/ComparePage";
import { NavBar } from "./components/layout/NavBar";
import { useAlertSocket } from "./hooks/useAlertSocket";
import { useRiskStore } from "./store/riskStore";
import type { TradeAlert } from "./types";

type Page = "dashboard" | "map" | "compare" | "country";

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null);
  const { alerts, connected } = useAlertSocket();
  const { loadAllRisks } = useRiskStore();

  useEffect(() => {
    loadAllRisks();
    const interval = setInterval(loadAllRisks, 30_000);
    return () => clearInterval(interval);
  }, []);

  const handleCountrySelect = useCallback((code: string) => {
    setSelectedCountry(code);
    setPage("country");
  }, []);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-mono">
      <NavBar
        page={page}
        onNavigate={setPage}
        wsConnected={connected}
        alertCount={alerts.filter(a => a.severity === "CRITICAL").length}
      />

      <main className="pt-16">
        {page === "dashboard" && (
          <RiskDashboard onCountrySelect={handleCountrySelect} />
        )}
        {page === "map" && (
          <WorldRiskMap onCountrySelect={handleCountrySelect} />
        )}
        {page === "compare" && <ComparePage />}
        {page === "country" && selectedCountry && (
          <CountryDeepDive
            countryCode={selectedCountry}
            onBack={() => setPage("dashboard")}
          />
        )}
      </main>

      {/* Floating Alert Feed */}
      <AlertFeed alerts={alerts} />
    </div>
  );
}
