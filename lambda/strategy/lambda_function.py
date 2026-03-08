"""
Lambda: trade-risk-strategy
Trigger: GET /strategy?product=semiconductors&origin=USA&target_market=DEU&budget=100000&industry=Electronics
Purpose: Bedrock Agent-style orchestration — fetches real risk data then generates
         a comprehensive trade strategy grounded in live scores + RAG knowledge base
"""

import json
import boto3
import os
import logging
import re
from datetime import date
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
bedrock = boto3.client('bedrock-runtime', region_name='eu-north-1')
bedrock_agent = boto3.client('bedrock-agent-runtime', region_name='eu-north-1')
lambda_client = boto3.client('lambda')

SCORES_TABLE = os.environ.get('SCORES_TABLE', 'risk_scores')
KB_ID = os.environ.get('KNOWLEDGE_BASE_ID', '')
MODEL_ID = 'eu.amazon.nova-pro-v1:0'
RECOMMEND_FUNCTION = os.environ.get('RECOMMEND_FUNCTION', 'trade-risk-recommend')

STRATEGY_PROMPT = """You are a senior global trade strategy consultant.

A company needs a comprehensive trade strategy:
- Product: {product}
- Industry: {industry}
- Origin Country: {origin}
- Target Market: {target_market}
- Budget: ${budget} USD
- Analysis Date: {date}

LIVE RISK INTELLIGENCE (computed from real-time news analysis):
{risk_scores}

TOP RECOMMENDED ALTERNATIVE COUNTRIES (by risk + profitability):
{alternatives}

RELEVANT TRADE POLICY CONTEXT:
{trade_context}

Based on ALL of the above real-time data, generate a comprehensive trade strategy.
Respond ONLY with valid JSON, no markdown:

{{
  "executive_summary": "3-4 sentence overview of the recommended strategy",
  "recommended_primary_route": {{
    "origin": "country code",
    "destination": "country code",
    "via_countries": ["intermediate countries if beneficial"],
    "rationale": "why this specific route is optimal given current risk scores"
  }},
  "recommended_backup_route": {{
    "origin": "country code",
    "destination": "country code",
    "rationale": "contingency if primary route is disrupted"
  }},
  "timeline": {{
    "immediate_30_days": "Specific actions to take immediately",
    "short_term_90_days": "Actions for next 3 months",
    "long_term_12_months": "Strategic moves for next year"
  }},
  "risk_mitigation": [
    "Specific actionable risk mitigation strategy 1",
    "Specific actionable risk mitigation strategy 2",
    "Specific actionable risk mitigation strategy 3"
  ],
  "cost_optimization": [
    "Specific cost saving opportunity 1",
    "Specific cost saving opportunity 2"
  ],
  "kpi_targets": {{
    "target_risk_score": 0.0,
    "target_roi_pct": 0.0,
    "diversification_target": "e.g. no single country >40% of supply"
  }},
  "warnings": ["Critical risks or red flags to be aware of"],
  "confidence": 0.0
}}"""


def get_risk_scores_for_strategy(countries: list) -> dict:
    """Fetch latest risk scores for a set of countries."""
    scores_table = dynamodb.Table(SCORES_TABLE)
    scores = {}
    for country in countries:
        try:
            resp = scores_table.query(
                KeyConditionExpression=Key('country_code').eq(country),
                ScanIndexForward=False,
                Limit=1
            )
            if resp['Items']:
                item = resp['Items'][0]
                scores[country] = {
                    'score': float(item['score_value']),
                    'trend': item.get('trend', 'STABLE')
                }
        except Exception as e:
            logger.warning(f"Could not fetch score for {country}: {e}")
    return scores


def get_recommendations(current_country: str, trade_type: str,
                         industry: str, product_value: str) -> list:
    """Invoke recommend Lambda to get top alternatives."""
    try:
        resp = lambda_client.invoke(
            FunctionName=RECOMMEND_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'queryStringParameters': {
                    'country_code': current_country,
                    'trade_type': trade_type,
                    'industry': industry,
                    'product_value': product_value,
                    'top_n': '3'
                }
            })
        )
        body = json.loads(json.loads(resp['Payload'].read()).get('body', '{}'))
        return body.get('alternatives', [])
    except Exception as e:
        logger.warning(f"Could not fetch recommendations: {e}")
        return []


