// frontend/src/App.tsx
import { useState, useEffect, useCallback } from "react";
import { WorldRiskMap } from "./components/map/WorldRiskMap";
import { RiskDashboard } from "./components/RiskDashboard";
import { CountryDeepDive } from "./pages/CountryDeepDive";
import { ComparePage } from "./pages/ComparePage";
import { ProductRoute } from "./pages/ProductRoute";
import { NavBar } from "./components/layout/NavBar";
import { useRiskStore } from "./store/riskStore";
import Login from "./Login";

type Page = "dashboard" | "map" | "compare" | "product" | "country";

export default function App() {
  const [user, setUser] = useState<string | null>(
    localStorage.getItem("auth_user")
  );
  const [page, setPage] = useState<Page>("dashboard");
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null);
  const { loadAllRisks } = useRiskStore();

  useEffect(() => {
    if (!user) return; // don't load data if not logged in
    loadAllRisks();
    const interval = setInterval(loadAllRisks, 30_000);
    return () => clearInterval(interval);
  }, [user]);

  const handleCountrySelect = useCallback((code: string) => {
    setSelectedCountry(code);
    setPage("country");
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("auth_user");
    setUser(null);
  };

  // 👇 Show login page if not authenticated
  if (!user) {
    return <Login onLogin={setUser} />;
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-mono">
      <NavBar
        page={page}
        onNavigate={setPage}
      />

      {/* Logout button */}
      <button
        onClick={handleLogout}
        className="fixed top-4 right-4 z-50 text-sm text-gray-400 hover:text-white border border-gray-600 px-3 py-1 rounded-lg"
      >
        Logout
      </button>

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