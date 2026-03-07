// frontend/src/types/index.ts

export type RiskLevel = "LOW" | "MODERATE" | "HIGH" | "CRITICAL";
export type AlertSeverity = "INFO" | "WARNING" | "CRITICAL";
export type SentimentLabel = "POSITIVE" | "NEUTRAL" | "NEGATIVE";
export type ForecastModel = "lstm" | "arima" | "ensemble";

export interface CountryRiskScore {
  country_code: string;
  country_name: string;
  risk_score: number;
  risk_level: RiskLevel;
  tariff_index: number;
  stability_score: number;
  stability_delta: number;
  sentiment_aggregate: number;
  confidence: number;
  top_entities: string[];
  last_updated: string;
}

export interface ForecastPoint {
  date: string;
  risk_score: number;
  lower_bound: number;
  upper_bound: number;
}

export interface CountryForecast {
  country_code: string;
  model_used: ForecastModel;
  forecast_horizon_days: number;
  points: ForecastPoint[];
  rmse: number;
  mae: number;
  generated_at: string;
}

export interface AlternativeCountry {
  country_code: string;
  country_name: string;
  alt_score: number;
  reasons: string[];
}

export interface SupplyChainRec {
  source_country: string;
  risk_level: RiskLevel;
  alternatives: AlternativeCountry[];
  disruption_probability: number;
  disruption_horizon_days: number;
}

export interface TradeAlert {
  alert_id: string;
  country_code: string;
  severity: AlertSeverity;
  title: string;
  summary: string;
  source_articles: string[];
  risk_delta: number;
  created_at: string;
}
