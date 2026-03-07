# backend/services/risk/main.py
"""
Risk Scoring Service — Port 8003
Aggregates NLP signals into per-country risk scores.
Consumes 'nlp-results', updates PostgreSQL + Redis.
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
from datetime import datetime, timedelta
from typing import List, Optional
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from contextlib import asynccontextmanager

from shared.models import CountryRiskScore, RiskLevel, RiskComparisonResponse, NLPResult, SentimentLabel
from shared.db import get_pg_pool, get_redis, init_schema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_IN = "nlp-results"
KAFKA_TOPIC_OUT = "risk-updates"

# Country code → name mapping (subset)
COUNTRY_NAMES = {
    "CN": "China", "US": "United States", "RU": "Russia", "IN": "India",
    "EU": "European Union", "UK": "United Kingdom", "JP": "Japan",
    "DE": "Germany", "FR": "France", "AU": "Australia", "BR": "Brazil",
    "VN": "Vietnam", "MX": "Mexico", "CA": "Canada", "KR": "South Korea",
    "SA": "Saudi Arabia", "TR": "Turkey", "ID": "Indonesia", "PK": "Pakistan",
    "NG": "Nigeria", "ZA": "South Africa", "EG": "Egypt", "TH": "Thailand",
}

# spaCy GPE → ISO code lookup (simplified)
GPE_TO_CODE = {
    "china": "CN", "united states": "US", "russia": "RU", "india": "IN",
    "european union": "EU", "united kingdom": "UK", "japan": "JP",
    "germany": "DE", "france": "FR", "australia": "AU", "brazil": "BR",
    "vietnam": "VN", "mexico": "MX", "canada": "CA", "south korea": "KR",
    "saudi arabia": "SA", "turkey": "TR", "indonesia": "ID", "pakistan": "PK",
    "nigeria": "NG", "south africa": "ZA", "egypt": "EG", "thailand": "TH",
    "us": "US", "uk": "UK", "eu": "EU",
}


def risk_level_from_score(score: float) -> RiskLevel:
    if score >= 75: return RiskLevel.CRITICAL
    if score >= 55: return RiskLevel.HIGH
    if score >= 35: return RiskLevel.MODERATE
    return RiskLevel.LOW


def sentiment_to_float(label: str) -> float:
    return {"NEGATIVE": -1.0, "NEUTRAL": 0.0, "POSITIVE": 1.0}.get(label, 0.0)


async def update_country_risk(nlp: dict):
    """Aggregate NLP result into country risk scores."""
    pool = await get_pg_pool()
    redis = await get_redis()

    entities = nlp.get("entities", [])
    countries = set()
    for e in entities:
        if e.get("label") == "GPE":
            code = GPE_TO_CODE.get(e["text"].lower())
            if code:
                countries.add(code)

    if not countries:
        return

    sentiment_val = sentiment_to_float(nlp.get("sentiment", "NEUTRAL"))
    tariff_prob = nlp.get("tariff_probability", 0.0)
    conflict_count = len(nlp.get("conflict_signals", []))

    for code in countries:
        # Compute incremental score contribution from this article
        # Weights: sentiment (negative=bad), tariff prob, conflict signals
        sentiment_contribution = (1 - sentiment_val) * 10  # 0-20
        tariff_contribution = tariff_prob * 30              # 0-30
        conflict_contribution = min(conflict_count * 10, 40)  # 0-40
        article_score = sentiment_contribution + tariff_contribution + conflict_contribution

        # Upsert with exponential moving average
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT risk_score, stability_score FROM country_risk_scores WHERE country_code = $1",
                code
            )
            if existing:
                new_score = existing["risk_score"] * 0.85 + article_score * 0.15
                delta = new_score - existing["stability_score"]
            else:
                new_score = article_score
                delta = 0.0

            level = risk_level_from_score(new_score)
            country_name = COUNTRY_NAMES.get(code, code)

            await conn.execute("""
                INSERT INTO country_risk_scores
                    (country_code, country_name, risk_score, risk_level, tariff_index,
                     stability_score, stability_delta, sentiment_aggregate, confidence, top_entities, last_updated)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,NOW())
                ON CONFLICT (country_code) DO UPDATE SET
                    risk_score = $3, risk_level = $4, tariff_index = $5,
                    stability_score = $6, stability_delta = $7,
                    sentiment_aggregate = $8, confidence = $9,
                    top_entities = $10, last_updated = NOW()
            """, code, country_name, new_score, level.value, tariff_prob,
                new_score, delta, sentiment_val,
                nlp.get("sentiment_confidence", 0.8),
                json.dumps([e["text"] for e in entities[:5]])
            )

        # Cache in Redis for sub-second reads
        score_data = {
            "country_code": code,
            "country_name": country_name,
            "risk_score": round(new_score, 1),
            "risk_level": level.value,
            "tariff_index": tariff_prob,
            "stability_delta": delta,
            "last_updated": datetime.utcnow().isoformat(),
        }
        await redis.setex(f"risk:{code}", 300, json.dumps(score_data))

    logger.info(f"Updated risk for countries: {countries}")


# ─── Kafka Consumer ───────────────────────────────────────────────────

kafka_producer: Optional[AIOKafkaProducer] = None


async def consume_loop():
    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC_IN,
        bootstrap_servers=KAFKA_SERVERS,
        group_id="risk-scorer",
        value_deserializer=lambda b: json.loads(b.decode()),
        auto_offset_reset="latest",
    )
    await consumer.start()
    logger.info("Risk scorer consumer started")
    try:
        async for msg in consumer:
            await update_country_risk(msg.value)
            await kafka_producer.send(KAFKA_TOPIC_OUT, msg.value)
    finally:
        await consumer.stop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global kafka_producer
    await init_schema()
    kafka_producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_SERVERS,
        value_serializer=lambda v: json.dumps(v, default=str).encode(),
    )
    await kafka_producer.start()
    asyncio.create_task(consume_loop())
    yield
    await kafka_producer.stop()


app = FastAPI(title="GeoTrade Risk Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ─── API Endpoints ────────────────────────────────────────────────────

@app.get("/risk/{country_code}")
async def get_country_risk(country_code: str):
    code = country_code.upper()
    redis = await get_redis()
    cached = await redis.get(f"risk:{code}")
    if cached:
        return json.loads(cached)

    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM country_risk_scores WHERE country_code = $1", code
        )
    if not row:
        raise HTTPException(404, f"No risk data for country {code}")
    d = dict(row)
    if isinstance(d.get("top_entities"), str):
        d["top_entities"] = json.loads(d["top_entities"])
    return d


@app.get("/risk")
async def list_all_risks():
    """Return risk scores for all tracked countries."""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM country_risk_scores ORDER BY risk_score DESC"
        )
    result = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("top_entities"), str):
            d["top_entities"] = json.loads(d["top_entities"])
        result.append(d)
    return result


@app.get("/compare")
async def compare_countries(codes: str):
    """Compare multiple countries by comma-separated ISO codes."""
    code_list = [c.strip().upper() for c in codes.split(",")]
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM country_risk_scores WHERE country_code = ANY($1::text[])",
            code_list
        )
    result = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("top_entities"), str):
            d["top_entities"] = json.loads(d["top_entities"])
        result.append(d)
    return {"countries": result, "generated_at": __import__("datetime").datetime.utcnow().isoformat()}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "risk", "port": 8003}


@app.post("/seed", summary="Seed mock risk data for all major countries")
async def seed_mock_data():
    """Insert realistic mock risk scores directly into the DB for testing."""
    mock_countries = [
        ("CN", "China",          78, "HIGH",     0.82, -12.0, -0.75, 0.91),
        ("RU", "Russia",         91, "CRITICAL", 0.95,  -8.0, -0.88, 0.94),
        ("US", "United States",  42, "MODERATE", 0.38,  +2.0,  0.12, 0.87),
        ("IN", "India",          31, "MODERATE", 0.28,  +4.0,  0.21, 0.83),
        ("EU", "European Union", 38, "MODERATE", 0.35,  +1.5,  0.08, 0.80),
        ("JP", "Japan",          25, "LOW",      0.18,  -1.0,  0.35, 0.85),
        ("DE", "Germany",        33, "MODERATE", 0.30,  +0.5,  0.15, 0.82),
        ("BR", "Brazil",         55, "HIGH",     0.48,  +6.0, -0.22, 0.75),
        ("TR", "Turkey",         62, "HIGH",     0.58,  +8.0, -0.41, 0.78),
        ("VN", "Vietnam",        22, "LOW",      0.15,  -2.0,  0.42, 0.88),
        ("MX", "Mexico",         44, "MODERATE", 0.40,  +3.0, -0.05, 0.76),
        ("CA", "Canada",         18, "LOW",      0.12,  -1.5,  0.48, 0.90),
        ("KR", "South Korea",    28, "LOW",      0.22,  -0.5,  0.31, 0.86),
        ("SA", "Saudi Arabia",   50, "MODERATE", 0.45,  +4.5, -0.18, 0.79),
        ("AU", "Australia",      20, "LOW",      0.14,  -1.0,  0.44, 0.89),
        ("FR", "France",         35, "MODERATE", 0.31,  +1.0,  0.10, 0.81),
        ("ID", "Indonesia",      40, "MODERATE", 0.36,  +2.5, -0.02, 0.77),
        ("PK", "Pakistan",       72, "HIGH",     0.70,  +9.0, -0.62, 0.80),
        ("NG", "Nigeria",        65, "HIGH",     0.60,  +7.0, -0.50, 0.74),
        ("ZA", "South Africa",   48, "MODERATE", 0.43,  +3.5, -0.14, 0.76),
    ]

    pool = await get_pg_pool()
    inserted = 0
    async with pool.acquire() as conn:
        for code, name, score, level, tariff, delta, sentiment, conf in mock_countries:
            await conn.execute("""
                INSERT INTO country_risk_scores
                    (country_code, country_name, risk_score, risk_level, tariff_index,
                     stability_score, stability_delta, sentiment_aggregate, confidence,
                     top_entities, last_updated)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,NOW())
                ON CONFLICT (country_code) DO UPDATE SET
                    risk_score=$3, risk_level=$4, tariff_index=$5,
                    stability_score=$6, stability_delta=$7,
                    sentiment_aggregate=$8, confidence=$9,
                    top_entities=$10, last_updated=NOW()
            """, code, name, float(score), level, tariff,
                float(score), delta, sentiment, conf,
                json.dumps([name, "Trade Policy", "Tariffs"]))
            inserted += 1

    return {"status": "seeded", "countries_inserted": inserted}
