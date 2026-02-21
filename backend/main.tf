terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  default = "us-east-1"
}

variable "oracle_vm_ip" {
  description = "IP público da sua VM Oracle"
  type        = string
}

variable "oracle_vm_postgres_password" {
  description = "Senha do PostgreSQL na VM Oracle"
  type        = string
  sensitive   = true
}

# DynamoDB para cache de conversas recentes
resource "aws_dynamodb_table" "conversations" {
  name           = "personal-assistant-conversations"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "user_id"
  range_key      = "timestamp"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
}

# S3 para backups
resource "aws_s3_bucket" "backups" {
  bucket = "personal-assistant-backups-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id
  versioning_configuration {
    status = "Enabled"
  }
}

# SNS para notificações push
resource "aws_sns_topic" "notifications" {
  name = "personal-assistant-notifications"
}

# IAM Role para Lambda
resource "aws_iam_role" "lambda_role" {
  name = "personal-assistant-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "personal-assistant-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = aws_dynamodb_table.conversations.arn
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = aws_sns_topic.notifications.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.backups.arn}/*"
      }
    ]
  })
}

# Lambda Function - Chat Handler
resource "aws_lambda_function" "chat_handler" {
  filename      = "lambda/chat_handler.zip"
  function_name = "personal-assistant-chat"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.handler"
  runtime       = "python3.11"
  timeout       = 30

  environment {
    variables = {
      ORACLE_VM_IP       = var.oracle_vm_ip
      POSTGRES_PASSWORD  = var.oracle_vm_postgres_password
      DYNAMODB_TABLE     = aws_dynamodb_table.conversations.name
      SNS_TOPIC_ARN      = aws_sns_topic.notifications.arn
    }
  }
}

# Lambda Function - Notification Sender
resource "aws_lambda_function" "notification_sender" {
  filename      = "lambda/notification_sender.zip"
  function_name = "personal-assistant-notifications"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.handler"
  runtime       = "python3.11"
  timeout       = 10

  environment {
    variables = {
      SNS_TOPIC_ARN = aws_sns_topic.notifications.arn
    }
  }
}

# API Gateway
resource "aws_apigatewayv2_api" "api" {
  name          = "personal-assistant-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["POST", "GET", "OPTIONS"]
    allow_headers = ["content-type", "authorization"]
  }
}

resource "aws_apigatewayv2_stage" "api" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "prod"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "chat" {
  api_id           = aws_apigatewayv2_api.api.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.chat_handler.invoke_arn
}

resource "aws_apigatewayv2_route" "chat" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "POST /chat"
  target    = "integrations/${aws_apigatewayv2_integration.chat.id}"
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.chat_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}

# EventBridge para automações (verificar lembretes a cada 5 minutos)
resource "aws_cloudwatch_event_rule" "check_reminders" {
  name                = "personal-assistant-check-reminders"
  schedule_expression = "rate(5 minutes)"
}

resource "aws_cloudwatch_event_target" "check_reminders" {
  rule      = aws_cloudwatch_event_rule.check_reminders.name
  target_id = "notification-sender"
  arn       = aws_lambda_function.notification_sender.arn
}

resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.notification_sender.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.check_reminders.arn
}

data "aws_caller_identity" "current" {}

# Outputs
output "api_endpoint" {
  value = aws_apigatewayv2_api.api.api_endpoint
}

output "sns_topic_arn" {
  value = aws_sns_topic.notifications.arn
}

output "s3_backup_bucket" {
  value = aws_s3_bucket.backups.bucket
}
