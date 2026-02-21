from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import psycopg2
import httpx
import os
from datetime import datetime
from typing import Optional

# Configuração
API_KEY = os.getenv("API_KEY", "change-this-key")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "change_this_password")

app = FastAPI(title="Jarvis API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Alterar para seu domínio em produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir PWA
app.mount("/static", StaticFiles(directory="pwa"), name="static")

# Models
class ChatRequest(BaseModel):
    message: str
    user_id: str = "default"

class ChatResponse(BaseModel):
    response: str
    context_used: int = 0

# Database
def get_db():
    return psycopg2.connect(
        host="localhost",
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
            "http://localhost:11434/api/generate",
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
    return {"status": "online", "service": "Jarvis API"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    authenticated: bool = Depends(verify_api_key)
):
    try:
        # Buscar contexto
        memories = search_memory(request.message)
        context = "\n".join([m["content"] for m in memories])
        
        # Gerar resposta
        response = await call_ollama(request.message, context)
        
        # Salvar conversa
        save_conversation(request.user_id, request.message, response)
        
        return ChatResponse(
            response=response,
            context_used=len(memories)
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
