"""
Lambda: trade-risk-health
Trigger: GET /health
Purpose: Verify all dependencies are reachable. Used by frontend and monitoring.
"""

import json
import boto3
import os
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
s3 = boto3.client('s3')

ARTICLES_TABLE = os.environ.get('ARTICLES_TABLE', 'articles')
SCORES_TABLE = os.environ.get('SCORES_TABLE', 'risk_scores')
S3_BUCKET = os.environ.get('S3_BUCKET', '')


def check_dynamodb() -> dict:
    try:
        table = dynamodb.Table(ARTICLES_TABLE)
        table.load()
        return {'status': 'ok', 'table': ARTICLES_TABLE}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def check_s3() -> dict:
    if not S3_BUCKET:
        return {'status': 'skipped', 'reason': 'S3_BUCKET not configured'}
    try:
        s3.head_bucket(Bucket=S3_BUCKET)
        return {'status': 'ok', 'bucket': S3_BUCKET}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def check_bedrock() -> dict:
    try:
        # Lightweight model list call to verify Bedrock is accessible
        client = boto3.client('bedrock', region_name='us-east-1')
        client.list_foundation_models(byOutputModality='TEXT')
        return {'status': 'ok', 'region': 'us-east-1'}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def lambda_handler(event, context):
    checks = {
        'dynamodb': check_dynamodb(),
        's3': check_s3(),
        'bedrock': check_bedrock()
    }

    all_ok = all(v.get('status') in ('ok', 'skipped') for v in checks.values())
    overall = 'healthy' if all_ok else 'degraded'

    response_body = {
        'status': overall,
        'timestamp': datetime.now().isoformat(),
        'checks': checks,
        'version': '1.0.0'
    }

    return {
        'statusCode': 200 if all_ok else 503,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Content-Type': 'application/json'
        },
        'body': json.dumps(response_body)
    }