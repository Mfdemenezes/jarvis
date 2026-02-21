# 🚀 Setup Rápido - 5 Passos

## Passo 1: Gerar API Key (1 min)

```bash
cd ~/Projeto/personal-assistant/oracle-only
openssl rand -hex 32 > api_key.txt
cat api_key.txt
```

**Salve esta key em local seguro!**

---

## Passo 2: Copiar para Oracle VM (2 min)

```bash
# Substitua pelo seu IP
export ORACLE_IP="seu.ip.oracle.aqui"

# Copiar arquivos
scp setup.sh main.py requirements.txt ubuntu@$ORACLE_IP:~/
scp -r ../pwa ubuntu@$ORACLE_IP:~/
```

---

## Passo 3: Setup na VM (15 min)

```bash
# Conectar
ssh ubuntu@$ORACLE_IP

# Executar setup
chmod +x setup.sh
./setup.sh

# Aguarde download do modelo (~10 min)
```

**Configurar senhas:**

```bash
# PostgreSQL
sudo -u postgres psql
ALTER USER assistant WITH PASSWORD 'SuaSenhaForte123!';
\q

# Atualizar .env
nano ~/jarvis/.env
# Altere:
# API_KEY=sua_key_do_passo1
# POSTGRES_PASSWORD=SuaSenhaForte123!

# Reiniciar
sudo systemctl restart jarvis

# Testar
curl http://localhost:8000/health
```

---

## Passo 4: Cloudflare Tunnel (10 min)

```bash
# Instalar
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/

# Login (abre navegador)
cloudflared tunnel login

# Criar tunnel
cloudflared tunnel create jarvis
# Anote o TUNNEL_ID

# Configurar DNS
cloudflared tunnel route dns jarvis seu-dominio.com

# Config
mkdir -p ~/.cloudflared
nano ~/.cloudflared/config.yml
```

**Cole no arquivo:**
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

**Cole:**
```ini
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
Type=simple
User=ubuntu
ExecStart=/usr/local/bin/cloudflared tunnel run jarvis
Restart=always

[Install]
WantedBy=multi-user.target
```

**Iniciar:**
```bash
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

---

## Passo 5: Configurar iPhone (2 min)

### PWA

1. Safari → `https://seu-dominio.com`
2. Compartilhar → "Adicionar à Tela de Início"
3. Nomear "Jarvis"

**Configurar API Key:**
```bash
# Na VM
nano ~/jarvis/pwa/index.html
# Linha ~30: const API_KEY = 'SUA_KEY_AQUI';
```

### Atalhos

1. App **Atalhos** → **+**
2. Nome: "Jarvis"
3. Adicionar ações:

**Ação 1:** Ditar Texto

**Ação 2:** Obter Conteúdo de URL
- URL: `https://seu-dominio.com/chat`
- Método: POST
- Cabeçalhos:
  - `Content-Type`: `application/json`
  - `X-Api-Key`: `SUA_KEY_AQUI`
- Corpo (JSON):
  ```json
  {
    "message": "Texto Ditado"
  }
  ```

**Ação 3:** Obter Dicionário  
- Entrada: Conteúdo de URL

**Ação 4:** Obter Valor do Dicionário  
- Chave: `response`

**Ação 5:** Falar Texto  
- Texto: Valor do Dicionário
- Idioma: Português (Brasil)

4. Adicionar à Siri: "Hey Siri, Jarvis"

---

## ✅ Testar

### Teste 1: API
```bash
curl https://seu-dominio.com/health
# Deve retornar: {"status":"healthy"}
```

### Teste 2: Chat
```bash
curl -X POST https://seu-dominio.com/chat \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: SUA_KEY" \
  -d '{"message": "Olá!"}'
```

### Teste 3: iPhone
- Abra PWA → fale "Olá"
- Ou: "Hey Siri, Jarvis" → "Olá"

---

## 🎉 Pronto!

Agora você tem:
- ✅ Jarvis rodando na Oracle VM
- ✅ Acesso via HTTPS (Cloudflare)
- ✅ PWA no iPhone
- ✅ Atalho com Siri
- ✅ Funciona no Apple Watch
- ✅ Custo: $0/mês

---

## 📱 Como Usar

**iPhone:**
- Toque no ícone "Jarvis" → fale/digite
- Ou: "Hey Siri, Jarvis" → fale comando

**Apple Watch:**
- "Hey Siri, Jarvis" → fale comando
- Ou: App Atalhos → Jarvis → fale

---

## 🔧 Comandos Úteis

```bash
# Ver status
sudo systemctl status jarvis nginx cloudflared

# Ver logs
sudo journalctl -u jarvis -f

# Reiniciar
sudo systemctl restart jarvis

# Backup
~/backup.sh
```

---

## 🆘 Problemas?

**Serviço não inicia:**
```bash
sudo journalctl -u jarvis -n 50
```

**API retorna erro:**
```bash
sudo tail -f /var/log/nginx/error.log
```

**Cloudflare offline:**
```bash
sudo systemctl restart cloudflared
```

---

## 📚 Documentação Completa

- `COMECE_AQUI.md` - Resumo executivo
- `README_ATUALIZADO.md` - Guia completo
- `oracle-only/README.md` - Setup detalhado
- `ATALHOS_APPLE.md` - Guia de Atalhos
- `MELHORIAS_SEGURANCA.md` - Segurança

---

**Tempo total:** ~30 minutos  
**Custo:** $0/mês  
**Dificuldade:** ⭐⭐⭐ (Intermediária)
