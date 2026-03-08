"""
Lambda: trade-risk-recommend (UPDATED with RAG)
Trigger: GET /recommend?country=CHN&trade_type=IMPORT&industry=Electronics
Purpose: Use risk scores + RAG knowledge base + Bedrock reasoning to recommend safer countries
"""

import json
import boto3
import os
import logging
from datetime import date
from decimal import Decimal
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
bedrock = boto3.client('bedrock-runtime', region_name='eu-north-1')
bedrock_agent = boto3.client('bedrock-agent-runtime', region_name='eu-north-1')

SCORES_TABLE = os.environ.get('SCORES_TABLE', 'risk_scores')
KB_ID = os.environ.get('KNOWLEDGE_BASE_ID', '')       # Set after creating KB in console
MODEL_ID = 'eu.amazon.nova-pro-v1:0'

# Regional groupings for geographic proximity scoring
REGIONS = {
    'EAST_ASIA': ['CHN', 'JPN', 'KOR', 'TWN', 'HKG'],
    'SOUTHEAST_ASIA': ['VNM', 'THA', 'MYS', 'IDN', 'SGP', 'PHL'],
    'SOUTH_ASIA': ['IND', 'PAK', 'BGD'],
    'MIDDLE_EAST': ['SAU', 'ARE', 'IRN', 'IRQ', 'ISR', 'JOR', 'KWT', 'QAT'],
    'EUROPE': ['DEU', 'FRA', 'GBR', 'ITA', 'ESP', 'NLD', 'BEL', 'CHE', 'SWE', 'POL'],
    'NORTH_AMERICA': ['USA', 'CAN', 'MEX'],
    'SOUTH_AMERICA': ['BRA', 'ARG', 'CHL', 'COL', 'PER'],
    'AFRICA': ['ZAF', 'NGA', 'EGY', 'ETH', 'KEN'],
    'OCEANIA': ['AUS', 'NZL'],
    'CENTRAL_ASIA': ['KAZ', 'UZB']
}

ALL_CANDIDATES = [
    'USA', 'CHN', 'DEU', 'GBR', 'FRA', 'IND', 'JPN', 'BRA', 'CAN', 'AUS',
    'KOR', 'MEX', 'IDN', 'SGP', 'THA', 'VNM', 'MYS', 'NLD', 'CHE', 'SWE',
    'POL', 'TUR', 'SAU', 'ARE', 'ZAF', 'NGA', 'ARG', 'CHL', 'COL', 'PHL'
]

MARKET_SIZE = {
    'USA': 1, 'CHN': 1, 'DEU': 1, 'JPN': 1, 'IND': 1,
    'GBR': 2, 'FRA': 2, 'BRA': 2, 'CAN': 2, 'KOR': 2, 'AUS': 2,
    'MEX': 2, 'IDN': 2, 'SAU': 2, 'TUR': 2, 'NLD': 2,
    'SGP': 3, 'THA': 3, 'VNM': 3, 'MYS': 3, 'CHE': 3, 'SWE': 3,
    'POL': 3, 'ARE': 3, 'ZAF': 3, 'NGA': 3, 'ARG': 3, 'CHL': 3,
    'COL': 3, 'PHL': 3
}

# Static tariff rates by country pair (percentage) — WTO averages
TARIFF_RATES = {
    ('CHN', 'USA'): 25.0,
    ('USA', 'CHN'): 20.0,
    ('VNM', 'USA'): 6.5,
    ('DEU', 'USA'): 3.5,
    ('IND', 'USA'): 8.0,
    ('MEX', 'USA'): 0.0,
    ('CAN', 'USA'): 0.0,
    ('SGP', 'USA'): 4.0,
    ('KOR', 'USA'): 2.5,
    ('JPN', 'USA'): 3.0,
    ('BRA', 'USA'): 14.0,
    ('AUS', 'USA'): 2.0,
    ('GBR', 'USA'): 3.5,
    ('FRA', 'USA'): 3.5,
    ('NLD', 'USA'): 3.5,
    ('THA', 'USA'): 8.0,
    ('MYS', 'USA'): 7.0,
    ('IDN', 'USA'): 8.5,
}

