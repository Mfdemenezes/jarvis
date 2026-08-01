import logging
import sys

# Logging estruturado
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("jarvis")

from fastapi import FastAPI, HTTPException, Header, Depends, Request, Response, Cookie, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import re
import psycopg2
import httpx
import os
from datetime import datetime, timedelta
import json
from typing import Optional
import redis
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import base64

# Configuração
API_KEY = os.getenv("API_KEY", "change-this-key")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "jarvis-db")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "change_this_password")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "jarvis-llm")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SESSION_SECRET = os.getenv("API_KEY", "secret")
ACTIVE_SESSIONS = set()
OPENWEATHER_KEY = os.getenv("OPENWEATHER_API_KEY")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
GOOGLE_MAPS_KEY = os.getenv("GOOGLE_MAPS_KEY", "")
GOOGLE_SEARCH_KEY = os.getenv("GOOGLE_SEARCH_KEY", GOOGLE_MAPS_KEY)
GOOGLE_SEARCH_CX = os.getenv("GOOGLE_SEARCH_CX", "")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1RjwiT3F-ubct12QHGyFu-YisARrAVQJzKCTM7VA__gU")
EVO_URL = os.getenv("EVO_URL", "")
EVO_KEY = os.getenv("EVO_KEY", "")
EVO_INSTANCE = os.getenv("EVO_INSTANCE", "")
# Instancia pessoal (numero do proprio Marcelo): usada para enviar mensagens a
# contatos em nome dele. As respostas do Jarvis no grupo continuam saindo pela
# instancia do bot (EVO_INSTANCE). Sem configuracao, cai no comportamento antigo.
from urllib.parse import quote as _urlquote
EVO_PERSONAL_INSTANCE = _urlquote(os.getenv("EVO_PERSONAL_INSTANCE", "")) or EVO_INSTANCE
EVO_PERSONAL_KEY = os.getenv("EVO_PERSONAL_KEY", "") or EVO_KEY
MARCELO_WHATSAPP = os.getenv("WHATSAPP_GROUP_ID", "120363426093960169@g.us")
WHATSAPP_WEBHOOK_SECRET = os.getenv("WHATSAPP_WEBHOOK_SECRET", "")
VAPID_PUBLIC = os.getenv("VAPID_PUBLIC", "")
VAPID_PRIVATE = os.getenv("VAPID_PRIVATE", "")
push_subscriptions = []
_home_addr = os.getenv("HOME_ADDRESS", "Rua de Paiva 124, Miguel Pereira, RJ")
LOCAIS = {"casa": _home_addr, "minha casa": _home_addr}
REDIS_HOST = os.getenv("REDIS_HOST", "jarvis-cache")

GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
GMAIL_REDIRECT_URI = os.getenv("GMAIL_REDIRECT_URI", "https://jarvis.mbam.com.br/auth/callback")
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.compose", "https://www.googleapis.com/auth/calendar.events", "https://www.googleapis.com/auth/calendar.readonly", "https://www.googleapis.com/auth/spreadsheets"]
gmail_credentials = None

SYSTEM_PROMPT = """Você é o Jarvis, assistente pessoal de elite do Marcelo Menezes.
Você é proativo, inteligente e informal, agindo como um braço direito.
Suas respostas devem ser curtas, diretas e entregues EXCLUSIVAMENTE via texto no chat.
Não mencione comandos de voz ou capacidade de falar.

Suas capacidades reais incluem:
1. INTERNET: Você tem acesso ao Google Search para pesquisar qualquer fato atual, preços ou informações gerais.
2. FINANÇAS: Você gerencia planilhas Google, registra gastos, dá saldos e categoriza despesas.
3. COMUNICAÇÃO: Você envia mensagens de WhatsApp, lê e redige E-mails (Gmail) e gerencia a Agenda (Google Calendar).
4. UTILIDADES: Você fornece previsão do tempo real, cotação de moedas/cripto e trânsito (Google Maps).

O Marcelo mora em {home_address}. Quando ele falar 'casa', é lá.
Hoje é {today}. Quando tiver dados reais no contexto, use-os na resposta.
Nunca diga que não pode fazer algo sem tentar usar suas ferramentas primeiro.

Responda sempre em texto corrido natural e descontraído — nunca em JSON, código ou
estruturas técnicas, a menos que o usuário peça explicitamente."""

app = FastAPI(title="Jarvis API", version="2.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis (cache)
try:
    redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
    redis_client.ping()
    REDIS_AVAILABLE = True
except:
    REDIS_AVAILABLE = False
    logger.warning("Redis nao disponivel - cache desabilitado")

# Models
class ChatRequest(BaseModel):
    message: str
    user_id: str = "default"
    lat: float = None
    lon: float = None

class ChatResponse(BaseModel):
    response: str
    context_used: int = 0
    cached: bool = False

# Database
def get_db():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        database=os.getenv("POSTGRES_DB", "personal_kb"),
        user=os.getenv("POSTGRES_USER", "assistant"),
        password=POSTGRES_PASSWORD,
        port=5432
    )

# Autenticação
def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

# Cache
# Palavras que indicam perguntas volateis (nao cachear)
VOLATILE_KEYWORDS = [
    "hora", "horas", "agora", "hoje", "tempo", "clima", "temperatura", "chuva",
    "chover", "previsao", "previsão", "dolar", "dólar", "euro", "bitcoin", "btc",
    "cotacao", "cotação", "cambio", "câmbio", "noticia", "notícia", "noticias",
    "notícias", "manchete", "transito", "trânsito", "atual", "agora", "momento",
    "ontem", "amanha", "amanhã", "semana", "mes", "mês", "agenda", "lembrete",
    # Confirmacoes/cancelamentos e acoes nunca podem vir do cache: uma resposta
    # cacheada aqui pularia a execucao da acao pendente (ex.: "pode enviar").
    "sim", "pode", "confirma", "confirmo", "ok", "manda", "envia", "envie",
    "cria", "nao", "não", "cancela", "whatsapp", "zap", "mensagem", "email", "e-mail"
]

def unwrap_llm_json(text: str) -> str:
    """Se o LLM embrulhar a resposta num JSON (ex: {"mensagem": "..."}) ou em
    cerca de código, extrai o texto util. Mantem intacto texto normal."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
        t = t.strip()
    if t.startswith("{") and t.endswith("}"):
        try:
            data = json.loads(t)
            for k in ("mensagem", "message", "texto", "text", "resposta", "response"):
                if isinstance(data.get(k), str):
                    return data[k].strip()
        except Exception:
            pass
    return text

def is_volatile(message: str) -> bool:
    ml = message.lower()
    return any(w in ml for w in VOLATILE_KEYWORDS)

def get_cached_response(message: str) -> Optional[str]:
    if not REDIS_AVAILABLE or is_volatile(message):
        return None
    try:
        return redis_client.get(f"chat:{message}")
    except:
        return None

def cache_response(message: str, response: str, ttl: int = 3600):
    if not REDIS_AVAILABLE or is_volatile(message):
        return
    try:
        redis_client.setex(f"chat:{message}", ttl, response)
    except:
        pass

async def get_embedding(text: str):
    if not OPENAI_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post("https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={"model": "text-embedding-3-small", "input": text, "dimensions": 384})
            data = r.json()
            return data["data"][0]["embedding"]
    except Exception as e:
        logger.warning(f"Erro ao gerar embedding: {e}")
        return None

def _vector_literal(embedding):
    return "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"

# Buscar memórias
async def search_memory(query: str, limit: int = 5):
    conn = get_db()
    cur = conn.cursor()
    results = []
    embedding = await get_embedding(query)
    if embedding:
        # Busca semantica por similaridade de embedding
        cur.execute("""
            SELECT content, metadata, created_at
            FROM memory_embeddings
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (_vector_literal(embedding), limit))
        results = cur.fetchall()
    else:
        # Fallback por palavra-chave se a API de embeddings nao estiver disponivel
        words = [w.strip() for w in query.lower().split() if len(w.strip()) > 3]
        if words:
            like_clauses = " OR ".join(["LOWER(content) LIKE %s" for _ in words[:6]])
            params = [f"%{w}%" for w in words[:6]] + [limit]
            cur.execute(f"""
                SELECT content, metadata, created_at
                FROM memory_embeddings
                WHERE {like_clauses}
                ORDER BY created_at DESC
                LIMIT %s
            """, params)
            results = cur.fetchall()
    # Sempre inclui memorias de identidade basica (nome, endereco) se nao estao nos resultados
    cur.execute("""
        SELECT content, metadata, created_at
        FROM memory_embeddings
        WHERE category IN ('identidade', 'endereco')
        ORDER BY created_at DESC
        LIMIT 3
    """)
    base = cur.fetchall()
    seen = {r[0] for r in results}
    for r in base:
        if r[0] not in seen:
            results.append(r)
    cur.close()
    conn.close()
    return [{"content": r[0], "metadata": r[1], "date": str(r[2])} for r in results[:limit]]

# Chamar LLM
async def search_google(query: str):
    if not GOOGLE_SEARCH_KEY or not GOOGLE_SEARCH_CX:
        return "Google Search não configurado."
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get("https://www.googleapis.com/customsearch/v1",
                params={"key": GOOGLE_SEARCH_KEY, "cx": GOOGLE_SEARCH_CX, "q": query})
            data = r.json()
            items = data.get("items", [])
            results = []
            for item in items[:3]:
                results.append(f"{item['title']}: {item['snippet']}")
            return "\n".join(results) if results else "Nenhum resultado encontrado."
    except Exception as e:
        return f"Erro na busca: {str(e)}"

COMPLEX_QUERY_MARKERS = [
    "por que", "porque", "explica", "explique", "compare", "comparar",
    "diferença", "diferenca", "história", "historia", "notícia", "noticia",
    "análise", "analise", "resumo", "opinião", "opiniao", "o que é", "o que e",
    "como funciona", "vantagens", "desvantagens", "detalha", "detalhe",
]

def is_complex_query(text: str) -> bool:
    if len(text.split()) > 15:
        return True
    lower = text.lower()
    return any(marker in lower for marker in COMPLEX_QUERY_MARKERS)

async def _try_anthropic(prompt: str, system: str, context: str, complex_query: bool, errors: list) -> Optional[str]:
    if not ANTHROPIC_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": "claude-sonnet-5" if complex_query else "claude-haiku-4-5",
                      "max_tokens": 1500 if complex_query else 500,
                      "system": system + "\n\nContexto:\n" + context,
                      "messages": [{"role": "user", "content": prompt}]})
            data = r.json()
            text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
            if text_blocks:
                return "".join(text_blocks)
            errors.append(f"Anthropic: {data.get('error', {}).get('message', str(data))}")
            logger.warning(f"Anthropic sem texto utilizavel: {data}")
    except Exception as e:
        errors.append(f"Anthropic exception: {e}")
        logger.warning(f"Anthropic exception: {e}")
    return None

async def _try_openai(prompt: str, system: str, context: str, complex_query: bool, errors: list) -> Optional[str]:
    if not OPENAI_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={"model": "gpt-4o" if complex_query else "gpt-4o-mini", "messages": [
                    {"role": "system", "content": system + "\n\nContexto:\n" + context},
                    {"role": "user", "content": prompt}],
                    "max_tokens": 1200 if complex_query else 300})
            data = r.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"]
            errors.append(f"OpenAI: {data.get('error', {}).get('message', str(data))}")
            logger.warning(f"OpenAI sem choices utilizavel: {data}")
    except Exception as e:
        errors.append(f"OpenAI exception: {e}")
        logger.warning(f"OpenAI exception: {e}")
    return None

async def _try_groq(prompt: str, system: str, context: str, complex_query: bool, errors: list) -> Optional[str]:
    if not GROQ_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={"model": "llama-3.3-70b-versatile", "messages": [
                    {"role": "system", "content": system + "\n\nContexto:\n" + context},
                    {"role": "user", "content": prompt}],
                    "max_tokens": 1200 if complex_query else 500})
            data = r.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"]
            errors.append(f"Groq: {data.get('error', {}).get('message', str(data))}")
            logger.warning(f"Groq sem choices utilizavel: {data}")
    except Exception as e:
        errors.append(f"Groq exception: {e}")
        logger.warning(f"Groq exception: {e}")
    return None

