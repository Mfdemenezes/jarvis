#!/bin/bash
set -e

echo "🐳 Setup Jarvis - Versão Docker"
echo "================================"
echo ""

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar se está rodando como root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}❌ Não execute como root!${NC}"
   exit 1
fi

# 1. Verificar Docker
echo "📦 Verificando Docker..."
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}⚠️  Docker não encontrado. Instalando...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo -e "${GREEN}✅ Docker instalado${NC}"
else
    echo -e "${GREEN}✅ Docker já instalado${NC}"
fi

# 2. Verificar Docker Compose
echo "📦 Verificando Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}⚠️  Docker Compose não encontrado. Instalando...${NC}"
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo -e "${GREEN}✅ Docker Compose instalado${NC}"
else
    echo -e "${GREEN}✅ Docker Compose já instalado${NC}"
fi

# 3. Criar .env se não existir
if [ ! -f .env ]; then
    echo "🔑 Gerando credenciais..."
    API_KEY=$(openssl rand -hex 32)
    POSTGRES_PASSWORD=$(openssl rand -base64 24)
    
    cat > .env <<EOF
# Gerado automaticamente em $(date)
API_KEY=$API_KEY
POSTGRES_PASSWORD=$POSTGRES_PASSWORD

# Configurações
POSTGRES_DB=personal_kb
POSTGRES_USER=assistant
OLLAMA_MODEL=llama3.1:8b
EOF
    
    echo -e "${GREEN}✅ Arquivo .env criado${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANTE: Salve estas credenciais em local seguro!${NC}"
    echo ""
    echo "API_KEY: $API_KEY"
    echo "POSTGRES_PASSWORD: $POSTGRES_PASSWORD"
    echo ""
    read -p "Pressione Enter para continuar..."
else
    echo -e "${GREEN}✅ Arquivo .env já existe${NC}"
fi

# 4. Criar diretórios necessários
echo "📁 Criando diretórios..."
mkdir -p ../pwa
echo -e "${GREEN}✅ Diretórios criados${NC}"

# 5. Iniciar containers
echo "🚀 Iniciando containers..."
docker-compose up -d

echo ""
echo "⏳ Aguardando containers iniciarem..."
sleep 10

# 6. Verificar status
echo ""
echo "📊 Status dos containers:"
docker-compose ps

# 7. Aguardar banco de dados
echo ""
echo "⏳ Aguardando banco de dados..."
until docker exec jarvis-db pg_isready -U assistant &> /dev/null; do
    echo -n "."
    sleep 2
done
echo ""
echo -e "${GREEN}✅ Banco de dados pronto${NC}"

# 8. Aguardar Ollama
echo ""
echo "⏳ Aguardando Ollama..."
until docker exec jarvis-llm curl -s http://localhost:11434/api/tags &> /dev/null; do
    echo -n "."
    sleep 2
done
echo ""
echo -e "${GREEN}✅ Ollama pronto${NC}"

# 9. Baixar modelo
echo ""
echo "📥 Baixando modelo Llama 3.1 (8B)..."
echo -e "${YELLOW}⚠️  Isso pode levar ~10 minutos (download de ~5GB)${NC}"
docker exec jarvis-llm ollama pull llama3.1:8b

echo ""
echo -e "${GREEN}✅ Modelo baixado${NC}"

# 10. Testar health
echo ""
echo "🏥 Testando health check..."
sleep 5
HEALTH=$(curl -s http://localhost/health | grep -o '"status":"healthy"' || echo "")

if [ -n "$HEALTH" ]; then
    echo -e "${GREEN}✅ Health check OK${NC}"
else
    echo -e "${YELLOW}⚠️  Health check falhou. Verificando logs...${NC}"
    docker-compose logs --tail=20
fi

# 11. Configurar firewall
echo ""
echo "🔒 Configurando firewall..."
if command -v firewall-cmd &> /dev/null; then
    sudo firewall-cmd --permanent --add-port=80/tcp 2>/dev/null || true
    sudo firewall-cmd --reload 2>/dev/null || true
    echo -e "${GREEN}✅ Firewall configurado${NC}"
else
    echo -e "${YELLOW}⚠️  firewall-cmd não encontrado. Configure manualmente.${NC}"
fi

# 12. Resumo final
echo ""
echo "================================"
echo -e "${GREEN}🎉 Setup Completo!${NC}"
echo "================================"
echo ""
echo "📦 Containers rodando:"
docker-compose ps --format "table {{.Name}}\t{{.Status}}"
echo ""
echo "🔗 URLs:"
echo "  - Health: http://localhost/health"
echo "  - API: http://localhost/chat"
echo "  - PWA: http://localhost/"
echo ""
echo "🔑 Credenciais (salve em local seguro):"
echo "  - API Key: $(grep API_KEY .env | cut -d'=' -f2)"
echo "  - Postgres: $(grep POSTGRES_PASSWORD .env | cut -d'=' -f2)"
echo ""
echo "📝 Próximos passos:"
echo "  1. Configure Cloudflare Tunnel (ver README.md)"
echo "  2. Instale PWA no iPhone"
echo "  3. Configure Atalhos da Apple"
echo ""
echo "📚 Comandos úteis:"
echo "  - Ver logs: docker-compose logs -f"
echo "  - Parar: docker-compose stop"
echo "  - Reiniciar: docker-compose restart"
echo "  - Status: docker-compose ps"
echo ""
echo "🆘 Problemas? Ver README.md seção Troubleshooting"
echo ""
