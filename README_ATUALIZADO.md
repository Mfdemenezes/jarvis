# Jarvis - Assistente Pessoal (Atualizado)

Assistente pessoal estilo JARVIS com acesso **somente seu**, funcionando via PWA + Atalhos da Apple.

## 🎯 Objetivo

Criar um assistente pessoal que:
- ✅ Funciona no iPhone e Apple Watch
- ✅ Acesso somente seu (seguro)
- ✅ Custo mínimo (idealmente $0)
- ✅ Funciona offline (parcialmente)
- ✅ Fácil de usar (voz e texto)

## 🏗️ Arquiteturas Disponíveis

### Opção 1: Oracle VM Only (Recomendado - $0/mês)

**Vantagens:**
- Custo zero
- Mais simples
- Controle total
- Sem vendor lock-in

**Arquitetura:**
```
iPhone/Watch → Cloudflare Tunnel (grátis) → Oracle VM
                                              ├─ FastAPI
                                              ├─ Ollama (LLM)
                                              └─ PostgreSQL
```

**Custos:**
- Oracle VM: $0 (free tier)
- Cloudflare Tunnel: $0
- **Total: $0/mês**

**Setup:** Ver `oracle-only/README.md`

### Opção 2: Oracle VM + AWS (Original - ~$3/mês)

**Vantagens:**
- Notificações push automáticas
- Escalável
- Backups automáticos na AWS

**Arquitetura:**
```
iPhone/Watch → API Gateway → Lambda → Oracle VM
                              ├─ DynamoDB
                              ├─ S3
                              └─ SNS
```

**Custos:**
- Oracle VM: $0 (free tier)
- AWS: ~$3/mês
- **Total: ~$3/mês**

**Setup:** Ver `backend/README.md`

## 🚀 Quick Start (Opção 1 - Recomendado)

### 1. Setup Oracle VM

```bash
# Na sua máquina local
cd oracle-only
scp setup.sh main.py requirements.txt usuario@IP_ORACLE:~/

# Na Oracle VM
ssh usuario@IP_ORACLE
chmod +x setup.sh
./setup.sh
```

### 2. Copiar PWA

```bash
# Na sua máquina local
scp -r pwa usuario@IP_ORACLE:~/jarvis/
```

### 3. Configurar Cloudflare Tunnel

```bash
# Na Oracle VM
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/

# Login no Cloudflare
cloudflared tunnel login

# Criar tunnel
cloudflared tunnel create jarvis

# Configurar DNS
cloudflared tunnel route dns jarvis seu-dominio.com

# Criar config
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml <<EOF
tunnel: jarvis
credentials-file: /home/$USER/.cloudflared/TUNNEL_ID.json

ingress:
  - hostname: seu-dominio.com
    service: http://localhost:80
  - service: http_status:404
EOF

# Rodar tunnel
cloudflared tunnel run jarvis
```

### 4. Configurar PWA no iPhone

1. Abra Safari: `https://seu-dominio.com`
2. Toque no botão "Compartilhar"
3. "Adicionar à Tela de Início"
4. Pronto! Agora você tem um app

### 5. Configurar Atalhos da Apple

Ver guia completo em: `ATALHOS_APPLE.md`

**Resumo rápido:**
1. Abra app Atalhos
2. Crie novo atalho "Jarvis"
3. Adicione ações:
   - Ditar Texto
   - Obter Conteúdo de URL (POST para seu domínio)
   - Falar resposta
4. Adicione à Siri: "Hey Siri, Jarvis"

## 🔒 Segurança

### API Key

Sua API Key foi gerada durante o setup. Para ver:

```bash
# Na Oracle VM
cat ~/jarvis/.env
```

**IMPORTANTE:**
- Nunca compartilhe sua API Key
- Guarde em local seguro (1Password, etc)
- Use a mesma key no PWA e Atalhos

### Alterar API Key

```bash
# Gerar nova key
openssl rand -hex 32

# Atualizar .env
nano ~/jarvis/.env
# Altere API_KEY=nova_key

# Reiniciar serviço
sudo systemctl restart jarvis
```

### Firewall

O firewall está configurado para aceitar apenas:
- Porta 80 (HTTP)
- Porta 443 (HTTPS)

Portas internas (PostgreSQL, Ollama) não são acessíveis externamente.

### SSL/HTTPS

Cloudflare Tunnel fornece SSL automaticamente. Seu tráfego é criptografado.

## 📱 Como Usar

### No iPhone

**Opção 1: PWA**
- Toque no ícone na tela inicial
- Fale ou digite sua mensagem
- Receba resposta em voz e texto

