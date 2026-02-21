from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import psycopg2
import httpx
import os
from datetime import datetime
from typing import Optional
import redis

# Configuração
API_KEY = os.getenv("API_KEY", "change-this-key")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "jarvis-db")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "change_this_password")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "jarvis-llm")
REDIS_HOST = os.getenv("REDIS_HOST", "jarvis-cache")

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

# Chamar Ollama
async def call_ollama(prompt: str, context: str = ""):
    full_prompt = f"""Você é Jarvis, um assistente pessoal inteligente e prestativo.

Contexto relevante:
{context}

Usuário: {prompt}

Jarvis:"""
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"http://{OLLAMA_HOST}:11434/api/generate",
            json={
                "model": "llama3.1:8b",
                "prompt": full_prompt,
                "stream": False
            }
        )
        return response.json()["response"]

# Salvar conversa
def save_conversation(user_id: str, user_message: str, assistant_response: str):
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO conversations (user_message, assistant_response, metadata)
        VALUES (%s, %s, %s)
    """, (user_message, assistant_response, {"user_id": user_id, "timestamp": datetime.now().isoformat()}))
    
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
        context = "\n".join([m["content"] for m in memories])
        
        # Gerar resposta
        response = await call_ollama(request.message, context)
        
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
        SELECT user_message, assistant_response, timestamp
        FROM conversations
        ORDER BY timestamp DESC
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
