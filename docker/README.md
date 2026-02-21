# 🐳 Jarvis - Versão Docker

Versão containerizada com nomenclatura organizada.

## 📦 Containers

```
jarvis-db       → PostgreSQL + pgvector (banco de dados)
jarvis-llm      → Ollama (modelo de linguagem)
jarvis-app      → FastAPI (API backend)
jarvis-web      → Nginx (servidor web + PWA)
jarvis-cache    → Redis (cache opcional)
```

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────┐
│  iPhone / Apple Watch                   │
└──────────────┬──────────────────────────┘
               │ HTTPS
               ▼
┌─────────────────────────────────────────┐
│  Cloudflare Tunnel                      │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  jarvis-web (Nginx)                     │
│  - Serve PWA                            │
│  - Proxy reverso                        │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  jarvis-app (FastAPI)                   │
│  - API REST                             │
│  - Lógica de negócio                    │
└──────┬───────────────┬──────────────────┘
       │               │
       ▼               ▼
┌─────────────┐  ┌─────────────┐
│ jarvis-llm  │  │ jarvis-db   │
│ (Ollama)    │  │ (PostgreSQL)│
└─────────────┘  └─────────────┘
       │
       ▼
┌─────────────┐
│jarvis-cache │
│  (Redis)    │
└─────────────┘
```

## 🚀 Setup Rápido

### Pré-requisitos

- Docker 20.10+
- Docker Compose 2.0+
- Oracle VM com 24GB RAM
- 50GB de espaço em disco

### Passo 1: Preparar Arquivos

```bash
cd ~/Projeto/personal-assistant/docker

# Copiar exemplo de .env
cp .env.example .env

# Gerar API Key
openssl rand -hex 32

# Editar .env
nano .env
```

**Configurar .env:**
```bash
API_KEY=sua_chave_gerada_aqui
POSTGRES_PASSWORD=sua_senha_forte_aqui
```

### Passo 2: Copiar para Oracle VM

```bash
# No seu Mac
export ORACLE_IP="seu.ip.oracle.aqui"

scp -r ../docker ubuntu@$ORACLE_IP:~/jarvis/
scp -r ../pwa ubuntu@$ORACLE_IP:~/jarvis/
```

### Passo 3: Iniciar Containers

```bash
# Na Oracle VM
ssh ubuntu@$ORACLE_IP

cd ~/jarvis/docker

# Iniciar todos os containers
docker-compose up -d

# Ver logs
docker-compose logs -f
```

### Passo 4: Baixar Modelo Ollama

```bash
# Aguarde jarvis-llm iniciar (~2 min)
docker-compose logs -f jarvis-llm

# Baixar modelo
docker exec -it jarvis-llm ollama pull llama3.1:8b

# Aguarde download (~5GB, ~10 min)
```

### Passo 5: Testar

```bash
# Health check
curl http://localhost/health

# Deve retornar:
# {
#   "status": "healthy",
#   "database": "connected",
#   "llm": "ready",
#   "cache": "available"
# }
```

## 🔧 Comandos Úteis

### Ver Status

```bash
# Todos os containers
docker-compose ps

# Logs de todos
docker-compose logs -f

# Logs de um específico
docker-compose logs -f jarvis-app
```

### Gerenciar Containers

```bash
# Iniciar
docker-compose up -d

# Parar
docker-compose stop

# Reiniciar
docker-compose restart

# Parar e remover
docker-compose down

# Parar e remover TUDO (incluindo volumes)
docker-compose down -v
```

### Acessar Containers

```bash
# jarvis-app
docker exec -it jarvis-app bash

# jarvis-db
docker exec -it jarvis-db psql -U assistant -d personal_kb

# jarvis-llm
docker exec -it jarvis-llm bash

# jarvis-cache
docker exec -it jarvis-cache redis-cli
```

### Ver Recursos

```bash
# Uso de CPU/RAM
docker stats

# Espaço em disco
docker system df

