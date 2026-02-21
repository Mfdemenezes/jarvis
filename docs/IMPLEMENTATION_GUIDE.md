# Guia de Implementação Completo

## Visão Geral

Este projeto implementa um assistente pessoal completo (estilo JARVIS) com:
- Backend na Oracle Cloud (grátis)
- API na AWS (~$3/mês)
- Apps iOS e Mac
- Memória persistente
- Notificações proativas

## Passo a Passo

### 1. Setup da Oracle VM (30 minutos)

```bash
# Na sua máquina local
cd oracle-vm
scp setup.sh usuario@SEU_IP_ORACLE:~/

# Na VM Oracle
ssh usuario@SEU_IP_ORACLE
chmod +x setup.sh
./setup.sh

# Após instalação, configure senha
sudo -u postgres psql
ALTER USER assistant WITH PASSWORD 'sua_senha_forte';
\q

# Configure AWS CLI para backups
aws configure
```

**Verificar instalação:**
```bash
# Testar PostgreSQL
psql -U assistant -d personal_kb -c "SELECT version();"

# Testar Ollama
curl http://localhost:11434/api/generate -d '{"model":"llama3.1:8b","prompt":"Hello","stream":false}'
```

### 2. Deploy do Backend AWS (20 minutos)

```bash
cd backend

# Configurar variáveis
cp terraform.tfvars.example terraform.tfvars
# Editar terraform.tfvars com IP da Oracle VM e senha

# Build das Lambdas
chmod +x build_lambdas.sh
./build_lambdas.sh

# Deploy
terraform init
terraform plan
terraform apply

# Salvar outputs
terraform output > outputs.txt
```

**Testar API:**
```bash
API_ENDPOINT=$(terraform output -raw api_endpoint)

curl -X POST $API_ENDPOINT/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","message":"Olá!"}'
```

### 3. Configurar App iOS (15 minutos)

```bash
cd ios-app
open PersonalAssistant.xcodeproj
```

No Xcode:
1. Altere Bundle Identifier
2. Configure Team (sua conta Apple)
3. Edite `ContentView.swift`:
   - Substitua `YOUR_API_ENDPOINT` pelo output do Terraform
4. Adicione capability "Push Notifications"
5. Build e Run (Cmd+R)

### 4. Configurar Notificações Push (10 minutos)

1. No app iOS, aceite permissões de notificação
2. Copie o device token do console do Xcode
3. Registre no SNS:

```bash
SNS_TOPIC=$(terraform output -raw sns_topic_arn)

aws sns subscribe \
  --topic-arn $SNS_TOPIC \
  --protocol application \
  --notification-endpoint SEU_DEVICE_TOKEN
```

### 5. Testar Sistema Completo

**Teste 1: Chat básico**
```bash
# No app iOS
"Olá, como você está?"
# Deve receber resposta do Ollama
```

**Teste 2: Memória**
```bash
# Primeira mensagem
"Meu nome é João e gosto de café"

# Segunda mensagem (depois de alguns minutos)
"Você lembra do que eu gosto?"
# Deve mencionar café
```

**Teste 3: Lembrete**
```bash
# No PostgreSQL da Oracle VM
psql -U assistant -d personal_kb

INSERT INTO reminders (title, description, trigger_time)
VALUES ('Teste', 'Lembrete de teste', NOW() + INTERVAL '2 minutes');

# Aguardar 2 minutos - deve receber notificação no iPhone
```

## Arquitetura Final

```
┌─────────────────┐
│   iPhone App    │
│   (SwiftUI)     │
└────────┬────────┘
         │ HTTPS
         ↓
┌─────────────────────────────┐
│         AWS                 │
│  ┌──────────────────────┐  │
│  │  API Gateway         │  │
│  │  Lambda Functions    │  │
│  │  DynamoDB (cache)    │  │
│  │  SNS (notificações)  │  │
│  │  S3 (backups)        │  │
│  └──────────┬───────────┘  │
└─────────────┼───────────────┘
              │ Internet
              ↓
┌─────────────────────────────┐
│    Oracle Cloud VM          │
│    (4 vCPU, 24GB RAM)       │
│  ┌──────────────────────┐  │
│  │  Ollama (LLM)        │  │
│  │  PostgreSQL+pgvector │  │
│  │  Cron (automações)   │  │
│  └──────────────────────┘  │
└─────────────────────────────┘
```

## Custos Mensais

```
Oracle VM              $0 (você já tem)
Ollama                 $0 (open source)
PostgreSQL             $0 (self-hosted)
API Gateway            $1
Lambda                 $1
DynamoDB               $0.50
SNS                    $0.50
S3                     $0.50
─────────────────────────────
Total                  ~$3.50/mês
```

## Próximos Passos

### Curto Prazo
- [ ] Adicionar autenticação (JWT)
- [ ] Implementar rate limiting
- [ ] Melhorar embeddings (usar API real)
- [ ] Adicionar mais action groups

### Médio Prazo
- [ ] App Mac (menu bar)
- [ ] Siri Shortcuts
- [ ] Widgets iOS
- [ ] Integração com calendário

### Longo Prazo
- [ ] Análise de sentimento
- [ ] Sugestões proativas
- [ ] Integração com smart home
- [ ] Dashboard web

## Troubleshooting

### Lambda não conecta no PostgreSQL
```bash
# Verificar firewall na Oracle VM
sudo firewall-cmd --list-all

# Adicionar IP da Lambda
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="IP_LAMBDA" port port="5432" protocol="tcp" accept'
sudo firewall-cmd --reload
```

### Ollama muito lento
```bash
# Trocar para modelo menor
ollama pull llama3.1:8b

# Ou aumentar recursos (já tem 24GB, deve ser rápido)
```

### Notificações não chegam
```bash
# Verificar logs da Lambda
aws logs tail /aws/lambda/personal-assistant-notifications --follow

# Verificar tópico SNS
aws sns list-subscriptions-by-topic --topic-arn SEU_TOPIC_ARN
```

## Manutenção

### Backups
- Automático: diário às 3am (cron)
- Manual: `ssh oracle-vm "~/backup.sh"`

### Monitoramento
```bash
# Logs AWS
aws logs tail /aws/lambda/personal-assistant-chat --follow

# Status Oracle VM
ssh oracle-vm "systemctl status postgresql ollama"
```

### Atualizações
```bash
# Atualizar modelo Ollama
ssh oracle-vm "ollama pull llama3.1:8b"

# Atualizar Lambda
cd backend
./build_lambdas.sh
terraform apply
```

## Suporte

- Issues: Abra issue no repositório
- Documentação AWS: https://docs.aws.amazon.com
- Ollama: https://ollama.com/docs
- PostgreSQL: https://www.postgresql.org/docs/
