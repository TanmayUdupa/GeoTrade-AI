# backend/services/ingestion/main.py
"""
News Ingestion Service — Port 8001
Crawls news sources, publishes to Kafka, stores raw in MongoDB + S3
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env.local")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import json
import uuid
import asyncio
import logging
from datetime import datetime
from typing import List, Optional

# ── Load .env.local automatically ──────────────────────────────────

# ── Fix import path so 'shared' is always findable ─────────────────

import feedparser
import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from aiokafka import AIOKafkaProducer
from contextlib import asynccontextmanager

from shared.models import NewsArticle, IngestRequest
from shared.db import get_mongo_db, get_redis, init_schema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_RAW = "raw-news"

# ─── Default RSS / API Sources ───────────────────────────────────────
DEFAULT_SOURCES = [
    {"name": "Reuters Trade", "url": "https://feeds.reuters.com/reuters/businessNews", "type": "rss"},
    {"name": "Yahoo Finance", "url": "https://feeds.finance.yahoo.com/rss/2.0/headline", "type": "rss"},
    {"name": "Google News Trade", "url": "https://news.google.com/rss/search?q=trade+war+tariff&hl=en", "type": "rss"},
    {"name": "WTO News", "url": "https://www.wto.org/english/news_e/rss_e/rss_news_e.xml", "type": "rss"},
]

kafka_producer: Optional[AIOKafkaProducer] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global kafka_producer
    await init_schema()
    kafka_producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    await kafka_producer.start()
    logger.info("Ingestion service started")
    yield
    await kafka_producer.stop()


app = FastAPI(title="GeoTrade Ingestion Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ─── RSS Crawler ─────────────────────────────────────────────────────

async def fetch_rss(source_url: str, source_name: str) -> List[dict]:
    """Fetch and parse RSS feed, return list of raw article dicts."""
    loop = asyncio.get_event_loop()
    feed = await loop.run_in_executor(None, feedparser.parse, source_url)
    articles = []
    for entry in feed.entries[:20]:
        articles.append({
            "article_id": str(uuid.uuid4()),
            "source": source_name,
            "title": entry.get("title", ""),
            "content": entry.get("summary", ""),
            "url": entry.get("link", ""),
            "published_at": entry.get("published", datetime.utcnow().isoformat()),
            "countries_mentioned": [],
            "metadata": {"feed_type": "rss"},
        })
    return articles


async def fetch_full_article(url: str) -> str:
    """Fetch and parse full article text from URL."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, follow_redirects=True)
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            paragraphs = soup.find_all("p")
            return " ".join(p.get_text(strip=True) for p in paragraphs[:20])
    except Exception as e:
        logger.warning(f"Failed to fetch full article {url}: {e}")
        return ""


# ─── Ingestion Pipeline ──────────────────────────────────────────────

async def run_ingestion_pipeline(sources: List[dict]):
    """Crawl sources, store in MongoDB, publish to Kafka."""
    db = get_mongo_db()
    redis = await get_redis()
    total_ingested = 0

    for source in sources:
        try:
            raw_articles = await fetch_rss(source["url"], source["name"])
            logger.info(f"Fetched {len(raw_articles)} from {source['name']}")

            for article in raw_articles:
                # Dedup check via Redis
                cache_key = f"ingested:{article['article_id']}"
                if await redis.exists(cache_key):
                    continue
                await redis.setex(cache_key, 86400 * 7, "1")  # TTL 7 days

                # Enrich with full content
                if article["url"]:
                    full_text = await fetch_full_article(article["url"])
                    if full_text:
                        article["content"] = full_text

                # Store in MongoDB
                await db.raw_articles.insert_one(article)

                # Publish to Kafka
                await kafka_producer.send(KAFKA_TOPIC_RAW, article)
                total_ingested += 1

        except Exception as e:
            logger.error(f"Error processing source {source['name']}: {e}")

    logger.info(f"Ingestion complete — {total_ingested} new articles")
    return total_ingested


# ─── API Endpoints ───────────────────────────────────────────────────

@app.post("/ingest", summary="Trigger ingestion from all default sources")
async def trigger_ingestion(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_ingestion_pipeline, DEFAULT_SOURCES)
    return {"status": "ingestion_started", "sources": len(DEFAULT_SOURCES)}


@app.post("/ingest/custom", summary="Ingest from a custom source URL")
async def ingest_custom(request: IngestRequest, background_tasks: BackgroundTasks):
    source = {"name": request.source_url, "url": request.source_url, "type": request.source_type}
    background_tasks.add_task(run_ingestion_pipeline, [source])
    return {"status": "ingestion_started", "source": request.source_url}


@app.get("/sources", summary="List configured news sources")
async def list_sources():
    return {"sources": DEFAULT_SOURCES, "count": len(DEFAULT_SOURCES)}


@app.get("/articles/recent", summary="Get recently ingested articles")
async def recent_articles(limit: int = 20):
    db = get_mongo_db()
    cursor = db.raw_articles.find({}, {"_id": 0}).sort("published_at", -1).limit(limit)
    articles = await cursor.to_list(length=limit)
    return {"articles": articles, "count": len(articles)}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ingestion", "port": 8001}
