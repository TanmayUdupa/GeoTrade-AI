# GeoTrade AI — AWS Deployment Guide

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| AWS CLI | ≥ 2.15 | `brew install awscli` |
| Terraform | ≥ 1.6 | `brew install terraform` |
| kubectl | ≥ 1.30 | `brew install kubectl` |
| Helm | ≥ 3.14 | `brew install helm` |
| Docker | ≥ 25 | docker.com |
| Node.js | ≥ 20 | `brew install node` |
| Python | ≥ 3.11 | `brew install python` |

---

## Step 1 — Configure AWS Credentials

```bash
aws configure
# AWS Access Key ID:     <your-key>
# AWS Secret Access Key: <your-secret>
# Default region:        ap-south-1
# Default output format: json

# Verify
aws sts get-caller-identity
```

Ensure your IAM user/role has these policies:
- `AdministratorAccess` (for initial setup) OR granular policies for:
  EKS, EC2, RDS, MSK, ElastiCache, S3, Lambda, SageMaker, Cognito, API Gateway, CloudWatch, SNS, IAM

---

## Step 2 — Create Terraform State Bucket

```bash
aws s3 mb s3://geotrade-terraform-state --region ap-south-1
aws s3api put-bucket-versioning \
  --bucket geotrade-terraform-state \
  --versioning-configuration Status=Enabled
```

---

## Step 3 — Deploy Infrastructure with Terraform

```bash
cd infrastructure/terraform

# Initialize
terraform init

# Plan (review what will be created)
terraform plan -var="db_password=YOUR_STRONG_PASSWORD_HERE"

# Apply (~15-20 minutes to provision EKS, RDS, MSK, etc.)
terraform apply -var="db_password=YOUR_STRONG_PASSWORD_HERE" -auto-approve

# Capture outputs
terraform output -json > ../outputs.json
```

**What gets created:**
- VPC with public/private subnets across 3 AZs
- EKS cluster (2 node groups: general + ML-optimized)
- RDS PostgreSQL (Multi-AZ)
- DocumentDB cluster (2 instances)
- ElastiCache Redis (2 replicas)
- MSK Kafka (3 brokers)
- S3 buckets (articles, models)
- Cognito User Pool + App Client
- API Gateway + WAF
- SNS Alert Topic
- SageMaker endpoint for LSTM model
- CloudWatch Dashboard

---

## Step 4 — Initialize Database Schema

```bash
# Get RDS endpoint from terraform output
RDS_ENDPOINT=$(terraform output -raw rds_endpoint)

# Connect and initialize schema
psql "postgresql://geotrade:YOUR_PASSWORD@${RDS_ENDPOINT}/geotrade" \
  -f ../../backend/shared/schema.sql
```

The schema is also auto-initialized on first service startup via `init_schema()`.

---

## Step 5 — Push Docker Images to ECR

```bash
cd ../../  # back to project root
chmod +x scripts/deploy.sh

# Build and push all services
./scripts/deploy.sh prod
```

This will:
1. Authenticate to ECR
2. Create ECR repositories if they don't exist
3. Build 5 backend service images + 1 frontend image
4. Tag with git SHA + latest
5. Push to ECR

---

## Step 6 — Configure EKS & Deploy Services

```bash
# Update kubeconfig
AWS_REGION=ap-south-1
CLUSTER=$(terraform output -raw eks_cluster_name)
aws eks update-kubeconfig --region $AWS_REGION --name $CLUSTER

# Install Nginx Ingress Controller
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.service.type=LoadBalancer \
  --set controller.service.annotations."service\.beta\.kubernetes\.io/aws-load-balancer-type"=nlb

# Install cert-manager (TLS certificates)
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set installCRDs=true

# Update K8s secrets with real values
kubectl create secret generic geotrade-secrets \
  --namespace geotrade \
  --from-literal=DATABASE_URL="postgresql://geotrade:PASS@$(terraform output -raw rds_endpoint)/geotrade" \
  --from-literal=MONGODB_URL="mongodb://geotrade:PASS@$(terraform output -raw docdb_endpoint):27017" \
  --from-literal=REDIS_URL="rediss://$(terraform output -raw redis_endpoint):6379" \
  --from-literal=SNS_TOPIC_ARN="$(terraform output -raw sns_alert_topic_arn)"

# Update ConfigMap with Kafka bootstrap
KAFKA_BOOTSTRAP=$(terraform output -raw kafka_bootstrap)
kubectl create configmap geotrade-config \
  --namespace geotrade \
  --from-literal=KAFKA_BOOTSTRAP_SERVERS="$KAFKA_BOOTSTRAP" \
  --from-literal=AWS_REGION="ap-south-1"

# Deploy all services
kubectl apply -f infrastructure/k8s/deployments.yaml

# Watch rollout
kubectl rollout status deployment -n geotrade --timeout=300s
```

