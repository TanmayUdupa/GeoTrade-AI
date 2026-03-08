# Trade Risk Intelligence System --- Complete API Reference

**Base URL:** "https://k4zbat7tx6.execute-api.eu-north-1.amazonaws.com"

All endpoints return **Content-Type: application/json**\
All endpoints have **CORS enabled (Access-Control-Allow-Origin: \*)**

------------------------------------------------------------------------

# 1. GET /health

Check system health and dependency status.

## Request

**Method:** GET\
**URL:** /health\
**Params:** none

### PowerShell Test

    Invoke-RestMethod -Uri "$BASE_URL/health" -Method GET

### Response (200 OK --- healthy)

``` json
{
  "status": "healthy",
  "timestamp": "2026-03-07T11:45:00.000Z",
  "checks": {
    "dynamodb": {
      "status": "ok",
      "table": "articles"
    },
    "s3": {
      "status": "ok",
      "bucket": "trade-risk-raw-articles-544853490571"
    },
    "bedrock": {
      "status": "ok",
      "region": "eu-north-1"
    }
  },
  "version": "1.0.0"
}
```

### Response (503 --- degraded)

``` json
{
  "status": "degraded",
  "timestamp": "2026-03-07T11:45:00.000Z",
  "checks": {
    "dynamodb": { "status": "error", "error": "Table not found" },
    "s3":        { "status": "ok",    "bucket": "trade-risk-raw-articles-544853490571" },
    "bedrock":   { "status": "ok",    "region": "eu-north-1" }
  },
  "version": "1.0.0"
}
```

------------------------------------------------------------------------

# 2. POST /analyze

Submit a news article for AI analysis. Extracts countries, geopolitical
events, severity scores, and country relationships using Amazon Bedrock
Nova Pro. Automatically triggers risk score recalculation for affected
countries.

## Request

**Method:** POST\
**URL:** /analyze\
**Content-Type:** application/json

### Body (required field: article_text)

``` json
{
  "article_text": "The United States imposed 25% tariffs on Chinese semiconductor imports worth $300 billion. China retaliated with sanctions on American agricultural exports.",
  "article_date": "2026-03-07",
  "source_url":   "https://reuters.com/article/us-china-trade-123"
}
```

### Fields

-   **article_text** (required) Full text or headline + description of
    the article
-   **article_date** (optional) ISO date string, defaults to today
-   **source_url** (optional) Source URL, used for deduplication and
    scraping

### PowerShell Test

    $body = '{"article_text": "The United States imposed 25% tariffs on Chinese semiconductor imports. China retaliated with sanctions on American agricultural exports.", "article_date": "2026-03-07"}'
    Invoke-RestMethod -Uri "$BASE_URL/analyze" -Method POST -ContentType "application/json" -Body $body

### Response (200 OK)

``` json
{
  "article_id":         "a3f9c2d1b4e5f6a7b8c9d0e1f2a3b4c5",
  "countries_found":    ["USA", "CHN"],
  "events_extracted":   2,
  "affected_countries": ["USA", "CHN"],
  "overall_severity":   0.85,
  "confidence":         0.9,
  "summary":            "The US-China trade war has escalated with new semiconductor tariffs and agricultural retaliations, significantly increasing bilateral trade risk.",
  "relationships": [
    {
      "country_a":         "USA",
      "country_b":         "CHN",
      "relationship_type": "DISPUTE",
      "strength":          0.9
    }
  ],
  "text_source": "scraped"
}
```

### Fields

-   **article_id** MD5 hash of article used as unique ID
-   **countries_found** All ISO alpha-3 country codes mentioned
-   **events_extracted** Number of geopolitical events saved to DynamoDB
-   **affected_countries** Countries that had risk scores recalculated
-   **overall_severity** 0.0--1.0 severity of the article overall
-   **confidence** 0.0--1.0 confidence in extraction quality
-   **summary** 2--3 sentence trade risk summary
-   **relationships** Country relationship pairs detected
-   **text_source** `"scraped"` (full article) or `"snippet"` (NewsAPI
    truncated)

