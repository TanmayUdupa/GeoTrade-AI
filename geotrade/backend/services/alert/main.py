# backend/services/alert/main.py
"""
Alert Service — Port 8005
WebSocket live push + SNS dispatch + alert storage.
Consumes 'risk-updates' Kafka topic.
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
from typing import Dict, Set, List

import boto3
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from aiokafka import AIOKafkaConsumer
from contextlib import asynccontextmanager

from shared.models import TradeAlert, AlertSeverity, AlertSubscription
from shared.db import get_pg_pool, get_redis, init_schema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_IN = "risk-updates"
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")

# ─── WebSocket Manager ────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, WebSocket] = {}   # conn_id → ws
        self.subscriptions: Dict[str, Set[str]] = {}  # conn_id → {country_code}

    async def connect(self, ws: WebSocket, conn_id: str, countries: List[str]):
        await ws.accept()
        self.active[conn_id] = ws
        self.subscriptions[conn_id] = set(c.upper() for c in countries)
        logger.info(f"WS {conn_id} connected, watching {countries}")

    def disconnect(self, conn_id: str):
        self.active.pop(conn_id, None)
        self.subscriptions.pop(conn_id, None)

    async def broadcast_alert(self, alert: TradeAlert):
        dead = []
        for conn_id, ws in self.active.items():
            subs = self.subscriptions.get(conn_id, set())
            if alert.country_code in subs or not subs:  # empty = watch all
                try:
                    await ws.send_json(alert.model_dump(mode="json"))
                except Exception:
                    dead.append(conn_id)
        for d in dead:
            self.disconnect(d)


manager = ConnectionManager()


# ─── Alert Detection ─────────────────────────────────────────────────

ALERT_THRESHOLDS = {
    AlertSeverity.CRITICAL: 20.0,   # risk_delta > 20 pts
    AlertSeverity.WARNING: 10.0,     # risk_delta > 10 pts
    AlertSeverity.INFO: 5.0,
}


def determine_severity(delta: float) -> AlertSeverity:
    if abs(delta) >= ALERT_THRESHOLDS[AlertSeverity.CRITICAL]:
        return AlertSeverity.CRITICAL
    if abs(delta) >= ALERT_THRESHOLDS[AlertSeverity.WARNING]:
        return AlertSeverity.WARNING
    return AlertSeverity.INFO


async def process_risk_update(update: dict):
    """Check if risk delta warrants an alert, fire if needed."""
    country = update.get("country_code", "")
    delta = update.get("stability_delta", 0.0)

    if abs(delta) < ALERT_THRESHOLDS[AlertSeverity.INFO]:
        return

    severity = determine_severity(delta)
    direction = "↑ rose" if delta > 0 else "↓ fell"
    alert = TradeAlert(
        alert_id=str(uuid.uuid4()),
        country_code=country,
        severity=severity,
        title=f"{country} risk {direction} by {abs(delta):.1f} pts",
        summary=(
            f"Risk score for {country} has changed significantly. "
            f"Current score: {update.get('risk_score', 'N/A')}. "
            f"Sentiment: {update.get('sentiment', 'N/A')}."
        ),
        risk_delta=delta,
    )

    # Persist to PostgreSQL
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO trade_alerts (alert_id, country_code, severity, title, summary, risk_delta)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (alert_id) DO NOTHING
        """, alert.alert_id, alert.country_code, alert.severity.value,
            alert.title, alert.summary, alert.risk_delta)

    # Push via WebSocket
    await manager.broadcast_alert(alert)

    # Push via SNS (production)
    if SNS_TOPIC_ARN and severity in (AlertSeverity.CRITICAL, AlertSeverity.WARNING):
        try:
            sns = boto3.client("sns", region_name=AWS_REGION)
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=f"[GeoTrade {severity.value}] {alert.title}",
                Message=alert.summary,
                MessageAttributes={
                    "country": {"DataType": "String", "StringValue": country},
                    "severity": {"DataType": "String", "StringValue": severity.value},
                }
            )
        except Exception as e:
            logger.warning(f"SNS publish failed: {e}")


async def consume_loop():
    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC_IN,
        bootstrap_servers=KAFKA_SERVERS,
        group_id="alert-dispatcher",
        value_deserializer=lambda b: json.loads(b.decode()),
        auto_offset_reset="latest",
    )
    await consumer.start()
    logger.info("Alert consumer started")
    try:
        async for msg in consumer:
            await process_risk_update(msg.value)
    finally:
        await consumer.stop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_schema()
    asyncio.create_task(consume_loop())
    yield


app = FastAPI(title="GeoTrade Alert Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ─── WebSocket Endpoint ───────────────────────────────────────────────

@app.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket, countries: str = ""):
    """
    Connect with ?countries=CN,US,IN to watch specific countries.
    Leave empty to watch all.
    """
    conn_id = str(uuid.uuid4())
    country_list = [c.strip() for c in countries.split(",") if c.strip()] if countries else []
    await manager.connect(websocket, conn_id, country_list)
    try:
        while True:
            await websocket.receive_text()  # keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(conn_id)


# ─── REST Endpoints ───────────────────────────────────────────────────

@app.get("/alerts", response_model=List[TradeAlert])
async def list_alerts(country: str = None, limit: int = 50, severity: str = None):
    pool = await get_pg_pool()
    query = "SELECT * FROM trade_alerts"
    conditions, params = [], []
    if country:
        params.append(country.upper())
        conditions.append(f"country_code = ${len(params)}")
    if severity:
        params.append(severity.upper())
        conditions.append(f"severity = ${len(params)}")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += f" ORDER BY created_at DESC LIMIT {limit}"
    async with (await get_pg_pool()).acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [dict(r) for r in rows]


@app.post("/subscribe")
async def subscribe(sub: AlertSubscription):
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO alert_subscriptions (user_id, countries, min_severity, channels)
            VALUES ($1, $2, $3, $4)
        """, sub.user_id, json.dumps(sub.countries), sub.min_severity.value, json.dumps(sub.channels))
    return {"status": "subscribed", "user_id": sub.user_id}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "alert",
        "port": 8005,
        "active_ws_connections": len(manager.active),
    }
