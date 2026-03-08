"""
Lambda: trade-risk-predict
Trigger: GET /predict?country=USA
Purpose: Forecast trade risk scores for 90, 180, 365 day horizons
         Uses exponential smoothing on historical score time series
"""

import json
import boto3
import os
import logging
import math
from datetime import datetime, date, timedelta
from decimal import Decimal
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')

SCORES_TABLE = os.environ.get('SCORES_TABLE', 'risk_scores')
PREDICTIONS_TABLE = os.environ.get('PREDICTIONS_TABLE', 'predictions')

FORECAST_HORIZONS = [90, 180, 365]
MIN_DATA_POINTS = 3  # Minimum scores needed to make predictions


def get_historical_scores(country_code: str, days: int = 180) -> list:
    """Retrieve historical risk scores for the country, sorted by date."""
    scores_table = dynamodb.Table(SCORES_TABLE)
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    try:
        response = scores_table.query(
            KeyConditionExpression=Key('country_code').eq(country_code) & Key('calculation_date').gte(cutoff),
            ScanIndexForward=True  # Ascending by date
        )
        items = response.get('Items', [])
        return [
            {
                'date': item['calculation_date'],
                'score': float(item['score_value'])
            }
            for item in items
        ]
    except Exception as e:
        logger.error(f"Failed to fetch historical scores for {country_code}: {e}")
        return []


def exponential_smoothing(scores: list, alpha: float = 0.3) -> list:
    """
    Simple exponential smoothing.
    alpha: smoothing factor (0 = heavy smoothing, 1 = no smoothing)
    Returns smoothed series.
    """
    if not scores:
        return []
    smoothed = [scores[0]]
    for i in range(1, len(scores)):
        s = alpha * scores[i] + (1 - alpha) * smoothed[i - 1]
        smoothed.append(s)
    return smoothed


