#!/bin/bash
set -e

echo "🚀 Configurando Oracle VM para Assistente Pessoal..."

# 1. Atualizar sistema
echo "📦 Atualizando sistema..."
sudo dnf update -y

# 2. Instalar PostgreSQL 15
echo "🐘 Instalando PostgreSQL 15..."
sudo dnf install -y postgresql15-server postgresql15-contrib postgresql15-devel
sudo postgresql-setup --initdb
sudo systemctl enable postgresql
sudo systemctl start postgresql

# 3. Instalar pgvector
echo "🔍 Instalando pgvector..."
sudo dnf install -y git gcc make
cd /tmp
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# 4. Configurar PostgreSQL
echo "⚙️  Configurando PostgreSQL..."
sudo -u postgres psql <<EOF
CREATE DATABASE personal_kb;
\c personal_kb
CREATE EXTENSION vector;
CREATE USER assistant WITH PASSWORD 'change_this_password';
GRANT ALL PRIVILEGES ON DATABASE personal_kb TO assistant;
EOF

# 5. Criar schema
sudo -u postgres psql -d personal_kb <<EOF
-- Tabela de conversas
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    user_message TEXT NOT NULL,
    assistant_response TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

-- Tabela de embeddings (memória vetorial)
CREATE TABLE memory_embeddings (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Índice vetorial para busca rápida
CREATE INDEX ON memory_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Tabela de lembretes/alertas
CREATE TABLE reminders (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    trigger_time TIMESTAMP NOT NULL,
    triggered BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tabela de preferências do usuário
CREATE TABLE user_preferences (
    key TEXT PRIMARY KEY,
    value JSONB,
    updated_at TIMESTAMP DEFAULT NOW()
);
EOF

# 6. Instalar Ollama
echo "🤖 Instalando Ollama..."
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable ollama
sudo systemctl start ollama

# 7. Baixar modelo
echo "📥 Baixando modelo Llama 3.1..."
ollama pull llama3.1:8b

# 8. Instalar AWS CLI
echo "☁️  Instalando AWS CLI..."
sudo dnf install -y awscli

# 9. Criar diretório de backups
mkdir -p ~/backups

# 10. Configurar firewall
echo "🔒 Configurando firewall..."
sudo firewall-cmd --permanent --add-port=5432/tcp
sudo firewall-cmd --permanent --add-port=11434/tcp  # Ollama
sudo firewall-cmd --reload

# 11. Criar script de backup
cat > ~/backup.sh <<'BACKUP'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump -U postgres personal_kb | gzip > ~/backups/backup_$DATE.sql.gz

# Upload para S3 (configure suas credenciais AWS)
# aws s3 cp ~/backups/backup_$DATE.sql.gz s3://seu-bucket/backups/

# Manter apenas últimos 7 backups
ls -t ~/backups/backup_*.sql.gz | tail -n +8 | xargs -r rm
BACKUP

chmod +x ~/backup.sh

# 12. Adicionar backup ao cron (diário às 3am)
(crontab -l 2>/dev/null; echo "0 3 * * * ~/backup.sh") | crontab -

echo "✅ Setup completo!"
echo ""
echo "📝 Próximos passos:"
echo "1. Altere a senha do PostgreSQL em: sudo -u postgres psql"
echo "2. Configure AWS CLI: aws configure"
echo "3. Teste Ollama: curl http://localhost:11434/api/generate -d '{\"model\":\"llama3.1:8b\",\"prompt\":\"Hello\"}'"
echo "4. Teste PostgreSQL: psql -U assistant -d personal_kb"
