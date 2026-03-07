# backend/shared/models.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SentimentLabel(str, Enum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"


# ─── News / Ingestion Models ────────────────────────────────────────

class NewsArticle(BaseModel):
    article_id: str
    source: str
    title: str
    content: str
    url: str
    published_at: datetime
    countries_mentioned: List[str] = []
    raw_html: Optional[str] = None
    metadata: Dict[str, Any] = {}


class IngestRequest(BaseModel):
    source_type: str  # "rss" | "api" | "crawler"
    source_url: str
    max_articles: int = 50


# ─── NLP Models ─────────────────────────────────────────────────────

class Entity(BaseModel):
    text: str
    label: str  # GPE, ORG, PERSON, etc.
    start: int
    end: int


class NLPResult(BaseModel):
    article_id: str
    entities: List[Entity]
    sentiment: SentimentLabel
    sentiment_confidence: float
    tariff_probability: float        # 0-1
    conflict_signals: List[str]
    policy_changes: List[str]
    processed_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Risk Scoring Models ─────────────────────────────────────────────

class CountryRiskScore(BaseModel):
    country_code: str                # ISO 3166-1 alpha-2
    country_name: str
    risk_score: float                # 0-100
    risk_level: RiskLevel
    tariff_index: float              # 0-1
    stability_score: float           # 7-day trend value
    stability_delta: float           # change vs previous period
    sentiment_aggregate: float       # avg sentiment
    confidence: float
    top_entities: List[str] = []
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class RiskComparisonResponse(BaseModel):
    countries: List[CountryRiskScore]
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Prediction Models ───────────────────────────────────────────────

class ForecastPoint(BaseModel):
    date: str         # YYYY-MM-DD
    risk_score: float
    lower_bound: float
    upper_bound: float


class CountryForecast(BaseModel):
    country_code: str
    model_used: str   # lstm | arima | xgboost | ensemble
    forecast_horizon_days: int
    points: List[ForecastPoint]
    rmse: float
    mae: float
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class AlternativeCountry(BaseModel):
    country_code: str
    country_name: str
    alt_score: float   # 0-1, higher = better alternative
    reasons: List[str]


class SupplyChainRecommendation(BaseModel):
    source_country: str
    risk_level: RiskLevel
    alternatives: List[AlternativeCountry]
    disruption_probability: float
    disruption_horizon_days: int


# ─── Alert Models ────────────────────────────────────────────────────

class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class TradeAlert(BaseModel):
    alert_id: str
    country_code: str
    severity: AlertSeverity
    title: str
    summary: str
    source_articles: List[str] = []
    risk_delta: float   # change that triggered the alert
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AlertSubscription(BaseModel):
    user_id: str
    countries: List[str]
    min_severity: AlertSeverity = AlertSeverity.WARNING
    channels: List[str] = ["websocket"]  # websocket | email | sns
