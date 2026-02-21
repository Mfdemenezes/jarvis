# Oracle VM Only - Setup Completo

Versão simplificada sem AWS. Custo: **$0/mês**

## Arquitetura

```
┌─────────────────────────────────────┐
│  iPhone / Apple Watch               │
│  - PWA (Safari)                     │
│  - Atalhos da Apple                 │
└──────────────┬──────────────────────┘
               │ HTTPS
               ▼
┌─────────────────────────────────────┐
│  Cloudflare Tunnel (grátis)         │
│  - SSL automático                   │
│  - DDoS protection                  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Oracle Cloud VM (free tier)        │
│  ┌───────────────────────────────┐  │
│  │  Nginx (reverse proxy)        │  │
│  └──────────┬────────────────────┘  │
│             │                        │
│  ┌──────────▼────────────────────┐  │
│  │  FastAPI (Python)             │  │
│  │  - Autenticação (API Key)     │  │
│  │  - Rate limiting              │  │
│  └──┬───────────────────┬────────┘  │
│     │                   │            │
│  ┌──▼──────┐     ┌─────▼──────┐    │
│  │ Ollama  │     │ PostgreSQL │    │
│  │ (LLM)   │     │ + pgvector │    │
│  └─────────┘     └────────────┘    │
└─────────────────────────────────────┘
```

## Pré-requisitos

1. **Oracle Cloud Account** (grátis)
   - VM criada (4 vCPU, 24GB RAM - free tier)
   - IP público configurado
   - Acesso SSH

2. **Cloudflare Account** (grátis)
   - Domínio configurado (pode usar subdomínio grátis)

3. **iPhone/iPad** com iOS 14+

## Instalação

### Passo 1: Preparar Arquivos Localmente

```bash
cd Projeto/personal-assistant/oracle-only

# Gerar API Key
openssl rand -hex 32 > api_key.txt
echo "Salve esta key em local seguro!"
cat api_key.txt
```

### Passo 2: Copiar para Oracle VM

```bash
# Substitua IP_ORACLE pelo seu IP
export ORACLE_IP="seu.ip.aqui"

# Copiar arquivos
scp setup.sh main.py requirements.txt ubuntu@$ORACLE_IP:~/
scp -r ../pwa ubuntu@$ORACLE_IP:~/
```

### Passo 3: Executar Setup na VM

```bash
# Conectar na VM
ssh ubuntu@$ORACLE_IP

# Executar setup
chmod +x setup.sh
./setup.sh

# Aguarde ~15 minutos (download do modelo Llama)
```

O script vai:
- ✅ Instalar PostgreSQL + pgvector
- ✅ Instalar Ollama + Llama 3.1
- ✅ Instalar Python + FastAPI
- ✅ Configurar Nginx
- ✅ Criar serviço systemd
- ✅ Configurar firewall
- ✅ Gerar API Key

### Passo 4: Configurar Senhas

```bash
# Ainda na VM

# 1. Alterar senha do PostgreSQL
sudo -u postgres psql
ALTER USER assistant WITH PASSWORD 'sua_senha_forte_aqui';
\q

# 2. Atualizar .env
nano ~/jarvis/.env
# Altere:
# API_KEY=sua_key_do_passo1
# POSTGRES_PASSWORD=sua_senha_forte_aqui

# 3. Reiniciar serviço
sudo systemctl restart jarvis

# 4. Testar
curl http://localhost:8000/health
# Deve retornar: {"status":"healthy"}
```

### Passo 5: Configurar Cloudflare Tunnel

```bash
# Ainda na VM

# 1. Instalar cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/

# 2. Login (vai abrir navegador)
cloudflared tunnel login

# 3. Criar tunnel
cloudflared tunnel create jarvis

# Anote o TUNNEL_ID que aparece

# 4. Configurar DNS
cloudflared tunnel route dns jarvis seu-dominio.com

# 5. Criar arquivo de config
mkdir -p ~/.cloudflared
nano ~/.cloudflared/config.yml
```

Cole no arquivo:
```yaml
tunnel: TUNNEL_ID_AQUI
credentials-file: /home/ubuntu/.cloudflared/TUNNEL_ID_AQUI.json

ingress:
  - hostname: seu-dominio.com
    service: http://localhost:80
  - service: http_status:404
```

```bash
# 6. Testar tunnel
cloudflared tunnel run jarvis

# Se funcionar, Ctrl+C e criar serviço

# 7. Criar serviço systemd
sudo nano /etc/systemd/system/cloudflared.service
```

Cole:
```ini
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
Type=simple
User=ubuntu
ExecStart=/usr/local/bin/cloudflared tunnel run jarvis
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 8. Iniciar serviço
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
sudo systemctl status cloudflared
```

### Passo 6: Testar Acesso

```bash
# No seu Mac/PC
curl https://seu-dominio.com/health
# Deve retornar: {"status":"healthy"}

# Testar chat
curl -X POST https://seu-dominio.com/chat \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: SUA_API_KEY" \
  -d '{"message": "Olá, como você está?"}'
```

### Passo 7: Configurar PWA no iPhone

1. Abra Safari: `https://seu-dominio.com`
2. Toque em "Compartilhar" (ícone de compartilhar)
3. Role e toque em "Adicionar à Tela de Início"
4. Nomeie como "Jarvis"
5. Toque em "Adicionar"

**Configurar API Key no PWA:**

