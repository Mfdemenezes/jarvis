# Assistente Pessoal (Estilo JARVIS)

Assistente pessoal completo com IA, memória persistente e notificações proativas.

## Arquitetura

- **Backend**: Oracle Cloud VM (Ollama + PostgreSQL)
- **API**: AWS (API Gateway + Lambda)
- **Frontend**: App iOS + Mac
- **Custo**: ~$3/mês

## Estrutura do Projeto

```
personal-assistant/
├── backend/              # Infraestrutura AWS (Terraform)
├── oracle-vm/           # Setup da VM Oracle
├── ios-app/             # App iPhone
├── mac-app/             # App Mac
└── docs/                # Documentação
```

## Quick Start

1. **Setup Oracle VM**: `cd oracle-vm && ./setup.sh`
2. **Deploy AWS**: `cd backend && terraform apply`
3. **Build iOS App**: `cd ios-app && open PersonalAssistant.xcodeproj`

## Custos Estimados

- API Gateway: $1/mês
- Lambda: $1/mês
- SNS: $0.50/mês
- S3: $0.50/mês
- Oracle VM: $0 (grátis)
- **Total: ~$3/mês**
