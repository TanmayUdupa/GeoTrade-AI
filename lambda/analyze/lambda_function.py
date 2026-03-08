"""
Lambda: trade-risk-analyze
Trigger: Async from trade-risk-ingest OR direct POST /analyze API call
Purpose: Use Bedrock Mistral to extract entities, events, severity from news articles
         Then write structured events to DynamoDB and trigger risk scoring
"""

import json
import boto3
import os
import logging
import re
import requests
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Clients
dynamodb = boto3.resource('dynamodb')
bedrock = boto3.client('bedrock-runtime', region_name='eu-north-1')
lambda_client = boto3.client('lambda')

# Env vars
ARTICLES_TABLE = os.environ.get('ARTICLES_TABLE', 'articles')
EVENTS_TABLE = os.environ.get('EVENTS_TABLE', 'geopolitical_events')
SCORE_FUNCTION = os.environ.get('SCORE_FUNCTION', 'trade-risk-score')
MODEL_ID = 'eu.amazon.nova-pro-v1:0'

# ISO 3166-1 alpha-3 sample list
VALID_COUNTRY_CODES = {
    "USA", "CHN", "DEU", "GBR", "FRA", "IND", "JPN", "BRA", "CAN", "AUS",
    "RUS", "KOR", "MEX", "IDN", "SAU", "TUR", "ARG", "ZAF", "NGA", "EGY",
    "IRN", "ISR", "PAK", "BGD", "VNM", "THA", "MYS", "SGP", "PHL", "ARE",
    "NLD", "CHE", "SWE", "NOR", "POL", "BEL", "AUT", "DNK", "FIN", "CZE",
    "UKR", "ITA", "ESP", "PRT", "GRC", "HUN", "ROU", "HRV", "SVK", "SVN",
    "TWN", "HKG", "NZL", "CHL", "COL", "PER", "VEN", "ECU", "BOL", "PRY",
    "IRQ", "SYR", "LBN", "JOR", "KWT", "QAT", "BHR", "OMN", "YEM", "LBY",
    "DZA", "MAR", "TUN", "ETH", "KEN", "TZA", "UGA", "GHA", "CIV", "CMR",
    "KAZ", "UZB", "TKM", "AZE", "GEO", "ARM", "BLR", "MDA", "LTU", "LVA",
    "EST", "CUB", "DOM", "GTM", "HND", "SLV", "NIC", "CRI"
}

# Updated prompt — extracts events even from short/truncated text
ANALYZE_PROMPT = """You are a geopolitical trade risk analyst. Analyze the following news headline and text.
Even if the content is brief or truncated, extract whatever trade risk signals are present.

Article Date: {article_date}
Article Text: {article_text}

Rules:
- Extract events even from headlines alone
- If the article mentions any country + any of these topics (tariff, sanction, trade, export, import,
  ban, restriction, agreement, tension, dispute, policy, tax, duty, embargo, war, conflict), create an event
- Be generous — if there is ANY trade risk signal, include it
- severity: 0.3 for minor or vague, 0.6 for clear policy action, 0.9 for major escalation
- confidence: 0.4 if only headline available, 0.8 if full article text present
- If no trade-related signals at all, return empty events array

Respond ONLY with valid JSON, no markdown, no explanation:

{{
  "countries": ["ISO 3166-1 alpha-3 codes of ALL countries mentioned e.g. USA CHN DEU"],
  "events": [
    {{
      "event_type": "TARIFF | SANCTION | TENSION | TRADE_AGREEMENT | OTHER",
      "affected_countries": ["ISO alpha-3 codes directly involved"],
      "initiator_country": "ISO alpha-3 of country initiating action or null",
      "severity": 0.0,
      "description": "One sentence summary of this specific event",
      "event_date": "YYYY-MM-DD or null if not mentioned"
    }}
  ],
  "relationships": [
    {{
      "country_a": "ISO alpha-3",
      "country_b": "ISO alpha-3",
      "relationship_type": "TRADE_AGREEMENT | DISPUTE | NEUTRAL | ALLIANCE",
      "strength": 0.0
    }}
  ],
  "overall_severity": 0.0,
  "confidence": 0.0,
  "summary": "2-3 sentence summary of trade risk significance"
}}"""