async def call_ollama(prompt: str, context: str = "", force_quality: bool = False, instructions: str = ""):
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    system = SYSTEM_PROMPT.format(today=today, home_address=os.getenv("HOME_ADDRESS", "Rua de Paiva 124, Miguel Pereira, RJ"))
    if instructions:
        # Instrucoes de acao (JSON de whatsapp/evento/lembrete/planilha) vao no
        # system prompt, nao no bloco de Contexto — instrucoes coladas junto com
        # dados/historico sao tratadas como possivel injecao e ignoradas pelo modelo.
        system += "\n\n" + instructions
    complex_query = is_complex_query(prompt)
    errors = []

    # Perguntas complexas ou que dependem de JSON exato (acoes: whatsapp,
    # evento, lembrete, planilha) priorizam qualidade (Anthropic). Perguntas
    # simples e puramente informativas priorizam custo, tentando o Groq primeiro.
    if complex_query or force_quality:
        providers = [_try_anthropic, _try_openai, _try_groq]
    else:
        providers = [_try_groq, _try_anthropic, _try_openai]

    for provider in providers:
        result = await provider(prompt, system, context, complex_query, errors)
        if result:
            return result

    if errors:
        raise Exception("Todos os provedores LLM falharam: " + " | ".join(errors))
    raise Exception("Nenhum provedor LLM configurado")

# Salvar conversa
def save_conversation(user_id: str, user_message: str, assistant_response: str):
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO conversations (user_message, assistant_response, metadata)
        VALUES (%s, %s, %s)
    """, (user_message, assistant_response, json.dumps({"user_id": user_id, "created_at": datetime.now().isoformat()})))
    
    conn.commit()
    cur.close()
    conn.close()

# Rotas
@app.get("/")
async def root():
    return {
        "service": "Jarvis API",
        "version": "2.0",
        "status": "online",
        "containers": {
            "app": "jarvis-app",
            "db": "jarvis-db",
            "llm": "jarvis-llm",
            "web": "jarvis-web",
            "cache": "jarvis-cache"
        }
    }

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/login")
async def login(req: LoginRequest, response: Response):
    if req.username == os.getenv("LOGIN_USER", "") and req.password == os.getenv("LOGIN_PASS", ""):
        import hashlib, time
        token = hashlib.sha256(f"{req.username}{time.time()}{SESSION_SECRET}".encode()).hexdigest()
        ACTIVE_SESSIONS.add(token)
        response.set_cookie("jarvis_session", token, httponly=True, secure=True, samesite="strict", max_age=86400*7)
        return {"ok": True}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/logout")
async def logout_endpoint(response: Response):
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("jarvis_session")
    return response

@app.get("/auth/verify-session")
async def verify_session(jarvis_session: Optional[str] = Cookie(None)):
    """Usado pelo nginx (auth_request) para validar a sessao de login antes de servir o PWA."""
    if jarvis_session and jarvis_session in ACTIVE_SESSIONS:
        return {"ok": True}
    raise HTTPException(status_code=401, detail="No session")

@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...), x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401)
    audio_data = await file.read()
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Tentar Groq Whisper primeiro (gratuito)
        if GROQ_API_KEY:
            try:
                r = await client.post("https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                    files={"file": ("audio.webm", audio_data, "audio/webm")},
                    data={"model": "whisper-large-v3-turbo", "language": "pt", "response_format": "json"})
                if r.status_code == 200:
                    return r.json()
            except:
                pass
        # Fallback: OpenAI Whisper
        if OPENAI_API_KEY:
            r = await client.post("https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                files={"file": ("audio.webm", audio_data, "audio/webm")},
                data={"model": "whisper-1", "language": "pt"})
            return r.json()
        raise HTTPException(status_code=503, detail="Nenhum provedor de transcricao disponivel")

@app.post("/api/push/subscribe")
async def push_subscribe(request: Request):
    sub = await request.json()
    if sub not in push_subscriptions:
        push_subscriptions.append(sub)
    logger.info(f"PUSH_SUB_REGISTERED total={len(push_subscriptions)}")
    return {"ok": True}

@app.get("/api/vapid-public-key")
async def get_vapid_key():
    return {"publicKey": VAPID_PUBLIC}

@app.post("/api/push/test")
async def push_test(authenticated: bool = Depends(verify_api_key)):
    if not push_subscriptions:
        return {"error": "Nenhuma subscription registrada", "count": 0}
    await send_push("Jarvis", "Teste de notificacao - estou funcionando!")
    return {"ok": True, "sent_to": len(push_subscriptions)}

async def send_push(title: str, body: str):
    from pywebpush import webpush
    for sub in push_subscriptions[:]:
        try:
            import json
            webpush(sub, json.dumps({"title": title, "body": body}),
                    vapid_private_key=VAPID_PRIVATE,
                    vapid_claims={"sub": f"mailto:{os.getenv('VAPID_EMAIL', 'mfdemenezes@gmail.com')}"})
        except:
            push_subscriptions.remove(sub)

async def send_whatsapp(text: str):
    async with httpx.AsyncClient(timeout=10.0) as c:
        await c.post(f"{EVO_URL}/message/sendText/{EVO_INSTANCE}",
            headers={"apikey": EVO_KEY, "Content-Type": "application/json"},
            json={"number": MARCELO_WHATSAPP, "text": text})

# Cron: verificar emails importantes a cada 5 min
import asyncio
last_checked_ids = set()

async def check_important_emails():
    global last_checked_ids
    while True:
        await asyncio.sleep(300)
        try:
            svc = get_gmail_service()
            if not svc: continue
            results = svc.users().messages().list(userId="me", maxResults=5, labelIds=["INBOX"], q="is:unread").execute()
            for msg_item in results.get("messages", []):
                if msg_item["id"] in last_checked_ids: continue
                last_checked_ids.add(msg_item["id"])
                detail = svc.users().messages().get(userId="me", id=msg_item["id"], format="metadata",
                         metadataHeaders=["From", "Subject"]).execute()
                headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
                subj = headers.get("Subject", "")
                frm = headers.get("From", "")
                # Classificar importância
                important_words = ["boleto", "pagamento", "fatura", "morgan stanley", "beto", "pai", "urgente", "banco", "pix", "transferencia", "vencimento", "medico", "saude", "tribunal", "intimacao", "seguranca", "security"]
                is_important = any(w in subj.lower() or w in frm.lower() for w in important_words)
                if is_important:
                    await send_whatsapp(f"[Jarvis] Email importante!\nDe: {frm}\n{subj}")
            if len(last_checked_ids) > 100:
                last_checked_ids = set(list(last_checked_ids)[-50:])
        except:
            pass

# Aliases financeiros
DESCRICAO_ALIASES_DEFAULT = {"PADA": "Padaria", "ZONA": "Mercado Zona Sul", "SUP": "Supermercado", "FARM": "Farmacia", "POST": "Posto de Gasolina", "REST": "Restaurante", "UBER": "Uber", "IFOOD": "iFood", "AUTO": "Auto Posto", "DROG": "Drogaria", "MERC": "Mercado"}

def load_aliases():
    aliases = dict(DESCRICAO_ALIASES_DEFAULT)
    if REDIS_AVAILABLE:
        saved = redis_client.get("fin_aliases")
        if saved: aliases.update(json.loads(saved))
    return aliases

def save_alias(abrev, nome):
    aliases = load_aliases()
    aliases[abrev.upper()] = nome
    if REDIS_AVAILABLE: redis_client.set("fin_aliases", json.dumps(aliases))
    return aliases

import unicodedata

def normalize_name(name: str) -> str:
    """Remove acentos, lowercase, strip — para busca fuzzy."""
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

async def sync_whatsapp_contacts():
    """Cron: sincroniza contatos do WhatsApp via Evolution API 1x por dia."""
    while True:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    f"{EVO_URL}/chat/findContacts/{EVO_INSTANCE}",
                    headers={"apikey": EVO_KEY, "Content-Type": "application/json"},
                    json={"where": {"isSaved": True}}
                )
                contacts = r.json()
                if not isinstance(contacts, list):
                    raise Exception(f"Resposta inesperada: {contacts}")
                conn = get_db()
                cur = conn.cursor()
                inserted = 0
                updated = 0
                for c in contacts:
                    name = (c.get("pushName") or "").strip()
                    jid  = (c.get("remoteJid") or "").strip()
                    if not name or not jid or "@g.us" in jid:
                        continue  # ignorar grupos
                    number = jid.replace("@s.whatsapp.net", "")
                    name_norm = normalize_name(name)
                    cur.execute("""
                        INSERT INTO whatsapp_contacts (name, number, name_normalized, synced_at)
                        VALUES (%s, %s, %s, NOW())
                        ON CONFLICT (number) DO UPDATE
                            SET name = EXCLUDED.name,
                                name_normalized = EXCLUDED.name_normalized,
                                synced_at = NOW()
                    """, (name, number, name_norm))
                    if cur.rowcount == 1:
                        inserted += 1
                    else:
                        updated += 1
                conn.commit()
                cur.close()
                conn.close()
                logger.info(f"CONTACTS_SYNC inserted={inserted} updated={updated} total={len(contacts)}")
        except Exception as e:
            logger.error(f"CONTACTS_SYNC_ERROR error={e}")
        await asyncio.sleep(86400)  # 1x por dia

def find_contact(query: str) -> Optional[dict]:
    """Busca fuzzy no banco: retorna {name, number} do contato mais próximo."""
    query_norm = normalize_name(query)
    if not query_norm:
        return None
    try:
        conn = get_db()
        cur = conn.cursor()
        # 1. Correspondência exata
        cur.execute(
            "SELECT name, number FROM whatsapp_contacts WHERE name_normalized = %s LIMIT 1",
            (query_norm,)
        )
        row = cur.fetchone()
        if row:
            cur.close(); conn.close()
            return {"name": row[0], "number": row[1]}
        # 2. Começa com o termo
        cur.execute(
            "SELECT name, number FROM whatsapp_contacts WHERE name_normalized LIKE %s LIMIT 1",
            (query_norm + "%",)
        )
        row = cur.fetchone()
        if row:
            cur.close(); conn.close()
            return {"name": row[0], "number": row[1]}
        # 3. Contém o termo em qualquer parte
        cur.execute(
            "SELECT name, number FROM whatsapp_contacts WHERE name_normalized LIKE %s LIMIT 1",
            ("%" + query_norm + "%",)
        )
        row = cur.fetchone()
        cur.close(); conn.close()
        if row:
            return {"name": row[0], "number": row[1]}
    except Exception as e:
        logger.warning(f"FIND_CONTACT_ERROR error={e}")
    return None

async def check_reminders():
    """Cron a cada 60s: dispara lembretes que estao na hora."""
    while True:
        await asyncio.sleep(60)
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                SELECT id, text, remind_at FROM reminders
                WHERE done = false AND remind_at <= NOW()
                ORDER BY remind_at ASC
            """)
            due = cur.fetchall()
            for rid, text, remind_at in due:
                # Marcar como feito imediatamente para evitar reenvio
                cur.execute("UPDATE reminders SET done = true WHERE id = %s", (rid,))
                conn.commit()
                # Enviar push notification
                await send_push("Lembrete Jarvis", text)
                # Enviar tambem por WhatsApp
                try:
                    await send_whatsapp(f"[Lembrete] {text}")
                except:
                    pass
                logger.info(f"REMINDER_FIRED text={text!r}")
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"REMINDER_CRON_ERROR error={e}")

EVENT_ALERT_LEAD_MINUTES = 15
_alerted_events = set()

async def fetch_calendar_events(day_start_local: datetime, day_end_local: datetime) -> str:
    """Busca eventos do Google Calendar entre os limites informados (horario local de Brasilia)."""
    svc = get_gmail_service()
    if not svc:
        return ""
    cal = build("calendar", "v3", credentials=gmail_credentials)
    start_utc = (day_start_local + timedelta(hours=3)).isoformat() + "Z"
    end_utc = (day_end_local + timedelta(hours=3)).isoformat() + "Z"
    calendars = cal.calendarList().list().execute()
    cal_events = []
    for c in calendars.get("items", []):
        try:
            events = cal.events().list(calendarId=c["id"], timeMin=start_utc, timeMax=end_utc,
                                        singleEvents=True, orderBy="startTime").execute()
            for e in events.get("items", []):
                start = e["start"].get("dateTime", e["start"].get("date", ""))
                if "T" in start:
                    time_part = f"[{start.split('T')[1][:5]}]"
                else:
                    time_part = "[Dia todo]"
                cal_events.append(f"{time_part} {e.get('summary', '')} ({c.get('summary', '')})")
        except:
            pass
    if cal_events:
        cal_events.sort()
        return "\n".join(cal_events)
    return ""

