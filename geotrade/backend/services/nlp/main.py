# backend/services/nlp/main.py
"""
NLP Processing Service — Port 8002
BERT sentiment + spaCy NER + tariff/conflict detection
Consumes from Kafka 'raw-news', publishes to 'nlp-results'
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env.local")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import json
import asyncio
import logging
from datetime import datetime
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from contextlib import asynccontextmanager

from shared.models import NLPResult, Entity, SentimentLabel, NewsArticle
from shared.db import get_mongo_db, get_redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_IN = "raw-news"
KAFKA_TOPIC_OUT = "nlp-results"

# Lazy-load heavy ML models
_nlp_model = None
_sentiment_pipeline = None
_tariff_classifier = None


def get_nlp():
    global _nlp_model
    if _nlp_model is None:
        import spacy
        try:
            _nlp_model = spacy.load("en_core_web_trf")
        except OSError:
            _nlp_model = spacy.load("en_core_web_sm")
    return _nlp_model


def get_sentiment_pipeline():
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        from transformers import pipeline
        _sentiment_pipeline = pipeline(
            "text-classification",
            model="ProsusAI/finbert",   # finance-tuned BERT
            top_k=None,
        )
    return _sentiment_pipeline


# ─── NLP Pipeline ────────────────────────────────────────────────────

TARIFF_KEYWORDS = [
    "tariff", "import duty", "trade war", "sanctions", "embargo",
    "trade restriction", "customs duty", "anti-dumping", "trade barrier",
    "export ban", "trade deficit", "protectionism"
]

CONFLICT_KEYWORDS = [
    "conflict", "war", "invasion", "military", "geopolitical tension",
    "coup", "protest", "sanction", "blockade", "crisis", "instability"
]


def extract_entities(text: str) -> List[Entity]:
    nlp = get_nlp()
    doc = nlp(text[:2000])  # truncate for performance
    entities = []
    seen = set()
    for ent in doc.ents:
        if ent.label_ in ("GPE", "ORG", "PERSON", "NORP", "EVENT"):
            key = (ent.text.lower(), ent.label_)
            if key not in seen:
                seen.add(key)
                entities.append(Entity(
                    text=ent.text,
                    label=ent.label_,
                    start=ent.start_char,
                    end=ent.end_char,
                ))
    return entities


def analyze_sentiment(text: str) -> tuple[SentimentLabel, float]:
    try:
        pipe = get_sentiment_pipeline()
        result = pipe(text[:512])[0]
        # FinBERT labels: positive, negative, neutral
        best = max(result, key=lambda x: x["score"])
        label_map = {"positive": SentimentLabel.POSITIVE,
                     "negative": SentimentLabel.NEGATIVE,
                     "neutral": SentimentLabel.NEUTRAL}
        return label_map.get(best["label"].lower(), SentimentLabel.NEUTRAL), best["score"]
    except Exception as e:
        logger.warning(f"Sentiment analysis failed: {e}")
        return SentimentLabel.NEUTRAL, 0.5


def compute_tariff_probability(text: str) -> float:
    text_lower = text.lower()
    matches = sum(1 for kw in TARIFF_KEYWORDS if kw in text_lower)
    return min(matches / 5.0, 1.0)


def detect_conflict_signals(text: str) -> List[str]:
    text_lower = text.lower()
    return [kw for kw in CONFLICT_KEYWORDS if kw in text_lower]


def process_article(article: dict) -> NLPResult:
    text = f"{article.get('title', '')} {article.get('content', '')}"
    entities = extract_entities(text)
    sentiment, confidence = analyze_sentiment(text)
    tariff_prob = compute_tariff_probability(text)
    conflict_signals = detect_conflict_signals(text)

    return NLPResult(
        article_id=article["article_id"],
        entities=entities,
        sentiment=sentiment,
        sentiment_confidence=confidence,
        tariff_probability=tariff_prob,
        conflict_signals=conflict_signals,
        policy_changes=[],  # TODO: fine-tuned policy classifier
    )


# ─── Kafka Consumer Loop ─────────────────────────────────────────────

kafka_producer: AIOKafkaProducer = None


async def consume_loop():
    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC_IN,
        bootstrap_servers=KAFKA_SERVERS,
        group_id="nlp-processor",
        value_deserializer=lambda b: json.loads(b.decode()),
        auto_offset_reset="latest",
    )
    await consumer.start()
    logger.info("NLP consumer started")
    try:
        async for msg in consumer:
            article = msg.value
            try:
                result = process_article(article)
                await kafka_producer.send(
                    KAFKA_TOPIC_OUT,
                    result.model_dump(mode="json"),
                )
                # Cache in MongoDB
                db = get_mongo_db()
                await db.nlp_results.replace_one(
                    {"article_id": result.article_id},
                    result.model_dump(mode="json"),
                    upsert=True,
                )
                logger.info(f"NLP processed {result.article_id[:8]}… sentiment={result.sentiment}")
            except Exception as e:
                logger.error(f"NLP processing error: {e}")
    finally:
        await consumer.stop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global kafka_producer
    kafka_producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_SERVERS,
        value_serializer=lambda v: json.dumps(v, default=str).encode(),
    )
    await kafka_producer.start()
    asyncio.create_task(consume_loop())
    yield
    await kafka_producer.stop()


app = FastAPI(title="GeoTrade NLP Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ─── API Endpoints ───────────────────────────────────────────────────

@app.post("/analyze", response_model=NLPResult)
async def analyze_text(article: NewsArticle):
    """Synchronous NLP analysis for a single article."""
    return process_article(article.model_dump())


@app.get("/entities/{article_id}")
async def get_entities(article_id: str):
    db = get_mongo_db()
    result = await db.nlp_results.find_one({"article_id": article_id}, {"_id": 0})
    if not result:
        raise HTTPException(404, f"No NLP result for article {article_id}")
    return result


@app.get("/health")
async def health():
    return {"status": "ok", "service": "nlp", "port": 8002}
