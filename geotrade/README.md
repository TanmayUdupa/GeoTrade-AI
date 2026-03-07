# GeoTrade AI — Geopolitical Intelligence Engine

Full-stack application for geopolitical trade risk analysis, built for AWS (ap-south-1 Mumbai).

## Architecture Overview

```
News Sources → Kafka → NLP Engine (BERT) → Risk Scorer → LSTM Forecast → React Dashboard
                 ↓
            S3 + MongoDB + PostgreSQL + Redis
                 ↓
        FastAPI Microservices (EKS)
                 ↓
         API Gateway + Cognito Auth
```

## Repository Structure

```
geotrade/
├── backend/
│   ├── services/
│   │   ├── ingestion/      # News crawler + Kafka producer (port 8001)
│   │   ├── nlp/            # BERT NLP processing (port 8002)
│   │   ├── risk/           # Risk scoring engine (port 8003)
│   │   ├── prediction/     # LSTM/XGBoost forecasting (port 8004)
│   │   └── alert/          # SNS alert dispatcher (port 8005)
│   └── shared/             # Common models, auth, DB clients
├── frontend/               # React + TypeScript SPA
├── infrastructure/
│   ├── terraform/          # AWS infrastructure as code
│   ├── k8s/                # Kubernetes manifests (EKS)
│   └── docker/             # Dockerfiles
└── scripts/                # CI/CD + deployment scripts
```

## Quick Start (Local Dev)

```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Backend services
cd backend && pip install -r requirements.txt
uvicorn services.ingestion.main:app --port 8001 &
uvicorn services.nlp.main:app --port 8002 &
uvicorn services.risk.main:app --port 8003 &
uvicorn services.prediction.main:app --port 8004 &
uvicorn services.alert.main:app --port 8005 &

# 3. Frontend
cd frontend && npm install && npm run dev
```

## AWS Deployment

See `infrastructure/terraform/` and follow `DEPLOYMENT.md` for full AWS setup.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Recharts, Leaflet, WebSockets |
| Backend | FastAPI, Python 3.11 |
| ML/NLP | BERT (HuggingFace), LSTM (PyTorch), XGBoost |
| Streaming | Apache Kafka (MSK) |
| Storage | PostgreSQL (RDS), MongoDB (DocumentDB), Redis (ElastiCache), S3 |
| AWS Services | EKS, SageMaker, Lambda, API Gateway, Cognito, CloudWatch, SNS |
| Security | OAuth2, JWT, WAF, KMS, CloudTrail, RBAC |
