"""
Lambda: trade-risk-score
Trigger: Async from trade-risk-analyze OR GET /score?country=USA
Purpose: Aggregate geopolitical events into a single risk score per country
         Applies temporal decay weighting — recent events matter more
"""

import json
import boto3
import os
import logging
import math
import uuid
from datetime import datetime, date
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
dynamodb_client = boto3.client('dynamodb')

EVENTS_TABLE = os.environ.get('EVENTS_TABLE', 'geopolitical_events')
SCORES_TABLE = os.environ.get('SCORES_TABLE', 'risk_scores')
SCORE_EVENTS_TABLE = os.environ.get('SCORE_EVENTS_TABLE', 'risk_score_events')

# Temporal decay constants
DECAY_RATE_RECENT = 0.0        # 0-30 days: no decay, full weight
DECAY_RATE_MEDIUM = 0.01       # 31-180 days
DECAY_RATE_LONG = 0.015        # 181-365 days
MAX_LOOKBACK_DAYS = 365


def calculate_temporal_weight(event_date_str: str, as_of_date: date) -> float:
    try:
        event_date = datetime.strptime(event_date_str[:10], '%Y-%m-%d').date()
    except Exception:
        return 0.5  # Default if date parsing fails

    days_ago = (as_of_date - event_date).days

    if days_ago < 0:
        days_ago = 0  # Future-dated events (announced policies) get full weight
    
    if days_ago <= 30:
        return 1.0
    elif days_ago <= 180:
        return math.exp(-DECAY_RATE_MEDIUM * days_ago)
    elif days_ago <= 365:
        return math.exp(-DECAY_RATE_LONG * days_ago)
    else:
        return 0.0  # Beyond 1 year: ignore


def get_events_for_country(country_code: str) -> list:
    """
    Scan geopolitical_events for events affecting this country.
    In production you'd use a GSI on country_code — for hackathon, scan is fine.
    """
    events_table = dynamodb.Table(EVENTS_TABLE)
    
    try:
        response = events_table.scan(
            FilterExpression=Attr('affected_countries').contains(country_code)
        )
        return response.get('Items', [])
    except Exception as e:
        logger.error(f"Failed to fetch events for {country_code}: {e}")
        return []


def get_previous_score(country_code: str) -> float | None:
    """Get the most recent score to calculate trend."""
    scores_table = dynamodb.Table(SCORES_TABLE)
    try:
        response = scores_table.query(
            KeyConditionExpression=Key('country_code').eq(country_code),
            ScanIndexForward=False,
            Limit=2  # Get last 2 to compare trend
        )
        items = response.get('Items', [])
        if len(items) >= 2:
            return float(items[1]['score_value'])
        elif len(items) == 1:
            return float(items[0]['score_value'])
        return None
    except Exception as e:
        logger.warning(f"Could not fetch previous score for {country_code}: {e}")
        return None


def calculate_trend(current_score: float, previous_score: float | None) -> str:
    if previous_score is None:
        return 'STABLE'
    delta = current_score - previous_score
    if delta > 5:
        return 'DETERIORATING'
    elif delta < -5:
        return 'IMPROVING'
    return 'STABLE'


def lambda_handler(event, context):
    scores_table = dynamodb.Table(SCORES_TABLE)

    # Parse country_code from event
    try:
        if 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        elif 'queryStringParameters' in event and event['queryStringParameters']:
            body = event['queryStringParameters']
        else:
            body = event

        country_code = body.get('country_code', '').upper().strip()

        if not country_code:
            return {'statusCode': 400, 'body': json.dumps({'error': 'country_code is required'})}
    except Exception as e:
        return {'statusCode': 400, 'body': json.dumps({'error': f'Invalid input: {str(e)}'})}

    today = date.today()
    logger.info(f"Calculating risk score for {country_code} as of {today}")

    # Fetch all events for this country
    events = get_events_for_country(country_code)
    logger.info(f"Found {len(events)} events for {country_code}")

    # Filter to within lookback window
    valid_events = []
    for ev in events:
        event_date_str = ev.get('event_date', '')
        try:
            event_date = datetime.strptime(event_date_str[:10], '%Y-%m-%d').date()
            days_ago = (today - event_date).days
            if days_ago <= MAX_LOOKBACK_DAYS:
                valid_events.append(ev)
        except Exception:
            valid_events.append(ev)  # Include if date unparseable

    # Calculate weighted risk score
    total_weighted_severity = 0.0
    total_weight = 0.0
    contributing_events = []

    for ev in valid_events:
        try:
            severity = float(ev.get('severity', 0.5))
            confidence = float(ev.get('extraction_confidence', 0.5))
            event_date_str = ev.get('event_date', today.isoformat())
            
            weight = calculate_temporal_weight(event_date_str, today)
            adjusted_weight = weight * confidence  # Down-weight low-confidence extractions

            weighted_impact = severity * adjusted_weight
            total_weighted_severity += weighted_impact
            total_weight += adjusted_weight

            contributing_events.append({
                'event_id': ev.get('event_id', ''),
                'event_type': ev.get('event_type', 'OTHER'),
                'event_date': event_date_str,
                'severity': severity,
                'weight': round(adjusted_weight, 4),
                'impact': round(weighted_impact, 4)
            })
        except Exception as e:
            logger.warning(f"Error processing event {ev.get('event_id', 'unknown')}: {e}")

    # Normalize to 0-100 scale
    if total_weight > 0:
        raw_score = total_weighted_severity / total_weight
        # raw_score is 0-1, scale to 0-100
        normalized_score = min(100.0, raw_score * 100)
    else:
        # No events = baseline score of 10 (nothing is perfectly safe)
        normalized_score = 10.0
        logger.info(f"No events found for {country_code}, using baseline score")

    # Calculate confidence based on data quality
    if len(valid_events) >= 10:
        data_confidence = 0.9
    elif len(valid_events) >= 5:
        data_confidence = 0.75
    elif len(valid_events) >= 2:
        data_confidence = 0.6
    elif len(valid_events) == 1:
        data_confidence = 0.4
    else:
        data_confidence = 0.2  # No data = low confidence

    # Get previous score for trend
    previous_score = get_previous_score(country_code)
    trend = calculate_trend(normalized_score, previous_score)

    # Build score record
    score_id = str(uuid.uuid4())
    calculation_date = today.isoformat()
    calculation_timestamp = datetime.now().isoformat()

    score_record = {
        'score_id': score_id,
        'country_code': country_code,
        'score_value': Decimal(str(round(normalized_score, 2))),
        'calculation_date': calculation_date,
        'calculation_timestamp': calculation_timestamp,
        'confidence': Decimal(str(round(data_confidence, 3))),
        'trend': trend,
        'event_count': len(valid_events),
        'contributing_events': json.dumps(contributing_events[:10])  # Store top 10
    }

    try:
        scores_table.put_item(Item=score_record)
        logger.info(f"Saved risk score for {country_code}: {normalized_score:.2f} ({trend})")
    except Exception as e:
        logger.error(f"Failed to save score for {country_code}: {e}")
        return {'statusCode': 500, 'body': json.dumps({'error': f'Failed to persist score: {str(e)}'})}

    result = {
        'country_code': country_code,
        'score': round(normalized_score, 2),
        'calculation_date': calculation_date,
        'trend': trend,
        'confidence': round(data_confidence, 3),
        'event_count': len(valid_events),
        'previous_score': round(previous_score, 2) if previous_score else None,
        'contributing_events': contributing_events[:5]  # Return top 5 in API response
    }

    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Content-Type': 'application/json'
        },
        'body': json.dumps(result)
    }