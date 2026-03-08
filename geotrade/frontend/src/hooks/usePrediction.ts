/**
 * Hook for fetching and transforming prediction data from /predict endpoint
 */

import { useState, useEffect } from "react";
import { adaptPredictResponse } from "../services/apiAdapter";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8003";

export interface PredictionData {
  country_code: string;
  current_score: number;
  model_confidence: number;
  data_points_used: number;
  predictions: Array<{
    horizon_days: number;
    predicted_score: number;
    confidence_interval_lower: number;
    confidence_interval_upper: number;
    confidence_level: number;
  }>;
  detected_patterns: any[];
  historical_scores: Array<{ date: string; score: number }>;
}

export function usePrediction(countryCode: string | null) {
  const [prediction, setPrediction] = useState<PredictionData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!countryCode) {
      setPrediction(null);
      return;
    }

    setLoading(true);
    setError(null);

    fetch(`${API_BASE}/predict?country_code=${countryCode}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        setPrediction(adaptPredictResponse(data));
        setLoading(false);
      })
      .catch(e => {
        setError(e.message);
        setLoading(false);
      });
  }, [countryCode]);

  return { prediction, loading, error };
}
