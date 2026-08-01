# Jarvis - Assistente Pessoal com IA

Assistente pessoal rodando em Oracle Cloud Free Tier, acessível via PWA (voz e texto) e WhatsApp (grupo dedicado via Evolution API).

## Arquitetura

```
Internet → Nginx Host (SSL/Lets Encrypt) → Nginx Container (8090)
                                              ├── PWA (login.html, index.html, sw.js)
                                              └── Proxy → FastAPI (8100)
                                                           ├── PostgreSQL (pgvector)
                                                           └── Redis

WhatsApp → Evolution API → webhook /webhook/whatsapp → FastAPI → resposta no grupo
```

| Container    | Imagem              | Porta               | Função              |
|-------------|---------------------|----------------------|----------------------|
| jarvis-web  | nginx:alpine        | 127.0.0.1:8090→80   | Proxy reverso + PWA  |
| jarvis-app  | python/fastapi      | 127.0.0.1:8100→8000 | Backend API          |
| jarvis-db   | pgvector/pgvector   | interno              | Banco + embeddings   |
| jarvis-cache| redis:7-alpine      | interno              | Cache + ações pendentes |
| evolution   | evolution-api:2.3.7 | 127.0.0.1:8082→8080 | Ponte WhatsApp       |

## Como funciona o cérebro (agente com ferramentas)

Desde 2026-07-27 o `/chat` é um **agente com tool use nativo da Anthropic** (`run_agent` em `main.py`):
o modelo recebe a lista de ferramentas e decide sozinho quais chamar, em até 6 passos encadeados,
antes de responder. Não existe mais detecção de intenção por palavras-chave.

- **Modelos**: Claude Haiku 4.5 (mensagens simples) / Claude Sonnet 5 (perguntas complexas — `is_complex_query`).
- **Fallback**: se a Anthropic falhar, cascata texto-puro OpenAI → Groq (`call_ollama`), sem ferramentas.
- **Instruções sempre no system prompt**, nunca misturadas ao bloco de contexto/dados
  (instrução colada em dados é tratada pelo modelo como injeção de prompt e ignorada).
- **Contexto por requisição**: memórias relevantes (pgvector) + últimas 15 mensagens + localização (se enviada).

### Ferramentas disponíveis (`TOOLS` / `execute_tool`)

| Ferramenta          | Função                                                    |
|---------------------|-----------------------------------------------------------|
| buscar_google       | Google Custom Search (fatos atuais, preços, pessoas)      |
| clima               | OpenWeatherMap (padrão Miguel Pereira/RJ)                 |
| cotacoes            | USD/EUR (open.er-api.com) + Bitcoin (CoinGecko)           |
| noticias            | NewsAPI (manchetes por tema)                              |
| transito            | Google Routes (rota de carro com trânsito)                |
| ler_agenda          | Google Calendar, todas as agendas, N dias                 |
| criar_evento        | Rascunho de evento → **exige confirmação sim/não**        |
| ler_emails          | Gmail inbox (OAuth2)                                      |
| ler_planilha        | Google Sheets de finanças, filtrado por mês               |
| escrever_planilha   | append/update/delete na planilha                          |
| criar_lembrete      | Salva lembrete no PostgreSQL (cron avisa na hora)         |
| listar_lembretes    | Lembretes pendentes                                       |
| enviar_whatsapp     | Rascunho de mensagem → **exige confirmação sim/não**      |
| salvar_memoria      | Grava fato pessoal permanente (embedding no pgvector)     |

### Confirmação de ações (determinística)

Ações sensíveis (WhatsApp, criar evento) **nunca são executadas pelo modelo**:
a ferramenta apenas registra um rascunho no Redis (`pending_action:{user_id}`, TTL 120s)
e o app pergunta "Confirma? (sim/não)". A detecção de sim/não é feita por código
(tokens em qualquer posição da frase — "ficou ótimo, pode enviar" confirma) no início
do `/chat`, antes de qualquer chamada de LLM. Confirmações e pedidos de ação nunca
entram no cache de respostas.

## WhatsApp — duas identidades (Evolution API)