### Response (400 --- missing article_text)

``` json
{
  "error": "article_text is required"
}
```

### Response (500 --- Bedrock error)

``` json
{
  "error": "Bedrock returned invalid JSON"
}
```

------------------------------------------------------------------------

# 3. GET /score

Get the current trade risk score for a country. Score is calculated
using temporal decay weighting over geopolitical events from the past
365 days. Recent events weighted more heavily than older events.

## Request

**Method:** GET\
**URL:** /score

**Params:**

-   **country_code** (required) --- ISO 3166-1 alpha-3 code

### PowerShell Test

    Invoke-RestMethod -Uri "$BASE_URL/score?country_code=CHN" -Method GET

### Available Country Codes with Data

USA, CHN, DEU, IND, RUS, GBR, JPN, KOR, MEX, BRA, VNM, SGP\
(and any country mentioned in ingested articles)

### Response (200 OK)

``` json
{
  "country_code":     "CHN",
  "score":            70.16,
  "calculation_date": "2026-03-07",
  "trend":            "STABLE",
  "confidence":       0.9,
  "event_count":      24,
  "previous_score":   68.5,
  "contributing_events": [
    {
      "event_id":   "a3f9c2_ev0",
      "event_type": "TARIFF",
      "event_date": "2026-03-06",
      "severity":   0.85,
      "weight":     1.0,
      "impact":     0.85
    },
    {
      "event_id":   "b7d1e4_ev1",
      "event_type": "TENSION",
      "event_date": "2026-02-28",
      "severity":   0.7,
      "weight":     0.93,
      "impact":     0.651
    }
  ]
}
```

### Fields

-   **score** 0.0--100.0 (higher = riskier)
-   **trend** IMPROVING \| STABLE \| DETERIORATING
-   **confidence** 0.0--1.0 based on data quantity and quality
-   **event_count** Total events used in calculation
-   **previous_score** Previous score for trend comparison (null if
    first score)
-   **contributing_events** Top 5 events that drove the score (weight
    shows temporal decay)

### Response (200 OK --- no data, baseline score)

``` json
{
  "country_code":      "VNM",
  "score":             10.0,
  "calculation_date":  "2026-03-07",
  "trend":             "STABLE",
  "confidence":        0.2,
  "event_count":       0,
  "previous_score":    null,
  "contributing_events": []
}
```

### Response (400 --- missing country_code)

``` json
{
  "error": "country_code is required"
}
```

------------------------------------------------------------------------

# 4. GET /predict

Forecast future trade risk scores for a country at 90, 180, and 365 day
horizons. Uses exponential smoothing on historical score time series.
Confidence increases as more historical data points accumulate over
time.

## Request

**Method:** GET\
**URL:** /predict

**Params:**

-   **country_code** (required) --- ISO 3166-1 alpha-3 code

### PowerShell Test

    Invoke-RestMethod -Uri "$BASE_URL/predict?country_code=USA" -Method GET

### Response (200 OK --- sufficient data)

``` json
{
  "country_code":     "USA",
  "current_score":    75.69,
  "model_confidence": 0.78,
  "data_points_used": 14,
  "predictions": [
    {
      "horizon_days":               90,
      "predicted_score":            77.2,
      "confidence_interval_lower":  71.4,
      "confidence_interval_upper":  83.0,
      "confidence_level":           0.82,
      "is_uncertain":               false,
      "uncertainty_reason":         null
    },
    {
      "horizon_days":               180,
      "predicted_score":            78.8,
      "confidence_interval_lower":  69.1,
      "confidence_interval_upper":  88.5,
      "confidence_level":           0.67,
      "is_uncertain":               false,
      "uncertainty_reason":         null
    },
    {
      "horizon_days":               365,
      "predicted_score":            81.5,
      "confidence_interval_lower":  64.2,
      "confidence_interval_upper":  98.8,
      "confidence_level":           0.52,
      "is_uncertain":               false,
      "uncertainty_reason":         null
    }
  ],
  "detected_patterns": [
    {
      "pattern_type":  "TREND",
      "description":   "Risk scores rising at approximately 0.4 points per data point",
      "strength":      0.4
    },
    {
      "pattern_type":  "EMERGING_RISK",
      "description":   "Recent risk scores significantly higher than historical baseline",
      "strength":      0.6
    }
  ],
  "historical_scores": [
    { "date": "2026-02-22", "score": 68.0 },
    { "date": "2026-02-23", "score": 70.0 },
    { "date": "2026-02-24", "score": 71.0 },
    { "date": "2026-03-07", "score": 75.69 }
  ]
}
```