1. Abra o PWA
2. Edite o arquivo `index.html` (via SSH):
   ```bash
   nano ~/jarvis/pwa/index.html
   ```
3. Encontre a linha:
   ```javascript
   const API_KEY = 'SUA_API_KEY_AQUI';
   ```
4. Substitua pela sua API Key
5. Salve e recarregue o PWA

### Passo 8: Configurar Atalhos da Apple

Ver guia completo: `../ATALHOS_APPLE.md`

**Resumo:**

1. Abra app **Atalhos**
2. Crie novo atalho "Jarvis"
3. Adicione ações:
   - **Ditar Texto**
   - **Obter Conteúdo de URL**
     - URL: `https://seu-dominio.com/chat`
     - Método: POST
     - Cabeçalhos:
       - `Content-Type`: `application/json`
       - `X-Api-Key`: `SUA_API_KEY`
     - Corpo: `{"message": "Texto Ditado"}`
   - **Obter Dicionário**
   - **Obter Valor** (chave: `response`)
   - **Falar Texto**
4. Adicionar à Siri: "Hey Siri, Jarvis"

## Uso

### PWA (iPhone)

1. Toque no ícone "Jarvis" na tela inicial
2. Toque no microfone 🎤 ou digite
3. Fale/digite sua mensagem
4. Receba resposta em voz e texto

### Atalhos (iPhone/Watch)

1. "Hey Siri, Jarvis"
2. Fale seu comando
3. Receba resposta em voz

### Apple Watch

1. Levante o pulso
2. "Hey Siri, Jarvis"
3. Fale seu comando

Ou:

1. Abra app Atalhos no Watch
2. Toque em "Jarvis"
3. Fale seu comando

## Manutenção

### Ver Status

```bash
# Todos os serviços
sudo systemctl status jarvis
sudo systemctl status nginx
sudo systemctl status postgresql
sudo systemctl status ollama
sudo systemctl status cloudflared
```

### Ver Logs

```bash
# API
sudo journalctl -u jarvis -f

# Nginx
sudo tail -f /var/log/nginx/access.log

# Cloudflare
sudo journalctl -u cloudflared -f
```

### Backup

```bash
# Manual
~/backup.sh

# Automático (diário às 3am)
crontab -l
```

### Atualizar Código

```bash
# No seu Mac
scp main.py ubuntu@$ORACLE_IP:~/jarvis/

# Na VM
sudo systemctl restart jarvis
```

### Atualizar PWA

```bash
# No seu Mac
scp -r pwa/* ubuntu@$ORACLE_IP:~/jarvis/pwa/

# No iPhone
# Recarregue o PWA (puxe para baixo)
```

## Segurança

### Alterar API Key

```bash
# Gerar nova
openssl rand -hex 32

# Atualizar .env
nano ~/jarvis/.env

# Reiniciar
sudo systemctl restart jarvis

# Atualizar PWA e Atalhos com nova key
```

### Monitorar Acessos

```bash
# Ver últimos acessos
sudo tail -100 /var/log/nginx/access.log

# Ver tentativas não autorizadas
sudo grep "401" /var/log/nginx/access.log
```

### Bloquear IP

```bash
# Se detectar abuso
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="IP_MALICIOSO" reject'
sudo firewall-cmd --reload
```

## Troubleshooting

### Serviço não inicia

```bash
# Ver erro
sudo journalctl -u jarvis -n 50

# Verificar dependências
python3.11 -m pip install -r ~/jarvis/requirements.txt

# Testar manualmente
cd ~/jarvis
python3.11 main.py
```

### Ollama lento

```bash
# Verificar RAM
free -h

# Se pouca RAM, usar modelo menor
ollama pull llama3.1:8b
# ou
ollama pull phi3:mini

# Atualizar main.py
nano ~/jarvis/main.py
# Altere o modelo
```

### PostgreSQL erro de conexão

```bash
# Verificar se está rodando
sudo systemctl status postgresql

# Testar conexão
psql -U assistant -d personal_kb

# Verificar senha no .env
cat ~/jarvis/.env
```

### Cloudflare Tunnel offline

```bash
# Verificar status
sudo systemctl status cloudflared

# Ver logs
sudo journalctl -u cloudflared -n 50

# Reiniciar
sudo systemctl restart cloudflared
```

## Custos

| Serviço | Custo |
|---------|-------|
| Oracle VM (4 vCPU, 24GB) | $0 (free tier) |
| Cloudflare Tunnel | $0 |
| Domínio (opcional) | $0-12/ano |
| **Total** | **$0/mês** |

## Performance

Com free tier Oracle (4 vCPU, 24GB RAM):

- **Latência:** 2-5 segundos
- **Throughput:** ~10 req/min
- **Modelo:** Llama 3.1 8B
- **Contexto:** 4k tokens

## Limitações

- Sem notificações push proativas
- Sem backup automático na nuvem
- Limitado a 1 usuário simultâneo
- Depende de conexão internet

## Próximos Passos

Depois de configurar:

1. ✅ Teste todas as funcionalidades
2. ✅ Configure backups
3. ✅ Personalize prompts
4. ✅ Adicione funcionalidades customizadas
5. ✅ Monitore uso de recursos

## Suporte

Se tiver problemas:

1. Verifique os logs
2. Consulte Troubleshooting
3. Revise cada passo do setup

---

**Tempo de setup:** ~30 minutos  
**Dificuldade:** Intermediária  
**Custo:** $0/mês
