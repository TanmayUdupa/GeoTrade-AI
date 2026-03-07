/**
 * Hook for fetching alternative countries from /recommend endpoint
 */

import { useState, useEffect } from "react";
import { adaptRecommendResponse } from "../services/apiAdapter";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8003";

export interface Alternative {
  country_code: string;
  country_name: string;
  risk_score: number;
  risk_reduction: number;
  composite_score: number;
  tariff_rate_pct: number;
  total_landed_cost_usd: number;
  estimated_roi_pct: number;
  profitability: "HIGH" | "MEDIUM" | "LOW";
  justification: string;
}

export interface RecommendationData {
  current_country: string;
  current_risk_score: number;
  alternatives: Alternative[];
}

export function useRecommendation(countryCode: string | null) {
  const [recommendation, setRecommendation] = useState<RecommendationData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!countryCode) {
      setRecommendation(null);
      return;
    }

    setLoading(true);
    setError(null);

    fetch(`${API_BASE}/recommend?country_code=${countryCode}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        setRecommendation(adaptRecommendResponse(data));
        setLoading(false);
      })
      .catch(e => {
        setError(e.message);
        setLoading(false);
      });
  }, [countryCode]);

  return { recommendation, loading, error };
}