# Volumes
docker volume ls
```

## 📊 Containers Detalhados

### jarvis-db (PostgreSQL)

**Imagem:** `pgvector/pgvector:pg15`  
**Porta:** 5432  
**Volume:** `jarvis-db-data`

**Acessar:**
```bash
docker exec -it jarvis-db psql -U assistant -d personal_kb
```

**Backup:**
```bash
docker exec jarvis-db pg_dump -U assistant personal_kb > backup.sql
```

**Restore:**
```bash
cat backup.sql | docker exec -i jarvis-db psql -U assistant -d personal_kb
```

### jarvis-llm (Ollama)

**Imagem:** `ollama/ollama:latest`  
**Porta:** 11434  
**Volume:** `jarvis-llm-data`

**Modelos disponíveis:**
```bash
docker exec jarvis-llm ollama list
```

**Baixar novo modelo:**
```bash
docker exec jarvis-llm ollama pull mistral:7b
```

**Testar modelo:**
```bash
docker exec jarvis-llm ollama run llama3.1:8b "Olá, como você está?"
```

### jarvis-app (FastAPI)

**Imagem:** Custom (build local)  
**Porta:** 8000  
**Código:** `/app`

**Ver logs:**
```bash
docker-compose logs -f jarvis-app
```

**Reiniciar após mudança de código:**
```bash
docker-compose restart jarvis-app
```

**Rebuild:**
```bash
docker-compose build jarvis-app
docker-compose up -d jarvis-app
```

### jarvis-web (Nginx)

**Imagem:** `nginx:alpine`  
**Portas:** 80, 443  
**PWA:** `/usr/share/nginx/html`

**Atualizar PWA:**
```bash
# Copiar novos arquivos
scp -r ../pwa/* ubuntu@$ORACLE_IP:~/jarvis/pwa/

# Reiniciar
docker-compose restart jarvis-web
```

**Ver logs de acesso:**
```bash
docker exec jarvis-web tail -f /var/log/nginx/access.log
```

### jarvis-cache (Redis)

**Imagem:** `redis:7-alpine`  
**Porta:** 6379  
**Volume:** `jarvis-cache-data`

**Acessar:**
```bash
docker exec -it jarvis-cache redis-cli
```

**Ver cache:**
```bash
docker exec jarvis-cache redis-cli KEYS "*"
```

**Limpar cache:**
```bash
docker exec jarvis-cache redis-cli FLUSHALL
```

## 🔒 Segurança

### Rede Isolada

Todos os containers estão na rede `jarvis-network`. Apenas `jarvis-web` expõe portas públicas.

### Secrets

Nunca commite o arquivo `.env`. Use `.env.example` como template.

### Firewall

```bash
# Apenas porta 80 pública
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --reload
```

### Atualizar Senhas

```bash
# Editar .env
nano .env

# Recriar containers
docker-compose down
docker-compose up -d
```

## 📈 Monitoramento

### Healthchecks

Todos os containers têm healthchecks configurados:

```bash
# Ver status de saúde
docker-compose ps
```

### Logs Centralizados

```bash
# Todos os logs
docker-compose logs -f

# Últimas 100 linhas
docker-compose logs --tail=100

# Desde tempo específico
docker-compose logs --since 30m
```

### Métricas

```bash
# Uso de recursos
docker stats

# Específico
docker stats jarvis-app jarvis-llm
```

## 🔧 Troubleshooting

### Container não inicia

```bash
# Ver logs
docker-compose logs jarvis-app

# Ver eventos
docker events --filter container=jarvis-app

# Inspecionar
docker inspect jarvis-app
```

### Banco de dados não conecta

```bash
# Verificar se está rodando
docker-compose ps jarvis-db

# Ver logs
docker-compose logs jarvis-db

# Testar conexão
docker exec jarvis-db pg_isready -U assistant
```

### Ollama lento

```bash
# Verificar RAM
docker stats jarvis-llm

# Usar modelo menor
docker exec jarvis-llm ollama pull llama3.1:8b
```

### Sem espaço em disco

```bash
# Limpar imagens não usadas
docker image prune -a

# Limpar volumes não usados
docker volume prune

# Limpar tudo
docker system prune -a --volumes
```

## 🚀 Cloudflare Tunnel

```bash
# Instalar cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/

# Configurar (mesmo processo da versão sem Docker)
cloudflared tunnel login
cloudflared tunnel create jarvis
cloudflared tunnel route dns jarvis seu-dominio.com

# Criar config
mkdir -p ~/.cloudflared
nano ~/.cloudflared/config.yml
```

**config.yml:**
```yaml
tunnel: SEU_TUNNEL_ID
credentials-file: /home/ubuntu/.cloudflared/SEU_TUNNEL_ID.json

ingress:
  - hostname: seu-dominio.com
    service: http://localhost:80
  - service: http_status:404
```

**Criar serviço:**
```bash
sudo nano /etc/systemd/system/cloudflared.service
```

```ini
[Unit]
Description=Cloudflare Tunnel
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=ubuntu
ExecStart=/usr/local/bin/cloudflared tunnel run jarvis
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

## 📊 Comparação: Docker vs Nativo

| Aspecto | Docker | Nativo |
|---------|--------|--------|
| **Setup** | Mais rápido | Mais lento |
| **Isolamento** | Melhor | Menor |
| **RAM** | ~20GB livre | ~22GB livre |
| **Performance** | Boa | Melhor |
| **Manutenção** | Mais fácil | Mais difícil |
| **Portabilidade** | Alta | Baixa |
| **Backup** | Volumes | Arquivos |

## 💰 Recursos

**Oracle Free Tier (24GB RAM):**
- jarvis-db: ~2GB
- jarvis-llm: ~16GB (modelo 8B)
- jarvis-app: ~500MB
- jarvis-web: ~50MB
- jarvis-cache: ~100MB
- Sistema: ~2GB
- **Livre: ~3GB**

## 🎯 Próximos Passos

1. ✅ Containers rodando
2. ✅ Modelo baixado
3. ✅ Health check OK
4. ✅ Cloudflare Tunnel configurado
5. ✅ PWA instalado no iPhone
6. ✅ Atalhos configurados

---

**Versão:** 2.0 (Docker)  
**Containers:** 5  
**Custo:** $0/mês
