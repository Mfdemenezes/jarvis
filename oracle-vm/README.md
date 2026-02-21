# Setup Oracle VM

Scripts para configurar a VM Oracle com PostgreSQL, pgvector e Ollama.

## Pré-requisitos

- VM Oracle Cloud (você já tem: 4 vCPU, 24GB RAM)
- Acesso SSH à VM
- Oracle Linux 8/9

## Instalação

1. Copie o script para a VM:
```bash
scp setup.sh usuario@SEU_IP_ORACLE:~/
```

2. Execute na VM:
```bash
ssh usuario@SEU_IP_ORACLE
chmod +x setup.sh
./setup.sh
```

O script vai:
- ✅ Instalar PostgreSQL 15
- ✅ Instalar pgvector
- ✅ Criar database e schema
- ✅ Instalar Ollama
- ✅ Baixar modelo Llama 3.1
- ✅ Configurar backups automáticos
- ✅ Configurar firewall

## Após a Instalação

### 1. Alterar senha do PostgreSQL

```bash
sudo -u postgres psql
ALTER USER assistant WITH PASSWORD 'sua_senha_segura';
\q
```

### 2. Configurar AWS CLI (para backups)

```bash
aws configure
# AWS Access Key ID: sua_key
# AWS Secret Access Key: sua_secret
# Default region: us-east-1
```

### 3. Testar Ollama

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.1:8b",
  "prompt": "Olá, como você está?",
  "stream": false
}'
```

### 4. Testar PostgreSQL

```bash
psql -U assistant -d personal_kb
\dt  # Listar tabelas
SELECT * FROM conversations LIMIT 5;
\q
```

## Modelos Ollama Alternativos

```bash
# Mais rápido (menor qualidade)
ollama pull llama3.1:8b

# Melhor qualidade (mais lento)
ollama pull qwen2.5:14b

# Especializado em código
ollama pull codellama:13b

# Multilíngue
ollama pull mistral:7b
```

## Backups

Backups automáticos configurados para rodar diariamente às 3am.

Manual:
```bash
~/backup.sh
```

## Monitoramento

```bash
# Status dos serviços
sudo systemctl status postgresql
sudo systemctl status ollama

# Logs
sudo journalctl -u postgresql -f
sudo journalctl -u ollama -f

# Uso de disco
df -h

# Uso de memória
free -h
```

## Segurança

O firewall está configurado para aceitar conexões nas portas:
- 5432 (PostgreSQL)
- 11434 (Ollama)

**IMPORTANTE**: Configure regras adicionais para aceitar apenas IPs confiáveis:

```bash
# Aceitar apenas do IP da AWS Lambda
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="IP_DA_LAMBDA" port port="5432" protocol="tcp" accept'
sudo firewall-cmd --reload
```