async def check_upcoming_events():
    """Cron a cada 5 min: avisa por WhatsApp quando um evento do Calendar esta proximo (15 min antes)."""
    global _alerted_events
    while True:
        await asyncio.sleep(300)
        try:
            svc = get_gmail_service()
            if not svc:
                continue
            cal = build("calendar", "v3", credentials=gmail_credentials)
            now_utc = datetime.utcnow()
            time_min = now_utc.isoformat() + "Z"
            time_max = (now_utc + timedelta(minutes=EVENT_ALERT_LEAD_MINUTES)).isoformat() + "Z"
            calendars = cal.calendarList().list().execute()
            for c in calendars.get("items", []):
                try:
                    evts = cal.events().list(calendarId=c["id"], timeMin=time_min, timeMax=time_max,
                                              singleEvents=True, orderBy="startTime").execute()
                    for e in evts.get("items", []):
                        start = e["start"].get("dateTime")
                        if not start:
                            continue  # ignora eventos de dia todo
                        event_id = e.get("id", "")
                        alert_key = f"event_alert_sent:{event_id}"
                        already_sent = redis_client.exists(alert_key) if REDIS_AVAILABLE else event_id in _alerted_events
                        if already_sent:
                            continue
                        time_str = start.split("T")[1][:5]
                        summary = e.get("summary") or "Sem titulo"
                        await send_whatsapp(f"[Jarvis] Em {EVENT_ALERT_LEAD_MINUTES} min: {summary} as {time_str} ({c.get('summary','')})")
                        if REDIS_AVAILABLE:
                            redis_client.setex(alert_key, 86400, "1")
                        else:
                            _alerted_events.add(event_id)
                            if len(_alerted_events) > 200:
                                _alerted_events = set(list(_alerted_events)[-100:])
                except Exception as _ee:
                    logger.warning(f"UPCOMING_EVENT_CAL_ERROR cal={c.get('id')} error={_ee}")
        except Exception as e:
            logger.error(f"UPCOMING_EVENTS_ERROR error={e}")

def check_morning_report_sent(date_str: str) -> bool:
    """Verifica se o relatorio diario ja foi enviado para a data informada."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT value FROM kv_store WHERE key = %s", (f"morning_report_sent:{date_str}",))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row is not None
    except:
        return False

def mark_morning_report_sent(date_str: str):
    """Marca o relatorio diario como enviado no banco de dados."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO kv_store (key, value, updated_at)
            VALUES (%s, 'true', NOW())
            ON CONFLICT (key) DO UPDATE SET value = 'true', updated_at = NOW()
        """, (f"morning_report_sent:{date_str}",))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Erro ao marcar envio de relatorio matinal: {e}")

def check_evening_preview_sent(date_str: str) -> bool:
    """Verifica se o aviso dos compromissos de amanha ja foi enviado para a data informada."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT value FROM kv_store WHERE key = %s", (f"evening_preview_sent:{date_str}",))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row is not None
    except:
        return False

def mark_evening_preview_sent(date_str: str):
    """Marca o aviso dos compromissos de amanha como enviado no banco de dados."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO kv_store (key, value, updated_at)
            VALUES (%s, 'true', NOW())
            ON CONFLICT (key) DO UPDATE SET value = 'true', updated_at = NOW()
        """, (f"evening_preview_sent:{date_str}",))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Erro ao marcar envio do aviso de compromissos de amanha: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# SISTEMA DE MÓDULOS DINÂMICOS DO RELATÓRIO MATINAL
# Módulos são configurados na tabela morning_modules do Postgres.
# Adicionar/remover via comandos no WhatsApp (handle_module_command).
# ══════════════════════════════════════════════════════════════════════════════

def get_morning_modules() -> list:
    """Retorna a lista de módulos ativos ordenados por ordem."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, tipo, parametro, label, fonte, observacao
            FROM morning_modules
            WHERE ativo = TRUE
            ORDER BY ordem ASC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{"id": r[0], "tipo": r[1], "parametro": r[2],
                 "label": r[3], "fonte": r[4], "obs": r[5]} for r in rows]
    except Exception as e:
        logger.error(f"get_morning_modules error: {e}")
        return []

def get_all_morning_modules() -> list:
    """Retorna TODOS os módulos (ativos e inativos) — usado no /modulo list."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, tipo, parametro, label, ativo, ordem, fonte
            FROM morning_modules
            ORDER BY ordem ASC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{"id": r[0], "tipo": r[1], "parametro": r[2], "label": r[3],
                 "ativo": r[4], "ordem": r[5], "fonte": r[6]} for r in rows]
    except Exception as e:
        logger.error(f"get_all_morning_modules error: {e}")
        return []