---

## Step 7 — Deploy Frontend to S3 + CloudFront

```bash
cd frontend
npm install
npm run build

# Create S3 bucket for frontend
FRONTEND_BUCKET="geotrade-frontend-$(aws sts get-caller-identity --query Account --output text)"
aws s3 mb s3://$FRONTEND_BUCKET --region ap-south-1
aws s3 website s3://$FRONTEND_BUCKET --index-document index.html --error-document index.html

# Sync build output
aws s3 sync dist/ s3://$FRONTEND_BUCKET --delete

# Create CloudFront distribution (run once)
aws cloudfront create-distribution \
  --distribution-config file://infrastructure/cloudfront-config.json
```

---

## Step 8 — Configure Cognito (Auth)

```bash
USER_POOL_ID=$(terraform output -raw cognito_user_pool_id)

# Create admin user
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username admin@geotrade.ai \
  --temporary-password "TempP@ss123!" \
  --user-attributes Name=email,Value=admin@geotrade.ai

# Update frontend env vars with Cognito details
echo "VITE_COGNITO_USER_POOL_ID=$USER_POOL_ID" >> frontend/.env.production
echo "VITE_COGNITO_CLIENT_ID=$(terraform output -raw cognito_client_id)" >> frontend/.env.production
```

---

## Step 9 — Verify Deployment

```bash
# Get API endpoint
API_HOST=$(kubectl get ingress geotrade-ingress -n geotrade \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

# Health checks
curl https://$API_HOST/risk/health
curl https://$API_HOST/forecast/health
curl https://$API_HOST/alerts/health

# Trigger first ingestion run
curl -X POST https://$API_HOST/ingest

# Watch logs
kubectl logs -f deployment/ingestion-service -n geotrade
kubectl logs -f deployment/nlp-service -n geotrade
kubectl logs -f deployment/risk-service -n geotrade
```

---

## Step 10 — Setup CloudWatch Alarms

```bash
# High CPU alarm on EKS nodes
aws cloudwatch put-metric-alarm \
  --alarm-name "geotrade-eks-high-cpu" \
  --metric-name CPUUtilization \
  --namespace AWS/EKS \
  --statistic Average \
  --period 300 \
  --threshold 85 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions $(terraform output -raw sns_alert_topic_arn)

# RDS connection count alarm
aws cloudwatch put-metric-alarm \
  --alarm-name "geotrade-rds-connections" \
  --metric-name DatabaseConnections \
  --namespace AWS/RDS \
  --statistic Average \
  --period 60 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 3 \
  --alarm-actions $(terraform output -raw sns_alert_topic_arn)
```

---

## Architecture Cost Estimate (ap-south-1)

| Service | Config | Monthly Cost |
|---------|--------|-------------|
| EKS Cluster | Control plane | ~$72 |
| EC2 (t3.xlarge × 3) | Worker nodes | ~$180 |
| EC2 (c5.2xlarge × 2) | ML nodes | ~$240 |
| RDS PostgreSQL | db.t3.medium Multi-AZ | ~$120 |
| DocumentDB | db.t3.medium × 2 | ~$110 |
| ElastiCache Redis | cache.t3.medium × 2 | ~$90 |
| MSK Kafka | kafka.t3.small × 3 | ~$120 |
| SageMaker Endpoint | ml.c5.large | ~$95 |
| S3 + Data Transfer | 100GB | ~$25 |
| API Gateway + WAF | 1M req/mo | ~$20 |
| CloudWatch + SNS | Standard | ~$15 |
| **TOTAL** | | **~$1,087/mo** |

> Reduce costs in dev/staging: use single-AZ RDS, 1-node DocumentDB, t3.micro workers, skip SageMaker (use local inference).

---

## Latency Budget (from architecture spec)

| Stage | Target | How |
|-------|--------|-----|
| News crawl | < 30s | Lambda + Scrapy, scheduled every 15m |
| NLP processing | < 2s/article | BERT on c5 ML nodes, batch of 8 |
| Risk scoring | < 500ms | Redis cache + EMA update |
| Dashboard refresh | < 3s | WebSocket push + React Query |
| Alert dispatch | < 1 min | Kafka consumer → SNS → WebSocket |

---

## Useful Commands

```bash
# View all pods
kubectl get pods -n geotrade

# Scale a service
kubectl scale deployment risk-service --replicas=5 -n geotrade

# View service logs
kubectl logs -f -l app=nlp-service -n geotrade

# Port-forward for local testing
kubectl port-forward svc/risk-service 8003:8003 -n geotrade

# Destroy everything (careful!)
cd infrastructure/terraform
terraform destroy -var="db_password=YOUR_PASSWORD"
```