**Opção 2: Atalhos**
- "Hey Siri, Jarvis"
- Fale seu comando
- Receba resposta em voz

**Opção 3: Atalho na Tela Inicial**
- Toque no ícone do atalho
- Fale seu comando
- Receba resposta

### No Apple Watch

**Opção 1: Siri**
- Levante o pulso
- "Hey Siri, Jarvis"
- Fale seu comando

**Opção 2: Complicação**
- Adicione atalho como complicação
- Toque na complicação
- Fale seu comando

**Opção 3: App Atalhos**
- Abra app Atalhos no Watch
- Toque em "Jarvis"
- Fale seu comando

## 🛠️ Manutenção

### Ver Logs

```bash
# API
sudo journalctl -u jarvis -f

# Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# PostgreSQL
sudo journalctl -u postgresql -f

# Ollama
sudo journalctl -u ollama -f
```

### Backup Manual

```bash
# Na Oracle VM
~/backup.sh
```

Backups automáticos rodam diariamente às 3am.

### Atualizar Modelo

```bash
# Baixar novo modelo
ollama pull llama3.1:70b  # Modelo maior (se tiver RAM)
ollama pull mistral:7b    # Alternativa

# Atualizar main.py
nano ~/jarvis/main.py
# Altere "llama3.1:8b" para o novo modelo

# Reiniciar
sudo systemctl restart jarvis
```

### Monitorar Recursos

```bash
# Uso de CPU/RAM
htop

# Uso de disco
df -h

# Uso de rede
sudo iftop
```

## 🐛 Troubleshooting

### "Não consigo acessar o PWA"

1. Verifique se Nginx está rodando:
   ```bash
   sudo systemctl status nginx
   ```

2. Verifique se Cloudflare Tunnel está ativo:
   ```bash
   ps aux | grep cloudflared
   ```

3. Teste localmente:
   ```bash
   curl http://localhost
   ```

### "API retorna 401 Unauthorized"

- API Key incorreta
- Verifique se está usando a mesma key do `.env`
- Verifique cabeçalho `X-Api-Key`

### "Resposta muito lenta"

- Modelo muito grande para a RAM disponível
- Troque para modelo menor:
  ```bash
  ollama pull llama3.1:8b
  ```

### "Erro ao conectar PostgreSQL"

1. Verifique se está rodando:
   ```bash
   sudo systemctl status postgresql
   ```

2. Teste conexão:
   ```bash
   psql -U assistant -d personal_kb
   ```

3. Verifique senha no `.env`

### "Reconhecimento de voz não funciona"

- iOS: Ajustes > Privacidade > Reconhecimento de Fala
- Ative para Safari e Atalhos

## 📊 Comparação de Opções

| Aspecto | Oracle Only | Oracle + AWS |
|---------|-------------|--------------|
| **Custo** | $0/mês | ~$3/mês |
| **Complexidade** | Baixa | Média |
| **Notificações Push** | ❌ | ✅ |
| **Backups** | Manual | Automático |
| **Escalabilidade** | Limitada | Alta |
| **Vendor Lock-in** | Não | Sim (AWS) |
| **Setup** | 30 min | 1-2 horas |

## 🎯 Recomendação Final

**Para uso pessoal:** Opção 1 (Oracle Only)
- Custo zero
- Mais simples
- Suficiente para um usuário

**Para uso familiar/equipe:** Opção 2 (Oracle + AWS)
- Notificações push
- Backups automáticos
- Mais robusto

## 📚 Documentação Adicional

- `MELHORIAS_SEGURANCA.md` - Guia completo de segurança
- `ATALHOS_APPLE.md` - Guia detalhado de Atalhos
- `oracle-only/README.md` - Setup Oracle VM only
- `backend/README.md` - Setup Oracle + AWS
- `pwa/README.md` - Documentação do PWA

## 🤝 Suporte

Se tiver problemas:

1. Verifique os logs
2. Consulte o Troubleshooting
3. Revise a documentação específica

## 📝 Próximos Passos

Depois de configurar:

1. ✅ Teste no iPhone
2. ✅ Teste no Apple Watch
3. ✅ Configure backups
4. ✅ Personalize prompts
5. ✅ Adicione funcionalidades customizadas

## 🔮 Roadmap

Funcionalidades futuras:

- [ ] Integração com calendário
- [ ] Integração com e-mail
- [ ] Controle de IoT (luzes, termostato)
- [ ] Lembretes inteligentes
- [ ] Resumo diário automático
- [ ] Análise de sentimento
- [ ] Múltiplos idiomas

---

**Versão:** 2.0  
**Última atualização:** 2026-02-21  
**Autor:** Marcelo
