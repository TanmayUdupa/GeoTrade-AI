/**
 * Hook for fetching trade strategy from /strategy endpoint
 */

import { useState } from "react";
import { adaptStrategyResponse } from "../services/apiAdapter";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8003";

export interface StrategyData {
  product: string;
  industry: string;
  origin: string;
  target_market: string;
  budget_usd: number;
  risk_context: Record<string, any>;
  top_alternatives: any[];
  strategy: {
    executive_summary: string;
    primary_route: any;
    backup_route: any;
    timeline: Record<string, string>;
    risk_mitigation: string[];
    cost_optimization: string[];
    kpi_targets: any;
    warnings: string[];
    confidence: number;
  };
  generated_date: string;
}

export function useStrategy(params: {
  product?: string;
  origin?: string;
  target_market?: string;
  industry?: string;
  budget?: number;
} | null) {
  const [strategy, setStrategy] = useState<StrategyData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStrategy = async () => {
    if (!params?.product || !params?.origin || !params?.target_market) {
      setError("Missing required parameters: product, origin, target_market");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const queryParams = new URLSearchParams({
        product: params.product,
        origin: params.origin,
        target_market: params.target_market,
        ...(params.industry && { industry: params.industry }),
        ...(params.budget && { budget: params.budget.toString() }),
      });

      const res = await fetch(`${API_BASE}/strategy?${queryParams}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      
      const data = await res.json();
      setStrategy(adaptStrategyResponse(data));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return { strategy, loading, error, fetchStrategy };
}