async def fetch_module_data(modulo: dict) -> str:
    """Busca os dados de um módulo e retorna string formatada ou vazia em caso de erro."""
    tipo = modulo["tipo"]
    param = modulo.get("parametro") or ""
    label = modulo.get("label") or tipo

    try:
        # ── Moedas (dólar / euro) ──────────────────────────────────────────
        if tipo == "moedas":
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get("https://open.er-api.com/v6/latest/USD")
                if r.status_code == 200:
                    d = r.json()
                    brl = d["rates"]["BRL"]
                    eur_usd = d["rates"]["EUR"]
                    return f"Dolar: R${brl:.2f} | Euro: R${brl/eur_usd:.2f}"
            return ""

        # ── Cripto ────────────────────────────────────────────────────────
        if tipo == "cripto":
            coin = param.lower() or "bitcoin"
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get(f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=brl")
                if r.status_code == 200:
                    d = r.json()
                    if coin in d:
                        preco = d[coin]["brl"]
                        return f"{label}: R${preco:,.0f}"
            return ""

        # ── Clima ─────────────────────────────────────────────────────────
        if tipo == "clima":
            cidade = param or os.getenv("DEFAULT_CITY", "Miguel Pereira")
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get(
                    f"https://api.openweathermap.org/data/2.5/weather"
                    f"?q={cidade}&appid={OPENWEATHER_KEY}&units=metric&lang=pt_br"
                )
                if r.status_code == 200:
                    d = r.json()
                    desc = d["weather"][0]["description"]
                    temp = d["main"]["temp"]
                    feels = d["main"]["feels_like"]
                    return f"Clima em {cidade}: {desc}, {temp:.0f}C (sensacao {feels:.0f}C)"
            return ""

        # ── Notícias ──────────────────────────────────────────────────────
        if tipo == "noticias":
            tema = param or "brasil"
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get(
                    f"https://newsapi.org/v2/everything"
                    f"?q={tema}&language=pt&sortBy=publishedAt&pageSize=3&apiKey={NEWSAPI_KEY}"
                )
                if r.status_code == 200:
                    d = r.json()
                    heads = [f"- {a['title']} ({a['source']['name']})"
                             for a in d.get("articles", [])[:3]]
                    return "\n".join(heads)
            return ""

        # ── Agenda Google Calendar ─────────────────────────────────────────
        if tipo == "agenda":
            now_local = datetime.now()
            today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end   = now_local.replace(hour=23, minute=59, second=59, microsecond=0)
            return await fetch_calendar_events(today_start, today_end)

        # ── Lembretes do banco ────────────────────────────────────────────
        if tipo == "lembretes":
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT text, remind_at FROM reminders WHERE done = false ORDER BY remind_at ASC")
            rems = cur.fetchall()
            cur.close(); conn.close()
            if not rems:
                return ""
            return "\n".join([
                f"- {r[0]} ({r[1].strftime('%H:%M') if r[1].date() == datetime.now().date() else r[1].strftime('%d/%m %H:%M')})"
                for r in rems
            ])

        # ── ETF / Ação americana via Yahoo Finance ─────────────────────────
        if tipo in ("etf", "acao_us"):
            ticker = param.upper()
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get(
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
                    f"?interval=1d&range=5d",
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                if r.status_code == 200:
                    d = r.json()
                    meta = d.get("chart", {}).get("result", [{}])[0].get("meta", {})
                    price = meta.get("regularMarketPrice", 0)
                    prev  = meta.get("chartPreviousClose", price)
                    chg   = ((price - prev) / prev * 100) if prev else 0
                    currency = meta.get("currency", "USD")
                    name = meta.get("longName") or meta.get("shortName") or ticker
                    return f"{ticker}: {currency} {price:.2f} ({chg:+.1f}%) | {name}"
            return f"{ticker}: cotacao indisponivel"

        # ── Ação BR via BrAPI ──────────────────────────────────────────────
        if tipo == "acao_br":
            ticker = param.upper()
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get(f"https://brapi.dev/api/quote/{ticker}?token={BRAPI_TOKEN}")
                if r.status_code == 200:
                    results = r.json().get("results", [])
                    if results:
                        s = results[0]
                        price = s.get("regularMarketPrice", 0)
                        chg   = s.get("regularMarketChangePercent", 0)
                        name  = s.get("longName") or s.get("shortName") or ticker
                        return f"{ticker}: R${price:.2f} ({chg:+.1f}%) | {name}"
            return f"{ticker}: cotacao indisponivel"

        # ── Alerta personalizado (texto livre do banco) ────────────────────
        if tipo == "alerta":
            return f"ALERTA: {label} — {param}" if param else f"ALERTA: {label}"

    except Exception as e:
        logger.warning(f"fetch_module_data tipo={tipo} param={param} error={e}")

    return ""


async def handle_module_command(text: str) -> Optional[str]:
    """
    Detecta e executa comandos de módulos enviados pelo WhatsApp.
    Retorna a resposta para enviar no grupo, ou None se não for um comando.

    Comandos reconhecidos:
      /modulo list | /modulo listar
      /modulo add <tipo> [parametro]  |  /modulo adicionar ...
      /modulo on <id_ou_tipo>         |  /modulo ativar ...
      /modulo off <id_ou_tipo>        |  /modulo pausar ...
      /modulo remove <id>             |  /modulo remover ...
    """
    t = text.strip()
    lower = t.lower()

    # Verifica se é um comando de módulo
    if not re.match(r"^/modulo\b", lower):
        return None

    parts = t.split(maxsplit=2)   # ['/modulo', 'ação', 'args...']
    action = parts[1].lower() if len(parts) > 1 else "list"
    args   = parts[2] if len(parts) > 2 else ""

    conn = get_db()
    cur  = conn.cursor()

    try:
        # ── LIST ──────────────────────────────────────────────────────────
        if action in ("list", "listar", "ls"):
            modules = get_all_morning_modules()
            if not modules:
                return "Nenhum modulo cadastrado ainda."
            lines = ["Modulos do relatorio matinal:"]
            for m in modules:
                status = "ON" if m["ativo"] else "OFF"
                param_str = f" ({m['parametro']})" if m["parametro"] else ""
                lines.append(f"[{m['id']}] {status} | {m['label']}{param_str} | tipo: {m['tipo']}")
            lines.append("\nComandos: /modulo add <tipo> <param> | /modulo on/off <id> | /modulo remove <id>")
            return "\n".join(lines)

        # ── ADD ───────────────────────────────────────────────────────────
        if action in ("add", "adicionar", "novo"):
            add_parts = args.split(maxsplit=1)
            tipo_novo = add_parts[0].lower() if add_parts else ""
            param_novo = add_parts[1] if len(add_parts) > 1 else None

            if not tipo_novo:
                return "Uso: /modulo add <tipo> [parametro]\nTipos: moedas, cripto, clima, noticias, agenda, lembretes, etf, acao_br, acao_us, alerta"

            # Verificar se já existe igual
            cur.execute(
                "SELECT id FROM morning_modules WHERE tipo = %s AND (parametro = %s OR (parametro IS NULL AND %s IS NULL))",
                (tipo_novo, param_novo, param_novo)
            )
            if cur.fetchone():
                # Reativar se estava desativado
                cur.execute(
                    "UPDATE morning_modules SET ativo = TRUE, atualizado_em = NOW() "
                    "WHERE tipo = %s AND (parametro = %s OR (parametro IS NULL AND %s IS NULL))",
                    (tipo_novo, param_novo, param_novo)
                )
                conn.commit()
                label_str = f"{tipo_novo.upper()} {param_novo or ''}".strip()
                return f"Modulo {label_str} ja existia — reativado!"

            # Determinar fonte e label padrão
            fonte_map = {"moedas": "openexchange", "cripto": "coingecko", "clima": "openweather",
                         "noticias": "newsapi", "agenda": "google_calendar", "lembretes": "interno",
                         "etf": "yahoo", "acao_us": "yahoo", "acao_br": "brapi", "alerta": "interno"}
            fonte = fonte_map.get(tipo_novo, "externo")
            label_novo = f"{param_novo.upper() if param_novo else tipo_novo.capitalize()}"

            cur.execute("""
                INSERT INTO morning_modules (tipo, parametro, label, ativo, ordem, fonte)
                VALUES (%s, %s, %s, TRUE, (SELECT COALESCE(MAX(ordem), 50) + 10 FROM morning_modules), %s)
                RETURNING id
            """, (tipo_novo, param_novo, label_novo, fonte))
            new_id = cur.fetchone()[0]
            conn.commit()
            return f"Modulo [{new_id}] {label_novo} adicionado! Aparecera no proximo relatorio matinal."

        # ── ON ────────────────────────────────────────────────────────────
        if action in ("on", "ativar", "ativar"):
            target = args.strip()
            if target.isdigit():
                cur.execute("UPDATE morning_modules SET ativo = TRUE, atualizado_em = NOW() WHERE id = %s RETURNING label", (int(target),))
            else:
                cur.execute("UPDATE morning_modules SET ativo = TRUE, atualizado_em = NOW() WHERE tipo = %s OR parametro ILIKE %s RETURNING label", (target.lower(), target))
            rows = cur.fetchall()
            conn.commit()
            if rows:
                labels = ", ".join(r[0] for r in rows)
                return f"Ativado: {labels}"
            return f"Nao encontrei modulo com id/tipo '{target}'."

        # ── OFF ───────────────────────────────────────────────────────────
        if action in ("off", "pausar", "desativar"):
            target = args.strip()
            if target.isdigit():
                cur.execute("UPDATE morning_modules SET ativo = FALSE, atualizado_em = NOW() WHERE id = %s RETURNING label", (int(target),))
            else:
                cur.execute("UPDATE morning_modules SET ativo = FALSE, atualizado_em = NOW() WHERE tipo = %s OR parametro ILIKE %s RETURNING label", (target.lower(), target))
            rows = cur.fetchall()
            conn.commit()
            if rows:
                labels = ", ".join(r[0] for r in rows)
                return f"Pausado: {labels} (use /modulo on para reativar)"
            return f"Nao encontrei modulo com id/tipo '{target}'."

        # ── REMOVE ────────────────────────────────────────────────────────
        if action in ("remove", "remover", "del", "deletar"):
            target = args.strip()
            if target.isdigit():
                cur.execute("DELETE FROM morning_modules WHERE id = %s RETURNING label", (int(target),))
            else:
                cur.execute("DELETE FROM morning_modules WHERE tipo = %s OR parametro ILIKE %s RETURNING label", (target.lower(), target))
            rows = cur.fetchall()
            conn.commit()
            if rows:
                labels = ", ".join(r[0] for r in rows)
                return f"Removido permanentemente: {labels}"
            return f"Nao encontrei modulo com id/tipo '{target}'."

        return (
            "Comandos disponíveis:\n"
            "/modulo list — listar todos\n"
            "/modulo add <tipo> <param> — adicionar (ex: /modulo add etf JEPQ)\n"
            "/modulo on <id> — ativar\n"
            "/modulo off <id> — pausar\n"
            "/modulo remove <id> — remover permanentemente"
        )

    except Exception as e:
        logger.error(f"handle_module_command error: {e}")
        return f"Erro ao executar comando: {e}"
    finally:
        cur.close()
        conn.close()

async def generate_morning_report() -> Optional[str]:
    """Gera o resumo matinal buscando dados de todos os módulos ativos no banco."""
    logger.info("Gerando boletim matinal dinamico via morning_modules...")

    modules = get_morning_modules()
    if not modules:
        logger.warning("Nenhum modulo ativo em morning_modules — usando defaults internos")
        modules = [
            {"tipo": "moedas",    "parametro": None,             "label": "Dolar & Euro",      "fonte": "openexchange"},
            {"tipo": "noticias",  "parametro": "brasil",         "label": "Noticias BR",       "fonte": "newsapi"},
            {"tipo": "agenda",    "parametro": None,             "label": "Agenda",            "fonte": "google_calendar"},
            {"tipo": "lembretes", "parametro": None,             "label": "Lembretes",         "fonte": "interno"},
        ]

    # Buscar dados de todos os módulos em paralelo
    import asyncio as _asyncio
    tasks = [fetch_module_data(m) for m in modules]
    results = await _asyncio.gather(*tasks, return_exceptions=True)

    # Montar blocos de dados para o prompt
    blocos = []
    for m, result in zip(modules, results):
        if isinstance(result, Exception):
            logger.warning(f"Modulo {m['tipo']} ({m.get('parametro','-')}) erro: {result}")
            continue
        if result and result.strip():
            blocos.append(f"- {m['label']}: {result}")

    dados_str = "\n".join(blocos) if blocos else "Nenhum dado disponivel no momento."

    prompt = f"""Elabore o resumo matinal para o Marcelo Menezes.
Seja conciso, informal e direto. Use emojis elegantes. Organize as informacoes de forma fluida.

Dados reais coletados para hoje:
{dados_str}

Escreva em portugues do Brasil e formate como uma mensagem para WhatsApp, pronta para envio."""

    try:
        report = await call_ollama(prompt, instructions="Gere um resumo executivo matinal. Responda em texto corrido, nunca em JSON.")
        report = unwrap_llm_json(report)
        report = "".join(c for c in report if ord(c) <= 0x024F or ord(c) == 0x00B0).strip()
        return report
    except Exception as e:
        logger.error(f"Erro ao chamar LLM para gerar relatorio matinal: {e}")
        return None

async def check_and_send_morning_report_loop():
    """Tarefa diaria rodando a cada 60s: dispara o relatorio matinal as 06:00."""
    while True:
        await asyncio.sleep(60)
        try:
            now = datetime.now()
            # Dispara exatamente as 06:00 da manha
            if now.hour == 6 and now.minute == 0:
                date_str = now.strftime("%Y-%m-%d")
                if not check_morning_report_sent(date_str):
                    report_text = await generate_morning_report()
                    if report_text:
                        await send_whatsapp(report_text)
                        mark_morning_report_sent(date_str)
                        logger.info(f"Relatorio matinal proativo enviado por WhatsApp para {date_str}!")
        except Exception as e:
            logger.error(f"Erro no loop do relatorio matinal diario: {e}")

async def generate_evening_preview() -> Optional[str]:
    """Coleta os compromissos de amanha e monta o aviso com a LLM, para envio as 18h."""
    tomorrow = datetime.now() + timedelta(days=1)
    day_start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = tomorrow.replace(hour=23, minute=59, second=59, microsecond=0)

    cal_events_str = ""
    try:
        cal_events_str = await fetch_calendar_events(day_start, day_end)
    except Exception as e:
        logger.warning(f"Erro busca calendar (aviso de amanha): {e}")

    if not cal_events_str:
        return None

    prompt = f"""Elabore um aviso curto para o Marcelo sobre os compromissos de amanha ({tomorrow.strftime('%d/%m')}).
Seja conciso e direto, formato WhatsApp, com emojis leves.

Compromissos de amanha (Google Calendar):
{cal_events_str}

Escreva em portugues do Brasil."""

    try:
        preview = await call_ollama(prompt, instructions="Gere um aviso curto dos compromissos de amanha. Responda em texto corrido, nunca em JSON.")
        preview = unwrap_llm_json(preview)
        preview = "".join(c for c in preview if ord(c) <= 0x024F or ord(c) == 0x00B0).strip()
        return preview
    except Exception as e:
        logger.error(f"Erro ao chamar LLM para gerar aviso de compromissos de amanha: {e}")
        return None

async def check_and_send_evening_preview_loop():
    """Tarefa diaria rodando a cada 60s: dispara o aviso dos compromissos de amanha as 18:00."""
    while True:
        await asyncio.sleep(60)
        try:
            now = datetime.now()
            # Dispara exatamente as 18:00
            if now.hour == 18 and now.minute == 0:
                date_str = now.strftime("%Y-%m-%d")
                if not check_evening_preview_sent(date_str):
                    preview_text = await generate_evening_preview()
                    if preview_text:
                        await send_whatsapp(preview_text)
                        mark_evening_preview_sent(date_str)
                        logger.info(f"Aviso de compromissos de amanha enviado por WhatsApp para {date_str}!")
                    else:
                        mark_evening_preview_sent(date_str)
                        logger.info(f"Sem compromissos de amanha ({date_str}) - aviso nao enviado.")
        except Exception as e:
            logger.error(f"Erro no loop do aviso de compromissos de amanha: {e}")

@app.on_event("startup")
async def start_email_cron():
    asyncio.create_task(check_important_emails())
    asyncio.create_task(check_reminders())
    asyncio.create_task(check_upcoming_events())
    asyncio.create_task(sync_whatsapp_contacts())
    asyncio.create_task(check_and_send_morning_report_loop())
    asyncio.create_task(check_and_send_evening_preview_loop())

@app.get("/health")
async def health():
    health_status = {
        "status": "healthy",
        "database": "unknown",
        "llm": "unknown",
        "cache": "available" if REDIS_AVAILABLE else "unavailable"
    }
    
    # Check database
    try:
        conn = get_db()
        conn.close()
        health_status["database"] = "connected"
    except:
        health_status["database"] = "disconnected"
        health_status["status"] = "degraded"
    
    # Check LLM (Groq)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get("https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"})
            if r.status_code == 200:
                health_status["llm"] = "ready"
            else:
                health_status["llm"] = "not ready"
                health_status["status"] = "degraded"
    except:
        health_status["llm"] = "not ready"
        health_status["status"] = "degraded"
    
    return health_status

# ══════════════════════════════════════════════════════════════════════════
# AGENTE COM FERRAMENTAS (tool use nativo da Anthropic)
# O modelo decide quando buscar dados ou executar ações; o código executa.
# Ações sensíveis (whatsapp/evento) só registram rascunho — a confirmação
# sim/não continua determinística, no início do /chat.
# ══════════════════════════════════════════════════════════════════════════

# Contatos resolvidos dinamicamente via find_contact() / Evolution API

TOOLS = [
    {"name": "buscar_google", "description": "Busca no Google fatos atuais, preços, pessoas, lugares e informações gerais.",
     "input_schema": {"type": "object", "properties": {"consulta": {"type": "string"}}, "required": ["consulta"]}},
    {"name": "clima", "description": "Previsão do tempo/temperatura atual de uma cidade brasileira.",
     "input_schema": {"type": "object", "properties": {"cidade": {"type": "string", "description": "Padrão: Miguel Pereira"}}, "required": []}},
    {"name": "cotacoes", "description": "Cotação atual de dólar e euro em reais; opcionalmente bitcoin.",
     "input_schema": {"type": "object", "properties": {"incluir_bitcoin": {"type": "boolean"}}, "required": []}},
    {"name": "noticias", "description": "Manchetes de notícias recentes do Brasil (ou de um tema).",
     "input_schema": {"type": "object", "properties": {"tema": {"type": "string", "description": "Padrão: brasil"}}, "required": []}},
    {"name": "transito", "description": "Rota de carro com trânsito atual: distância e tempo entre dois lugares.",
     "input_schema": {"type": "object", "properties": {"origem": {"type": "string", "description": "Padrão: casa do Marcelo"}, "destino": {"type": "string"}}, "required": ["destino"]}},
    {"name": "ler_agenda", "description": "Lista os eventos do Google Calendar dos próximos dias (todas as agendas).",
     "input_schema": {"type": "object", "properties": {"dias": {"type": "integer", "description": "Padrão: 7"}}, "required": []}},
    {"name": "criar_evento", "description": "Registra um rascunho de evento no Google Calendar. O aplicativo pede confirmação ao usuário antes de criar de verdade.",
     "input_schema": {"type": "object", "properties": {"titulo": {"type": "string"}, "inicio": {"type": "string", "description": "YYYY-MM-DDTHH:MM:00"}, "fim": {"type": "string"}, "local": {"type": "string"}, "descricao": {"type": "string"}}, "required": ["titulo", "inicio"]}},
    {"name": "ler_emails", "description": "Lê os e-mails mais recentes da caixa de entrada do Gmail.",
     "input_schema": {"type": "object", "properties": {"limite": {"type": "integer", "description": "Padrão: 5"}}, "required": []}},
    {"name": "ler_planilha", "description": "Lê a planilha de finanças do Google Sheets (gastos, receitas, pagamentos), filtrando pelo mês.",
     "input_schema": {"type": "object", "properties": {"mes": {"type": "string", "description": "MM/YYYY; padrão: mês atual"}}, "required": []}},
    {"name": "escrever_planilha", "description": "Adiciona, altera ou apaga uma linha na planilha de finanças.",
     "input_schema": {"type": "object", "properties": {"acao": {"type": "string", "enum": ["append", "update", "delete"]}, "aba": {"type": "string"}, "valores": {"type": "array", "items": {"type": "string"}}, "celula": {"type": "string", "description": "Ex: A5 (update) ou A5:Z5 (delete)"}}, "required": ["acao", "aba"]}},
    {"name": "criar_lembrete", "description": "Cria um lembrete que será enviado ao usuário no horário marcado.",
     "input_schema": {"type": "object", "properties": {"texto": {"type": "string"}, "quando": {"type": "string", "description": "YYYY-MM-DD HH:MM"}}, "required": ["texto", "quando"]}},
    {"name": "listar_lembretes", "description": "Lista os lembretes pendentes do usuário.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "enviar_whatsapp", "description": "Registra um rascunho de mensagem de WhatsApp para um contato (por nome) ou número de telefone. O aplicativo mostra o rascunho e pede confirmação ao usuário antes de enviar de verdade, pelo número pessoal do Marcelo.",
     "input_schema": {"type": "object", "properties": {"destinatario": {"type": "string", "description": "Nome do contato como o usuário falou, ou número (+55...)"}, "mensagem": {"type": "string"}}, "required": ["destinatario", "mensagem"]}},
    {"name": "salvar_memoria", "description": "Guarda permanentemente um fato pessoal que o usuário pediu para lembrar.",
     "input_schema": {"type": "object", "properties": {"conteudo": {"type": "string"}, "categoria": {"type": "string", "description": "geral|saude|profissao|familia|financeiro|identidade|endereco"}}, "required": ["conteudo"]}},
    {"name": "gerenciar_modulo", "description": (
        "Gerencia os módulos do relatório/resumo matinal enviado por WhatsApp todo dia às 06h. "
        "SEMPRE use esta ferramenta (não gere o relatório) quando o usuário pedir para: "
        "ADICIONAR algo ao resumo/relatório de manhã (ex: 'adiciona JEPQ de manhã', 'quero ver o clima do Rio'); "
        "REMOVER ou TIRAR algo do resumo (ex: 'tira o bitcoin', 'remove as notícias', 'não quero mais ver X'); "
        "PAUSAR ou DESATIVAR temporariamente (ex: 'pausa as cotações', 'desativa o clima por enquanto'); "
        "REATIVAR algo que estava pausado; "
        "LISTAR o que está configurado (ex: 'o que sai de manhã?', 'quais módulos ativos?', 'o que está no resumo'). "
        "Tipos disponíveis: moedas, cripto, clima, noticias, agenda, lembretes, etf, acao_br, acao_us, alerta."
     ),
     "input_schema": {"type": "object", "properties": {
         "acao":      {"type": "string", "enum": ["add", "remove", "on", "off", "list"],
                       "description": "add=adicionar, remove=apagar, on=ativar, off=pausar, list=listar"},
         "tipo":      {"type": "string",
                       "description": "Categoria do módulo: moedas | cripto | clima | noticias | agenda | lembretes | etf | acao_br | acao_us | alerta"},
         "parametro": {"type": "string",
                       "description": "Ticker (JEPQ, PETR4), cidade (Rio de Janeiro), tema (tecnologia), texto do alerta, etc."},
         "label":     {"type": "string",
                       "description": "Nome amigável opcional para exibir no relatório, ex: 'JEPQ ETF', 'Clima Rio'"},
         "id":        {"type": "integer",
                       "description": "ID numérico do módulo (use só para on/off/remove quando souber o ID exato)"}
     }, "required": ["acao"]}},
]

TOOLS_GUIDE = """
Você tem ferramentas. Use-as sempre que precisar de dados reais ou de executar uma ação — nunca invente dados nem diga que fez algo sem chamar a ferramenta correspondente.
As ferramentas enviar_whatsapp e criar_evento apenas registram um RASCUNHO: o aplicativo mostra o conteúdo ao usuário e pergunta "Confirma? (sim/não)" antes de executar de verdade. Depois de chamá-las, apenas repasse ao usuário o texto que a ferramenta retornar. Isso vale mesmo quando o usuário pedir para revisar antes — o rascunho É a revisão.

REGRA CRÍTICA para gerenciar_modulo: quando o usuário pedir para TIRAR, REMOVER, PAUSAR, DESATIVAR, ou PARAR de incluir qualquer informação no resumo/relatório matinal (ex: "tira o bitcoin", "remove as notícias", "não quero mais ver o clima"), você DEVE chamar gerenciar_modulo(acao="off", ...) IMEDIATAMENTE — nunca gere o relatório matinal em resposta a esse tipo de pedido.
Da mesma forma, quando pedir para ADICIONAR algo ao resumo de manhã, chame gerenciar_modulo(acao="add", ...) antes de qualquer outra coisa."""


async def _resolve_whatsapp_number(destinatario: str):
    """Resolve destinatario (nome ou telefone) para (numero, nome_exibido)."""
    import re as _re
    d = destinatario.strip()
    digits = _re.sub(r"\D", "", d)
    if 10 <= len(digits) <= 15 and len(digits) >= len(d) - 6:
        number = digits if len(digits) >= 12 else "55" + digits
        return number, "+" + number
    hit = find_contact(d)
    if hit:
        return hit["number"], hit["name"]
    try:
        async with httpx.AsyncClient(timeout=10.0) as wc:
            for variant in [d, d.title(), d.upper()]:
                cr = await wc.post(f"{EVO_URL}/chat/findContacts/{EVO_PERSONAL_INSTANCE}",
                    headers={"apikey": EVO_PERSONAL_KEY, "Content-Type": "application/json"},
                    json={"where": {"pushName": variant}})
                found = cr.json()
                if isinstance(found, list) and found:
                    return found[0].get("remoteJid", "").replace("@s.whatsapp.net", ""), found[0].get("pushName", d)
    except Exception as e:
        logger.warning(f"findContacts falhou: {e}")
    return "", d


async def execute_tool(name: str, args: dict, user_id: str) -> str:
    """Executa uma ferramenta chamada pelo modelo e retorna o resultado como texto."""
    if name == "buscar_google":
        return await search_google(args.get("consulta", ""))

    if name == "clima":
        city = args.get("cidade") or os.getenv("DEFAULT_CITY", "Miguel Pereira")
        async with httpx.AsyncClient(timeout=15.0) as wc:
            wr = await wc.get(f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_KEY}&units=metric&lang=pt_br")
            wd = wr.json()
            if "main" not in wd:
                return f"Não achei o clima de {city}."
            return (f"Clima em {city}: {wd['weather'][0]['description']}, {wd['main']['temp']}°C, "
                    f"sensação {wd['main']['feels_like']}°C, umidade {wd['main']['humidity']}%, vento {wd['wind']['speed']}m/s")

    if name == "cotacoes":
        parts = []
        async with httpx.AsyncClient(timeout=15.0) as cc:
            d1 = (await cc.get("https://open.er-api.com/v6/latest/USD")).json()
            brl = d1["rates"]["BRL"]
            parts.append(f"Dólar: R${brl:.2f}")
            parts.append(f"Euro: R${brl / d1['rates']['EUR']:.2f}")
            if args.get("incluir_bitcoin"):
                try:
                    d2 = (await cc.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=brl")).json()
                    parts.append(f"Bitcoin: R${d2['bitcoin']['brl']:,.0f}")
                except Exception:
                    parts.append("Bitcoin: indisponível agora")
        return " | ".join(parts)

    if name == "noticias":
        tema = args.get("tema") or "brasil"
        async with httpx.AsyncClient(timeout=15.0) as nc:
            nd = (await nc.get(f"https://newsapi.org/v2/everything?q={tema}&language=pt&sortBy=publishedAt&pageSize=5&apiKey={NEWSAPI_KEY}")).json()
            heads = [f"- {a['title']} ({a['source']['name']})" for a in nd.get("articles", [])[:5]]
            return "\n".join(heads) if heads else "Sem notícias encontradas."

    if name == "transito":
        origem = args.get("origem") or LOCAIS["casa"]
        destino = args.get("destino", "")
        for alias, addr in LOCAIS.items():
            if alias in origem.lower():
                origem = addr
            if alias in destino.lower():
                destino = addr
        async with httpx.AsyncClient(timeout=15.0) as mc:
            mr = await mc.post("https://routes.googleapis.com/directions/v2:computeRoutes",
                headers={"Content-Type": "application/json", "X-Goog-Api-Key": GOOGLE_MAPS_KEY,
                         "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.description"},
                json={"origin": {"address": origem}, "destination": {"address": destino},
                      "travelMode": "DRIVE", "routingPreference": "TRAFFIC_AWARE"})
            md = mr.json()
            if not md.get("routes"):
                return f"Não consegui calcular a rota ({md.get('error', {}).get('message', 'sem rota')})."
            r = md["routes"][0]
            dist_m = r["distanceMeters"]
            km = f"{dist_m/1000:.1f}km" if dist_m >= 1000 else f"{dist_m}m"
            total_min = int(r["duration"].rstrip("s")) / 60
            tempo = f"{int(total_min//60)}h{int(total_min%60):02d}min" if total_min >= 60 else f"{int(total_min)} min"
            return f"De {origem} até {destino}: {km}, ~{tempo} com trânsito atual. {r.get('description','')}"

    if name == "ler_agenda":
        svc = get_gmail_service()
        if not svc:
            return "Google não conectado."
        from googleapiclient.discovery import build as _b
        cal = _b("calendar", "v3", credentials=gmail_credentials)
        from datetime import timedelta as _td
        now = datetime.utcnow()
        days = int(args.get("dias") or 7)
        time_min, time_max = now.isoformat() + "Z", (now + _td(days=days)).isoformat() + "Z"
        evs = []
        for c in cal.calendarList().list().execute().get("items", []):
            try:
                for e in cal.events().list(calendarId=c["id"], timeMin=time_min, timeMax=time_max,
                                           maxResults=20, singleEvents=True, orderBy="startTime").execute().get("items", []):
                    start = e["start"].get("dateTime", e["start"].get("date", ""))
                    evs.append(f"{start} - {e.get('summary','')} ({c.get('summary','')})")
            except Exception:
                pass
        evs.sort()
        return "\n".join(evs) if evs else f"Nenhum evento nos próximos {days} dias."

    if name == "criar_evento":
        titulo, inicio = args.get("titulo", ""), args.get("inicio", "")
        if not titulo or not inicio:
            return "Faltou título ou data/hora de início."
        if not REDIS_AVAILABLE:
            return "Não consigo registrar a confirmação (cache indisponível)."
        ev = {"summary": titulo, "start": inicio, "end": args.get("fim", ""),
              "location": args.get("local", ""), "description": args.get("descricao", "")}
        redis_client.setex(f"pending_action:{user_id}", 120, json.dumps({"type": "criar_evento", "evento": ev}))
        data_fmt = inicio[:16].replace("T", " às ")
        return f'Rascunho registrado. Diga ao usuário: Vou criar o evento "{titulo}" em {data_fmt}h. Confirma? (sim/não)'

    if name == "ler_emails":
        svc = get_gmail_service()
        if not svc:
            return "Google não conectado."
        limite = min(int(args.get("limite") or 5), 10)
        results = svc.users().messages().list(userId="me", maxResults=limite, labelIds=["INBOX"]).execute()
        emails = []
        for m in results.get("messages", []):
            det = svc.users().messages().get(userId="me", id=m["id"], format="metadata",
                                             metadataHeaders=["From", "Subject", "Date"]).execute()
            h = {x["name"]: x["value"] for x in det["payload"]["headers"]}
            emails.append(f"De: {h.get('From','')} | Assunto: {h.get('Subject','')} | {det.get('snippet','')[:80]}")
        return "\n".join(emails) if emails else "Caixa de entrada vazia."

    if name == "ler_planilha":
        svc = get_gmail_service()
        if not svc:
            return "Google não conectado."
        from googleapiclient.discovery import build as _b
        sheets = _b("sheets", "v4", credentials=gmail_credentials)
        meta = sheets.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
        month_str = args.get("mes") or datetime.now().strftime("%m/%Y")
        out = [f"Planilha (filtro: {month_str}):"]
        for s in meta["sheets"]:
            sn = s["properties"]["title"]
            rows = sheets.spreadsheets().values().get(spreadsheetId=SHEET_ID, range=f"{sn}!A1:Z10000").execute().get("values", [])
            if not rows:
                continue
            filtered = [r for r in rows[1:] if r and month_str in r[0]] or rows[1:30]
            out.append(f"\n[Aba: {sn}] Colunas: {' | '.join(rows[0])} | Registros no período: {len(filtered)}")
            out.extend("  ".join(r) for r in filtered[:30])
        return "\n".join(out)

    if name == "escrever_planilha":
        svc = get_gmail_service()
        if not svc:
            return "Google não conectado."
        from googleapiclient.discovery import build as _b
        sheets = _b("sheets", "v4", credentials=gmail_credentials)
        acao, aba = args.get("acao"), args.get("aba")
        valores, celula = args.get("valores") or [], args.get("celula", "")
        if acao == "append":
            sheets.spreadsheets().values().append(spreadsheetId=SHEET_ID, range=f"{aba}!A1",
                valueInputOption="USER_ENTERED", body={"values": [valores]}).execute()
            return f"Linha adicionada na aba {aba}: {valores}"
        if acao == "update" and celula:
            sheets.spreadsheets().values().update(spreadsheetId=SHEET_ID, range=f"{aba}!{celula}",
                valueInputOption="USER_ENTERED", body={"values": [valores]}).execute()
            return f"Célula {celula} da aba {aba} atualizada."
        if acao == "delete" and celula:
            sheets.spreadsheets().values().clear(spreadsheetId=SHEET_ID, range=f"{aba}!{celula}").execute()
            return f"Faixa {celula} da aba {aba} apagada."
        return "Ação inválida ou faltou a célula."

    if name == "criar_lembrete":
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO reminders (text, remind_at) VALUES (%s, %s)",
                    (args.get("texto"), args.get("quando")))
        conn.commit()
        cur.close(); conn.close()
        return f"Lembrete criado: {args.get('texto')} em {args.get('quando')}."

    if name == "listar_lembretes":
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT text, remind_at FROM reminders WHERE done = false ORDER BY remind_at ASC")
        rems = cur.fetchall()
        cur.close(); conn.close()
        if not rems:
            return "Nenhum lembrete pendente."
        return "\n".join(f"- {r[0]} ({r[1].strftime('%d/%m/%Y %H:%M')})" for r in rems)

    if name == "enviar_whatsapp":
        destinatario, mensagem = args.get("destinatario", ""), args.get("mensagem", "")
        if not destinatario or not mensagem:
            return "Faltou destinatário ou mensagem."
        if not REDIS_AVAILABLE:
            return "Não consigo registrar a confirmação (cache indisponível)."
        number, found_name = await _resolve_whatsapp_number(destinatario)
        if not number:
            return f'Não achei o contato "{destinatario}" no WhatsApp.'
        redis_client.setex(f"pending_action:{user_id}", 120, json.dumps(
            {"type": "whatsapp", "number": number, "text": mensagem, "contact": found_name}))
        return f'Rascunho registrado. Diga ao usuário: Vou enviar pra {found_name}: "{mensagem}" — Confirma? (sim/não)'

    if name == "salvar_memoria":
        conteudo = args.get("conteudo", "").strip()
        if not conteudo:
            return "Nada para salvar."
        emb = await get_embedding(conteudo)
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM memory_embeddings WHERE content = %s", (conteudo,))
        if not cur.fetchone():
            cur.execute("INSERT INTO memory_embeddings (content, category, metadata, embedding) VALUES (%s, %s, %s, %s)",
                        (conteudo, args.get("categoria", "geral"),
                         json.dumps({"source": "chat", "user_id": user_id}),
                         _vector_literal(emb) if emb else None))
            conn.commit()
        cur.close(); conn.close()
        return f'Memória guardada: "{conteudo}"'

    if name == "gerenciar_modulo":
        acao     = args.get("acao", "list").lower()
        tipo     = (args.get("tipo") or "").lower()
        parametro = args.get("parametro") or None
        label    = args.get("label") or None
        mod_id   = args.get("id")

        # Montar comando e delegar para handle_module_command
        if acao == "list":
            cmd = "/modulo list"
        elif acao == "add":
            if not tipo:
                return "Preciso saber o tipo do módulo (ex: etf, clima, noticias, acao_br)."
            cmd = f"/modulo add {tipo} {parametro}" if parametro else f"/modulo add {tipo}"
        elif acao in ("on", "off", "remove"):
            target = str(mod_id) if mod_id else (parametro or tipo)
            if not target:
                return "Preciso do ID ou nome do módulo para essa ação."
            cmd = f"/modulo {acao} {target}"
        else:
            return f"Ação '{acao}' não reconhecida."

        result = await handle_module_command(cmd)

        # Se foi um add e tem label customizado, atualizar no banco
        if acao == "add" and label and result and "adicionado" in result:
            try:
                conn = get_db()
                cur = conn.cursor()
                cur.execute(
                    "UPDATE morning_modules SET label = %s, atualizado_em = NOW() "
                    "WHERE tipo = %s AND (parametro = %s OR (parametro IS NULL AND %s IS NULL)) "
                    "ORDER BY id DESC LIMIT 1",
                    (label, tipo, parametro, parametro)
                )
                conn.commit()
                cur.close(); conn.close()
            except Exception as _le:
                logger.warning(f"gerenciar_modulo label update error: {_le}")

        return result or "Comando executado."

    return f"Ferramenta desconhecida: {name}"


async def run_agent(user_message: str, context: str, user_id: str) -> str:
    """Loop do agente: Claude decide quais ferramentas chamar até ter a resposta."""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    system = SYSTEM_PROMPT.format(today=today, home_address=os.getenv("HOME_ADDRESS", "Rua de Paiva 124, Miguel Pereira, RJ")) + TOOLS_GUIDE + "\n\nContexto:\n" + context
    model = "claude-sonnet-5" if is_complex_query(user_message) else "claude-haiku-4-5"
    messages = [{"role": "user", "content": user_message}]
    async with httpx.AsyncClient(timeout=45.0) as client:
        for _ in range(6):
            r = await client.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": model, "max_tokens": 2000, "system": system,
                      "tools": TOOLS, "messages": messages})
            data = r.json()
            if "content" not in data:
                raise Exception(f"Anthropic: {data.get('error', {}).get('message', str(data))}")
            messages.append({"role": "assistant", "content": data["content"]})
            if data.get("stop_reason") == "tool_use":
                results = []
                for block in data["content"]:
                    if block.get("type") != "tool_use":
                        continue
                    try:
                        out = await execute_tool(block["name"], block.get("input", {}) or {}, user_id)
                    except Exception as e:
                        out = f"Erro na ferramenta: {e}"
                        logger.warning(f"TOOL_ERROR {block['name']}: {e}")
                    logger.info(f"TOOL {block['name']} args={json.dumps(block.get('input', {}), ensure_ascii=False)[:200]} -> {str(out)[:200]}")
                    results.append({"type": "tool_result", "tool_use_id": block["id"], "content": str(out)[:4000]})
                messages.append({"role": "user", "content": results})
                continue
            texts = [b["text"] for b in data["content"] if b.get("type") == "text"]
            final = "\n".join(texts).strip()
            if final:
                return final
            raise Exception("Anthropic devolveu resposta vazia")
    return "Essa tarefa ficou longa demais e eu parei no meio — tenta quebrar em pedidos menores?"


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    authenticated: bool = Depends(verify_api_key)
):
    try:
        msg_lower = request.message.lower().strip()

        # ── 1. Confirmação de ação pendente (determinística, antes de qualquer LLM)
        _pending_key = f"pending_action:{request.user_id}"
        _confirm_words = ["sim", "pode", "confirma", "confirmo", "ok", "vai", "manda", "envia", "cria", "certo", "isso"]
        _cancel_words = ["nao", "não", "cancela", "cancelo", "desiste", "pare"]
        import re as _re_confirm
        _msg_tokens = set(_re_confirm.findall(r"\w+", msg_lower))
        _is_confirm = bool(_msg_tokens & set(_confirm_words))
        _is_cancel = bool(_msg_tokens & set(_cancel_words))

        if REDIS_AVAILABLE and (_is_confirm or _is_cancel):
            _pending_raw = redis_client.get(_pending_key)
            if _pending_raw:
                _pending = json.loads(_pending_raw)
                redis_client.delete(_pending_key)
                if _is_cancel:
                    save_conversation(request.user_id, request.message, "Cancelado.")
                    return ChatResponse(response="Cancelado.", context_used=0, cached=False)
                _ptype = _pending.get("type")
                if _ptype == "whatsapp":
                    try:
                        # Mensagem a contato sai pela instancia PESSOAL (numero do Marcelo)
                        async with httpx.AsyncClient(timeout=10.0) as wc:
                            _sr = await wc.post(f"{EVO_URL}/message/sendText/{EVO_PERSONAL_INSTANCE}",
                                headers={"apikey": EVO_PERSONAL_KEY, "Content-Type": "application/json"},
                                json={"number": _pending["number"], "text": _pending["text"]})
                        if _sr.status_code in (200, 201):
                            _resp = f"Mensagem enviada pra {_pending['contact']} (do seu numero): {_pending['text']}"
                        else:
                            _resp = f"Erro ao enviar ({_sr.status_code}): {_sr.text[:200]}"
                            logger.error(f"SEND_PERSONAL_FAIL status={_sr.status_code} body={_sr.text[:300]}")
                    except Exception as _ew:
                        _resp = f"Erro ao enviar: {_ew}"
                    save_conversation(request.user_id, request.message, _resp)
                    return ChatResponse(response=_resp, context_used=0, cached=False)
                elif _ptype == "criar_evento":
                    _ev = _pending["evento"]
                    try:
                        svc_cal = get_gmail_service()
                        if svc_cal:
                            from googleapiclient.discovery import build as _b
                            _cal_svc = _b("calendar", "v3", credentials=gmail_credentials)
                            _end = _ev.get("end", "")
                            if not _end:
                                from datetime import datetime as _dtc, timedelta as _tdc
                                _end = (_dtc.fromisoformat(_ev["start"]) + _tdc(hours=1)).isoformat()
                            _cal_svc.events().insert(calendarId="primary", body={
                                "summary": _ev["summary"], "location": _ev.get("location", ""),
                                "description": _ev.get("description", ""),
                                "start": {"dateTime": _ev["start"], "timeZone": "America/Sao_Paulo"},
                                "end": {"dateTime": _end, "timeZone": "America/Sao_Paulo"}}).execute()
                            _resp = f"Evento criado: {_ev['summary']} em {_ev['start'][:16].replace('T', ' às ')}h"
                        else:
                            _resp = "Google não conectado."
                    except Exception as _ec:
                        _resp = f"Erro ao criar evento: {_ec}"
                    save_conversation(request.user_id, request.message, _resp)
                    return ChatResponse(response=_resp, context_used=0, cached=False)

        # ── 2. Comandos de módulos (/modulo) — interceptar antes do cache/LLM
        if request.message.strip().lower().startswith("/modulo"):
            mod_resp = await handle_module_command(request.message.strip())
            if mod_resp:
                save_conversation(request.user_id, request.message, mod_resp)
                return ChatResponse(response=mod_resp, context_used=0, cached=False)

        # ── 2b. Interceptor determinístico: verbo de remoção + tipo/ticker + contexto matinal
        _rm_tokens = set(re.findall(r'[a-zA-Z0-9]+', msg_lower))
        _rm_verbs  = {"tira", "tirar", "retira", "retirar", "remove", "remover",
                      "apaga", "apagar", "pausa", "pausar", "desativa", "desativar"}
        _rm_ctx    = {"manha", "matinal", "resumo", "relatorio", "mensagem", "mensagens", "whatsapp"}
        _rm_tipos  = {
            "bitcoin": "bitcoin", "btc": "bitcoin", "cripto": "cripto",
            "dolar": "moedas", "euro": "moedas", "moedas": "moedas",
            "clima": "clima", "tempo": "clima",
            "noticia": "noticias", "noticias": "noticias",
            "agenda": "agenda", "lembretes": "lembretes",
            "jepq": "JEPQ", "etf": "etf",
        }
        if (_rm_tokens & _rm_verbs) and (_rm_tokens & _rm_ctx):
            for kw, target in _rm_tipos.items():
                if kw in msg_lower:
                    _rm_resp = await handle_module_command(f"/modulo off {target}")
                    if _rm_resp:
                        save_conversation(request.user_id, request.message, _rm_resp)
                        return ChatResponse(response=_rm_resp, context_used=0, cached=False)
                    break

        # ── 3. Cache (perguntas estáveis apenas; ações/voláteis nunca são cacheadas)
        cached = get_cached_response(request.message)
        if cached:
            return ChatResponse(response=cached, context_used=0, cached=True)

        # ── 3. Relatório matinal sob demanda
        if any(w in msg_lower for w in ["resumo do dia", "relatorio matinal", "relatório matinal", "resumo matinal", "resumo de hoje", "o que tenho para hoje"]):
            try:
                report = await generate_morning_report()
                if report:
                    save_conversation(request.user_id, request.message, report)
                    return ChatResponse(response=report, context_used=0, cached=False)
            except Exception as e:
                logger.error(f"Erro ao gerar relatorio matinal reativo: {e}")

        # ── 4. Atalho determinístico: ensinar alias de planilha ("PADA eh padaria")
        import re as _re_alias
        _am = _re_alias.match(r'^([A-Z0-9]{2,10})\s+(?:eh|significa|quer dizer|=)\s+(.+)', request.message.strip())
        if _am:
            _abrev, _nome = _am.group(1).strip(), _am.group(2).strip().rstrip('.!?')
            save_alias(_abrev, _nome)
            return ChatResponse(response=f'Beleza! Agora "{_abrev.upper()}" vira "{_nome}" na planilha.', context_used=0, cached=False)

        # ── 5. Contexto: memórias relevantes + histórico recente
        memories = await search_memory(request.message)
        mem_context = "\n".join(m["content"] for m in memories)
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT user_message, assistant_response FROM conversations ORDER BY created_at DESC LIMIT 15")
        history = cur.fetchall()
        cur.close(); conn.close()
        hist_lines = []
        for u, a in reversed(history):
            if u: hist_lines.append(f"Usuario: {u}")
            if a: hist_lines.append(f"Jarvis: {a}")
        context = "\n".join(hist_lines) + "\n" + mem_context
        if request.lat and request.lon:
            context += f"\nLocalização atual do usuário: {request.lat},{request.lon}"

        # ── 6. Agente com ferramentas (Claude); fallback texto-puro se indisponível
        logger.info(f"CHAT user={request.user_id!r} msg={request.message!r}")
        try:
            response = await run_agent(request.message, context, request.user_id)
        except Exception as e:
            logger.warning(f"Agente indisponível ({e}); usando fallback texto-puro")
            response = await call_ollama(request.message, context)
        response = unwrap_llm_json(response)
        response = "".join(c for c in response if ord(c) <= 0x024F or ord(c) == 0x00B0).strip()

        # ── 7. Persistir e cachear
        save_conversation(request.user_id, request.message, response)
        cache_response(request.message, response)
        return ChatResponse(response=response, context_used=len(memories), cached=False)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """Recebe eventos da Evolution API. Processa mensagens de texto vindas do grupo do Jarvis
    como se fossem mensagens de chat, e responde no proprio WhatsApp."""
    try:
        payload = await request.json()
    except Exception:
        return {"status": "ignored"}

    if WHATSAPP_WEBHOOK_SECRET:
        if request.headers.get("x-webhook-secret") != WHATSAPP_WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Unauthorized")

    event = (payload.get("event") or "").lower()
    if event not in ("messages.upsert", "messages_upsert"):
        return {"status": "ignored"}

    data = payload.get("data") or {}
    key = data.get("key") or {}

    # Ignora mensagens enviadas pelo proprio Jarvis (evita loop)
    if key.get("fromMe"):
        return {"status": "ignored"}

    # So processa mensagens do grupo configurado
    if key.get("remoteJid") != MARCELO_WHATSAPP:
        return {"status": "ignored"}

    msg = data.get("message") or {}
    text = (msg.get("conversation")
            or (msg.get("extendedTextMessage") or {}).get("text")
            or "").strip()
    if not text:
        return {"status": "ignored"}

    # ── Comandos de módulos (/modulo add, /modulo list, etc.) ────────────────
    if text.lower().startswith("/modulo"):
        try:
            mod_resp = await handle_module_command(text)
            if mod_resp:
                await send_whatsapp(mod_resp)
                return {"status": "ok"}
        except Exception as e:
            logger.error(f"MODULE_CMD_ERROR error={e}")
            await send_whatsapp(f"Erro ao executar comando: {e}")
            return {"status": "ok"}

    if is_complex_query(text):
        asyncio.create_task(send_whatsapp("🧠 Deixa eu pensar nessa..."))

    try:
        chat_req = ChatRequest(message=text, user_id="whatsapp")
        result = await chat(chat_req, authenticated=True)
        await send_whatsapp(result.response)
    except Exception as e:
        logger.error(f"WHATSAPP_WEBHOOK_ERROR error={e}")

    return {"status": "ok"}

