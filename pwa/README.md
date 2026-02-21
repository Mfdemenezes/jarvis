# PWA - Progressive Web App

Interface web do Jarvis que funciona como app nativo no iPhone.

## Arquivos

```
pwa/
├── index.html       # Interface principal
├── manifest.json    # Configuração do PWA
├── sw.js           # Service Worker (cache)
├── icon-192.png    # Ícone 192x192 (criar)
└── icon-512.png    # Ícone 512x512 (criar)
```

## Criar Ícones

### Opção 1: Online (Rápido)

1. Acesse: https://www.favicon-generator.org/
2. Upload uma imagem (logo do Jarvis)
3. Baixe os ícones gerados
4. Renomeie para `icon-192.png` e `icon-512.png`

### Opção 2: ImageMagick (Local)

```bash
# Instalar ImageMagick
brew install imagemagick

# Criar ícones a partir de uma imagem
convert sua-imagem.png -resize 192x192 icon-192.png
convert sua-imagem.png -resize 512x512 icon-512.png
```

### Opção 3: Usar Emoji (Temporário)

```bash
# Criar ícone simples com emoji
# Use um gerador online como: https://favicon.io/emoji-favicons/
# Emoji sugerido: 🤖 ou 🎙️
```

## Configuração

### 1. Alterar API URL

Edite `index.html` linha ~30:

```javascript
const API_URL = 'https://seu-dominio.com/chat';
const API_KEY = 'SUA_API_KEY_AQUI';
```

### 2. Personalizar Cores

Edite `manifest.json`:

```json
{
  "background_color": "#0a0a0a",  // Cor de fundo
  "theme_color": "#667eea"        // Cor do tema
}
```

Edite `index.html` CSS (linha ~20):

```css
body {
    background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
}

#mic-button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
```

### 3. Personalizar Mensagem Inicial

Edite `index.html` linha ~200:

```javascript
addMessage('Olá! Sou o Jarvis, seu assistente pessoal. Como posso ajudar?', 'assistant');
```

## Funcionalidades

### ✅ Implementadas

- **Reconhecimento de Voz** (Web Speech API)
- **Síntese de Voz** (Speech Synthesis API)
- **Interface Responsiva** (mobile-first)
- **Animações Suaves**
- **Cache Offline** (Service Worker)
- **Instalável** (Add to Home Screen)

### 🔄 Melhorias Futuras

- [ ] Histórico de conversas
- [ ] Modo escuro/claro
- [ ] Configurações personalizáveis
- [ ] Notificações push
- [ ] Compartilhar conversas
- [ ] Exportar histórico

## Instalação no iPhone

### Passo 1: Acessar

1. Abra **Safari** (não Chrome!)
2. Acesse: `https://seu-dominio.com`

### Passo 2: Adicionar à Tela Inicial

1. Toque no botão **Compartilhar** (ícone de compartilhar)
2. Role para baixo
3. Toque em **"Adicionar à Tela de Início"**
4. Edite o nome (ex: "Jarvis")
5. Toque em **"Adicionar"**

### Passo 3: Usar

1. Toque no ícone "Jarvis" na tela inicial
2. O app abre em tela cheia (sem barra do Safari)
3. Funciona como app nativo!

## Uso

### Voz

1. Toque no botão 🎤
2. Fale sua mensagem
3. Aguarde resposta (texto + voz)

### Texto

1. Digite no campo de texto
2. Pressione Enter
3. Aguarde resposta (texto + voz)

## Personalização Avançada

### Alterar Voz

Edite `index.html` linha ~90:

```javascript
function speak(text) {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'pt-BR';
    utterance.rate = 1.0;      // Velocidade (0.5 a 2.0)
    utterance.pitch = 1.0;     // Tom (0 a 2)
    utterance.volume = 1.0;    // Volume (0 a 1)
    synth.speak(utterance);
}
```

### Alterar Animações

Edite `index.html` CSS:

```css
@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateY(10px);  /* Altere para mudar direção */
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}
```

### Adicionar Botões Rápidos