# Shipping cost index relative to China baseline
SHIPPING_COST_INDEX = {
    'CHN': 1.0,
    'VNM': 1.1,
    'IND': 1.2,
    'MEX': 0.7,
    'CAN': 0.5,
    'DEU': 1.4,
    'SGP': 1.15,
    'KOR': 1.05,
    'JPN': 1.1,
    'BRA': 1.5,
    'AUS': 1.6,
    'GBR': 1.45,
    'FRA': 1.4,
    'NLD': 1.35,
    'THA': 1.15,
    'MYS': 1.2,
    'IDN': 1.25,
    'USA': 0.8,
}


def get_country_region(country_code: str) -> str:
    for region, countries in REGIONS.items():
        if country_code in countries:
            return region
    return 'OTHER'


def geographic_proximity_score(current: str, candidate: str) -> float:
    current_region = get_country_region(current)
    candidate_region = get_country_region(candidate)
    return 1.0 if current_region == candidate_region else 0.3


def calculate_profitability(country: str, current_country: str,
                            risk_score: float, product_value: float = 100.0) -> dict:
    """Calculate trade profitability metrics for a candidate country."""
    # Get tariff rate
    tariff_key = (country, current_country)
    reverse_key = (current_country, country)
    tariff_rate = TARIFF_RATES.get(tariff_key) or TARIFF_RATES.get(reverse_key) or 12.0

    # Shipping cost
    shipping_index = SHIPPING_COST_INDEX.get(country, 1.3)
    base_shipping = 8.0
    shipping_cost = round(base_shipping * shipping_index, 2)

    # Tariff cost
    tariff_cost = round(product_value * tariff_rate / 100, 2)

    # Risk cost (insurance, hedging, delays)
    risk_cost = round(product_value * (risk_score / 100) * 0.05, 2)

    # Total landed cost
    total_cost = round(tariff_cost + shipping_cost + risk_cost, 2)

    # ROI calculation (assume 30% gross margin)
    gross_margin = product_value * 0.30
    net_margin = gross_margin - total_cost
    roi = round((net_margin / product_value) * 100, 2)

    return {
        'tariff_rate_pct': tariff_rate,
        'tariff_cost_usd': tariff_cost,
        'shipping_cost_usd': shipping_cost,
        'risk_cost_usd': risk_cost,
        'total_landed_cost_usd': total_cost,
        'estimated_roi_pct': roi,
        'profitability': 'HIGH' if roi > 15 else 'MEDIUM' if roi > 5 else 'LOW'
    }


def get_latest_risk_scores(country_codes: list) -> dict:
    scores_table = dynamodb.Table(SCORES_TABLE)
    scores = {}
    for code in country_codes:
        try:
            response = scores_table.query(
                KeyConditionExpression=Key('country_code').eq(code),
                ScanIndexForward=False,
                Limit=1
            )
            items = response.get('Items', [])
            if items:
                scores[code] = float(items[0]['score_value'])
            else:
                scores[code] = 20.0
        except Exception as e:
            logger.warning(f"Could not fetch score for {code}: {e}")
            scores[code] = 20.0
    return scores


def calculate_composite_score(risk_score: float, feasibility: float,
                               strategic_fit: float, roi_pct: float) -> float:
    """Weighted composite: 40% risk, 25% feasibility, 15% strategic fit, 20% ROI."""
    risk_component = (100 - risk_score) / 100
    roi_component = min(1.0, max(0.0, (roi_pct + 10) / 40))
    return (0.4 * risk_component + 0.25 * feasibility + 0.15 * strategic_fit + 0.2 * roi_component) * 100