# ─────────────────────────────────────────────
# METHOD 1: Scrape full article from URL
# ─────────────────────────────────────────────
def fetch_full_article(url: str) -> str:
    """
    Try to scrape full article text from the source URL.
    Returns empty string if scraping fails (paywall, bot block, timeout).
    """
    if not url:
        return ''
    try:
        from bs4 import BeautifulSoup
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        resp = requests.get(url, timeout=6, headers=headers)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Remove noise tags
        for tag in soup(['script', 'style', 'nav', 'footer', 'aside',
                         'header', 'form', 'iframe', 'noscript']):
            tag.decompose()

        # Extract meaningful paragraphs only
        paragraphs = soup.find_all('p')
        full_text = ' '.join(
            p.get_text().strip()
            for p in paragraphs
            if len(p.get_text().strip()) > 40
        )

        if len(full_text) > 200:
            logger.info(f"Scraped full article: {len(full_text)} chars from {url}")
            return full_text[:4000]
        return ''

    except ImportError:
        logger.warning("BeautifulSoup not available — skipping scrape")
        return ''
    except Exception as e:
        logger.warning(f"Could not scrape {url}: {e}")
        return ''


# ─────────────────────────────────────────────
# METHOD 2: Clean NewsAPI snippet
# ─────────────────────────────────────────────
def clean_newsapi_text(article_text: str) -> str:
    """Remove NewsAPI truncation marker [+XXXX chars]."""
    cleaned = re.sub(r'\[\+\d+ chars\].*$', '', article_text).strip()
    return cleaned


# ─────────────────────────────────────────────
# Combine both — scrape first, fallback to snippet
# ─────────────────────────────────────────────
def get_best_article_text(article_text: str, source_url: str) -> tuple:
    """
    Returns (best_text, method_used).
    Tries full scrape first, falls back to cleaned NewsAPI snippet.
    """
    scraped = fetch_full_article(source_url)
    if len(scraped) > 200:
        return scraped, 'scraped'

    cleaned = clean_newsapi_text(article_text)
    return cleaned, 'snippet'

def invoke_bedrock(prompt: str) -> dict:
    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            "messages": [
                {"role": "user", "content": [{"text": prompt}]}
            ],
            "inferenceConfig": {
                "maxTokens": 2000,
                "temperature": 0.1
            }
        })
    )
    result = json.loads(response['body'].read())
    raw_text = result['output']['message']['content'][0]['text'].strip()

    # Strip markdown fences
    raw_text = re.sub(r'^```json\s*', '', raw_text)
    raw_text = re.sub(r'^```\s*', '', raw_text)
    raw_text = re.sub(r'\s*```$', '', raw_text)

    return json.loads(raw_text)


def validate_and_normalize_countries(countries: list) -> list:
    normalized = []
    for code in countries:
        if not code:
            continue
        upper = code.upper().strip()
        if upper in VALID_COUNTRY_CODES:
            normalized.append(upper)
        else:
            logger.warning(f"Invalid country code skipped: {code}")
    return list(set(normalized))


