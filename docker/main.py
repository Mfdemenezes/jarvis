from fastapi import FastAPI, HTTPException, Header, Depends, Request, Response, Cookie, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
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
SESSION_SECRET = os.getenv("API_KEY", "secret")
ACTIVE_SESSIONS = set()
OPENWEATHER_KEY = os.getenv("OPENWEATHER_API_KEY")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
GOOGLE_MAPS_KEY = os.getenv("GOOGLE_MAPS_KEY", "")
GOOGLE_SEARCH_KEY = os.getenv("GOOGLE_SEARCH_KEY", GOOGLE_MAPS_KEY)
GOOGLE_SEARCH_CX = os.getenv("GOOGLE_SEARCH_CX", "")
SHEET_ID = "1RjwiT3F-ubct12QHGyFu-YisARrAVQJzKCTM7VA__gU"
EVO_URL = os.getenv("EVO_URL", "")
EVO_KEY = os.getenv("EVO_KEY", "")
EVO_INSTANCE = os.getenv("EVO_INSTANCE", "")
MARCELO_WHATSAPP = "120363426093960169@g.us"
VAPID_PUBLIC = os.getenv("VAPID_PUBLIC", "")
VAPID_PRIVATE = os.getenv("VAPID_PRIVATE", "")
push_subscriptions = []
LOCAIS = {"casa": "Rua de Paiva 124, Miguel Pereira, RJ", "minha casa": "Rua de Paiva 124, Miguel Pereira, RJ"}
REDIS_HOST = os.getenv("REDIS_HOST", "jarvis-cache")

GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
GMAIL_REDIRECT_URI = "https://jarvis.mbam.com.br/auth/callback"
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

O Marcelo mora em Miguel Pereira, RJ (Rua de Paiva 124). Quando ele falar 'casa', é lá.
Hoje é {today}. Quando tiver dados reais no contexto, use-os na resposta.
Nunca diga que não pode fazer algo sem tentar usar suas ferramentas primeiro."""

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
    print("⚠️  Redis não disponível - cache desabilitado")

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
        database="personal_kb",
        user="assistant",
        password=POSTGRES_PASSWORD,
        port=5432
    )

# Autenticação
def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

# Cache
def get_cached_response(message: str) -> Optional[str]:
    if not REDIS_AVAILABLE:
        return None
    try:
        return redis_client.get(f"chat:{message}")
    except:
        return None

def cache_response(message: str, response: str, ttl: int = 3600):
    if not REDIS_AVAILABLE:
        return
    try:
        redis_client.setex(f"chat:{message}", ttl, response)
    except:
        pass

# Buscar memórias
def search_memory(query: str, limit: int = 5):
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT content, metadata, created_at
        FROM memory_embeddings
        ORDER BY created_at DESC
        LIMIT %s
    """, (limit,))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [{"content": r[0], "metadata": r[1], "date": str(r[2])} for r in results]

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

async def call_ollama(prompt: str, context: str = ""):
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    system = SYSTEM_PROMPT.format(today=today)
    if OPENAI_API_KEY:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={"model": "gpt-4o-mini", "messages": [
                    {"role": "system", "content": system + "\n\nContexto:\n" + context},
                    {"role": "user", "content": prompt}], "max_tokens": 300})
            return r.json()["choices"][0]["message"]["content"]
    else:
        full_prompt = f"""{system}\n\nContexto:\n{context}\n\nUsuário: {prompt}\n\nJarvis:"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(f"http://{OLLAMA_HOST}:11434/api/generate",
                json={"model": "llama3.2:3b", "prompt": full_prompt, "stream": False})
            return r.json()["response"]

# Salvar conversa
def save_conversation(user_id: str, user_message: str, assistant_response: str):
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO conversations (user_message, assistant_response, metadata)
        VALUES (%s, %s, %s)
    """, (user_message, assistant_response, json.dumps({"user_id": user_id, "timestamp": datetime.now().isoformat()})))
    
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

@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...), x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401)
    audio_data = await file.read()
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post("https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            files={"file": ("audio.webm", audio_data, "audio/webm")},
            data={"model": "whisper-1", "language": "pt"})
        return r.json()

