# Exemplos de Uso

## Chat Básico

### Perguntas Simples
```
Você: Qual é a capital do Brasil?
Assistente: A capital do Brasil é Brasília.
```

### Com Contexto
```
Você: Meu nome é João e trabalho com tecnologia
Assistente: Prazer em conhecê-lo, João! Vou lembrar que você trabalha com tecnologia.

[Mais tarde...]

Você: Você lembra qual é minha área?
Assistente: Sim! Você trabalha com tecnologia.
```

## Lembretes

### Criar Lembrete via SQL
```sql
-- Conectar ao PostgreSQL
psql -U assistant -d personal_kb

-- Criar lembrete
INSERT INTO reminders (title, description, trigger_time)
VALUES (
    'Reunião com cliente',
    'Discutir proposta do projeto X',
    '2024-02-15 14:00:00'
);
```

### Criar Lembrete via Chat (futuro)
```
Você: Me lembre de ligar para o João amanhã às 14h
Assistente: Ok! Vou te lembrar de ligar para o João amanhã às 14h.
```

## Busca em Memória

### Buscar Conversas Antigas
```sql
-- Buscar por palavra-chave
SELECT user_message, assistant_response, timestamp
FROM conversations
WHERE user_message ILIKE '%investimentos%'
ORDER BY timestamp DESC
LIMIT 5;
```

### Via Chat
```
Você: O que conversamos sobre investimentos?
Assistente: [Busca no histórico e resume as conversas relevantes]
```

## Preferências do Usuário

### Salvar Preferências
```sql
INSERT INTO user_preferences (key, value)
VALUES 
    ('notification_time', '"09:00"'),
    ('language', '"pt-BR"'),
    ('timezone', '"America/Sao_Paulo"')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
```

### Consultar Preferências
```sql
SELECT * FROM user_preferences;
```

## Análise de Padrões

### Ver Histórico de Conversas
```sql
-- Conversas por dia
SELECT DATE(timestamp) as dia, COUNT(*) as total
FROM conversations
GROUP BY DATE(timestamp)
ORDER BY dia DESC;

-- Tópicos mais discutidos (simplificado)
SELECT 
    SUBSTRING(user_message, 1, 50) as topico,
    COUNT(*) as vezes
FROM conversations
GROUP BY SUBSTRING(user_message, 1, 50)
ORDER BY vezes DESC
LIMIT 10;
```

## Integrações Futuras

### Calendário (exemplo de como seria)
```
Você: Agende reunião com Maria amanhã às 15h
Assistente: Reunião agendada com Maria para 15/02 às 15h. Deseja adicionar alguma descrição?

Você: Sim, discussão sobre o projeto Y
Assistente: Perfeito! Adicionei a descrição. Você receberá um lembrete 15 minutos antes.
```

### Smart Home (exemplo)
```
Você: Apague as luzes da sala
Assistente: Luzes da sala apagadas.

Você: Qual a temperatura da casa?
Assistente: A temperatura atual é 23°C.
```

### Email (exemplo)
```
Você: Resuma os emails importantes de hoje
Assistente: Você recebeu 3 emails importantes:
1. Proposta do cliente X (urgente)
2. Relatório mensal da equipe
3. Convite para evento de tecnologia

Você: Responda o email do cliente X dizendo que vou analisar
Assistente: Email enviado para o cliente X com a mensagem solicitada.
```

## Comandos Úteis

### Backup Manual
```bash
ssh oracle-vm "~/backup.sh"
```

### Ver Logs em Tempo Real
```bash
# Lambda
aws logs tail /aws/lambda/personal-assistant-chat --follow

# PostgreSQL na Oracle VM
ssh oracle-vm "sudo journalctl -u postgresql -f"

# Ollama na Oracle VM
ssh oracle-vm "sudo journalctl -u ollama -f"
```

### Estatísticas
```sql
-- Total de conversas
SELECT COUNT(*) FROM conversations;

-- Conversas hoje
SELECT COUNT(*) FROM conversations 
WHERE DATE(timestamp) = CURRENT_DATE;

-- Lembretes pendentes
SELECT * FROM reminders 
WHERE triggered = FALSE 
ORDER BY trigger_time;
```

## Testes de Performance

### Testar Latência da API
```bash
time curl -X POST $API_ENDPOINT/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","message":"Olá"}'
```

### Testar Ollama Diretamente
```bash
time ssh oracle-vm 'curl -s http://localhost:11434/api/generate -d "{\"model\":\"llama3.1:8b\",\"prompt\":\"Hello\",\"stream\":false}"'
```

### Benchmark PostgreSQL
```sql
-- Criar dados de teste
INSERT INTO conversations (user_message, assistant_response)
SELECT 
    'Mensagem de teste ' || i,
    'Resposta de teste ' || i
FROM generate_series(1, 1000) i;

-- Testar busca
EXPLAIN ANALYZE
SELECT * FROM conversations
WHERE user_message ILIKE '%teste%'
LIMIT 10;
```
