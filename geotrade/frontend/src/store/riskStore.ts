// frontend/src/store/riskStore.ts
import { create } from "zustand";
import type { CountryRiskScore } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8003";

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
      const res = await fetch(`${API_BASE}/risk`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: CountryRiskScore[] = await res.json();
      const map: Record<string, CountryRiskScore> = {};
      data.forEach(r => { map[r.country_code] = r; });
      set({ risks: map, loading: false });
    } catch (e: any) {
      set({ error: e.message, loading: false });
    }
  },

  getCountryRisk: async (code: string) => {
    const cached = get().risks[code];
    if (cached) return cached;
    try {
      const res = await fetch(`${API_BASE}/risk/${code}`);
      if (!res.ok) return null;
      const data: CountryRiskScore = await res.json();
      set(state => ({ risks: { ...state.risks, [code]: data } }));
      return data;
    } catch {
      return null;
    }
  },
}));