@app.get("/history")
async def get_history(
    limit: int = 10,
    authenticated: bool = Depends(verify_api_key)
):
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT user_message, assistant_response, created_at
        FROM conversations
        ORDER BY created_at DESC
        LIMIT %s
    """, (limit,))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [
        {
            "user": r[0],
            "assistant": r[1],
            "created_at": str(r[2])
        }
        for r in results
    ]

@app.get("/stats")
async def get_stats(authenticated: bool = Depends(verify_api_key)):
    conn = get_db()
    cur = conn.cursor()
    
    # Total de conversas
    cur.execute("SELECT COUNT(*) FROM conversations")
    total_conversations = cur.fetchone()[0]
    
    # Conversas hoje
    cur.execute("SELECT COUNT(*) FROM conversations WHERE DATE(created_at) = CURRENT_DATE")
    today_conversations = cur.fetchone()[0]
    
    # Lembretes ativos
    cur.execute("SELECT COUNT(*) FROM reminders WHERE done = false")
    active_reminders = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    return {
        "total_conversations": total_conversations,
        "today_conversations": today_conversations,
        "active_reminders": active_reminders,
        "cache_enabled": REDIS_AVAILABLE
    }

# Gmail OAuth
@app.get("/auth/gmail")
async def gmail_auth(authenticated: bool = Depends(verify_api_key)):
    flow = Flow.from_client_config(
        {"web": {"client_id": GMAIL_CLIENT_ID, "client_secret": GMAIL_CLIENT_SECRET,
                 "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                 "token_uri": "https://oauth2.googleapis.com/token"}},
        scopes=GMAIL_SCOPES, redirect_uri=GMAIL_REDIRECT_URI)
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    return {"auth_url": auth_url}

@app.get("/auth/callback")
async def gmail_callback(code: str):
    global gmail_credentials
    flow = Flow.from_client_config(
        {"web": {"client_id": GMAIL_CLIENT_ID, "client_secret": GMAIL_CLIENT_SECRET,
                 "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                 "token_uri": "https://oauth2.googleapis.com/token"}},
        scopes=GMAIL_SCOPES, redirect_uri=GMAIL_REDIRECT_URI)
    flow.fetch_token(code=code)
    gmail_credentials = flow.credentials
    # Save token to Redis for persistence
    _td = {"token": gmail_credentials.token, "refresh_token": gmail_credentials.refresh_token,
           "token_uri": gmail_credentials.token_uri, "client_id": gmail_credentials.client_id,
           "client_secret": gmail_credentials.client_secret}
    if REDIS_AVAILABLE:
        redis_client.set("gmail_token", json.dumps(_td))
    _db_save_token(_td)
    return {"status": "Gmail conectado com sucesso! Pode fechar esta aba."}


def _db_save_token(token_data: dict):
    """Salva token Google no PostgreSQL (fallback permanente do Redis)."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO kv_store (key, value, updated_at)
            VALUES ('gmail_token', %s, NOW())
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
        """, (json.dumps(token_data),))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"TOKEN_SAVE_ERROR error={e}")

def _db_load_token() -> Optional[dict]:
    """Le token Google do PostgreSQL."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT value FROM kv_store WHERE key = 'gmail_token'")
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return json.loads(row[0])
    except:
        pass
    return None

