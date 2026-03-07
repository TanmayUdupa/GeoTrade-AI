#!/usr/bin/env bash
# scripts/deploy.sh — Build, push, and deploy GeoTrade AI to AWS EKS
# Usage: ./scripts/deploy.sh [prod|staging]

set -euo pipefail

ENV=${1:-staging}
AWS_REGION="ap-south-1"
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ECR_BASE="${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"
CLUSTER="geotrade-${ENV}-eks"
IMAGE_TAG=$(git rev-parse --short HEAD)

SERVICES=(ingestion nlp risk prediction alert)

echo "╔══════════════════════════════════════════════════╗"
echo "║  GeoTrade AI Deploy → ${ENV} (${IMAGE_TAG})         ║"
echo "╚══════════════════════════════════════════════════╝"

# ─── 1. ECR Login ─────────────────────────────────────────────────────
echo "▶ Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ECR_BASE

# ─── 2. Build & Push Backend Services ─────────────────────────────────
for SERVICE in "${SERVICES[@]}"; do
  REPO="${ECR_BASE}/geotrade-${SERVICE}"
  echo "▶ Building ${SERVICE}..."

  # Create ECR repo if it doesn't exist
  aws ecr describe-repositories --repository-names "geotrade-${SERVICE}" \
    --region $AWS_REGION 2>/dev/null || \
    aws ecr create-repository --repository-name "geotrade-${SERVICE}" \
      --region $AWS_REGION --image-scanning-configuration scanOnPush=true

  docker build \
    --build-arg SERVICE=$SERVICE \
    -f infrastructure/docker/Dockerfile.service \
    -t "${REPO}:${IMAGE_TAG}" \
    -t "${REPO}:latest" \
    ./backend

  docker push "${REPO}:${IMAGE_TAG}"
  docker push "${REPO}:latest"
  echo "  ✓ Pushed ${SERVICE}:${IMAGE_TAG}"
done

# ─── 3. Build & Push Frontend ─────────────────────────────────────────
FRONTEND_REPO="${ECR_BASE}/geotrade-frontend"
echo "▶ Building frontend..."

aws ecr describe-repositories --repository-names "geotrade-frontend" \
  --region $AWS_REGION 2>/dev/null || \
  aws ecr create-repository --repository-name "geotrade-frontend" \
    --region $AWS_REGION

docker build \
  -f infrastructure/docker/Dockerfile.frontend \
  -t "${FRONTEND_REPO}:${IMAGE_TAG}" \
  -t "${FRONTEND_REPO}:latest" \
  ./frontend

docker push "${FRONTEND_REPO}:${IMAGE_TAG}"
docker push "${FRONTEND_REPO}:latest"
echo "  ✓ Pushed frontend:${IMAGE_TAG}"

# ─── 4. Update kubeconfig ─────────────────────────────────────────────
echo "▶ Updating kubeconfig for ${CLUSTER}..."
aws eks update-kubeconfig \
  --region $AWS_REGION \
  --name $CLUSTER

# ─── 5. Update image tags in K8s manifests & apply ────────────────────
echo "▶ Deploying to Kubernetes..."
for SERVICE in "${SERVICES[@]}"; do
  kubectl set image deployment/${SERVICE}-service \
    ${SERVICE}="${ECR_BASE}/geotrade-${SERVICE}:${IMAGE_TAG}" \
    -n geotrade
done

kubectl set image deployment/frontend \
  frontend="${FRONTEND_REPO}:${IMAGE_TAG}" \
  -n geotrade 2>/dev/null || true

# ─── 6. Wait for rollouts ─────────────────────────────────────────────
echo "▶ Waiting for rollouts to complete..."
for SERVICE in "${SERVICES[@]}"; do
  kubectl rollout status deployment/${SERVICE}-service -n geotrade --timeout=300s
  echo "  ✓ ${SERVICE} deployed"
done

# ─── 7. Health Check ──────────────────────────────────────────────────
echo "▶ Running health checks..."
API_URL=$(kubectl get ingress geotrade-ingress -n geotrade -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
for PORT in 8001 8002 8003 8004 8005; do
  STATUS=$(curl -sf "http://${API_URL}:${PORT}/health" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','unknown'))" 2>/dev/null || echo "unreachable")
  echo "  Service :${PORT} → ${STATUS}"
done

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  ✅ Deploy complete! Tag: ${IMAGE_TAG}            ║"
echo "╚══════════════════════════════════════════════════╝"
