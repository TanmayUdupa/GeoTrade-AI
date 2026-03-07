# infrastructure/terraform/main.tf
# GeoTrade AI — AWS Infrastructure (ap-south-1 Mumbai)

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    bucket = "geotrade-terraform-state"
    key    = "prod/terraform.tfstate"
    region = "ap-south-1"
  }
}

provider "aws" {
  region = var.aws_region
}

# ─── Variables ─────────────────────────────────────────────────────────

variable "aws_region"     { default = "ap-south-1" }
variable "env"            { default = "prod" }
variable "project"        { default = "geotrade" }
variable "db_password"    { sensitive = true }
variable "ecr_image_tag"  { default = "latest" }

locals {
  prefix = "${var.project}-${var.env}"
  tags   = { Project = var.project, Env = var.env, ManagedBy = "terraform" }
}

# ─── VPC ────────────────────────────────────────────────────────────────

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${local.prefix}-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway   = true
  single_nat_gateway   = false   # HA: one NAT per AZ
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = local.tags
}

# ─── EKS Cluster ─────────────────────────────────────────────────────────

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "${local.prefix}-eks"
  cluster_version = "1.30"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access = true

  eks_managed_node_groups = {
    main = {
      instance_types = ["t3.xlarge"]
      min_size       = 2
      max_size       = 10
      desired_size   = 3

      labels = { role = "main" }
      taints = []
    }
    ml = {
      instance_types = ["c5.2xlarge"]
      min_size       = 1
      max_size       = 5
      desired_size   = 2
      labels         = { role = "ml-workload" }
      taints = [{
        key    = "ml-only"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]
    }
  }

  tags = local.tags
}

# ─── RDS PostgreSQL ───────────────────────────────────────────────────────

resource "aws_db_subnet_group" "main" {
  name       = "${local.prefix}-db-subnet"
  subnet_ids = module.vpc.private_subnets
  tags       = local.tags
}

resource "aws_security_group" "rds" {
  name   = "${local.prefix}-rds-sg"
  vpc_id = module.vpc.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [module.vpc.vpc_cidr_block]
  }
  tags = local.tags
}

resource "aws_db_instance" "postgres" {
  identifier              = "${local.prefix}-postgres"
  engine                  = "postgres"
  engine_version          = "15.6"
  instance_class          = "db.t3.medium"
  allocated_storage       = 50
  max_allocated_storage   = 200
  storage_encrypted       = true

  db_name  = "geotrade"
  username = "geotrade"
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  backup_retention_period = 7
  deletion_protection     = true
  skip_final_snapshot     = false
  final_snapshot_identifier = "${local.prefix}-final-snapshot"

  tags = local.tags
}

# ─── DocumentDB (MongoDB-compatible) ─────────────────────────────────────

resource "aws_docdb_cluster" "main" {
  cluster_identifier  = "${local.prefix}-docdb"
  engine              = "docdb"
  master_username     = "geotrade"
  master_password     = var.db_password
  db_subnet_group_name = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  storage_encrypted   = true
  backup_retention_period = 7
  tags                = local.tags
}

resource "aws_docdb_cluster_instance" "main" {
  count              = 2
  identifier         = "${local.prefix}-docdb-${count.index}"
  cluster_identifier = aws_docdb_cluster.main.id
  instance_class     = "db.t3.medium"
}

# ─── ElastiCache Redis ────────────────────────────────────────────────────

resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.prefix}-redis-subnet"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${local.prefix}-redis"
  description          = "GeoTrade Redis cache"
  node_type            = "cache.t3.medium"
  num_cache_clusters   = 2
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.rds.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  tags = local.tags
}

# ─── S3 Buckets ───────────────────────────────────────────────────────────

resource "aws_s3_bucket" "raw_articles" {
  bucket = "${local.prefix}-raw-articles-${data.aws_caller_identity.current.account_id}"
  tags   = local.tags
}