def calculate_trend_slope(scores: list) -> float:
    """Simple linear regression slope to detect trend direction."""
    n = len(scores)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2
    y_mean = sum(scores) / n
    numerator = sum((i - x_mean) * (scores[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    return numerator / denominator if denominator != 0 else 0.0


def calculate_residual_variance(actual: list, smoothed: list) -> float:
    """Measure how volatile the series is around the smoothed line."""
    if len(actual) < 2:
        return 25.0  # High uncertainty default
    residuals = [(a - s) ** 2 for a, s in zip(actual, smoothed)]
    return sum(residuals) / len(residuals)


def detect_patterns(scores: list, smoothed: list) -> list:
    """Simple pattern detection based on slope and variance."""
    patterns = []
    
    if len(scores) < 3:
        return patterns

    slope = calculate_trend_slope(scores)
    variance = calculate_residual_variance(scores, smoothed)

    if slope > 1.0:
        patterns.append({
            'pattern_type': 'TREND',
            'description': f'Risk scores rising at approximately {slope:.1f} points per data point',
            'strength': min(1.0, abs(slope) / 10)
        })
    elif slope < -1.0:
        patterns.append({
            'pattern_type': 'TREND',
            'description': f'Risk scores declining at approximately {abs(slope):.1f} points per data point',
            'strength': min(1.0, abs(slope) / 10)
        })

    if variance > 100:
        patterns.append({
            'pattern_type': 'EMERGING_RISK',
            'description': 'High score volatility detected — risk environment is unstable',
            'strength': min(1.0, variance / 400)
        })

    # Check if recent scores are significantly higher than older scores
    if len(scores) >= 6:
        recent_avg = sum(scores[-3:]) / 3
        older_avg = sum(scores[:3]) / 3
        if recent_avg > older_avg + 10:
            patterns.append({
                'pattern_type': 'EMERGING_RISK',
                'description': 'Recent risk scores significantly higher than historical baseline',
                'strength': min(1.0, (recent_avg - older_avg) / 50)
            })

    return patterns


def project_score(last_score: float, slope: float, horizon_days: int,
                  data_points: int) -> tuple[float, float, float, float]:
    """
    Project score forward and calculate confidence interval.
    Returns: (predicted_score, lower_ci, upper_ci, confidence_level)
    """
    # Scale slope from per-data-point to per-day
    daily_slope = slope / 7  # Assume weekly data points on average

    # Project forward
    projected = last_score + (daily_slope * horizon_days)
    projected = max(0.0, min(100.0, projected))  # Clamp to valid range

    # Confidence interval widens with horizon and narrows with more data
    base_uncertainty = 10.0
    horizon_factor = math.sqrt(horizon_days / 30)  # Uncertainty grows with sqrt(time)
    data_factor = max(0.5, 1.0 - (data_points / 30))  # More data = tighter intervals

    half_width = base_uncertainty * horizon_factor * data_factor
    lower = max(0.0, projected - half_width)
    upper = min(100.0, projected + half_width)

    # Confidence level decreases with horizon and low data
    if horizon_days <= 90:
        base_confidence = 0.85
    elif horizon_days <= 180:
        base_confidence = 0.70
    else:
        base_confidence = 0.55

    confidence = base_confidence * min(1.0, data_points / 10)

    return round(projected, 2), round(lower, 2), round(upper, 2), round(confidence, 3)


def lambda_handler(event, context):
    predictions_table = dynamodb.Table(PREDICTIONS_TABLE)

    # Parse input
    try:
        params = event.get('queryStringParameters') or {}
        if not params and 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
            params = body or {}

        country_code = params.get('country_code', params.get('country', '')).upper().strip()

        if not country_code:
            return {'statusCode': 400, 'body': json.dumps({'error': 'country_code is required'})}
    except Exception as e:
        return {'statusCode': 400, 'body': json.dumps({'error': f'Invalid input: {str(e)}'})}

    logger.info(f"Generating prediction for {country_code}")

    # Get historical scores
    historical = get_historical_scores(country_code, days=180)
    score_values = [h['score'] for h in historical]

    if len(score_values) < MIN_DATA_POINTS:
        # Not enough data — return a placeholder with low confidence
        logger.warning(f"Insufficient data for {country_code}: {len(score_values)} points")
        last_score = score_values[-1] if score_values else 25.0  # Default moderate risk

        forecast_points = []
        for horizon in FORECAST_HORIZONS:
            forecast_points.append({
                'horizon_days': horizon,
                'predicted_score': last_score,
                'confidence_interval_lower': max(0.0, last_score - 20),
                'confidence_interval_upper': min(100.0, last_score + 20),
                'confidence_level': 0.2,
                'is_uncertain': True
            })

        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'country_code': country_code,
                'predictions': forecast_points,
                'model_confidence': 0.2,
                'data_points_used': len(score_values),
                'warning': f'Only {len(score_values)} historical data points available. Predictions are unreliable.',
                'detected_patterns': []
            })
        }

    # Apply exponential smoothing
    smoothed = exponential_smoothing(score_values, alpha=0.3)
    slope = calculate_trend_slope(score_values)
    variance = calculate_residual_variance(score_values, smoothed)
    patterns = detect_patterns(score_values, smoothed)

    last_smoothed = smoothed[-1]
    model_confidence = min(0.95, 0.4 + (len(score_values) / 20) - (variance / 1000))
    model_confidence = max(0.1, model_confidence)

    # Generate forecast points
    forecast_points = []
    for horizon in FORECAST_HORIZONS:
        predicted, lower, upper, confidence = project_score(
            last_smoothed, slope, horizon, len(score_values)
        )
        is_uncertain = confidence < 0.5

        forecast_points.append({
            'horizon_days': horizon,
            'predicted_score': predicted,
            'confidence_interval_lower': lower,
            'confidence_interval_upper': upper,
            'confidence_level': confidence,
            'is_uncertain': is_uncertain,
            'uncertainty_reason': 'Limited historical data or high volatility' if is_uncertain else None
        })

        # Persist each forecast point
        try:
            predictions_table.put_item(Item={
                'prediction_id': f"{country_code}_{date.today().isoformat()}_{horizon}d",
                'country_code': country_code,
                'prediction_date': date.today().isoformat(),
                'horizon_days': horizon,
                'predicted_score': Decimal(str(predicted)),
                'confidence_interval_lower': Decimal(str(lower)),
                'confidence_interval_upper': Decimal(str(upper)),
                'model_confidence': Decimal(str(round(model_confidence, 3))),
                'created_at': datetime.now().isoformat()
            })
        except Exception as e:
            logger.warning(f"Failed to persist prediction for {country_code} at {horizon}d: {e}")

    result = {
        'country_code': country_code,
        'predictions': forecast_points,
        'model_confidence': round(model_confidence, 3),
        'data_points_used': len(score_values),
        'current_score': round(last_smoothed, 2),
        'detected_patterns': patterns,
        'historical_scores': [
            {'date': h['date'], 'score': round(h['score'], 2)}
            for h in historical[-30:]  # Return last 30 for charting
        ]
    }

    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Content-Type': 'application/json'
        },
        'body': json.dumps(result)
    }