def get_gmail_service():
    global gmail_credentials
    if not gmail_credentials:
        # 1. Tentar Redis
        token_data = None
        if REDIS_AVAILABLE:
            saved = redis_client.get("gmail_token")
            if saved:
                token_data = json.loads(saved)
        # 2. Fallback: banco PostgreSQL
        if not token_data:
            token_data = _db_load_token()
            if token_data and REDIS_AVAILABLE:
                # Sincronizar de volta pro Redis
                redis_client.set("gmail_token", json.dumps(token_data))
        if token_data:
            gmail_credentials = Credentials(**token_data)
    if not gmail_credentials:
        return None
    if gmail_credentials.expired and gmail_credentials.refresh_token:
        from google.auth.transport.requests import Request
        gmail_credentials.refresh(Request())
        td = {"token": gmail_credentials.token, "refresh_token": gmail_credentials.refresh_token,
              "token_uri": gmail_credentials.token_uri, "client_id": gmail_credentials.client_id,
              "client_secret": gmail_credentials.client_secret}
        if REDIS_AVAILABLE:
            redis_client.set("gmail_token", json.dumps(td))
        _db_save_token(td)
    return build("gmail", "v1", credentials=gmail_credentials)

@app.get("/emails")
async def get_emails(limit: int = 10, authenticated: bool = Depends(verify_api_key)):
    service = get_gmail_service()
    if not service:
        raise HTTPException(status_code=400, detail="Gmail não conectado. Use /auth/gmail primeiro.")
    results = service.users().messages().list(userId="me", maxResults=limit, labelIds=["INBOX"]).execute()
    messages = []
    for msg in results.get("messages", []):
        detail = service.users().messages().get(userId="me", id=msg["id"], format="metadata",
                 metadataHeaders=["From", "Subject", "Date"]).execute()
        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
        messages.append({"id": msg["id"], "from": headers.get("From", ""),
                        "subject": headers.get("Subject", ""), "date": headers.get("Date", ""),
                        "snippet": detail.get("snippet", "")})
    return messages

