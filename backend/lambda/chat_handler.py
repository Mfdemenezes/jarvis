import json
import os
import boto3
import psycopg2
import requests
from datetime import datetime

# Configurações
ORACLE_VM_IP = os.environ['ORACLE_VM_IP']
POSTGRES_PASSWORD = os.environ['POSTGRES_PASSWORD']
DYNAMODB_TABLE = os.environ['DYNAMODB_TABLE']

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE)

def get_db_connection():
    """Conecta ao PostgreSQL na Oracle VM"""
    return psycopg2.connect(
        host=ORACLE_VM_IP,
        database="personal_kb",
        user="assistant",
        password=POSTGRES_PASSWORD,
        port=5432
    )

def search_memory(query, limit=5):
    """Busca memórias relevantes usando embeddings"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Gerar embedding da query (simplificado - use API real)
    # embedding = generate_embedding(query)
    
    # Buscar memórias similares
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

def call_ollama(prompt, context=""):
    """Chama Ollama na Oracle VM"""
    url = f"http://{ORACLE_VM_IP}:11434/api/generate"
    
    full_prompt = f"""Você é um assistente pessoal inteligente.

Contexto relevante:
{context}

Usuário: {prompt}

Assistente:"""
    
    response = requests.post(url, json={
        "model": "llama3.1:8b",
        "prompt": full_prompt,
        "stream": False
    })
    
    return response.json()['response']

def save_conversation(user_id, user_message, assistant_response):
    """Salva conversa no DynamoDB e PostgreSQL"""
    timestamp = int(datetime.now().timestamp())
    
    # DynamoDB (cache recente - 30 dias TTL)
    table.put_item(Item={
        'user_id': user_id,
        'timestamp': timestamp,
        'user_message': user_message,
        'assistant_response': assistant_response,
        'ttl': timestamp + (30 * 24 * 60 * 60)  # 30 dias
    })
    
    # PostgreSQL (permanente)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO conversations (user_message, assistant_response, metadata)
        VALUES (%s, %s, %s)
    """, (user_message, assistant_response, json.dumps({'user_id': user_id})))
    conn.commit()
    cur.close()
    conn.close()

def handler(event, context):
    """Handler principal da Lambda"""
    try:
        body = json.loads(event['body'])
        user_id = body.get('user_id', 'default')
        message = body['message']
        
        # Buscar contexto relevante
        memories = search_memory(message)
        context = "\n".join([m['content'] for m in memories])
        
        # Gerar resposta
        response = call_ollama(message, context)
        
        # Salvar conversa
        save_conversation(user_id, message, response)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'response': response,
                'context_used': len(memories)
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
