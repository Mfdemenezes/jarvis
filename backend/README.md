# Deploy do Backend AWS

## Pré-requisitos

1. AWS CLI configurado: `aws configure`
2. Terraform instalado: `brew install terraform`
3. Python 3.11+

## Configuração

1. Copie o arquivo de exemplo:
```bash
cp terraform.tfvars.example terraform.tfvars
```

2. Edite `terraform.tfvars` com suas informações:
```hcl
aws_region                    = "us-east-1"
oracle_vm_ip                  = "SEU_IP_ORACLE"
oracle_vm_postgres_password   = "SUA_SENHA_POSTGRES"
```

## Deploy

```bash
# 1. Build das Lambda functions
./build_lambdas.sh

# 2. Inicializar Terraform
terraform init

# 3. Planejar mudanças
terraform plan

# 4. Aplicar infraestrutura
terraform apply
```

## Após o Deploy

O Terraform vai retornar:
- `api_endpoint`: URL da API (use no app)
- `sns_topic_arn`: ARN do tópico SNS (para notificações)
- `s3_backup_bucket`: Bucket para backups

## Testar API

```bash
# Obter endpoint
API_ENDPOINT=$(terraform output -raw api_endpoint)

# Testar chat
curl -X POST $API_ENDPOINT/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "message": "Olá, como você está?"
  }'
```

## Custos Estimados

- API Gateway: ~$1/mês
- Lambda: ~$1/mês
- DynamoDB: ~$0.50/mês
- SNS: ~$0.50/mês
- S3: ~$0.50/mês
- **Total: ~$3.50/mês**

## Destruir Infraestrutura

```bash
terraform destroy
```