class DraftRequest(BaseModel):
    to: str
    subject: str
    body: str

@app.post("/drafts")
async def create_draft(req: DraftRequest, authenticated: bool = Depends(verify_api_key)):
    service = get_gmail_service()
    if not service:
        raise HTTPException(status_code=400, detail="Gmail não conectado. Use /auth/gmail primeiro.")
    msg = "To: " + req.to + "\r\nSubject: " + req.subject + "\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n" + req.body
    raw = base64.urlsafe_b64encode(msg.encode()).decode()
    draft = service.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
    return {"id": draft["id"], "status": "Rascunho criado"}

@app.get("/calendar")
async def get_calendar(days: int = 7, authenticated: bool = Depends(verify_api_key)):
    creds = None
    if gmail_credentials:
        creds = gmail_credentials
    elif REDIS_AVAILABLE:
        saved = redis_client.get("gmail_token")
        if saved:
            data = json.loads(saved)
            creds = Credentials(**data)
    if not creds:
        raise HTTPException(status_code=400, detail="Google nao conectado.")
    service = build("calendar", "v3", credentials=creds)
    now = datetime.utcnow()
    from datetime import timedelta
    time_min = now.isoformat() + "Z"
    time_max = (now + timedelta(days=days)).isoformat() + "Z"
    calendars = service.calendarList().list().execute()
    all_events = []
    for cal in calendars.get("items", []):
        try:
            events = service.events().list(calendarId=cal["id"], timeMin=time_min, timeMax=time_max,
                                            maxResults=50, singleEvents=True, orderBy="startTime").execute()
            for e in events.get("items", []):
                all_events.append({"summary": e.get("summary", ""), "calendar": cal.get("summary", ""),
                    "start": e["start"].get("dateTime", e["start"].get("date", "")),
                    "end": e["end"].get("dateTime", e["end"].get("date", "")),
                    "location": e.get("location", "")})
        except:
            pass
    all_events.sort(key=lambda x: x["start"])
    return all_events

class EventRequest(BaseModel):
    summary: str
    start: str
    end: str
    location: str = ""
    description: str = ""