# ─────────────────────────────────────────────
# Main handler
# ─────────────────────────────────────────────
def lambda_handler(event, context):
    articles_table = dynamodb.Table(ARTICLES_TABLE)
    events_table = dynamodb.Table(EVENTS_TABLE)

    # Parse input
    try:
        if 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            body = event

        article_id = body.get('article_id')
        article_text = body.get('article_text', '')
        article_date = body.get('article_date', datetime.now().isoformat())
        source_url = body.get('source_url', '')

        if not article_text:
            return {'statusCode': 400, 'body': json.dumps({'error': 'article_text is required'})}

        if not article_id:
            import hashlib
            article_id = hashlib.md5(article_text[:200].encode()).hexdigest()

    except Exception as e:
        logger.error(f"Input parsing failed: {e}")
        return {'statusCode': 400, 'body': json.dumps({'error': f'Invalid input: {str(e)}'})}

    # Get best available text — scrape or snippet
    best_text, method_used = get_best_article_text(article_text, source_url)
    logger.info(f"Using [{method_used}] for {article_id}: {len(best_text)} chars")
    logger.info(f"Text preview: {best_text[:200]}")

    # Call Bedrock
    try:
        prompt = ANALYZE_PROMPT.format(
            article_date=article_date,
            article_text=best_text
        )
        analysis = invoke_bedrock(prompt)
        logger.info(f"Bedrock analysis complete for {article_id}: {len(analysis.get('events', []))} events found")
    except json.JSONDecodeError as e:
        logger.error(f"Bedrock returned invalid JSON for {article_id}: {e}")
        try:
            articles_table.update_item(
                Key={'article_id': article_id},
                UpdateExpression='SET analysis_status = :s',
                ExpressionAttributeValues={':s': 'FAILED'}
            )
        except Exception:
            pass
        return {'statusCode': 500, 'body': json.dumps({'error': 'Bedrock returned invalid JSON'})}
    except Exception as e:
        logger.error(f"Bedrock call failed for {article_id}: {e}")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}

    # Validate countries
    all_countries = validate_and_normalize_countries(analysis.get('countries', []))

    # Write events to DynamoDB
    affected_country_set = set()
    saved_event_ids = []

    for i, ev in enumerate(analysis.get('events', [])):
        event_id = f"{article_id}_ev{i}"
        affected = validate_and_normalize_countries(ev.get('affected_countries', []))
        affected_country_set.update(affected)

        event_date = ev.get('event_date')
        if not event_date:
            event_date = article_date[:10]

        try:
            events_table.put_item(Item={
                'event_id': event_id,
                'article_id': article_id,
                'event_type': ev.get('event_type', 'OTHER'),
                'affected_countries': affected,
                'initiator_country': ev.get('initiator_country'),
                'severity': str(round(float(ev.get('severity', 0.5)), 3)),
                'event_date': event_date,
                'description': ev.get('description', ''),
                'extraction_confidence': str(round(float(analysis.get('confidence', 0.5)), 3)),
                'text_source': method_used,
                'created_at': datetime.now().isoformat()
            })
            saved_event_ids.append(event_id)
        except Exception as e:
            logger.error(f"Failed to save event {event_id}: {e}")

    # Mark article COMPLETED
    try:
        articles_table.update_item(
            Key={'article_id': article_id},
            UpdateExpression='SET analysis_status = :s, extracted_countries = :c, event_count = :e, analysis_timestamp = :t, text_source = :m',
            ExpressionAttributeValues={
                ':s': 'COMPLETED',
                ':c': all_countries,
                ':e': len(saved_event_ids),
                ':t': datetime.now().isoformat(),
                ':m': method_used
            }
        )
    except Exception as e:
        logger.warning(f"Could not update article status for {article_id}: {e}")

    # Async trigger risk scoring for each affected country
    for country in affected_country_set:
        try:
            lambda_client.invoke(
                FunctionName=SCORE_FUNCTION,
                InvocationType='Event',
                Payload=json.dumps({
                    'source': 'analyze',
                    'body': json.dumps({'country_code': country})
                })
            )
        except Exception as e:
            logger.warning(f"Could not trigger scoring for {country}: {e}")

    result = {
        'article_id': article_id,
        'countries_found': all_countries,
        'events_extracted': len(saved_event_ids),
        'affected_countries': list(affected_country_set),
        'overall_severity': analysis.get('overall_severity', 0),
        'confidence': analysis.get('confidence', 0),
        'summary': analysis.get('summary', ''),
        'relationships': analysis.get('relationships', []),
        'text_source': method_used
    }

    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Content-Type': 'application/json'
        },
        'body': json.dumps(result)
    }