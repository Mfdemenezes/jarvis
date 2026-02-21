# Atalhos da Apple - Jarvis

Guia completo para criar atalhos que funcionam no iPhone e Apple Watch.

## Atalho Principal - "Jarvis"

### Passo 1: Criar Novo Atalho

1. Abra o app **Atalhos** no iPhone
2. Toque em **+** (novo atalho)
3. Nomeie como **"Jarvis"**

### Passo 2: Adicionar Ações

Adicione as seguintes ações na ordem:

#### 1. Ditar Texto
- Busque: "Ditar Texto"
- Adicione a ação
- Configure: "Parar ao pausar" = Ativado

#### 2. Definir Variável
- Busque: "Definir Variável"
- Nome da variável: `comando`
- Valor: Texto Ditado

#### 3. Obter Conteúdo de URL
- Busque: "Obter Conteúdo de URL"
- Configure:
  - **URL**: `https://seu-dominio.com/chat`
  - **Método**: POST
  - **Cabeçalhos**:
    - `Content-Type`: `application/json`
    - `X-Api-Key`: `SUA_API_KEY_AQUI`
  - **Corpo da Requisição**: JSON
  - **JSON**:
    ```json
    {
      "message": "comando"
    }
    ```
    (Use a variável `comando` do menu)

#### 4. Obter Dicionário de Conteúdo de URL
- Busque: "Obter Dicionário"
- Entrada: Conteúdo de URL

#### 5. Obter Valor do Dicionário
- Busque: "Obter Valor do Dicionário"
- Chave: `response`
- Dicionário: Dicionário

#### 6. Falar Texto
- Busque: "Falar Texto"
- Texto: Valor do Dicionário
- Idioma: Português (Brasil)
- Taxa: 1.0

### Passo 3: Configurar Ícone

1. Toque nos **...** (mais opções)
2. Toque no ícone
3. Escolha cor roxa/azul
4. Escolha ícone de microfone ou robô

### Passo 4: Adicionar à Tela Inicial

1. Toque em **...** (mais opções)
2. Role até "Adicionar à Tela de Início"
3. Escolha nome e ícone
4. Toque em "Adicionar"

### Passo 5: Configurar Siri

1. Nas configurações do atalho
2. Toque em "Adicionar à Siri"
3. Grave a frase: **"Hey Siri, Jarvis"**

## Atalho Alternativo - "Perguntar ao Jarvis"

Para quando você quer digitar ao invés de falar:

### Ações:

1. **Pedir Entrada**
   - Pergunta: "O que você quer perguntar?"
   - Tipo de entrada: Texto

2. **Definir Variável**
   - Nome: `pergunta`
   - Valor: Entrada Fornecida

3. **Obter Conteúdo de URL** (mesmo do anterior)

4. **Obter Dicionário** (mesmo do anterior)

5. **Obter Valor** (mesmo do anterior)

6. **Mostrar Resultado**
   - Texto: Valor do Dicionário

7. **Falar Texto** (mesmo do anterior)

## Atalho para Apple Watch

O atalho "Jarvis" funciona automaticamente no Apple Watch se:

1. O atalho estiver no iPhone
2. Você adicionar à Siri
3. O Watch estiver pareado

### Usar no Watch:

**Opção 1: Siri**
- Levante o pulso
- Diga: "Hey Siri, Jarvis"
- Fale seu comando

**Opção 2: Complicação**
1. No iPhone, abra o app Watch
2. Vá em "Mostradores"
3. Escolha um mostrador
4. Toque em "Editar"
5. Adicione complicação "Atalhos"
6. Escolha o atalho "Jarvis"

**Opção 3: App Atalhos no Watch**
1. Abra o app Atalhos no Watch
2. Toque em "Jarvis"
3. Fale seu comando

## Atalhos Adicionais Úteis

### "Lembrete para Jarvis"

Criar lembretes através do Jarvis:

1. **Pedir Entrada**: "Sobre o que é o lembrete?"
2. **Definir Variável**: `lembrete`
3. **Pedir Entrada**: "Para quando?" (Tipo: Data e Hora)
4. **Definir Variável**: `data`
5. **Texto**: "Crie um lembrete: [lembrete] para [data]"
6. **Obter Conteúdo de URL** (enviar para Jarvis)
7. **Falar Texto**: resposta

### "Status do Jarvis"

Verificar se o Jarvis está online:

1. **Obter Conteúdo de URL**
   - URL: `https://seu-dominio.com/health`
   - Método: GET
   - Cabeçalhos: `X-Api-Key`

2. **Se** (Código de Status = 200)
   - **Falar Texto**: "Jarvis está online e funcionando"
   - **Senão**
   - **Falar Texto**: "Jarvis está offline"

### "Nota Rápida para Jarvis"

Salvar notas rapidamente:

1. **Pedir Entrada**: "Qual nota você quer salvar?"
2. **Texto**: "Salve esta nota: [Entrada Fornecida]"
3. **Obter Conteúdo de URL** (enviar para Jarvis)
4. **Mostrar Notificação**: "Nota salva com sucesso"

## Configuração da API

### Alterar URL e API Key

Em cada atalho, você precisa configurar:

1. **URL**: Substitua `https://seu-dominio.com/chat` pelo seu domínio real
2. **API Key**: Substitua `SUA_API_KEY_AQUI` pela sua chave gerada

### Gerar API Key

```bash
# No terminal do Mac
openssl rand -hex 32
```

Copie a chave gerada e use nos atalhos.

## Troubleshooting

### "Não foi possível conectar"

- Verifique se a URL está correta
- Verifique se a API Key está correta
- Teste a URL no Safari primeiro

### "Erro 401 Unauthorized"

- API Key incorreta
- Verifique se o cabeçalho `X-Api-Key` está configurado

### "Reconhecimento de voz não funciona"

- Vá em Ajustes > Privacidade > Reconhecimento de Fala
- Ative para o app Atalhos

### "Não fala a resposta"

- Vá em Ajustes > Acessibilidade > Conteúdo Falado
- Ative "Falar Seleção"

## Dicas

1. **Teste primeiro no iPhone** antes de usar no Watch
2. **Use nomes curtos** para ativar mais rápido com Siri
3. **Adicione à tela inicial** para acesso rápido
4. **Configure complicação no Watch** para acesso com um toque
5. **Crie atalhos específicos** para tarefas frequentes

## Exemplos de Uso

### No iPhone:
- "Hey Siri, Jarvis" → "Qual a previsão do tempo?"
- Toque no ícone na tela inicial → fale comando
- Abra Atalhos → toque em Jarvis → fale comando

### No Apple Watch:
- "Hey Siri, Jarvis" → "Defina um timer de 5 minutos"
- Toque na complicação → fale comando
- Abra Atalhos → Jarvis → fale comando

## Backup dos Atalhos

1. Abra o app Atalhos
2. Toque em "Jarvis"
3. Toque em **...** (mais opções)
4. Toque em "Compartilhar"
5. Salve no iCloud Drive

Para restaurar:
1. Abra o arquivo .shortcut no iCloud
2. Toque em "Adicionar Atalho"

## Próximos Passos

Depois de configurar os atalhos:

1. Teste cada um no iPhone
2. Verifique se funcionam no Watch
3. Ajuste a taxa de fala se necessário
4. Crie atalhos personalizados para suas necessidades
5. Compartilhe com família (se quiser)