@app.post("/calendar")
async def create_event(req: EventRequest, authenticated: bool = Depends(verify_api_key)):
    service = get_gmail_service()
    if not service:
        raise HTTPException(status_code=400, detail="Google nao conectado.")
    cal = build("calendar", "v3", credentials=gmail_credentials)
    event = cal.events().insert(calendarId="primary", body={
        "summary": req.summary,
        "location": req.location,
        "description": req.description,
        "start": {"dateTime": req.start, "timeZone": "America/Sao_Paulo"},
        "end": {"dateTime": req.end, "timeZone": "America/Sao_Paulo"}
    }).execute()
    return {"id": event["id"], "status": "Evento criado", "link": event.get("htmlLink", "")}

# ─── PAINEL DE STATUS ──────────────────────────────────────────────────────────
@app.get("/status", response_class=HTMLResponse)
async def status_panel():
    checks = {}
    # Database
    try:
        conn = get_db(); conn.close()
        checks["PostgreSQL"] = ("ok", "Conectado")
    except Exception as e:
        checks["PostgreSQL"] = ("error", str(e)[:80])
    # Redis
    if REDIS_AVAILABLE:
        try:
            redis_client.ping()
            keys = redis_client.dbsize()
            checks["Redis"] = ("ok", f"{keys} chaves")
        except Exception as e:
            checks["Redis"] = ("error", str(e)[:80])
    else:
        checks["Redis"] = ("warn", "Indisponivel")
    # Groq
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get("https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"})
            checks["Groq LLM"] = ("ok", "API respondendo") if r.status_code == 200 else ("error", f"HTTP {r.status_code}")
    except Exception as e:
        checks["Groq LLM"] = ("error", str(e)[:80])
    # Google OAuth
    svc = get_gmail_service()
    checks["Google OAuth"] = ("ok", "Token valido") if svc else ("error", "Nao autenticado — acesse /auth/gmail")
    # Gmail
    if svc:
        try:
            svc.users().getProfile(userId="me").execute()
            checks["Gmail"] = ("ok", "Acessivel")
        except Exception as e:
            checks["Gmail"] = ("error", str(e)[:80])
    else:
        checks["Gmail"] = ("warn", "Depende do OAuth")
    # OpenWeather
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"https://api.openweathermap.org/data/2.5/weather?q=Miguel+Pereira&appid={OPENWEATHER_KEY}&units=metric")
            checks["OpenWeather"] = ("ok", f"{r.json().get('main',{}).get('temp','?')}°C em Miguel Pereira") if r.status_code == 200 else ("error", f"HTTP {r.status_code}")
    except Exception as e:
        checks["OpenWeather"] = ("error", str(e)[:80])
    # Evolution WhatsApp
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{EVO_URL}/instance/fetchInstances",
                headers={"apikey": EVO_KEY})
            checks["WhatsApp (Evolution)"] = ("ok", f"Instancia {EVO_INSTANCE}") if r.status_code == 200 else ("error", f"HTTP {r.status_code}")
    except Exception as e:
        checks["WhatsApp (Evolution)"] = ("error", str(e)[:80])
    # Contatos sincronizados
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*), MAX(synced_at) FROM whatsapp_contacts")
        cnt, last_sync = cur.fetchone()
        cur.close(); conn.close()
        sync_str = last_sync.strftime("%d/%m %H:%M") if last_sync else "nunca"
        checks["Contatos WhatsApp"] = ("ok", f"{cnt} contatos (sync: {sync_str})")
    except Exception as e:
        checks["Contatos WhatsApp"] = ("warn", str(e)[:80])
    # NewsAPI
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"https://newsapi.org/v2/top-headlines?country=br&apiKey={NEWSAPI_KEY}&pageSize=1")
            checks["NewsAPI"] = ("ok", "Respondendo") if r.status_code == 200 else ("warn", f"HTTP {r.status_code}")
    except Exception as e:
        checks["NewsAPI"] = ("error", str(e)[:80])

    # Lembretes e conversas
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM reminders WHERE done = false")
        rem = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM conversations WHERE DATE(created_at) = CURRENT_DATE")
        conv_today = cur.fetchone()[0]
        cur.close(); conn.close()
        checks["Lembretes ativos"] = ("ok" if rem == 0 else "warn", f"{rem} pendentes")
        checks["Conversas hoje"] = ("ok", str(conv_today))
    except Exception as e:
        checks["Lembretes ativos"] = ("warn", str(e)[:80])

    # Build HTML
    color = {"ok": "#22c55e", "warn": "#f59e0b", "error": "#ef4444"}
    icon  = {"ok": "✅", "warn": "⚠️", "error": "❌"}
    rows = ""
    for name, (status, detail) in checks.items():
        rows += f"""
        <tr>
          <td style="padding:10px 16px;font-weight:600">{icon[status]} {name}</td>
          <td style="padding:10px 16px;color:{color[status]};font-weight:500">{status.upper()}</td>
          <td style="padding:10px 16px;color:#94a3b8">{detail}</td>
        </tr>"""
    ok_count  = sum(1 for s,_ in checks.values() if s == "ok")
    err_count = sum(1 for s,_ in checks.values() if s == "error")
    overall   = "🟢 Tudo OK" if err_count == 0 else f"🔴 {err_count} erro(s)"
    now_str   = __import__('datetime').datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="refresh" content="30">
  <title>Jarvis — Status</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif;padding:32px}}
    h1{{font-size:1.8rem;margin-bottom:4px}}
    .sub{{color:#64748b;font-size:.9rem;margin-bottom:32px}}
    .badge{{display:inline-block;background:#1e293b;border-radius:8px;padding:8px 16px;font-size:1rem;margin-bottom:24px}}
    table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:12px;overflow:hidden}}
    thead tr{{background:#0f172a}}
    th{{padding:12px 16px;text-align:left;color:#64748b;font-size:.8rem;text-transform:uppercase;letter-spacing:.05em}}
    tbody tr:hover{{background:#263352}}
    tbody tr+tr{{border-top:1px solid #0f172a}}
    .footer{{margin-top:16px;color:#334155;font-size:.8rem;text-align:right}}
  </style>
</head>
<body>
  <div style="text-align:center;margin-bottom:12px"><img src="/logo-jarvis.png" alt="Jarvis" style="height:56px;object-fit:contain"></div>
  <h1>Jarvis — Painel de Status</h1>
  <div class="sub">Atualizado em {now_str} &nbsp;·&nbsp; Auto-refresh a cada 30s</div>
  <div class="badge">{overall} &nbsp;·&nbsp; {ok_count}/{len(checks)} serviços OK</div>
  <table>
    <thead><tr><th>Serviço</th><th>Status</th><th>Detalhe</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <div class="footer">" + os.getenv("APP_DOMAIN", "jarvis.mbam.com.br") + "</div>
</body>
</html>"""
    return HTMLResponse(content=html)


# ─── TESTES DE INTEGRAÇÃO ──────────────────────────────────────────────────────
@app.get("/api/health/full")
async def health_full(authenticated: bool = Depends(verify_api_key)):
    import time
    results = {}

    async def test(name, coro):
        t0 = time.monotonic()
        try:
            detail = await coro
            results[name] = {"status": "ok", "detail": detail, "ms": round((time.monotonic()-t0)*1000)}
        except Exception as e:
            results[name] = {"status": "error", "detail": str(e)[:200], "ms": round((time.monotonic()-t0)*1000)}

    async def _test_db():
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM conversations"); n = cur.fetchone()[0]
        cur.close(); conn.close()
        return f"{n} conversas"

    async def _test_redis():
        redis_client.ping()
        return f"{redis_client.dbsize()} chaves"

    async def _test_groq():
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":"ping"}],"max_tokens":5})
            d = r.json()
            if "choices" in d: return d["choices"][0]["message"]["content"]
            raise Exception(d.get("error",{}).get("message","unknown"))

    async def _test_weather():
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(f"https://api.openweathermap.org/data/2.5/weather?q=Miguel+Pereira&appid={OPENWEATHER_KEY}&units=metric")
            d = r.json()
            return f"{d['main']['temp']}°C, {d['weather'][0]['description']}"

    async def _test_exchange():
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get("https://open.er-api.com/v6/latest/USD")
            d = r.json()
            return f"USD/BRL={d['rates']['BRL']:.2f}"

    async def _test_gmail():
        svc = get_gmail_service()
        if not svc: raise Exception("Nao autenticado")
        profile = svc.users().getProfile(userId="me").execute()
        return profile.get("emailAddress","ok")

    async def _test_whatsapp():
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(f"{EVO_URL}/instance/fetchInstances", headers={"apikey": EVO_KEY})
            if r.status_code != 200: raise Exception(f"HTTP {r.status_code}")
            return f"Instancia {EVO_INSTANCE} acessivel"

    async def _test_contacts():
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM whatsapp_contacts")
        n = cur.fetchone()[0]; cur.close(); conn.close()
        return f"{n} contatos"

    async def _test_news():
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(f"https://newsapi.org/v2/top-headlines?country=br&apiKey={NEWSAPI_KEY}&pageSize=1")
            if r.status_code != 200: raise Exception(f"HTTP {r.status_code}")
            return "ok"

    import asyncio as _aio
    await _aio.gather(
        test("database",   _test_db()),
        test("redis",      _test_redis()),
        test("groq",       _test_groq()),
        test("weather",    _test_weather()),
        test("exchange",   _test_exchange()),
        test("gmail",      _test_gmail()),
        test("whatsapp",   _test_whatsapp()),
        test("contacts",   _test_contacts()),
        test("news",       _test_news()),
    )
    ok  = sum(1 for v in results.values() if v["status"] == "ok")
    err = sum(1 for v in results.values() if v["status"] == "error")
    return {"summary": {"ok": ok, "error": err, "total": len(results)}, "services": results}


# ─── LEITURA DE PDF / IMAGEM ───────────────────────────────────────────────────
@app.post("/api/analyze")
async def analyze_file(
    file: UploadFile = File(...),
    prompt: str = "Extraia e resuma as informações principais deste documento.",
    x_api_key: str = Header(None)
):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    data = await file.read()
    filename = file.filename or ""
    content_type = file.content_type or ""
    logger.info(f"ANALYZE filename={filename!r} size={len(data)} content_type={content_type!r}")

    # ── Imagem → Groq Vision (llama-4-scout) ──
    if content_type.startswith("image/") or filename.lower().endswith((".jpg",".jpeg",".png",".webp",".gif")):
        if not GROQ_API_KEY:
            raise HTTPException(status_code=503, detail="Groq nao configurado")
        import base64 as _b64
        b64 = _b64.b64encode(data).decode()
        mime = content_type if content_type.startswith("image/") else "image/jpeg"
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={"model": "meta-llama/llama-4-scout-17b-16e-instruct",
                      "messages": [{"role": "user", "content": [
                          {"type": "text", "text": prompt},
                          {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
                      ]}], "max_tokens": 1024})
            d = r.json()
            if "choices" in d:
                return {"type": "image", "filename": filename, "result": d["choices"][0]["message"]["content"]}
            raise HTTPException(status_code=500, detail=str(d.get("error",{})))

    # ── PDF → extrair texto e enviar ao LLM ──
    if content_type == "application/pdf" or filename.lower().endswith(".pdf"):
        try:
            import io
            # Usar pypdf para extrair texto
            try:
                from pypdf import PdfReader
            except ImportError:
                from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(data))
            pages_text = []
            for i, page in enumerate(reader.pages[:20]):  # máx 20 páginas
                t = page.extract_text() or ""
                if t.strip():
                    pages_text.append("[Pagina " + str(i+1) + "]\n" + t.strip())
            full_text = "\n\n".join(pages_text)
            if not full_text.strip():
                raise HTTPException(status_code=422, detail="PDF sem texto extraível (pode ser escaneado/imagem)")
            # Truncar para não estourar contexto
            if len(full_text) > 12000:
                full_text = full_text[:12000] + "\n\n[... texto truncado ...]"
            llm_prompt = prompt + "\n\nConteudo do PDF:\n" + full_text
            result = await call_ollama(llm_prompt, "")
            return {"type": "pdf", "filename": filename, "pages": len(reader.pages), "chars": len(full_text), "result": result}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao processar PDF: {e}")

    raise HTTPException(status_code=415, detail=f"Tipo nao suportado: {content_type}. Use imagem (jpg/png/webp) ou PDF.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