resource "aws_s3_bucket_versioning" "raw_articles" {
  bucket = aws_s3_bucket.raw_articles.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw_articles" {
  bucket = aws_s3_bucket.raw_articles.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

# ─── MSK (Managed Kafka) ──────────────────────────────────────────────────

resource "aws_msk_cluster" "kafka" {
  cluster_name           = "${local.prefix}-kafka"
  kafka_version          = "3.6.0"
  number_of_broker_nodes = 3

  broker_node_group_info {
    instance_type   = "kafka.t3.small"
    client_subnets  = module.vpc.private_subnets
    storage_info {
      ebs_storage_info { volume_size = 100 }
    }
    security_groups = [aws_security_group.rds.id]
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }

  tags = local.tags
}

# ─── Cognito User Pool ─────────────────────────────────────────────────────

resource "aws_cognito_user_pool" "main" {
  name = "${local.prefix}-users"

  password_policy {
    minimum_length    = 12
    require_uppercase = true
    require_numbers   = true
    require_symbols   = true
  }

  mfa_configuration = "OPTIONAL"

  software_token_mfa_configuration {
    enabled = true
  }

  tags = local.tags
}

resource "aws_cognito_user_pool_client" "frontend" {
  name         = "${local.prefix}-frontend-client"
  user_pool_id = aws_cognito_user_pool.main.id

  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  callback_urls                        = ["https://app.geotrade.ai/callback"]
  logout_urls                          = ["https://app.geotrade.ai/logout"]
}

# ─── API Gateway ──────────────────────────────────────────────────────────

resource "aws_api_gateway_rest_api" "main" {
  name = "${local.prefix}-api"
  tags = local.tags
}

resource "aws_wafv2_web_acl" "main" {
  name  = "${local.prefix}-waf"
  scope = "REGIONAL"

  default_action { allow {} }

  rule {
    name     = "RateLimit"
    priority = 1
    action { block {} }
    statement {
      rate_based_statement {
        limit              = 1000
        aggregate_key_type = "IP"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimit"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 2
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "CommonRules"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.prefix}-waf"
    sampled_requests_enabled   = true
  }

  tags = local.tags
}

# ─── SNS Topic for Alerts ─────────────────────────────────────────────────

resource "aws_sns_topic" "trade_alerts" {
  name              = "${local.prefix}-trade-alerts"
  kms_master_key_id = "alias/aws/sns"
  tags              = local.tags
}

# ─── CloudWatch Dashboard ─────────────────────────────────────────────────

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.prefix}-dashboard"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", width = 12, height = 6,
        properties = {
          title  = "EKS Node CPU"
          metrics = [["AWS/EKS", "node_cpu_utilization", "ClusterName", module.eks.cluster_name]]
          period = 60
        }
      },
      {
        type = "metric", width = 12, height = 6,
        properties = {
          title   = "RDS Connections"
          metrics = [["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", aws_db_instance.postgres.identifier]]
          period  = 60
        }
      }
    ]
  })
}

# ─── SageMaker ───────────────────────────────────────────────────────────

resource "aws_sagemaker_model" "lstm_risk" {
  name               = "${local.prefix}-lstm-risk"
  execution_role_arn = aws_iam_role.sagemaker.arn

  primary_container {
    image          = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${local.prefix}-lstm:${var.ecr_image_tag}"
    model_data_url = "s3://${aws_s3_bucket.raw_articles.bucket}/models/lstm/model.tar.gz"
  }
  tags = local.tags
}

resource "aws_sagemaker_endpoint_configuration" "lstm_risk" {
  name = "${local.prefix}-lstm-config"
  production_variants {
    variant_name           = "primary"
    model_name             = aws_sagemaker_model.lstm_risk.name
    initial_instance_count = 1
    instance_type          = "ml.c5.large"
  }
  tags = local.tags
}

resource "aws_sagemaker_endpoint" "lstm_risk" {
  name                 = "${local.prefix}-lstm-endpoint"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.lstm_risk.name
  tags                 = local.tags
}

# ─── IAM Role: SageMaker ─────────────────────────────────────────────────

resource "aws_iam_role" "sagemaker" {
  name = "${local.prefix}-sagemaker-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "sagemaker.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "sagemaker_full" {
  role       = aws_iam_role.sagemaker.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

# ─── Data Sources ─────────────────────────────────────────────────────────

data "aws_caller_identity" "current" {}

# ─── Outputs ──────────────────────────────────────────────────────────────

output "eks_cluster_name"      { value = module.eks.cluster_name }
output "rds_endpoint"          { value = aws_db_instance.postgres.endpoint }
output "docdb_endpoint"        { value = aws_docdb_cluster.main.endpoint }
output "redis_endpoint"        { value = aws_elasticache_replication_group.redis.primary_endpoint_address }
output "kafka_bootstrap"       { value = aws_msk_cluster.kafka.bootstrap_brokers_tls }
output "cognito_user_pool_id"  { value = aws_cognito_user_pool.main.id }
output "sns_alert_topic_arn"   { value = aws_sns_topic.trade_alerts.arn }
output "sagemaker_endpoint"    { value = aws_sagemaker_endpoint.lstm_risk.name }
