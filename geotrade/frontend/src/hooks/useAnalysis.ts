/**
 * Hook for checking API health and submitting articles for analysis
 */

import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8003";

export interface HealthStatus {
  status: "healthy" | "degraded";
  timestamp: string;
  checks: Record<string, { status: string; [key: string]: any }>;
  version: string;
}

export interface AnalysisResult {
  article_id: string;
  countries_found: string[];
  events_extracted: number;
  affected_countries: string[];
  overall_severity: number;
  confidence: number;
  summary: string;
  relationships: Array<{
    country_a: string;
    country_b: string;
    relationship_type: string;
    strength: number;
  }>;
  text_source: string;
}

/**
 * Check API health status
 */
export async function checkHealth(): Promise<HealthStatus | null> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

/**
 * Submit article for AI analysis
 */
export async function analyzeArticle(articleText: string, options?: {
  article_date?: string;
  source_url?: string;
}): Promise<AnalysisResult | null> {
  try {
    const res = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        article_text: articleText,
        article_date: options?.article_date,
        source_url: options?.source_url,
      }),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

/**
 * Hook for article analysis with loading state
 */
export function useArticleAnalysis() {
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analyze = async (articleText: string, options?: {
    article_date?: string;
    source_url?: string;
  }) => {
    setLoading(true);
    setError(null);
    
    try {
      const res = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          article_text: articleText,
          article_date: options?.article_date,
          source_url: options?.source_url,
        }),
      });
      
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      
      const data: AnalysisResult = await res.json();
      setResult(data);
      return data;
    } catch (e: any) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  };

  return { result, loading, error, analyze };
}
