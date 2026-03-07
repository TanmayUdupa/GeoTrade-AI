// frontend/src/App.tsx
import { useState, useEffect, useCallback } from "react";
import { WorldRiskMap } from "./components/map/WorldRiskMap";
import { RiskDashboard } from "./components/RiskDashboard";
import { CountryDeepDive } from "./pages/CountryDeepDive";
import { ComparePage } from "./pages/ComparePage";
import { ProductRoute } from "./pages/ProductRoute";
import { NavBar } from "./components/layout/NavBar";
import { useRiskStore } from "./store/riskStore";

type Page = "dashboard" | "map" | "compare" | "product" | "country";

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null);
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
      />

      <main className="pt-16">
        {page === "dashboard" && (
          <RiskDashboard onCountrySelect={handleCountrySelect} />
        )}
        {page === "map" && (
          <WorldRiskMap onCountrySelect={handleCountrySelect} />
        )}
        {page === "compare" && <ComparePage />}
        {page === "product" && (
          <ProductRoute onBack={() => setPage("dashboard")} />
        )}
        {page === "country" && selectedCountry && (
          <CountryDeepDive
            countryCode={selectedCountry}
            onBack={() => setPage("dashboard")}
          />
        )}
      </main>
    </div>
  );
}
