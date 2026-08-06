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

| Container     | Imagem             | Porta                | Função                   |
|---------------|--------------------|----------------------|--------------------------|
| jarvis-web    | nginx:alpine       | 127.0.0.1:8090→80   | Proxy reverso + PWA      |
| jarvis-app    | python/fastapi     | 127.0.0.1:8100→8000 | Backend API              |
| jarvis-db     | pgvector/pgvector  | interno              | Banco + embeddings       |
| jarvis-cache  | redis:7-alpine     | interno              | Cache + ações pendentes  |
| evolution     | evolution-api      | 127.0.0.1:8082→8080 | Ponte WhatsApp           |

## Como funciona o cérebro (agente com ferramentas)

O `/chat` é um **agente com tool use nativo da Anthropic** (`run_agent` em `main.py`):
o modelo recebe a lista de ferramentas e decide sozinho quais chamar, em até 6 passos encadeados,
antes de responder.

- **Modelos**: Claude Haiku 4.5 (simples) / Claude Sonnet 5 (complexo — `is_complex_query`)
- **Fallback LLM**: Anthropic → OpenAI → Groq (cascata automática)
- **Contexto por requisição**: memórias relevantes (pgvector) + últimas 15 mensagens + localização

### Ferramentas disponíveis (`TOOLS` / `execute_tool`)

| Ferramenta        | Função                                                      |
|-------------------|-------------------------------------------------------------|
| buscar_google     | Google Custom Search (fatos atuais, preços, pessoas)        |
| clima             | OpenWeatherMap (padrão: `DEFAULT_CITY`)                     |
| cotacoes          | USD/EUR (open.er-api.com) + Bitcoin (CoinGecko)             |
| noticias          | NewsAPI (manchetes por tema)                                |
| transito          | Google Routes (rota de carro com trânsito)                  |
| ler_agenda        | Google Calendar, todas as agendas, N dias                   |
| criar_evento      | Rascunho de evento → **exige confirmação sim/não**          |
| ler_emails        | Gmail inbox (OAuth2)                                        |
| ler_planilha      | Google Sheets de finanças, filtrado por mês                 |
| escrever_planilha | append/update/delete na planilha                            |
| criar_lembrete    | Salva lembrete no PostgreSQL (cron avisa na hora)           |
| listar_lembretes  | Lembretes pendentes                                         |
| enviar_whatsapp   | Rascunho de mensagem → **exige confirmação sim/não**        |
| salvar_memoria    | Grava fato pessoal permanente (embedding no pgvector)       |
| gerenciar_modulo  | Adiciona/remove/ativa/pausa módulos do relatório matinal    |
| analisar_movimento| Movimento de ETF/ação é anormal? (z-score por hora)         |
| niveis_tecnicos   | Perfil de volume (POC/área de valor), pivots, fundos e topos |

### Confirmação de ações (determinística)

Ações sensíveis (WhatsApp, criar evento) **nunca são executadas pelo modelo**:
a ferramenta registra rascunho no Redis (`pending_action:{user_id}`, TTL 120s)
e o app pergunta "Confirma? (sim/não)" — detectado por código antes de qualquer LLM.

## Relatório Matinal — Módulos Dinâmicos

O resumo enviado às **06:00** no WhatsApp é 100% configurável via tabela `morning_modules`
no PostgreSQL. Cada módulo pode ser ativado/desativado sem alterar código.

### Comandos pelo WhatsApp (linguagem natural ou direto)

```
adiciona etf JEPQ nas mensagens de manhã   → adiciona módulo
tira o bitcoin do resumo matinal           → pausa módulo
não quero mais ver notícias                → pausa módulo
/modulo list                               → lista todos com status
/modulo add etf JEPQ                       → adiciona por comando direto
/modulo on 7                               → ativa pelo ID
/modulo off 7                              → pausa pelo ID
/modulo remove 7                           → remove permanentemente
```

### Tipos de módulo suportados

| Tipo       | Fonte          | Exemplo de parâmetro     |
|------------|----------------|--------------------------|
| moedas     | open.er-api.com| —                        |
| cripto     | CoinGecko      | bitcoin, ethereum        |
| clima      | OpenWeather    | Miguel Pereira, Rio      |
| noticias   | NewsAPI        | brasil, tecnologia       |
| agenda     | Google Calendar| —                        |
| lembretes  | interno (DB)   | —                        |
| etf        | Yahoo Finance  | JEPQ, SPY, QQQ           |
| acao_us    | Yahoo Finance  | AAPL, TSLA               |
| acao_br    | BrAPI          | PETR4, VALE3             |
| alerta     | interno        | texto livre              |
| vol        | Yahoo Finance  | JEPQ, SPY (com z-score)  |
| niveis     | Yahoo Finance  | JEPQ (POC + área valor)  |

### Módulos padrão (pré-configurados)

```sql
SELECT id, tipo, parametro, label, ativo FROM morning_modules ORDER BY ordem;
```

## WhatsApp — duas identidades (Evolution API)

| Instância          | Uso                                              |
|--------------------|--------------------------------------------------|
| `EVO_INSTANCE`     | Respostas do Jarvis no grupo + alertas proativos |
| `EVO_PERSONAL_INSTANCE` | Mensagens a contatos, enviadas em seu nome  |

- Webhook só processa `messages.upsert` do grupo `WHATSAPP_GROUP_ID`
- Ignora mensagens do próprio bot (anti-loop)
- Valida `X-Webhook-Secret`
- Perguntas complexas disparam aviso "🧠 Deixa eu pensar nessa..." imediato

## Rotinas proativas (cron internos)