def retrieve_trade_context(query: str) -> str:
    """Retrieve relevant trade policy context from Bedrock Knowledge Base."""
    if not KB_ID:
        return 'Trade policy knowledge base not configured.'
    try:
        response = bedrock_agent.retrieve(
            knowledgeBaseId=KB_ID,
            retrievalQuery={'text': query},
            retrievalConfiguration={
                'vectorSearchConfiguration': {'numberOfResults': 4}
            }
        )
        chunks = response.get('retrievalResults', [])
        context = '\n\n'.join([c['content']['text'] for c in chunks])
        logger.info(f"RAG retrieved {len(chunks)} chunks")
        return context[:3000]
    except Exception as e:
        logger.warning(f"RAG retrieval failed: {e}")
        return 'Trade policy context unavailable.'


def lambda_handler(event, context):
    # Parse input
    try:
        params = event.get('queryStringParameters') or {}
        if not params and 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
            params = body or {}

        product = params.get('product', 'General goods')
        industry = params.get('industry', 'General Trade')
        origin = params.get('origin', '').upper().strip()
        target_market = params.get('target_market', '').upper().strip()
        budget = params.get('budget', '100000')

        if not origin or not target_market:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'origin and target_market are required'})
            }
    except Exception as e:
        return {'statusCode': 400, 'body': json.dumps({'error': f'Invalid input: {str(e)}'})}

    logger.info(f"Generating strategy: {product} from {origin} to {target_market}")

    # Step 1: Fetch real-time risk scores for key countries
    key_countries = list(set([origin, target_market, 'CHN', 'VNM', 'IND', 'MEX', 'SGP', 'DEU']))
    risk_data = get_risk_scores_for_strategy(key_countries)
    risk_scores_text = '\n'.join([
        f"- {k}: score={v['score']:.1f}/100 trend={v['trend']}"
        for k, v in sorted(risk_data.items(), key=lambda x: x[1]['score'], reverse=True)
    ])

    # Step 2: Get top alternatives from recommend Lambda
    alternatives = get_recommendations(origin, 'BILATERAL', industry, budget)
    if alternatives:
        alt_text = '\n'.join([
            f"- {a['country_code']}: composite={a['composite_score']:.1f}, "
            f"risk={a['risk_score']:.1f}, ROI={a.get('estimated_roi_pct', 0):.1f}%, "
            f"tariff={a.get('tariff_rate_pct', 0):.1f}%"
            for a in alternatives[:3]
        ])
    else:
        alt_text = 'No alternatives data available.'

    # Step 3: Retrieve RAG trade policy context
    rag_query = f"{product} {industry} trade strategy {origin} {target_market} tariff risk"
    trade_context = retrieve_trade_context(rag_query)

    # Step 4: Generate strategy via Bedrock
    prompt = STRATEGY_PROMPT.format(
        product=product,
        industry=industry,
        origin=origin,
        target_market=target_market,
        budget=budget,
        date=date.today().isoformat(),
        risk_scores=risk_scores_text,
        alternatives=alt_text,
        trade_context=trade_context
    )

    try:
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": 2000, "temperature": 0.3}
            })
        )
        result = json.loads(response['body'].read())
        raw_text = result['output']['message']['content'][0]['text'].strip()

        raw_text = re.sub(r'^```json\s*', '', raw_text)
        raw_text = re.sub(r'\s*```$', '', raw_text)
        strategy = json.loads(raw_text)

    except json.JSONDecodeError as e:
        logger.error(f"Bedrock returned invalid JSON: {e}")
        return {'statusCode': 500, 'body': json.dumps({'error': 'Strategy generation failed — invalid JSON from model'})}
    except Exception as e:
        logger.error(f"Bedrock call failed: {e}")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}

    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'product': product,
            'industry': industry,
            'origin': origin,
            'target_market': target_market,
            'budget_usd': budget,
            'strategy': strategy,
            'risk_context': risk_data,
            'top_alternatives': alternatives[:3],
            'rag_context_used': bool(KB_ID),
            'generated_date': date.today().isoformat()
        })
    }