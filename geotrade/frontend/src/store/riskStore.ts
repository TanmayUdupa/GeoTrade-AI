// frontend/src/store/riskStore.ts
import { create } from "zustand";
import type { CountryRiskScore } from "../types";
import { adaptScoreResponse } from "../services/apiAdapter";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8003";

// List of countries to load on init
const DEFAULT_COUNTRIES = ["USA", "CHN", "DEU", "IND", "RUS", "GBR", "JPN", "KOR", "MEX", "BRA", "VNM", "SGP"];

interface RiskStore {
  risks: Record<string, CountryRiskScore>;
  loading: boolean;
  error: string | null;
  loadAllRisks: () => Promise<void>;
  getCountryRisk: (code: string) => Promise<CountryRiskScore | null>;
}

export const useRiskStore = create<RiskStore>((set, get) => ({
  risks: {},
  loading: false,
  error: null,

  loadAllRisks: async () => {
    set({ loading: true, error: null });
    try {
      // Fetch scores for all default countries in parallel
      const promises = DEFAULT_COUNTRIES.map(code =>
        fetch(`${API_BASE}/score?country_code=${code}`)
          .then(r => r.json())
          .then(data => ({ code, data }))
          .catch(() => ({ code, data: null }))
      );
      
      const results = await Promise.all(promises);
      const map: Record<string, CountryRiskScore> = {};
      
      results.forEach(({ code, data }) => {
        if (data) {
          map[code] = adaptScoreResponse(data, code);
        }
      });
      
      set({ risks: map, loading: false });
    } catch (e: any) {
      set({ error: e.message, loading: false });
    }
  },

  getCountryRisk: async (code: string) => {
    const cached = get().risks[code];
    if (cached) return cached;
    
    try {
      const res = await fetch(`${API_BASE}/score?country_code=${code}`);
      if (!res.ok) return null;
      const data = await res.json();
      const adapted = adaptScoreResponse(data, code);
      set(state => ({ risks: { ...state.risks, [code]: adapted } }));
      return adapted;
    } catch {
      return null;
    }
  },
}));