| Rotina                  | Quando      | O que faz                                         |
|-------------------------|-------------|---------------------------------------------------|
| Relatório matinal       | 06:00       | Módulos ativos do DB → LLM → envia no grupo       |
| Preview compromissos    | 18:00       | Eventos de amanhã no Google Calendar              |
| Alertas de e-mail       | a cada 5min | Keywords (boleto, fatura, pix...) → aviso no grupo|
| Lembretes               | a cada 60s  | Dispara lembretes vencidos no WhatsApp            |
| Sincronização contatos  | 1x por dia  | Evolution API → PostgreSQL (busca fuzzy por nome) |
| Alerta de vol anormal   | 1x/h no pregão | Movimento ≥2σ de ativo monitorado → avisa no grupo |

## Banco de Dados — Tabelas

| Tabela               | Uso                                              |
|----------------------|--------------------------------------------------|
| conversations        | Histórico de chat                                |
| memory_embeddings    | Memórias pessoais com embedding (pgvector)       |
| reminders            | Lembretes com data/hora                          |
| morning_modules      | Módulos configuráveis do relatório matinal       |
| whatsapp_contacts    | Contatos sincronizados da Evolution API          |
| kv_store             | Chave-valor (tokens Google, flags de envio)      |

## Segurança

- Login por formulário → cookie HttpOnly, Secure, SameSite=strict (7 dias)
- API protegida por `X-Api-Key`; webhook por `X-Webhook-Secret`
- Portas Docker em 127.0.0.1 (não expostas); acesso externo apenas HTTPS (443)
- Rate limiting: 5r/s API, 1r/s login; 3 conexões simultâneas por IP
- Dados pessoais e identidade só em variáveis de ambiente, **sem fallback no código** — `_env_obrig()` derruba o boot se faltar, em vez de rodar com o dado de outra pessoa
- Chave de API **não fica no frontend**: o nginx injeta `X-Api-Key` no proxy (`docker/nginx-apikey.conf`, gitignored) — o navegador nunca a recebe
- Confirmação de ações fora do alcance do LLM (código determinístico)
- Headers: HSTS, X-Frame-Options DENY, CSP, nosniff

## Estrutura

```
jarvis/
├── docker/
│   ├── main.py            # FastAPI + agente (TOOLS, execute_tool, run_agent)
│   ├── vol.py             # Z-score de movimento por hora da sessão
│   ├── niveis.py          # Perfil de volume, pivot points, fundos/topos
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
│   └── manifest.json
├── scripts/
└── README.md
```

## Variáveis de Ambiente (.env)

```env
# Acesso
API_KEY=                    LOGIN_USER=               LOGIN_PASS=

# Banco
POSTGRES_PASSWORD=          POSTGRES_DB=              POSTGRES_USER=

# LLM (cascata: Anthropic → OpenAI → Groq)
ANTHROPIC_API_KEY=          OPENAI_API_KEY=           GROQ_API_KEY=

# Google
GMAIL_CLIENT_ID=            GMAIL_CLIENT_SECRET=      GMAIL_REDIRECT_URI=
GOOGLE_MAPS_KEY=            GOOGLE_SEARCH_CX=         GOOGLE_SHEET_ID=

# WhatsApp (Evolution API)
EVO_URL=                    EVO_KEY=
EVO_INSTANCE=               # instância do bot (grupo)
EVO_PERSONAL_INSTANCE=      EVO_PERSONAL_KEY=         # número pessoal
WHATSAPP_GROUP_ID=          WHATSAPP_WEBHOOK_SECRET=

# APIs externas
OPENWEATHER_API_KEY=        NEWSAPI_KEY=              BRAPI_TOKEN=

# Configurações pessoais
HOME_ADDRESS=               DEFAULT_CITY=             APP_DOMAIN=
VAPID_PUBLIC=               VAPID_PRIVATE=            VAPID_EMAIL=
USER_NAME=                  ASSISTANT_NAME=           # identidade (USER_NAME obrigatória)

# Alertas de mercado — opcional, default entre parênteses
VOL_LIMIAR_ALERTA=          # (2.0)  z mínimo para alertar
VOL_PIORA_REALERTA=         # (1.0)  piora para reavisar no mesmo dia
NIVEIS_JANELA_SWING=        # (3)    barras de cada lado para fundo/topo
NIVEIS_RETRACAO_MIN=        # (1.5)  % mínimo entre swings
NIVEIS_N_FAIXAS=            # (40)   faixas do perfil de volume
NIVEIS_AREA_VALOR=          # (0.70) fração do volume na área de valor
```

## Deploy

```bash
cd ~/app/jarvis/docker
docker compose build jarvis-app --no-cache
docker compose up -d jarvis-app
```

Verificar:
```bash
docker ps --filter name=jarvis-app
curl http://localhost:8100/health
```

## Migração SQL (morning_modules)

Aplicada em 2026-08-01. Para recriar do zero:

```bash
docker cp migration.sql jarvis-db:/tmp/migration.sql
docker exec jarvis-db psql -U assistant -d personal_kb -f /tmp/migration.sql
```

## Stack

Python 3.11 · FastAPI · Claude Haiku/Sonnet (tool use) · OpenAI · Groq · PostgreSQL 15 + pgvector · Redis 7 · Nginx · Let's Encrypt · Oracle Cloud Free Tier (ARM Ampere A1) · Evolution API

## Roadmap — SaaS multi-tenant

Para transformar em produto vendável:

1. **tenant_id em todas as tabelas** + Row Level Security no Postgres
2. **tenant_credentials** — API keys criptografadas por usuário (AES-256)
3. **Onboarding web** — cadastro + conectar Google (OAuth) + escanear QR WhatsApp
4. **LLM por tenant** — Groq gratuito como base; usuário cola própria key OpenAI/Anthropic para mais qualidade
5. **Provisionamento automático** de instância Evolution por usuário
6. **Billing** — Stripe integrado ao onboarding