### Response (200 OK --- insufficient data, low confidence)

``` json
{
  "country_code":     "VNM",
  "current_score":    10.0,
  "model_confidence": 0.2,
  "data_points_used": 1,
  "warning":          "Only 1 historical data points available. Predictions are unreliable.",
  "predictions": [
    {
      "horizon_days":               90,
      "predicted_score":            10.0,
      "confidence_interval_lower":  0.0,
      "confidence_interval_upper":  30.0,
      "confidence_level":           0.2,
      "is_uncertain":               true,
      "uncertainty_reason":         "Limited historical data or high volatility"
    }
  ],
  "detected_patterns": []
}
```

------------------------------------------------------------------------

# 5. GET /recommend

Get safer alternative countries for trade with risk scores,
profitability metrics, and AI-generated justifications grounded in RAG
trade policy documents.

## Request

**Method:** GET\
**URL:** /recommend

**Params:**

-   **country_code** (required) Current country to find alternatives for
-   **trade_type** (optional) IMPORT \| EXPORT \| BILATERAL --- default:
    BILATERAL
-   **industry** (optional) e.g. Electronics, Automotive, Textile ---
    default: General Trade
-   **product_value** (optional) Product value in USD for ROI
    calculation --- default: 100
-   **top_n** (optional) Number of alternatives to return --- default: 5

### PowerShell Test

    Invoke-RestMethod -Uri "$BASE_URL/recommend?country_code=CHN&trade_type=IMPORT&industry=Electronics&product_value=1000" -Method GET

### Response (200 OK)

``` json
{
  "current_country":     "CHN",
  "current_risk_score":  70.16,
  "trade_type":          "IMPORT",
  "industry":            "Electronics",
  "product_value_usd":   1000.0,
  "analysis_date":       "2026-03-07",
  "candidates_evaluated": 29,
  "rag_context_used":    true,
  "overall_reasoning":   "Given elevated US-China trade tensions and 25% tariff exposure, Vietnam and Singapore offer significantly lower risk profiles with strong FTA access to major markets. Vietnam's EU-Vietnam FTA and proximity to Chinese supply chains make it the optimal nearshore alternative for electronics manufacturing.",
  "alternatives": []
}
```

### Response (200 OK --- already lowest risk)

``` json
{
  "current_country":    "SGP",
  "current_risk_score": 10.0,
  "alternatives":       [],
  "message":            "SGP already has one of the lowest risk scores among candidate countries.",
  "analysis_date":      "2026-03-07"
}
```

------------------------------------------------------------------------

## 6. GET /strategy

Generate a comprehensive AI trade strategy grounded in:

-   Live risk scores computed from today's news
-   Top alternative country recommendations with profitability
-   RAG-retrieved trade policy context (tariffs, FTAs, sanctions)

------------------------------------------------------------------------

### Request

Method: GET\
URL: /strategy

**Params:**

-   **product** (required) Product or commodity being traded
-   **origin** (required) ISO alpha-3 origin country
-   **target_market** (required) ISO alpha-3 destination country
-   **industry** (optional) Industry sector --- default: General Trade
-   **budget** (optional) Budget in USD --- default: 100000

### PowerShell Test

``` powershell
Invoke-RestMethod -Uri "$BASE_URL/strategy?product=semiconductors&origin=USA&target_market=DEU&budget=500000&industry=Electronics" -Method GET
```

------------------------------------------------------------------------

### More Test Examples

#### Vietnam apparel to EU

