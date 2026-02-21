# Melhorias de Segurança - Acesso Somente Seu

## Problema Atual
- API Gateway aberta para qualquer pessoa
- Sem autenticação
- Qualquer um pode usar seu assistente

## Solução: Autenticação com API Key

### Opção 1: API Key Simples (Recomendado)

**Vantagens:**
- Simples de implementar
- Sem custo adicional
- Funciona com PWA e Atalhos

**Implementação:**

1. Gerar API Key única:
```bash
# Gerar chave aleatória
openssl rand -hex 32
# Exemplo: a1b2c3d4e5f6...
```

2. Adicionar ao Terraform (`backend/main.tf`):
```hcl
variable "api_key" {
  description = "API Key para autenticação"
  type        = string
  sensitive   = true
}

# Adicionar ao Lambda
resource "aws_lambda_function" "chat_handler" {
  # ... código existente ...
  
  environment {
    variables = {
      ORACLE_VM_IP       = var.oracle_vm_ip
      POSTGRES_PASSWORD  = var.oracle_vm_postgres_password
      DYNAMODB_TABLE     = aws_dynamodb_table.conversations.name
      SNS_TOPIC_ARN      = aws_sns_topic.notifications.arn
      API_KEY            = var.api_key  # NOVO
    }
  }
}
```

3. Atualizar Lambda (`backend/lambda/chat_handler.py`):
```python
import os

API_KEY = os.environ['API_KEY']

def handler(event, context):
    # Verificar API Key
    headers = event.get('headers', {})
    provided_key = headers.get('x-api-key') or headers.get('X-Api-Key')
    
    if provided_key != API_KEY:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthorized'})
        }
    
    # ... resto do código ...
```

4. Adicionar ao `terraform.tfvars`:
```hcl
api_key = "SUA_CHAVE_GERADA_AQUI"
```

### Opção 2: AWS Cognito (Mais Robusto)

**Vantagens:**
- Autenticação completa
- Suporta múltiplos usuários (futuro)
- Integração nativa com API Gateway

**Custo:** ~$0 (50.000 MAUs grátis)

**Implementação:**

Adicionar ao `backend/main.tf`:
```hcl
# Cognito User Pool
resource "aws_cognito_user_pool" "pool" {
  name = "personal-assistant-users"
  
  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }
}

resource "aws_cognito_user_pool_client" "client" {
  name         = "personal-assistant-client"
  user_pool_id = aws_cognito_user_pool.pool.id
  
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]
}

# Criar usuário (você)
resource "aws_cognito_user" "you" {
  user_pool_id = aws_cognito_user_pool.pool.id
  username     = "seu_email@example.com"
  
  attributes = {
    email          = "seu_email@example.com"
    email_verified = true
  }
}

# Integrar com API Gateway
resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.api.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "cognito-authorizer"

  jwt_configuration {
    audience = [aws_cognito_user_pool_client.client.id]
    issuer   = "https://${aws_cognito_user_pool.pool.endpoint}"
  }
}

# Adicionar autorização à rota
resource "aws_apigatewayv2_route" "chat" {
  api_id             = aws_apigatewayv2_api.api.id
  route_key          = "POST /chat"
  target             = "integrations/${aws_apigatewayv2_integration.chat.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}
```

### Opção 3: Remover AWS e Usar Só Oracle (Mais Simples)

**Vantagens:**
- Custo $0
- Mais simples
- Controle total

**Desvantagens:**
- Sem notificações push automáticas
- Precisa gerenciar SSL manualmente

**Arquitetura:**
```
iPhone/PWA → Cloudflare Tunnel (grátis) → Oracle VM (FastAPI)
```

Vou criar essa opção no próximo arquivo.

## Recomendação

Para uso pessoal, recomendo **Opção 1 (API Key)** porque:
- Simples de implementar
- Sem custo adicional
- Suficiente para acesso pessoal
- Funciona com PWA e Atalhos

## Segurança Adicional

### 1. Restringir CORS

Atualizar `backend/main.tf`:
```hcl
resource "aws_apigatewayv2_api" "api" {
  name          = "personal-assistant-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["https://seu-dominio.com"]  # Seu domínio específico
    allow_methods = ["POST", "OPTIONS"]
    allow_headers = ["content-type", "x-api-key"]
    max_age       = 300
  }
}
```

### 2. Rate Limiting

Adicionar ao `backend/main.tf`:
```hcl
resource "aws_apigatewayv2_stage" "api" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "prod"
  auto_deploy = true
  
  default_route_settings {
    throttling_burst_limit = 10
    throttling_rate_limit  = 5
  }
}
```

### 3. Firewall Oracle VM

Restringir acesso apenas do seu IP:
```bash
# Na Oracle VM
sudo firewall-cmd --permanent --remove-port=5432/tcp
sudo firewall-cmd --permanent --remove-port=11434/tcp

# Aceitar apenas do IP da AWS Lambda
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="IP_DA_LAMBDA/32" port port="5432" protocol="tcp" accept'
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="IP_DA_LAMBDA/32" port port="11434" protocol="tcp" accept'

sudo firewall-cmd --reload
```

### 4. Logs e Monitoramento

Adicionar ao `backend/main.tf`:
```hcl
resource "aws_cloudwatch_log_group" "api_logs" {
  name              = "/aws/apigateway/personal-assistant"
  retention_in_days = 7
}

resource "aws_apigatewayv2_stage" "api" {
  # ... código existente ...
  
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }
}

# Alarme para tentativas suspeitas
resource "aws_cloudwatch_metric_alarm" "unauthorized_attempts" {
  alarm_name          = "personal-assistant-unauthorized"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "4XXError"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "Muitas tentativas não autorizadas"
  
  dimensions = {
    ApiId = aws_apigatewayv2_api.api.id
  }
}
```

## Próximos Passos

1. Escolher opção de autenticação (recomendo Opção 1)
2. Aplicar mudanças no Terraform
3. Atualizar PWA/Atalhos com API Key
4. Testar acesso
5. Monitorar logs
