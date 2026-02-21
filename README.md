# Jarvis - Assistente Pessoal com IA

Assistente pessoal rodando em Oracle Cloud Free Tier, acessível via PWA com interação por voz e texto.

## Arquitetura

```
Internet → Nginx Host (SSL/Lets Encrypt) → Nginx Container (8090)
                                              ├── PWA (login.html, index.html, sw.js)
                                              └── Proxy → FastAPI (8100)
                                                           ├── PostgreSQL
                                                           └── Redis
```

| Container    | Imagem              | Porta               | Função              |
|-------------|---------------------|----------------------|----------------------|
| jarvis-web  | nginx:alpine        | 127.0.0.1:8090→80   | Proxy reverso + PWA  |
| jarvis-app  | python/fastapi      | 127.0.0.1:8100→8000 | Backend API          |
| jarvis-db   | pgvector/pgvector   | interno              | Banco de dados       |
| jarvis-cache| redis:7-alpine      | interno              | Cache + tokens OAuth |

## Funcionalidades

### Chat com IA
- LLM: GPT-4o mini (OpenAI API), ~2s de resposta
- Personalidade: informal, curto, sem emojis
- Detecção de intenção por keywords → busca dados reais antes de responder

### Voz
- Input: Web Speech API + Whisper API fallback (iOS)
- Output: SpeechSynthesis pt-BR masculina (Luciano)

### Integrações

| Serviço       | API                 | Função                              |
|--------------|---------------------|--------------------------------------|
| Clima        | OpenWeatherMap      | Tempo real, padrão Miguel Pereira/RJ |
| Notícias     | NewsAPI             | Manchetes do Brasil                  |
| Câmbio       | open.er-api.com     | USD/EUR                              |
| Bitcoin      | CoinGecko           | BTC em BRL                           |
| Trânsito     | Google Routes       | Rotas com trânsito + GPS             |
| Planilha     | Google Sheets       | Leitura/escrita de despesas          |
| Email        | Gmail (OAuth2)      | Inbox + rascunhos                    |
| Agenda       | Google Calendar     | Leitura + criação de eventos         |
| WhatsApp     | Evolution API       | Envio de mensagens + alertas         |

### WhatsApp via Chat
- "manda mensagem pra [contato] dizendo [texto]"
- Busca no mapa local → fallback Evolution API (case-insensitive)

### Alertas de Email
- Cron 5min verifica emails não lidos
- Keywords: boleto, pagamento, fatura, banco, pix, urgente...
- Alerta no grupo WhatsApp dedicado

### Lembretes
- GPT extrai texto + data/hora → salva no PostgreSQL

### Planilha de Despesas
- Leitura por mês, escrita via JSON gerado pelo GPT

### GPS
- PWA captura localização a cada 5min
- Origem automática em rotas

## Segurança

- Login por formulário → cookie HttpOnly, Secure, SameSite=strict (7 dias)
- API protegida por X-Api-Key
- Portas Docker em 127.0.0.1 (não expostas)
- Acesso externo apenas HTTPS (443)
- Rate limiting: 5r/s API, 1r/s login
- 3 conexões simultâneas por IP
- Credenciais em .env (não commitado)
- Headers: HSTS, X-Frame-Options DENY, CSP, nosniff

## Estrutura

```
jarvis/
├── docker/
│   ├── main.py            # FastAPI backend
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── nginx.conf
│   ├── requirements.txt
│   ├── init-db.sql
│   └── .env               # Credenciais (gitignored)
├── pwa/
│   ├── index.html         # Chat PWA
│   ├── login.html         # Login
│   ├── sw.js              # Service Worker
│   ├── manifest.json
│   └── icons/logos
└── README.md
```

## Variáveis de Ambiente

```env
API_KEY=                  OPENAI_API_KEY=
POSTGRES_PASSWORD=        OPENWEATHER_API_KEY=
POSTGRES_DB=              NEWSAPI_KEY=
POSTGRES_USER=            GOOGLE_MAPS_KEY=
GMAIL_CLIENT_ID=          EVO_URL=
GMAIL_CLIENT_SECRET=      EVO_KEY=
LOGIN_USER=               EVO_INSTANCE=
LOGIN_PASS=               VAPID_PUBLIC=
                          VAPID_PRIVATE=
```

## Deploy

```bash
cd ~/jarvis/docker
docker-compose up -d --build
```

## Stack

Python 3.11 · FastAPI · GPT-4o mini · PostgreSQL 15 · Redis 7 · Nginx · Lets Encrypt · Oracle Cloud Free Tier (ARM Ampere A1) · Evolution API