@app.post("/api/push/subscribe")
async def push_subscribe(request: Request):
    sub = await request.json()
    if sub not in push_subscriptions:
        push_subscriptions.append(sub)
    print(f"PUSH SUB REGISTERED: {len(push_subscriptions)} total")
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
                    vapid_claims={"sub": "mailto:mfdemenezes@gmail.com"})
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

async def normalize_descriptions():
    while True:
        await asyncio.sleep(1200)
        try:
            svc = get_gmail_service()
            if not svc: continue
            sheets = build("sheets", "v4", credentials=gmail_credentials)
            result = sheets.spreadsheets().values().get(spreadsheetId=SHEET_ID, range="Pagina1!A1:Z10000").execute()
            rows = result.get("values", [])
            if len(rows) < 2: continue
            header = rows[0]
            desc_col = next((i for i, h in enumerate(header) if "descri" in h.lower()), None)
            if desc_col is None: continue
            aliases = load_aliases()
            updates, unknown = [], []
            for i, row in enumerate(rows[1:], start=2):
                if desc_col >= len(row): continue
                desc = row[desc_col].strip()
                if not desc or len(desc) > 30: continue
                matched = False
                for alias, full_name in aliases.items():
                    if desc.upper() == alias.upper() or desc.upper().startswith(alias.upper()):
                        if desc != full_name:
                            updates.append({"range": f"Pagina1!{chr(65+desc_col)}{i}", "values": [[full_name]]})
                        matched = True; break
                if not matched and len(desc) <= 10 and desc.upper() == desc:
                    unknown.append({"row": i, "desc": desc})
            if unknown and OPENAI_API_KEY:
                descs_str = ", ".join(['"' + u["desc"] + '"' for u in unknown[:20]])
                prompt_sys = "Voce recebe abreviacoes de estabelecimentos comerciais brasileiros de emails de cartao. Retorne APENAS JSON: {ABREV: Nome completo}. Se nao souber, mantenha o original."
                async with httpx.AsyncClient(timeout=30.0) as client:
                    r = await client.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, json={"model": "gpt-4o-mini", "messages": [{"role": "system", "content": prompt_sys}, {"role": "user", "content": f"Normalize: {descs_str}"}], "max_tokens": 500})
                    resp = r.json()["choices"][0]["message"]["content"]
                    if "{" in resp:
                        mapping = json.loads(resp[resp.index("{"):resp.rindex("}")+1])
                        for u in unknown:
                            full = mapping.get(u["desc"], u["desc"])
                            if full != u["desc"]:
                                updates.append({"range": f"Pagina1!{chr(65+desc_col)}{u['row']}", "values": [[full]]})
                                save_alias(u["desc"], full)
            if updates:
                sheets.spreadsheets().values().batchUpdate(spreadsheetId=SHEET_ID, body={"valueInputOption": "USER_ENTERED", "data": updates}).execute()
                print(f"Normalizadas {len(updates)} descricoes")
        except Exception as e:
            print(f"Erro normalizar descricoes: {e}")

@app.on_event("startup")
async def start_email_cron():
    asyncio.create_task(check_important_emails())
    asyncio.create_task(normalize_descriptions())

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
    
    # Check Ollama
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.get(f"http://{OLLAMA_HOST}:11434/api/tags")
            health_status["llm"] = "ready"
    except:
        health_status["llm"] = "not ready"
        health_status["status"] = "degraded"
    
    return health_status

