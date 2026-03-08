"""
Lambda: trade-risk-ingest
Trigger: EventBridge every 30 minutes
Purpose: Fetch news from NewsAPI, deduplicate, store in S3 + DynamoDB, trigger analyze
"""

import json
import boto3
import urllib3
import urllib.parse
import hashlib
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# HTTP connection pool
http = urllib3.PoolManager(
    num_pools=5,
    maxsize=10,
    retries=urllib3.Retry(total=3)
)

# AWS Clients
dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')
s3 = boto3.client('s3')

# Env vars (set these in Lambda console)
NEWS_API_KEY = os.environ['NEWS_API_KEY']
S3_BUCKET = os.environ['S3_BUCKET']
ARTICLES_TABLE = os.environ.get('ARTICLES_TABLE', 'articles')
ANALYZE_FUNCTION = os.environ.get('ANALYZE_FUNCTION', 'trade-risk-analyze')

QUERIES = [
    "trade tariff",
    "trade sanctions",
    "trade war",
    "trade policy",
    "geopolitical tension",
    "import export ban",
    "trade agreement"
]


def lambda_handler(event, context):

    articles_table = dynamodb.Table(ARTICLES_TABLE)

    ingested = 0
    skipped = 0
    errors = 0

    yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()

    for query in QUERIES:
        try:

            url = (
                f"https://newsapi.org/v2/everything"
                f"?q={urllib.parse.quote(query)}"
                f"&language=en"
                f"&sortBy=publishedAt"
                f"&from={yesterday}"
                f"&pageSize=20"
                f"&apiKey={NEWS_API_KEY}"
            )

            resp = http.request(
                "GET",
                url,
                timeout=urllib3.Timeout(connect=5, read=10)
            )

            if resp.status != 200:
                raise Exception(f"NewsAPI request failed with status {resp.status}")

            data = json.loads(resp.data.decode("utf-8"))

            for article in data.get('articles', []):

                source_url = article.get('url', '')
                if not source_url:
                    continue

                article_id = hashlib.md5(source_url.encode()).hexdigest()

                # Deduplicate
                try:
                    existing = articles_table.get_item(Key={'article_id': article_id})
                    if 'Item' in existing:
                        skipped += 1
                        continue
                except Exception as e:
                    logger.warning(f"DynamoDB check failed for {article_id}: {e}")

                # Build article text
                title = article.get('title') or ''
                description = article.get('description') or ''
                content = article.get('content') or ''

                article_text = f"{title}. {description}. {content}".strip()

                if len(article_text) < 50:
                    skipped += 1
                    continue

                article_date = article.get(
                    'publishedAt',
                    datetime.now().isoformat()
                )

                # Store raw JSON in S3
                try:
                    s3.put_object(
                        Bucket=S3_BUCKET,
                        Key=f"raw/{article_id}.json",
                        Body=json.dumps(article),
                        ContentType='application/json'
                    )
                except Exception as e:
                    logger.error(f"S3 write failed for {article_id}: {e}")

                # Write stub record to DynamoDB
                try:
                    articles_table.put_item(Item={
                        'article_id': article_id,
                        'source_url': source_url,
                        'article_text': article_text,
                        'article_date': article_date,
                        'ingestion_timestamp': datetime.now().isoformat(),
                        'language': 'en',
                        'analysis_status': 'PENDING',
                        'query_used': query
                    })
                except Exception as e:
                    logger.error(f"DynamoDB write failed for {article_id}: {e}")
                    errors += 1
                    continue

                # Trigger analyze Lambda
                try:
                    lambda_client.invoke(
                        FunctionName=ANALYZE_FUNCTION,
                        InvocationType='Event',
                        Payload=json.dumps({
                            'source': 'ingest',
                            'body': json.dumps({
                                'article_id': article_id,
                                'article_text': article_text,
                                'article_date': article_date,
                                'source_url': source_url
                            })
                        })
                    )

                    ingested += 1

                except Exception as e:
                    logger.error(
                        f"Failed to invoke analyze for {article_id}: {e}"
                    )
                    errors += 1

        except Exception as e:
            logger.error(f"NewsAPI request failed for query '{query}': {e}")
            errors += 1

    summary = {
        'ingested': ingested,
        'skipped_duplicates': skipped,
        'errors': errors,
        'timestamp': datetime.now().isoformat()
    }

    logger.info(f"Ingestion complete: {summary}")

    return {
        'statusCode': 200,
        'body': json.dumps(summary)
    }