# ─────────────────────────────────────────────
# RAG: Retrieve trade policy context
# ─────────────────────────────────────────────
def retrieve_trade_context(query: str) -> str:
    """
    Retrieve relevant trade policy context from Bedrock Knowledge Base.
    Falls back to empty string if KB not configured or retrieval fails.
    """
    if not KB_ID:
        logger.info("Knowledge Base ID not configured — skipping RAG")
        return ''
    try:
        response = bedrock_agent.retrieve(
            knowledgeBaseId=KB_ID,
            retrievalQuery={'text': query},
            retrievalConfiguration={
                'vectorSearchConfiguration': {'numberOfResults': 3}
            }
        )
        chunks = response.get('retrievalResults', [])
        if not chunks:
            return ''
        context = '\n\n'.join([c['content']['text'] for c in chunks])
        logger.info(f"RAG retrieved {len(chunks)} chunks for query: {query[:50]}")
        return context[:2000]  # Cap to avoid token overflow
    except Exception as e:
        logger.warning(f"RAG retrieval failed: {e}")
        return ''


# ─────────────────────────────────────────────
# Bedrock: Generate justifications (with RAG context)
# ─────────────────────────────────────────────
def generate_bedrock_justification(current_country: str, alternatives: list,
                                    trade_type: str, industry: str,
                                    trade_context: str) -> dict:
    """Use Bedrock + RAG context to generate human-readable justifications."""

    alt_summary = "\n".join([
        f"- {a['country_code']}: risk={a['risk_score']:.1f}/100, "
        f"composite={a['composite_score']:.1f}/100, "
        f"tariff={a.get('tariff_rate_pct', 'N/A')}%, "
        f"ROI={a.get('estimated_roi_pct', 'N/A')}%, "
        f"profitability={a.get('profitability', 'N/A')}"
        for a in alternatives[:5]
    ])

    # Include RAG context if available
    rag_section = ""
    if trade_context:
        rag_section = f"""
Relevant trade policy context from knowledge base:
{trade_context}
"""

    prompt = f"""You are a global trade strategy consultant with deep expertise in international trade.

A company wants to {trade_type.lower()} in the {industry} sector.
They are currently trading with {current_country} and need safer, more profitable alternatives.
{rag_section}
Top alternative countries identified by quantitative risk and profitability analysis:
{alt_summary}

For EACH country listed above, provide:
1. A 1-2 sentence justification of why it is a good alternative
2. 2-3 specific risk factors they would avoid compared to {current_country}
3. One potential challenge or limitation to be aware of

Respond ONLY with valid JSON, no markdown:
{{
  "overall_reasoning": "2-3 sentence strategic recommendation grounded in trade policy",
  "alternatives": [
    {{
      "country_code": "XXX",
      "justification": "...",
      "risk_factors_avoided": ["factor1", "factor2"],
      "limitation": "..."
    }}
  ]
}}"""

    try:
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": 1500, "temperature": 0.3}
            })
        )
        result = json.loads(response['body'].read())
        raw_text = result['output']['message']['content'][0]['text'].strip()

        import re
        raw_text = re.sub(r'^```json\s*', '', raw_text)
        raw_text = re.sub(r'\s*```$', '', raw_text)

        return json.loads(raw_text)
    except Exception as e:
        logger.error(f"Bedrock justification failed: {e}")
        return {
            'overall_reasoning': f'Analysis based on quantitative risk and profitability scores.',
            'alternatives': [
                {
                    'country_code': a['country_code'],
                    'justification': f"Lower risk score ({a['risk_score']:.1f}/100) with estimated ROI of {a.get('estimated_roi_pct', 0):.1f}%.",
                    'risk_factors_avoided': ['Higher geopolitical volatility', 'Potential tariff escalation'],
                    'limitation': 'Conduct further due diligence before committing.'
                }
                for a in alternatives[:5]
            ]
        }


