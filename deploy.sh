#!/bin/bash

echo "🚀 Iniciando deploy completo do Assistente Pessoal..."
echo ""

# Verificar pré-requisitos
echo "📋 Verificando pré-requisitos..."

if ! command -v terraform &> /dev/null; then
    echo "❌ Terraform não encontrado. Instale com: brew install terraform"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI não encontrado. Instale com: brew install awscli"
    exit 1
fi

if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS CLI não configurado. Execute: aws configure"
    exit 1
fi

echo "✅ Pré-requisitos OK"
echo ""

# Solicitar informações
read -p "IP da Oracle VM: " ORACLE_IP
read -sp "Senha do PostgreSQL: " POSTGRES_PASSWORD
echo ""

# Criar terraform.tfvars
echo "📝 Criando configuração..."
cd backend
cat > terraform.tfvars <<EOF
aws_region = "us-east-1"
oracle_vm_ip = "$ORACLE_IP"
oracle_vm_postgres_password = "$POSTGRES_PASSWORD"
EOF

# Build das Lambdas
echo ""
echo "🔨 Compilando Lambda functions..."
chmod +x build_lambdas.sh
./build_lambdas.sh

# Deploy Terraform
echo ""
echo "☁️  Fazendo deploy na AWS..."
terraform init
terraform plan -out=tfplan

read -p "Continuar com o deploy? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deploy cancelado"
    exit 1
fi

terraform apply tfplan

# Salvar outputs
echo ""
echo "💾 Salvando outputs..."
terraform output > outputs.txt

API_ENDPOINT=$(terraform output -raw api_endpoint)
SNS_TOPIC=$(terraform output -raw sns_topic_arn)

echo ""
echo "✅ Deploy completo!"
echo ""
echo "📊 Informações importantes:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "API Endpoint: $API_ENDPOINT"
echo "SNS Topic: $SNS_TOPIC"
echo ""
echo "📱 Próximos passos:"
echo "1. Abra o app iOS no Xcode"
echo "2. Substitua YOUR_API_ENDPOINT por: $API_ENDPOINT"
echo "3. Build e execute o app"
echo "4. Aceite as permissões de notificação"
echo ""
echo "🧪 Testar API:"
echo "curl -X POST $API_ENDPOINT/chat \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"user_id\":\"test\",\"message\":\"Olá!\"}'"
echo ""
echo "📖 Documentação completa em: docs/IMPLEMENTATION_GUIDE.md"
