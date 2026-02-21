# App iOS - Assistente Pessoal

App nativo iOS para interagir com seu assistente pessoal.

## Funcionalidades

- ✅ Chat em tempo real
- ✅ Notificações push
- 🚧 Siri Shortcuts (próxima versão)
- 🚧 Widgets (próxima versão)
- 🚧 Modo offline (próxima versão)

## Requisitos

- Xcode 15+
- iOS 17+
- Conta Apple Developer (para notificações push)

## Setup

1. Abra o projeto no Xcode:
```bash
cd ios-app
open PersonalAssistant.xcodeproj
```

2. Configure o Bundle Identifier:
   - Selecione o projeto no navegador
   - Em "Signing & Capabilities"
   - Altere o Bundle Identifier para algo único (ex: `com.seudominio.personalassistant`)

3. Configure o endpoint da API:
   - Abra `ContentView.swift`
   - Substitua `YOUR_API_ENDPOINT` pelo endpoint do Terraform output

4. Configure notificações push:
   - Em "Signing & Capabilities"
   - Clique em "+ Capability"
   - Adicione "Push Notifications"

## Build e Run

1. Selecione seu dispositivo ou simulador
2. Pressione Cmd+R para build e run

## Notificações Push

Para receber notificações:

1. O app vai pedir permissão na primeira execução
2. O device token será impresso no console
3. Você precisa registrar esse token no SNS (AWS)

### Registrar no SNS

```bash
aws sns create-platform-endpoint \
  --platform-application-arn arn:aws:sns:REGION:ACCOUNT:app/APNS/PersonalAssistant \
  --token SEU_DEVICE_TOKEN
```

## Próximas Funcionalidades

### Siri Shortcuts
Permitirá comandos como:
- "Hey Siri, pergunte ao meu assistente sobre..."
- "Hey Siri, lembre-me de..."

### Widgets
- Resumo do dia
- Próximos lembretes
- Insights rápidos

### Modo Offline
- Cache de conversas recentes
- Sincronização quando voltar online

## Estrutura do Projeto

```
PersonalAssistant/
├── ContentView.swift           # Interface principal
├── NotificationManager.swift   # Gerenciamento de notificações
├── Models/                     # Modelos de dados
├── ViewModels/                 # Lógica de negócio
└── Services/                   # APIs e serviços
```

## Troubleshooting

### Notificações não funcionam
- Verifique se as permissões foram concedidas
- Confirme que o certificado APNs está configurado
- Teste em dispositivo físico (simulador tem limitações)

### Erro de conexão com API
- Verifique se o endpoint está correto
- Confirme que a API está rodando (teste com curl)
- Verifique a conexão de internet