| Instância         | Número                     | Uso                                          |
|-------------------|----------------------------|----------------------------------------------|
| `mbam1`           | comercial (bot)            | Respostas do Jarvis no grupo + alertas       |
| `Marcelo Menezes` | pessoal (5521960192189)    | Mensagens a contatos, enviadas em seu nome   |

- Mensagens a contatos saem pelo **número pessoal** (`EVO_PERSONAL_INSTANCE`/`EVO_PERSONAL_KEY`) —
  o destinatário recebe na conversa normal com o Marcelo.
- Destinatário pode ser nome de contato ("Amor"), apelido fixo, ou número direto (`+5521...`).
- Webhook do grupo: só processa `messages.upsert` do grupo configurado (`MARCELO_WHATSAPP`),
  ignora mensagens do próprio bot (anti-loop) e valida `X-Webhook-Secret`.
- Perguntas complexas disparam aviso imediato "🧠 Deixa eu pensar nessa..." no grupo.

## Rotinas proativas (cron internos)

| Rotina                  | Quando       | O que faz                                      |
|-------------------------|--------------|------------------------------------------------|
| Relatório matinal       | 06:00        | Agenda + lembretes + câmbio + manchetes no zap |
| Preview do dia seguinte | 18:00        | Compromissos de amanhã                          |
| Alertas de e-mail       | a cada 5min  | Keywords (boleto, fatura, pix...) → aviso no grupo |
| Lembretes               | a cada 60s   | Dispara lembretes vencidos no WhatsApp          |
| Sincronização contatos  | no startup   | Contatos do WhatsApp → PostgreSQL (busca fuzzy) |

## Voz (PWA)

- Input: Web Speech API + Whisper API fallback (iOS) via `/api/transcribe`
- Output: SpeechSynthesis pt-BR

## Segurança

- Login por formulário → cookie HttpOnly, Secure, SameSite=strict (7 dias)
- API protegida por X-Api-Key; webhook por X-Webhook-Secret
- Portas Docker em 127.0.0.1 (não expostas); acesso externo apenas HTTPS (443)
- Rate limiting: 5r/s API, 1r/s login; 3 conexões simultâneas por IP
- Credenciais em .env (não commitado)
- Headers: HSTS, X-Frame-Options DENY, CSP, nosniff
- Confirmação de ações fora do alcance do LLM (código determinístico)

## Estrutura

```
jarvis/
├── docker/
│   ├── main.py            # FastAPI + agente (TOOLS, execute_tool, run_agent)
│   ├── app/               # config.py, integrations/, services/
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
├── scripts/               # notify_login.sh etc.
└── README.md
```

## Variáveis de Ambiente

```env
API_KEY=                  ANTHROPIC_API_KEY=        # LLM principal (agente)
POSTGRES_PASSWORD=        OPENAI_API_KEY=           # fallback + embeddings + Whisper
POSTGRES_DB=              GROQ_API_KEY=             # fallback final
POSTGRES_USER=            OPENWEATHER_API_KEY=
GMAIL_CLIENT_ID=          NEWSAPI_KEY=
GMAIL_CLIENT_SECRET=      GOOGLE_MAPS_KEY=
LOGIN_USER=               GOOGLE_SEARCH_KEY=        GOOGLE_SEARCH_CX=
LOGIN_PASS=               EVO_URL=                  EVO_KEY=
VAPID_PUBLIC=             EVO_INSTANCE=             # instância do bot (grupo)
VAPID_PRIVATE=            EVO_PERSONAL_INSTANCE=    # instância do número pessoal
WHATSAPP_WEBHOOK_SECRET=  EVO_PERSONAL_KEY=
```

## Deploy

```bash
cd ~/app/jarvis/docker
docker compose build jarvis-app && docker compose up -d jarvis-app
```

Backups de versões anteriores do backend ficam em `docker/main.py.bak.*`.

## Stack

Python 3.11 · FastAPI · Claude (Haiku 4.5 / Sonnet 5, tool use) · OpenAI/Groq (fallback) · PostgreSQL 15 + pgvector · Redis 7 · Nginx · Lets Encrypt · Oracle Cloud Free Tier (ARM Ampere A1) · Evolution API v2.3.7