``` powershell
Invoke-RestMethod -Uri "$BASE_URL/strategy?product=apparel&origin=VNM&target_market=DEU&budget=100000&industry=Textile" -Method GET
```

#### India pharma to USA

``` powershell
Invoke-RestMethod -Uri "$BASE_URL/strategy?product=pharmaceuticals&origin=IND&target_market=USA&budget=250000&industry=Pharmaceuticals" -Method GET
```

------------------------------------------------------------------------

### Response (200 OK)

``` json
{
  "product": "semiconductors",
  "industry": "Electronics",
  "origin": "USA",
  "target_market": "DEU",
  "budget_usd": "500000",
  "generated_date": "2026-03-07",
  "rag_context_used": true,
  "risk_context": {
    "USA": { "score": 75.69, "trend": "STABLE" },
    "DEU": { "score": 80.0, "trend": "STABLE" },
    "CHN": { "score": 70.16, "trend": "STABLE" },
    "VNM": { "score": 10.0, "trend": "STABLE" },
    "IND": { "score": 61.54, "trend": "STABLE" },
    "MEX": { "score": 70.0, "trend": "STABLE" },
    "SGP": { "score": 10.0, "trend": "STABLE" }
  },
  "top_alternatives": [
    {
      "country_code": "VNM",
      "composite_score": 82.4,
      "risk_score": 10.0,
      "estimated_roi_pct": 25.7
    }
  ],
  "strategy": {
    "executive_summary": "The USA-DEU semiconductor trade route faces elevated bilateral risk due to geopolitical tensions affecting both markets. We recommend routing through Singapore as a low-risk hub while diversifying sourcing to Vietnam and South Korea to reduce dependency on high-risk supply chains. This approach reduces total landed cost by an estimated 18% while lowering geopolitical exposure.",
    "recommended_primary_route": {
      "origin": "USA",
      "destination": "DEU",
      "via_countries": ["SGP"],
      "rationale": "Singapore hub routing avoids Red Sea disruptions, provides neutral trade environment with zero tariffs, and offers financial hedging services. Direct USA-DEU route viable but higher cost."
    },
    "recommended_backup_route": {
      "origin": "KOR",
      "destination": "DEU",
      "rationale": "South Korean semiconductor suppliers (Samsung, SK Hynix) provide alternative sourcing under KORUS FTA with strong logistics to European market."
    },
    "timeline": {
      "immediate_30_days": "Audit current supplier concentration. Identify Korean and Vietnamese backup suppliers for critical components. Negotiate forward currency contracts for EUR/USD exposure.",
      "short_term_90_days": "Qualify one Vietnamese assembly partner. Establish Singapore subsidiary for regional procurement. Review export control compliance for semiconductor technology transfers.",
      "long_term_12_months": "Achieve maximum 40% single-country sourcing. Establish dual-certification for EU and US market requirements. Evaluate CPTPP benefits through Singapore membership."
    },
    "risk_mitigation": [
      "Limit China sourcing to maximum 30% of total semiconductor supply to reduce Section 301 tariff exposure",
      "Maintain 90-day safety stock of critical components given Taiwan Strait supply chain risk",
      "Obtain export control licenses proactively for advanced chip technology transfers to avoid shipment delays"
    ],
    "cost_optimization": [
      "Vietnam assembly reduces landed cost by 15-20% vs China due to lower tariffs under EU-Vietnam FTA",
      "Singapore hub consolidation reduces per-shipment logistics cost by 12% through volume aggregation"
    ],
    "kpi_targets": {
      "target_risk_score": 45.0,
      "target_roi_pct": 22.0,
      "diversification_target": "No single country to exceed 40% of supply chain volume"
    },
    "warnings": [
      "DEU risk score (80.0) is elevated — monitor for EU regulatory changes affecting semiconductor imports",
      "Export control compliance is critical — violations carry penalties up to $1M per incident"
    ],
    "confidence": 0.78
  }
}
```

### Response (400 --- missing required params)

``` json
{
  "error": "origin and target_market are required"
}
```

------------------------------------------------------------------------
