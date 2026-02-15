# Design Document: AI-Based Trade Risk Intelligence System

## Overview

The AI-based Trade Risk Intelligence System is designed to transform unstructured geopolitical news into actionable trade risk insights. The system follows a pipeline architecture where news articles flow through analysis, scoring, prediction, and recommendation stages. Each stage produces structured outputs that feed into subsequent stages, enabling comprehensive risk assessment and strategic decision-making.

The system is built around five core components:
1. **News Analyzer**: Extracts structured entities and events from unstructured text
2. **Risk Scorer**: Computes numerical risk indicators from extracted events
3. **Predictor**: Forecasts future trade conditions using time-series modeling
4. **Recommendation Engine**: Suggests alternative trade routes based on risk analysis
5. **Data Store**: Persists all data with temporal tracking and referential integrity

## Architecture

The system follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                        API Layer                             │
│              (REST endpoints, validation, auth)              │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                     Processing Pipeline                      │
│  News Analyzer → Risk Scorer → Predictor → Recommender     │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Data Access Layer                       │
│         (Repositories, queries, transactions)                │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                       Data Store                             │
│    (Articles, Events, Scores, Predictions, Metadata)        │
└─────────────────────────────────────────────────────────────┘
```

### Processing Flow

1. **Ingestion**: News articles arrive via REST API
2. **Analysis**: News Analyzer extracts entities (countries, dates, policy types) and identifies geopolitical events
3. **Scoring**: Risk Scorer aggregates events into country-specific risk scores with temporal weighting
4. **Prediction**: Predictor generates forecasts using historical risk score time series
5. **Recommendation**: Recommendation Engine identifies safer alternative countries based on current and predicted risk scores
6. **Response**: Structured results returned to client with metadata and confidence indicators

## Components and Interfaces

### News Analyzer

**Purpose**: Extract structured information from unstructured news text.

**Interface**:
```
function analyze_article(article_text: String, article_date: Date, source_url: String) -> AnalysisResult

type AnalysisResult = {
  article_id: UUID,
  extracted_countries: List<CountryCode>,
  extracted_events: List<GeopoliticalEvent>,
  relationships: List<CountryRelationship>,
  confidence: Float  // 0.0 to 1.0
}

type GeopoliticalEvent = {
  event_type: EventType,  // TARIFF | SANCTION | TENSION
  affected_countries: List<CountryCode>,
  severity: Float,  // 0.0 to 1.0
  event_date: Date,
  description: String
}

type CountryRelationship = {
  country_a: CountryCode,
  country_b: CountryCode,
  relationship_type: RelationType,  // TRADE_AGREEMENT | DISPUTE | NEUTRAL
  strength: Float  // 0.0 to 1.0
}
```

**Implementation Notes**:
- Use NLP techniques (named entity recognition) to extract country names
- Validate extracted countries against ISO 3166-1 alpha-3 codes
- Classify events using keyword matching and semantic analysis
- Handle multi-language input by detecting language and applying appropriate processing
- Return confidence scores based on extraction certainty

### Risk Scorer

**Purpose**: Calculate numerical risk scores for countries based on geopolitical events.

**Interface**:
```
function calculate_risk_score(country: CountryCode, as_of_date: Date) -> RiskScore

function calculate_risk_scores_batch(countries: List<CountryCode>, as_of_date: Date) -> Map<CountryCode, RiskScore>

type RiskScore = {
  country: CountryCode,
  score: Float,  // 0.0 to 100.0
  calculation_date: Date,
  contributing_events: List<EventReference>,
  confidence: Float,  // 0.0 to 1.0
  trend: Trend  // IMPROVING | STABLE | DETERIORATING
}

type EventReference = {
  event_id: UUID,
  weight: Float,
  impact: Float
}
```

**Scoring Algorithm**:
1. Retrieve all geopolitical events affecting the country within a time window (e.g., 12 months)
2. Apply temporal decay: `weight = base_weight * exp(-decay_rate * days_ago)`
3. Aggregate weighted event impacts: `risk_score = sum(event.severity * event.weight)`
4. Normalize to 0-100 scale
5. Calculate trend by comparing current score to historical average

**Temporal Weighting**:
- Recent events (0-30 days): weight = 1.0
- Medium-term events (31-180 days): weight = exp(-0.01 * days_ago)
- Long-term events (181-365 days): weight = exp(-0.015 * days_ago)

### Predictor

**Purpose**: Forecast future trade risk scores using time-series analysis.

**Interface**:
```
function predict_risk(country: CountryCode, forecast_horizons: List<Integer>) -> PredictionResult

type PredictionResult = {
  country: CountryCode,
  predictions: List<ForecastPoint>,
  model_confidence: Float,
  detected_patterns: List<Pattern>
}

type ForecastPoint = {
  horizon_days: Integer,
  predicted_score: Float,
  confidence_interval_lower: Float,
  confidence_interval_upper: Float,
  confidence_level: Float  // e.g., 0.95 for 95% confidence
}

