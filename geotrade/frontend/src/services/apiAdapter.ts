import type { CountryRiskScore } from "../types";

function scoreToRiskLevel(score: number): "LOW" | "MODERATE" | "HIGH" | "CRITICAL" {
  if (score < 30) return "LOW";
  if (score < 60) return "MODERATE";
  if (score < 80) return "HIGH";
  return "CRITICAL";
}

function getCountryName(code: string): string {
  const names: Record<string, string> = {
    USA: "United States",
    CHN: "China",
    DEU: "Germany",
    IND: "India",
    RUS: "Russia",
    GBR: "United Kingdom",
    JPN: "Japan",
    KOR: "South Korea",
    MEX: "Mexico",
    BRA: "Brazil",
    VNM: "Vietnam",
    SGP: "Singapore",
    FRA: "France",
    AUS: "Australia",
    CAN: "Canada",
  };
  return names[code] || code;
}

export function adaptScoreResponse(apiResponse: any, countryCode: string): CountryRiskScore {
  const score = apiResponse.score || 10; // default to 10 if missing
  const previousScore = apiResponse.previous_score || null;

  return {
    country_code: countryCode,
    country_name: getCountryName(countryCode),
    risk_score: score,
    risk_level: scoreToRiskLevel(score),
    
    // Calculate stability_delta from previous score
    stability_delta: previousScore ? score - previousScore : 0,
    stability_score: 100 - Math.abs(score - 50), // 50 is neutral, higher = more stable
    
    // Use confidence from API or reasonable default
    confidence: apiResponse.confidence || 0.5,
    
    // Extract top events and convert to entities (simplified)
    top_entities: apiResponse.contributing_events
      ?.slice(0, 5)
      ?.map((evt: any) => `${evt.event_type}: ${evt.event_date}`) || [],
    
    // Placeholder values (API doesn't provide these)
    tariff_index: 0.5, // default 50% - should come from separate tariff API
    sentiment_aggregate: 0, // not provided by this API version
    
    last_updated: new Date().toISOString(),
  };
}

export function adaptPredictResponse(apiResponse: any) {
  return {
    country_code: apiResponse.country_code,
    current_score: apiResponse.current_score,
    model_confidence: apiResponse.model_confidence,
    data_points_used: apiResponse.data_points_used,
    predictions: apiResponse.predictions.map((p: any) => ({
      horizon_days: p.horizon_days,
      predicted_score: p.predicted_score,
      confidence_interval_lower: p.confidence_interval_lower,
      confidence_interval_upper: p.confidence_interval_upper,
      confidence_level: p.confidence_level,
    })),
    detected_patterns: apiResponse.detected_patterns || [],
    historical_scores: apiResponse.historical_scores || [],
  };
}

export function adaptRecommendResponse(apiResponse: any) {
  if (!apiResponse.alternatives || apiResponse.alternatives.length === 0) {
    return null;
  }

  return {
    current_country: apiResponse.current_country,
    current_risk_score: apiResponse.current_risk_score,
    alternatives: apiResponse.alternatives.map((alt: any) => ({
      country_code: alt.country_code,
      country_name: getCountryName(alt.country_code),
      risk_score: alt.risk_score,
      risk_reduction: alt.risk_reduction,
      composite_score: alt.composite_score,
      tariff_rate_pct: alt.tariff_rate_pct,
      total_landed_cost_usd: alt.total_landed_cost_usd,
      estimated_roi_pct: alt.estimated_roi_pct,
      profitability: alt.profitability, // HIGH | MEDIUM | LOW
      justification: alt.justification,
    })),
  };
}

export function adaptStrategyResponse(apiResponse: any) {
  return {
    product: apiResponse.product,
    industry: apiResponse.industry,
    origin: apiResponse.origin,
    target_market: apiResponse.target_market,
    budget_usd: apiResponse.budget_usd,
    
    risk_context: apiResponse.risk_context, // Direct pass-through
    top_alternatives: apiResponse.top_alternatives,
    
    strategy: {
      executive_summary: apiResponse.strategy?.executive_summary,
      primary_route: apiResponse.strategy?.recommended_primary_route,
      backup_route: apiResponse.strategy?.recommended_backup_route,
      timeline: apiResponse.strategy?.timeline,
      risk_mitigation: apiResponse.strategy?.risk_mitigation || [],
      cost_optimization: apiResponse.strategy?.cost_optimization || [],
      kpi_targets: apiResponse.strategy?.kpi_targets,
      warnings: apiResponse.strategy?.warnings || [],
      confidence: apiResponse.strategy?.confidence,
    },
    
    generated_date: apiResponse.generated_date,
  };
}