Edite `index.html` antes do `</body>`:

```html
<div class="quick-actions">
    <button onclick="sendMessage('Que horas são?')">⏰ Horas</button>
    <button onclick="sendMessage('Qual a data?')">📅 Data</button>
    <button onclick="sendMessage('Como está o tempo?')">🌤️ Tempo</button>
</div>
```

E adicione CSS:

```css
.quick-actions {
    display: flex;
    gap: 10px;
    padding: 10px 20px;
    overflow-x: auto;
}

.quick-actions button {
    padding: 10px 20px;
    border-radius: 20px;
    border: 1px solid rgba(255,255,255,0.2);
    background: rgba(255,255,255,0.1);
    color: #fff;
    white-space: nowrap;
}
```

## Troubleshooting

### "Reconhecimento de voz não funciona"

**Problema:** Web Speech API não disponível

**Soluções:**
1. Use Safari (não Chrome)
2. Permita acesso ao microfone
3. Verifique: Ajustes > Safari > Microfone

### "Não fala a resposta"

**Problema:** Speech Synthesis não funciona

**Soluções:**
1. Aumente o volume do iPhone
2. Desative modo silencioso
3. Verifique: Ajustes > Acessibilidade > Conteúdo Falado

### "Erro 401 Unauthorized"

**Problema:** API Key incorreta

**Soluções:**
1. Verifique API_KEY no código
2. Verifique se é a mesma do servidor
3. Limpe cache do Safari

### "App não instala"

**Problema:** Manifest ou ícones faltando

**Soluções:**
1. Verifique se `manifest.json` existe
2. Verifique se ícones existem
3. Acesse via HTTPS (não HTTP)

### "Cache não funciona"

**Problema:** Service Worker não registrado

**Soluções:**
1. Verifique console do Safari
2. Acesse via HTTPS
3. Recarregue a página

## Desenvolvimento Local

### Testar Localmente

```bash
# Instalar servidor HTTP simples
python3 -m http.server 8080

# Ou
npx serve pwa

# Acessar
open http://localhost:8080
```

### Debug no iPhone

1. iPhone: Ajustes > Safari > Avançado > Web Inspector (ativar)
2. Mac: Safari > Desenvolver > [Seu iPhone] > [Página]
3. Console aparece no Mac

### Hot Reload

Use um servidor com hot reload:

```bash
npm install -g live-server
live-server pwa
```

## Deploy

### Copiar para Oracle VM

```bash
scp -r pwa/* ubuntu@$ORACLE_IP:~/jarvis/pwa/
```

### Atualizar no Servidor

```bash
# Na VM
cd ~/jarvis/pwa
# Editar arquivos
nano index.html

# Nginx serve automaticamente
# Sem necessidade de reiniciar
```

### Forçar Atualização no iPhone

1. Abra o PWA
2. Puxe para baixo (pull to refresh)
3. Ou: Feche e abra novamente

## Performance

### Otimizações

1. **Minificar CSS/JS** (produção)
2. **Comprimir imagens**
3. **Cache agressivo** (Service Worker)
4. **Lazy loading** (imagens)

### Métricas

- **First Paint:** < 1s
- **Time to Interactive:** < 2s
- **Lighthouse Score:** > 90

## Segurança

### HTTPS Obrigatório

PWA só funciona com HTTPS. Cloudflare Tunnel fornece SSL automaticamente.

### API Key

Nunca exponha a API Key no código público. Use variáveis de ambiente ou configuração do servidor.

### CORS

Configurado no servidor (FastAPI) para aceitar apenas seu domínio.

## Recursos

- [Web Speech API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API)
- [PWA Guide](https://web.dev/progressive-web-apps/)
- [Service Workers](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)
- [Web App Manifest](https://developer.mozilla.org/en-US/docs/Web/Manifest)

## Suporte

- **iOS:** 14.0+
- **Safari:** 14.0+
- **Chrome (iOS):** Limitado (use Safari)
- **Firefox (iOS):** Limitado (use Safari)

---

**Dica:** Para melhor experiência, sempre use Safari no iOS!