type Pattern = {
  pattern_type: PatternType,  // SEASONAL | TREND | CYCLICAL | EMERGING_RISK
  description: String,
  strength: Float
}
```

**Prediction Approach**:
1. Retrieve historical risk scores for the country (minimum 90 days of data)
2. Decompose time series into trend, seasonal, and residual components
3. Apply exponential smoothing or ARIMA model for forecasting
4. Generate predictions for 90, 180, and 365 day horizons
5. Calculate confidence intervals using prediction error variance
6. Detect patterns using autocorrelation and spectral analysis

**Confidence Calculation**:
- High confidence (>0.8): Stable historical data, clear patterns, low residual variance
- Medium confidence (0.5-0.8): Some volatility, identifiable patterns
- Low confidence (<0.5): High volatility, insufficient data, or regime changes detected

### Recommendation Engine

**Purpose**: Suggest alternative countries for trade operations based on risk analysis.

**Interface**:
```
function recommend_alternatives(current_country: CountryCode, trade_context: TradeContext) -> RecommendationResult

type TradeContext = {
  trade_type: TradeType,  // IMPORT | EXPORT | BILATERAL
  industry_sector: String,
  required_capabilities: List<String>,
  geographic_preferences: List<Region>
}

type RecommendationResult = {
  alternatives: List<CountryRecommendation>,
  analysis_date: Date,
  reasoning: String
}

type CountryRecommendation = {
  country: CountryCode,
  composite_score: Float,  // 0.0 to 100.0
  risk_score: Float,
  feasibility_score: Float,
  strategic_fit_score: Float,
  justification: String,
  risk_factors_avoided: List<String>
}
```

**Recommendation Algorithm**:
1. Retrieve current and predicted risk scores for all candidate countries
2. Filter countries based on trade context constraints
3. Calculate feasibility score based on:
   - Geographic proximity (distance from current country)
   - Trade agreement compatibility
   - Market size and economic indicators
4. Calculate strategic fit score based on:
   - Industry sector alignment
   - Required capabilities match
   - Historical trade volume
5. Compute composite score: `composite = 0.5 * (100 - risk) + 0.3 * feasibility + 0.2 * strategic_fit`
6. Rank alternatives by composite score
7. Generate justification explaining why each alternative is safer

### Data Store

**Purpose**: Persist all system data with temporal tracking and referential integrity.

**Schema**:

```
Table: articles
- article_id: UUID (primary key)
- source_url: String
- article_text: Text
- article_date: Date
- ingestion_timestamp: Timestamp
- language: String

Table: geopolitical_events
- event_id: UUID (primary key)
- article_id: UUID (foreign key -> articles)
- event_type: Enum (TARIFF, SANCTION, TENSION)
- severity: Float
- event_date: Date
- description: Text
- extraction_confidence: Float

Table: event_countries
- event_id: UUID (foreign key -> geopolitical_events)
- country_code: String (ISO 3166-1 alpha-3)
- role: Enum (AFFECTED, INITIATOR, PARTICIPANT)

Table: risk_scores
- score_id: UUID (primary key)
- country_code: String
- score_value: Float
- calculation_date: Date
- calculation_timestamp: Timestamp
- confidence: Float
- trend: Enum (IMPROVING, STABLE, DETERIORATING)

Table: risk_score_events
- score_id: UUID (foreign key -> risk_scores)
- event_id: UUID (foreign key -> geopolitical_events)
- weight: Float
- impact: Float

Table: predictions
- prediction_id: UUID (primary key)
- country_code: String
- prediction_date: Date
- horizon_days: Integer
- predicted_score: Float
- confidence_interval_lower: Float
- confidence_interval_upper: Float
- model_confidence: Float

Table: country_relationships
- relationship_id: UUID (primary key)
- country_a: String
- country_b: String
- relationship_type: Enum (TRADE_AGREEMENT, DISPUTE, NEUTRAL)
- strength: Float
- as_of_date: Date
```

**Data Access Patterns**:
- Query risk scores by country and date range
- Retrieve all events affecting a country within a time window
- Fetch historical risk score time series for prediction
- Look up country relationships for recommendation context

## Data Models

### Core Domain Objects

**Article**:
```
type Article = {
  id: UUID,
  source_url: String,
  text: String,
  publication_date: Date,
  ingestion_timestamp: Timestamp,
  language: String,
  analysis_status: AnalysisStatus  // PENDING | COMPLETED | FAILED
}
```

**GeopoliticalEvent**:
```
type GeopoliticalEvent = {
  id: UUID,
  article_id: UUID,
  event_type: EventType,
  affected_countries: List<CountryCode>,
  severity: Float,  // 0.0 to 1.0
  event_date: Date,
  description: String,
  confidence: Float
}
```

**RiskScore**:
```
type RiskScore = {
  id: UUID,
  country: CountryCode,
  score: Float,  // 0.0 to 100.0
  calculation_date: Date,
  calculation_timestamp: Timestamp,
  contributing_events: List<EventReference>,
  confidence: Float,
  trend: Trend
}
```

**Prediction**:
```
type Prediction = {
  id: UUID,
  country: CountryCode,
  prediction_date: Date,
  forecast_points: List<ForecastPoint>,
  model_confidence: Float,
  detected_patterns: List<Pattern>
}
```

### Validation Rules

**CountryCode Validation**:
- Must be valid ISO 3166-1 alpha-3 code
- Must exist in reference country list
- Case-insensitive matching with normalization to uppercase

**Date Validation**:
- Article dates must not be in the future
- Event dates must not be more than 30 days in the future (allows for announced future policies)
- Calculation dates must be <= current date

**Score Validation**:
- Risk scores must be in range [0.0, 100.0]
- Confidence values must be in range [0.0, 1.0]
- Severity values must be in range [0.0, 1.0]

**Duplicate Detection**:
- Articles with identical source URLs are considered duplicates
- Articles with >95% text similarity (using cosine similarity) are flagged as potential duplicates
- Duplicate articles are not re-processed