@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    authenticated: bool = Depends(verify_api_key)
):
    try:
        # Verificar cache
        cached = get_cached_response(request.message)
        if cached:
            return ChatResponse(
                response=cached,
                context_used=0,
                cached=True
            )
        
        # Buscar contexto
        memories = search_memory(request.message)
        mem_context = "\n".join([m["content"] for m in memories])
        
        # Historico recente
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT user_message, assistant_response FROM conversations ORDER BY created_at DESC LIMIT 5")
        history = cur.fetchall()
        cur.close()
        conn.close()
        hist_lines = []
        for u, a in reversed(history):
            if u: hist_lines.append(f"Usuario: {u}")
            if a: hist_lines.append(f"Jarvis: {a}")
        context = "\n".join(hist_lines) + "\n" + mem_context
        
        # Ensinar alias: "PADA eh padaria"
        import re as _re_alias
        _am = _re_alias.match(r'(.{2,15})\s+(?:e|eh|significa|quer dizer|=)\s+(.+)', request.message.strip(), _re_alias.IGNORECASE)
        if _am:
            _abrev = _am.group(1).strip()
            _nome = _am.group(2).strip().rstrip('.!?')
            save_alias(_abrev, _nome)
            return ChatResponse(response=f'Beleza! Agora "{_abrev.upper()}" vira "{_nome}" na planilha.', context_used=0, cached=False)

        # Detectar intencao e buscar dados reais
        msg_lower = request.message.lower()
        print(f"CHAT: {request.message}")
        import re as _re
        
        # Busca Geral no Google (Gatilho)
        search_triggers = ["pesquise", "quem é", "quem foi", "o que é", "onde fica", "preço de", "como fazer", "significado de", "notícias sobre", "resultado do", "quem ganhou"]
        if any(w in msg_lower for w in search_triggers):
            search_query = request.message
            for w in search_triggers:
                if msg_lower.startswith(w):
                    search_query = request.message[len(w):].strip()
                    break
            google_results = await search_google(search_query)
            context += f"\n\nResultados da busca Google para '{search_query}':\n{google_results}"

        is_finance = any(w in msg_lower for w in ["gasto", "despesa", "receita", "planilha", "pagamento", "supermercado", "conta", "financ"])
        if any(w in msg_lower for w in ["clima", "tempo", "temperatura", "chuva", "chover", "frio", "calor", "previsao", "previsão", "weather"]):
            try:
                city = "Miguel Pereira"
                cities = {"são paulo":"São Paulo","sp":"São Paulo","rio":"Rio de Janeiro","rj":"Rio de Janeiro","curitiba":"Curitiba","brasilia":"Brasília","bh":"Belo Horizonte","belo horizonte":"Belo Horizonte","salvador":"Salvador","recife":"Recife","fortaleza":"Fortaleza","porto alegre":"Porto Alegre"}
                for k,v in cities.items():
                    if k in msg_lower: city = v; break
                async with httpx.AsyncClient(timeout=30.0) as wc:
                    wr = await wc.get(f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_KEY}&units=metric&lang=pt_br")
                    wd = wr.json()
                    context += f"\n\nClima em {city}: {wd['weather'][0]['description']}, {wd['main']['temp']}°C, sensação {wd['main']['feels_like']}°C, umidade {wd['main']['humidity']}%, vento {wd['wind']['speed']}m/s"
            except: pass
        if any(w in msg_lower for w in ["noticia", "notícia", "noticias", "notícias", "news", "manchete", "jornal", "acontecendo", "novidades"]):
            try:
                async with httpx.AsyncClient(timeout=10.0) as nc:
                    nr = await nc.get(f"https://newsapi.org/v2/everything?q=brasil&language=pt&sortBy=publishedAt&pageSize=5&apiKey={NEWSAPI_KEY}")
                    nd = nr.json()
                    headlines = [f"- {a['title']} ({a['source']['name']})" for a in nd.get("articles", [])[:5]]
                    context += "\n\nNotícias do Brasil agora:\n" + "\n".join(headlines)
            except Exception as _we:
                pass
                pass
        if any(w in msg_lower for w in ["dolar", "dólar", "dollar", "cotacao", "cotação", "bitcoin", "btc", "euro", "moeda", "cambio", "câmbio"]):
            try:
                async with httpx.AsyncClient(timeout=10.0) as cc:
                    parts = []
                    r1 = await cc.get("https://open.er-api.com/v6/latest/USD")
                    d1 = r1.json()
                    brl = d1["rates"]["BRL"]
                    eur_usd = d1["rates"]["EUR"]
                    parts.append(f"Dólar: R${brl:.2f}")
                    parts.append(f"Euro: R${brl/eur_usd:.2f}")
                    if "bitcoin" in msg_lower or "btc" in msg_lower:
                        try:
                            r2 = await cc.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=brl")
                            d2 = r2.json()
                            parts.append(f"Bitcoin: R${d2['bitcoin']['brl']:,.0f}")
                        except Exception as _we:
                            pass
                            pass
                    context += "\n\nCotações agora:\n" + " | ".join(parts)
            except Exception as _we:
                pass
                pass
        if any(w in msg_lower for w in ["transito", "trânsito", "rota", "caminho", "chegar", "ir para", "ir pra", "distancia", "distância", "quanto tempo", "trajeto", "como chego", "até o", "ate o", "daqui", "longe", "perto", "percurso", "viagem"]):
            try:
                home = "Rua de Paiva 124, Miguel Pereira, RJ"
                origin = home
                if request.lat and request.lon:
                    origin = f"{request.lat},{request.lon}"
                dest = None
                # Extrair origem e destino: "de X até Y" ou "até Y"
                import re as _re
                m = _re2.search(r'(?:de|do|da)\s+(.+?)\s+(?:até|para|pra|ao|à)\s+(.+)', request.message, _re2.IGNORECASE)
                if m:
                    origin = m.group(1).strip().rstrip("?. ")
                    dest = m.group(2).strip().rstrip("?. ")
                else:
                    for p2 in ["até ", "para ", "pra ", "ao ", "à "]:
                        if p2 in msg_lower:
                            dest = request.message[msg_lower.index(p2)+len(p2):].strip().rstrip("?. ")
                            break
                # Resolver aliases
                for alias, addr in LOCAIS.items():
                    if origin and alias in origin.lower(): origin = addr
                    if dest and alias in dest.lower(): dest = addr
                if not dest: dest = request.message
                async with httpx.AsyncClient(timeout=10.0) as mc:
                    mr = await mc.post("https://routes.googleapis.com/directions/v2:computeRoutes",
                        headers={"Content-Type":"application/json","X-Goog-Api-Key":GOOGLE_MAPS_KEY,
                                 "X-Goog-FieldMask":"routes.duration,routes.distanceMeters,routes.description"},
                        json={"origin":{"address":origin} if "," not in str(origin) or not request.lat else {"location":{"latLng":{"latitude":request.lat,"longitude":request.lon}}},"destination":{"address":dest},
                              "travelMode":"DRIVE","routingPreference":"TRAFFIC_AWARE"})
                    md = mr.json()
                    if md.get("routes"):
                        r = md["routes"][0]
                        dist_m = r["distanceMeters"]; km = f"{dist_m/1000:.1f}km" if dist_m >= 1000 else f"{dist_m}m"
                        total_min = int(r["duration"].rstrip("s"))/60; tempo = f"{int(total_min//60)}h{int(total_min%60):02d}min" if total_min >= 60 else f"{int(total_min)} min"
                        desc = r.get("description","")
                        context += f"\n\nTrânsito de {origin} até {dest}: {km}, ~{tempo} com trânsito atual. Via {desc}"
            except Exception as _we:
                pass
                pass
        if any(w in msg_lower for w in ["gasto", "gastos", "despesa", "despesas", "receita", "receitas", "financ", "planilha", "pagamento", "pagamentos", "saldo", "quanto gastei", "extrato", "contas", "adiciona", "adicionar", "registra", "registrar", "apaga", "apagar", "deleta", "deletar", "altera", "alterar"]):
            try:
                svc = get_gmail_service()
                if svc:
                    from googleapiclient.discovery import build as _build
                    sheets = _build("sheets", "v4", credentials=gmail_credentials)
                    meta = sheets.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
                    sheet_names = [s["properties"]["title"] for s in meta["sheets"]]
                    all_data = {}
                    for sn in sheet_names:
                        result = sheets.spreadsheets().values().get(spreadsheetId=SHEET_ID, range=f"{sn}!A1:Z10000").execute()
                        rows = result.get("values", [])
                        if rows:
                            header = " | ".join(rows[0])
                            # Filtrar por mes atual ou mencionado
                            from datetime import datetime as _dt
                            now = _dt.now()
                            month_str = f"{now.month:02d}/{now.year}"
                            # Detectar mes na mensagem
                            meses = {"janeiro":"01","fevereiro":"02","marco":"03","março":"03","abril":"04","maio":"05","junho":"06","julho":"07","agosto":"08","setembro":"09","outubro":"10","novembro":"11","dezembro":"12"}
                            for mn, mv in meses.items():
                                if mn in msg_lower:
                                    month_str = f"{mv}/{now.year}"; break
                            filtered = [r for r in rows[1:] if len(r) > 0 and month_str in r[0]]
                            if not filtered:
                                filtered = rows[1:30]
                            # Resumir: total e detalhes
                            data_lines = ["  ".join(r) for r in filtered[:30]]
                            total_count = len(filtered)
                            all_data[sn] = f"Colunas: {header}\nTotal registros no periodo: {total_count}\n" + "\n".join(data_lines)
                    sheets_context = "\n\nPlanilha de gastos (abas: " + ", ".join(sheet_names) + "):\n"
                    for sn, data in all_data.items():
                        sheets_context += f"\n[Aba: {sn}]\n{data}\n"
                    # Se é comando de escrita, pedir ao GPT para gerar ação
                    is_write = any(w in msg_lower for w in ["adiciona", "adicionar", "registra", "registrar", "apaga", "apagar", "deleta", "deletar", "altera", "alterar", "coloca", "colocar", "lanca", "lançar", "lancar"])
                    if is_write:
                        sheets_context += "\nVocê pode modificar a planilha. Responda com JSON: {\"acao\": \"append|update|delete\", \"aba\": \"nome\", \"valores\": [\"col1\",\"col2\",...], \"celula\": \"A5\"(para update/delete)} seguido de uma confirmação amigável."
                    context += sheets_context
            except Exception as _we:
                pass
                pass
        if any(w in msg_lower for w in ["email", "e-mail", "gmail", "inbox", "caixa", "mensagem", "mensagens"]):
            try:
                svc = get_gmail_service()
                if svc:
                    results = svc.users().messages().list(userId="me", maxResults=5, labelIds=["INBOX"]).execute()
                    emails = []
                    for msg_item in results.get("messages", []):
                        detail = svc.users().messages().get(userId="me", id=msg_item["id"], format="metadata",
                                 metadataHeaders=["From", "Subject", "Date"]).execute()
                        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
                        emails.append(f"De: {headers.get('From','')} | Assunto: {headers.get('Subject','')} | {detail.get('snippet','')[:80]}")
                    context += "\n\nUltimos emails:\n" + "\n".join(emails)
            except Exception as _we:
                pass
                pass
        if any(w in msg_lower for w in ["agenda", "evento", "calendario", "compromisso", "reuniao", "semana", "amanha", "hoje", "proximo", "aniversario"]):
            try:
                svc = get_gmail_service()
                if svc:
                    cal = build("calendar", "v3", credentials=gmail_credentials)
                    now = datetime.utcnow()
                    from datetime import timedelta
                    days = 30 if "aniversario" in msg_lower or "mes" in msg_lower else 7
                    time_min = now.isoformat() + "Z"
                    time_max = (now + timedelta(days=days)).isoformat() + "Z"
                    calendars = cal.calendarList().list().execute()
                    cal_events = []
                    for c in calendars.get("items", []):
                        try:
                            evts = cal.events().list(calendarId=c["id"], timeMin=time_min, timeMax=time_max,
                                                      maxResults=20, singleEvents=True, orderBy="startTime").execute()
                            for e in evts.get("items", []):
                                start = e["start"].get("dateTime", e["start"].get("date", ""))
                                cal_events.append(f"{start} - {e.get('summary','')} ({c.get('summary','')})")
                        except Exception as _we:
                            pass
                            pass
                    cal_events.sort()
                    context += "\n\nEventos da agenda:\n" + "\n".join(cal_events) if cal_events else ""
            except Exception as _we:
                pass
                pass
        
        # Injetar instrução dinâmica
        if not is_finance and any(w in msg_lower for w in ["lembr", "remind", "avisa", "avise"]):
            context += '\n\nINSTRUÇÃO: Extraia o lembrete e responda APENAS com JSON: {"lembrete": "texto", "quando": "YYYY-MM-DD HH:MM"}. Se não souber a hora, use 09:00.'
        if is_finance and any(w in msg_lower for w in ["adiciona", "registra", "coloca", "lanca", "lança"]):
            context += '\n\nINSTRUÇÃO: Para adicionar na planilha, responda APENAS com JSON: {"acao": "append", "aba": "nome_da_aba", "valores": ["col1","col2",...]}. Use as colunas existentes.'
        if is_finance and any(w in msg_lower for w in ["apaga", "deleta", "remove"]):
            context += '\n\nINSTRUÇÃO: Para deletar da planilha, responda APENAS com JSON: {"acao": "delete", "aba": "nome_da_aba", "celula": "A5:Z5"}.'
        if is_finance and any(w in msg_lower for w in ["altera", "muda", "corrige", "atualiza"]):
            context += '\n\nINSTRUÇÃO: Para alterar na planilha, responda APENAS com JSON: {"acao": "update", "aba": "nome_da_aba", "celula": "A5", "valores": ["col1","col2",...]}.'
        
        if any(w in msg_lower for w in ["whatsapp", "zap", "manda mensagem", "envia mensagem", "manda msg", "fala pra", "avisa", "me liga", "envia pra", "envie pra", "enviar pra", "manda pra", "mandar pra", "falar pra", "avisar", "mensagem pra", "mensagem para", "envia para", "envie para", "enviar para", "manda para", "mandar para", "fala para", "falar para"]):
            context += '\nINSTRUÇÃO: Para enviar WhatsApp, responda APENAS com JSON: {"whatsapp": "nome_do_contato", "mensagem": "texto"}. Use o nome como o usuário falou.'
        
        # Gerar resposta
        response = await call_ollama(request.message, context)
        response = "".join(c for c in response if ord(c) <= 0x024F or ord(c) == 0x00B0).strip()
        
        # Verificar se resposta contém envio de WhatsApp
        CONTATOS_ZAP = {"amor": "5524998826028", "marcelo": "5521960192189", "mel": "5521980078829"}
        if any(w in msg_lower for w in ["whatsapp", "zap", "manda mensagem", "envia mensagem", "manda msg", "fala pra", "envia pra", "envie pra", "enviar pra", "manda pra", "mandar pra", "falar pra", "avisar", "mensagem pra", "mensagem para", "envia para", "envie para", "enviar para", "manda para", "mandar para", "fala para", "falar para"]):
            try:
                import json as _jw
                if "{" in response and "whatsapp" in response:
                    start = response.index("{")
                    end = response.rindex("}") + 1
                    wdata = _jw.loads(response[start:end])
                    contact_name = wdata.get("whatsapp", "")
                    msg_text = wdata.get("mensagem", "")
                    number = CONTATOS_ZAP.get(contact_name.lower(), "")
                    if not number:
                        async with httpx.AsyncClient(timeout=10.0) as wc:
                            for variant in [contact_name, contact_name.title(), contact_name.upper()]:
                                cr = await wc.post(f"{EVO_URL}/chat/findContacts/{EVO_INSTANCE}",
                                    headers={"apikey": EVO_KEY, "Content-Type": "application/json"},
                                    json={"where":{"pushName": variant}})
                                found = cr.json()
                                if found:
                                    number = found[0].get("remoteJid","").replace("@s.whatsapp.net","")
                                    break
                    if number:
                        async with httpx.AsyncClient(timeout=10.0) as wc:
                            await wc.post(f"{EVO_URL}/message/sendText/{EVO_INSTANCE}",
                                headers={"apikey": EVO_KEY, "Content-Type": "application/json"},
                                json={"number": number, "text": msg_text})
                        response = f"Mensagem enviada pra {contact_name}: {msg_text}"
                    else:
                        response = f"Nao achei o contato {contact_name} no WhatsApp."
            except Exception as _we:
                pass
        # Verificar se resposta contém ação de planilha
        if any(w in msg_lower for w in ["adiciona", "registra", "apaga", "deleta", "altera", "coloca", "lanca", "lança"]):
            try:
                import json as _j2
                if "{" in response and "acao" in response:
                    start = response.index("{")
                    end = response.rindex("}") + 1
                    act = _j2.loads(response[start:end])
                    svc = get_gmail_service()
                    if svc:
                        from googleapiclient.discovery import build as _build2
                        sheets = _build2("sheets", "v4", credentials=gmail_credentials)
                        if act["acao"] == "append":
                            sheets.spreadsheets().values().append(
                                spreadsheetId=SHEET_ID, range=f"{act['aba']}!A1",
                                valueInputOption="USER_ENTERED",
                                body={"values": [act["valores"]]}).execute()
                        elif act["acao"] == "update" and "celula" in act:
                            sheets.spreadsheets().values().update(
                                spreadsheetId=SHEET_ID, range=f"{act['aba']}!{act['celula']}",
                                valueInputOption="USER_ENTERED",
                                body={"values": [act["valores"]]}).execute()
                        elif act["acao"] == "delete" and "celula" in act:
                            sheets.spreadsheets().values().clear(
                                spreadsheetId=SHEET_ID, range=f"{act['aba']}!{act['celula']}").execute()
                        # Limpar o JSON da resposta
                        response = response[:start].strip() or response[end:].strip() or "Feito!"
            except Exception as _we:
                pass
                pass
        # Verificar se resposta contém lembrete JSON
            try:
                import json as _json
                # Tentar extrair JSON da resposta
                if "{" in response and "lembrete" in response:
                    start = response.index("{")
                    end = response.rindex("}") + 1
                    reminder = _json.loads(response[start:end])
                    conn2 = get_db()
                    cur2 = conn2.cursor()
                    cur2.execute("INSERT INTO reminders (text, remind_at) VALUES (%s, %s)",
                                (reminder["lembrete"], reminder["quando"]))
                    conn2.commit()
                    cur2.close()
                    conn2.close()
                    response = f"Beleza, vou te lembrar: {reminder['lembrete']} em {reminder['quando']}."
            except Exception as _we:
                pass
                pass
        
        # Salvar conversa
        save_conversation(request.user_id, request.message, response)
        
        # Cachear resposta
        cache_response(request.message, response)
        
        return ChatResponse(
            response=response,
            context_used=len(memories),
            cached=False
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
            "timestamp": str(r[2])
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
    cur.execute("SELECT COUNT(*) FROM conversations WHERE DATE(timestamp) = CURRENT_DATE")
    today_conversations = cur.fetchone()[0]
    
    # Lembretes ativos
    cur.execute("SELECT COUNT(*) FROM reminders WHERE NOT triggered")
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
    if REDIS_AVAILABLE:
        redis_client.set("gmail_token", json.dumps({
            "token": gmail_credentials.token,
            "refresh_token": gmail_credentials.refresh_token,
            "token_uri": gmail_credentials.token_uri,
            "client_id": gmail_credentials.client_id,
            "client_secret": gmail_credentials.client_secret}))
    return {"status": "Gmail conectado com sucesso! Pode fechar esta aba."}

def get_gmail_service():
    global gmail_credentials
    if not gmail_credentials and REDIS_AVAILABLE:
        saved = redis_client.get("gmail_token")
        if saved:
            data = json.loads(saved)
            gmail_credentials = Credentials(**data)
    if not gmail_credentials:
        return None
    if gmail_credentials.expired and gmail_credentials.refresh_token:
        from google.auth.transport.requests import Request
        gmail_credentials.refresh(Request())
        if REDIS_AVAILABLE:
            redis_client.set("gmail_token", json.dumps({"token": gmail_credentials.token, "refresh_token": gmail_credentials.refresh_token, "token_uri": gmail_credentials.token_uri, "client_id": gmail_credentials.client_id, "client_secret": gmail_credentials.client_secret}))
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
