# 🐳 Jarvis com Docker - Resumo

## ✅ Containers Criados

```
jarvis-db       → PostgreSQL 15 + pgvector
jarvis-llm      → Ollama (Llama 3.1 8B)
jarvis-app      → FastAPI (Python 3.11)
jarvis-web      → Nginx (Alpine)
jarvis-cache    → Redis 7 (opcional)
```

## 🚀 Setup em 3 Comandos

```bash
# 1. Copiar para Oracle VM
scp -r docker pwa ubuntu@SEU_IP:~/jarvis/

# 2. Conectar e executar
ssh ubuntu@SEU_IP
cd ~/jarvis/docker
./setup.sh

# 3. Aguardar (~15 min)
# Script faz tudo automaticamente!
```

## 📊 O Que o Script Faz

1. ✅ Instala Docker e Docker Compose
2. ✅ Gera API Key e senhas automaticamente
3. ✅ Cria arquivo .env
4. ✅ Inicia todos os containers
5. ✅ Aguarda serviços ficarem prontos
6. ✅ Baixa modelo Llama 3.1 (8B)
7. ✅ Testa health check
8. ✅ Configura firewall

## 🎯 Vantagens da Versão Docker

### vs Versão Nativa

| Aspecto | Docker | Nativo |
|---------|--------|--------|
| **Setup** | 15 min | 30 min |
| **Isolamento** | ✅ Completo | ⚠️ Parcial |
| **Portabilidade** | ✅ Alta | ❌ Baixa |
| **Backup** | ✅ Volumes | 📁 Arquivos |
| **Atualização** | ✅ Fácil | ⚠️ Manual |
| **Rollback** | ✅ Instantâneo | ❌ Difícil |
| **RAM** | 20GB livre | 22GB livre |
| **Performance** | 95% | 100% |

### Quando Usar Docker

✅ **Use Docker se:**
- Quer setup mais rápido
- Precisa de isolamento
- Quer facilidade de backup
- Planeja migrar para outro servidor
- Quer testar mudanças facilmente

❌ **Use Nativo se:**
- Quer máxima performance
- Tem pouca RAM disponível
- Prefere controle total
- Não quer overhead de containers

## 📁 Estrutura de Arquivos

```
docker/
├── docker-compose.yml      # Orquestração
├── Dockerfile              # Build jarvis-app
├── main.py                 # API FastAPI
├── requirements.txt        # Dependências Python
├── nginx.conf              # Config Nginx
├── init-db.sql            # Schema PostgreSQL
├── setup.sh               # Setup automatizado
├── .env.example           # Template de variáveis
├── .dockerignore          # Arquivos ignorados
└── README.md              # Documentação completa
```

## 🔧 Comandos Essenciais

```bash
# Ver status
docker-compose ps

# Ver logs
docker-compose logs -f

# Reiniciar tudo
docker-compose restart

# Parar tudo
docker-compose stop

# Iniciar tudo
docker-compose up -d

# Remover tudo (CUIDADO!)
docker-compose down -v

# Acessar container
docker exec -it jarvis-app bash

# Ver recursos
docker stats
```

## 🔒 Segurança

### Rede Isolada
- Containers na rede `jarvis-network`
- Apenas `jarvis-web` expõe porta 80
- Comunicação interna via DNS

### Secrets
- API Key e senhas no `.env`
- Nunca commitar `.env`
- Geração automática de credenciais

### Healthchecks
- Todos os containers monitorados
- Restart automático se falhar
- Logs centralizados

## 💾 Volumes Persistentes

```
jarvis-db-data      → Dados PostgreSQL
jarvis-llm-data     → Modelos Ollama
jarvis-cache-data   → Cache Redis
```

**Backup:**
```bash
# Backup de tudo
docker-compose down
sudo tar -czf jarvis-backup.tar.gz \
  /var/lib/docker/volumes/jarvis-*

# Restore
sudo tar -xzf jarvis-backup.tar.gz -C /
docker-compose up -d
```

## 📊 Uso de Recursos

**Oracle Free Tier (24GB RAM):**
```
jarvis-db:     ~2GB   (PostgreSQL)
jarvis-llm:    ~16GB  (Llama 3.1 8B)
jarvis-app:    ~500MB (FastAPI)
jarvis-web:    ~50MB  (Nginx)
jarvis-cache:  ~100MB (Redis)
Sistema:       ~2GB   (Ubuntu)
Docker:        ~500MB (Overhead)
─────────────────────
Livre:         ~3GB
```

## 🎯 Próximos Passos

Depois do setup:

1. ✅ **Cloudflare Tunnel**
   ```bash
   # Ver README.md seção Cloudflare Tunnel
   ```

2. ✅ **PWA no iPhone**
   - Acessar https://seu-dominio.com
   - Adicionar à tela inicial

3. ✅ **Atalhos da Apple**
   - Ver `../ATALHOS_APPLE.md`

4. ✅ **Testar**
   ```bash
   curl http://localhost/health
   ```

## 🆘 Troubleshooting Rápido

### Container não inicia
```bash
docker-compose logs jarvis-app
docker-compose restart jarvis-app
```

### Sem memória
```bash
docker stats
# Se jarvis-llm > 18GB, usar modelo menor
docker exec jarvis-llm ollama pull phi3:mini
```

### Banco não conecta
```bash
docker exec jarvis-db pg_isready -U assistant
docker-compose restart jarvis-db
```

### Limpar espaço
```bash
docker system prune -a --volumes
```

## 📚 Documentação Completa

- **[README.md](README.md)** - Guia completo
- **[../COMECE_AQUI.md](../COMECE_AQUI.md)** - Visão geral
- **[../ATALHOS_APPLE.md](../ATALHOS_APPLE.md)** - Atalhos
- **[../EXEMPLOS_USO.md](../EXEMPLOS_USO.md)** - Como usar

## 💡 Dicas

1. **Sempre use `docker-compose`** (não `docker` direto)
2. **Monitore recursos** com `docker stats`
3. **Faça backup** dos volumes regularmente
4. **Veja logs** quando algo der errado
5. **Use `.env`** para todas as configurações

## 🎉 Resultado Final

Depois do setup você terá:

✅ 5 containers rodando  
✅ Jarvis API funcionando  
✅ PWA servido pelo Nginx  
✅ Banco de dados com pgvector  
✅ LLM local (Ollama)  
✅ Cache Redis  
✅ Backups fáceis  
✅ Isolamento completo  
✅ Custo: $0/mês  

---

**Tempo de setup:** ~15 minutos  
**Dificuldade:** ⭐⭐ (Fácil)  
**Custo:** $0/mês