def lambda_handler(event, context):
    # Parse input
    try:
        params = event.get('queryStringParameters') or {}
        if not params and 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
            params = body or {}

        current_country = params.get('country_code', params.get('country', '')).upper().strip()
        trade_type = params.get('trade_type', 'BILATERAL').upper()
        industry = params.get('industry', 'General Trade')
        product_value = float(params.get('product_value', 100.0))
        top_n = int(params.get('top_n', 5))

        if not current_country:
            return {'statusCode': 400, 'body': json.dumps({'error': 'country_code is required'})}
    except Exception as e:
        return {'statusCode': 400, 'body': json.dumps({'error': f'Invalid input: {str(e)}'})}

    logger.info(f"Generating recommendations for {current_country} ({trade_type}, {industry})")

    # Get risk scores
    candidates = [c for c in ALL_CANDIDATES if c != current_country]
    risk_scores = get_latest_risk_scores(candidates + [current_country])
    current_risk = risk_scores.get(current_country, 50.0)

    # Filter to safer candidates only
    safer_candidates = [c for c in candidates if risk_scores.get(c, 100) < current_risk]

    if not safer_candidates:
        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'current_country': current_country,
                'current_risk_score': round(current_risk, 2),
                'alternatives': [],
                'message': f'{current_country} already has one of the lowest risk scores.',
                'analysis_date': date.today().isoformat()
            })
        }

    # Score each candidate — risk + feasibility + profitability
    scored_alternatives = []
    for code in safer_candidates:
        risk = risk_scores[code]

        geo_score = geographic_proximity_score(current_country, code)
        market_tier = MARKET_SIZE.get(code, 3)
        market_score = (4 - market_tier) / 3
        feasibility = geo_score * 0.4 + market_score * 0.6

        strategic_fit = min(1.0, 0.5 + (0.3 if get_country_region(code) == get_country_region(current_country) else 0.0))

        profit_data = calculate_profitability(code, current_country, risk, product_value)
        roi_pct = profit_data['estimated_roi_pct']

        composite = calculate_composite_score(risk, feasibility, strategic_fit, roi_pct)

        alt = {
            'country_code': code,
            'composite_score': round(composite, 2),
            'risk_score': round(risk, 2),
            'risk_reduction': round(current_risk - risk, 2),
            'feasibility_score': round(feasibility * 100, 2),
            'strategic_fit_score': round(strategic_fit * 100, 2),
            'region': get_country_region(code)
        }
        alt.update(profit_data)
        scored_alternatives.append(alt)

    # Sort by composite score
    scored_alternatives.sort(key=lambda x: x['composite_score'], reverse=True)
    top_alternatives = scored_alternatives[:top_n]

    # RAG: Retrieve relevant trade policy context
    rag_query = f"{trade_type} trade {industry} {current_country} alternatives tariff risk"
    trade_context = retrieve_trade_context(rag_query)
    rag_used = bool(trade_context)

    # Bedrock: Generate justifications with RAG context
    justifications = generate_bedrock_justification(
        current_country, top_alternatives, trade_type, industry, trade_context
    )

    # Merge justifications
    justification_map = {j['country_code']: j for j in justifications.get('alternatives', [])}
    for alt in top_alternatives:
        j = justification_map.get(alt['country_code'], {})
        alt['justification'] = j.get('justification', 'Lower geopolitical risk profile.')
        alt['risk_factors_avoided'] = j.get('risk_factors_avoided', [])
        alt['limitation'] = j.get('limitation', 'Further due diligence recommended.')

    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'current_country': current_country,
            'current_risk_score': round(current_risk, 2),
            'trade_type': trade_type,
            'industry': industry,
            'product_value_usd': product_value,
            'alternatives': top_alternatives,
            'overall_reasoning': justifications.get('overall_reasoning', ''),
            'analysis_date': date.today().isoformat(),
            'candidates_evaluated': len(candidates),
            'rag_context_used': rag_used
        })
    }