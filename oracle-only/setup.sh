#!/bin/bash
set -e

echo "🚀 Setup Completo - Oracle VM + PWA + Segurança"

# 1. Executar setup básico
echo "📦 Executando setup básico..."
bash ../oracle-vm/setup.sh

# 2. Instalar Python e dependências
echo "🐍 Instalando Python 3.11..."
sudo dnf install -y python3.11 python3.11-pip

# 3. Criar diretório do projeto
echo "📁 Criando estrutura..."
mkdir -p ~/jarvis
cd ~/jarvis

# 4. Copiar arquivos (você fará isso via scp)
echo "📋 Copie os arquivos:"
echo "  scp main.py usuario@IP_ORACLE:~/jarvis/"
echo "  scp requirements.txt usuario@IP_ORACLE:~/jarvis/"
echo "  scp -r ../pwa usuario@IP_ORACLE:~/jarvis/"

# 5. Instalar dependências Python
echo "📦 Instalando dependências..."
python3.11 -m pip install -r requirements.txt

# 6. Gerar API Key
echo "🔑 Gerando API Key..."
API_KEY=$(openssl rand -hex 32)
echo "API_KEY=$API_KEY" > .env
echo "POSTGRES_PASSWORD=change_this_password" >> .env

echo ""
echo "⚠️  IMPORTANTE: Salve esta API Key:"
echo "   $API_KEY"
echo ""

# 7. Criar serviço systemd
echo "⚙️  Criando serviço..."
sudo tee /etc/systemd/system/jarvis.service > /dev/null <<EOF
[Unit]
Description=Jarvis Personal Assistant API
After=network.target postgresql.service ollama.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/jarvis
Environment="PATH=/home/$USER/.local/bin:/usr/local/bin:/usr/bin"
EnvironmentFile=/home/$USER/jarvis/.env
ExecStart=/usr/local/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 8. Configurar Nginx
echo "🌐 Instalando e configurando Nginx..."
sudo dnf install -y nginx certbot python3-certbot-nginx

sudo tee /etc/nginx/conf.d/jarvis.conf > /dev/null <<'NGINX'
server {
    listen 80;
    server_name _;  # Alterar para seu domínio

    # PWA
    location / {
        root /home/USER/jarvis/pwa;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # API
    location /chat {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /health {
        proxy_pass http://localhost:8000;
    }

    location /history {
        proxy_pass http://localhost:8000;
    }
}
NGINX

# Substituir USER pelo usuário atual
sudo sed -i "s/USER/$USER/g" /etc/nginx/conf.d/jarvis.conf

# 9. Configurar firewall
echo "🔒 Configurando firewall..."
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload

# 10. Iniciar serviços
echo "🚀 Iniciando serviços..."
sudo systemctl enable jarvis
sudo systemctl start jarvis
sudo systemctl enable nginx
sudo systemctl start nginx

# 11. Configurar SSL (Cloudflare Tunnel - grátis)
echo ""
echo "📝 Próximos passos:"
echo ""
echo "1. Altere a senha do PostgreSQL:"
echo "   sudo -u postgres psql"
echo "   ALTER USER assistant WITH PASSWORD 'sua_senha_forte';"
echo "   \\q"
echo ""
echo "2. Atualize o arquivo .env com a nova senha:"
echo "   nano ~/jarvis/.env"
echo ""
echo "3. Configure Cloudflare Tunnel (grátis):"
echo "   curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared"
echo "   chmod +x cloudflared"
echo "   sudo mv cloudflared /usr/local/bin/"
echo "   cloudflared tunnel login"
echo "   cloudflared tunnel create jarvis"
echo "   cloudflared tunnel route dns jarvis seu-dominio.com"
echo "   cloudflared tunnel run jarvis"
echo ""
echo "4. Sua API Key (salve em local seguro):"
echo "   $API_KEY"
echo ""
echo "5. Teste a API:"
echo "   curl http://localhost:8000/health"
echo ""
echo "6. Acesse o PWA:"
echo "   http://SEU_IP"
echo ""
echo "✅ Setup completo!"
