# backend/shared/db.py
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env.local")
from typing import Optional
import asyncpg
import motor.motor_asyncio
import redis.asyncio as aioredis
from contextlib import asynccontextmanager


# ─── PostgreSQL ──────────────────────────────────────────────────────

_pg_pool: Optional[asyncpg.Pool] = None

async def get_pg_pool() -> asyncpg.Pool:
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = await asyncpg.create_pool(
            dsn=os.environ["DATABASE_URL"],
            min_size=2,
            max_size=10,
        )
    return _pg_pool


async def close_pg_pool():
    global _pg_pool
    if _pg_pool:
        await _pg_pool.close()
        _pg_pool = None


# ─── MongoDB ─────────────────────────────────────────────────────────

_mongo_client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None

def get_mongo_db():
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = motor.motor_asyncio.AsyncIOMotorClient(
            os.environ["MONGODB_URL"]
        )
    return _mongo_client["geotrade"]


# ─── Redis ───────────────────────────────────────────────────────────

_redis: Optional[aioredis.Redis] = None

async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = await aioredis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379"),
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


# ─── Schema Init ─────────────────────────────────────────────────────

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS country_risk_scores (
    id SERIAL PRIMARY KEY,
    country_code VARCHAR(2) NOT NULL,
    country_name VARCHAR(100) NOT NULL,
    risk_score FLOAT NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    tariff_index FLOAT DEFAULT 0,
    stability_score FLOAT DEFAULT 0,
    stability_delta FLOAT DEFAULT 0,
    sentiment_aggregate FLOAT DEFAULT 0,
    confidence FLOAT DEFAULT 0,
    top_entities JSONB DEFAULT '[]',
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_country_risk_code
    ON country_risk_scores (country_code);

CREATE TABLE IF NOT EXISTS trade_alerts (
    id SERIAL PRIMARY KEY,
    alert_id VARCHAR(64) UNIQUE NOT NULL,
    country_code VARCHAR(2) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    source_articles JSONB DEFAULT '[]',
    risk_delta FLOAT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_country ON trade_alerts (country_code);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON trade_alerts (created_at DESC);

CREATE TABLE IF NOT EXISTS risk_forecasts (
    id SERIAL PRIMARY KEY,
    country_code VARCHAR(2) NOT NULL,
    model_used VARCHAR(30) NOT NULL,
    forecast_horizon_days INT NOT NULL,
    points JSONB NOT NULL,
    rmse FLOAT,
    mae FLOAT,
    generated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_forecasts_country ON risk_forecasts (country_code);

CREATE TABLE IF NOT EXISTS alert_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    countries JSONB NOT NULL,
    min_severity VARCHAR(20) DEFAULT 'WARNING',
    channels JSONB DEFAULT '["websocket"]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

async def init_schema():
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        await conn.execute(POSTGRES_SCHEMA)
