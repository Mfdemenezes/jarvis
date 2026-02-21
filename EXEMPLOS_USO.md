# 💬 Exemplos de Uso - Jarvis

## Comandos Básicos

### Informações
```
Você: "Que horas são?"
Jarvis: "São 14:30."

Você: "Qual a data de hoje?"
Jarvis: "Hoje é sábado, 21 de fevereiro de 2026."

Você: "Como está o tempo?"
Jarvis: "Deixe-me verificar... [resposta baseada em contexto]"
```

### Lembretes
```
Você: "Me lembre de ligar para o dentista amanhã às 10h"
Jarvis: "Entendido. Vou criar um lembrete para ligar para o dentista amanhã às 10h."

Você: "Quais são meus lembretes?"
Jarvis: "Você tem 2 lembretes: 1) Ligar para o dentista amanhã às 10h..."
```

### Notas
```
Você: "Anote: comprar leite, pão e café"
Jarvis: "Anotado. Salvei sua lista de compras."

Você: "Qual era minha lista de compras?"
Jarvis: "Sua lista de compras: leite, pão e café."
```

### Conversação
```
Você: "Como você está?"
Jarvis: "Estou funcionando perfeitamente, obrigado por perguntar! Como posso ajudá-lo?"

Você: "Conte uma piada"
Jarvis: "Por que o computador foi ao médico? Porque estava com vírus!"
```

## Comandos Avançados

### Análise e Resumo
```
Você: "Resuma nossa conversa de ontem"
Jarvis: "Ontem conversamos sobre... [resumo baseado no histórico]"

Você: "O que discutimos sobre o projeto X?"
Jarvis: "Sobre o projeto X, você mencionou... [busca no histórico]"
```

### Planejamento
```
Você: "Me ajude a planejar minha semana"
Jarvis: "Claro! Vamos começar. Quais são suas prioridades para esta semana?"

Você: "Crie um plano de estudos para aprender Python"
Jarvis: "Vou criar um plano de estudos estruturado para você..."
```

### Produtividade
```
Você: "Defina um timer de 25 minutos"
Jarvis: "Timer de 25 minutos iniciado. Vou avisá-lo quando terminar."

Você: "Quanto tempo falta?"
Jarvis: "Faltam 12 minutos."
```

## Integrações Futuras

### Calendário (a implementar)
```
Você: "Qual meu próximo compromisso?"
Jarvis: "Seu próximo compromisso é reunião com João às 15h."

Você: "Agende reunião com Maria para terça às 14h"
Jarvis: "Reunião agendada com Maria para terça-feira às 14h."
```

### E-mail (a implementar)
```
Você: "Tenho e-mails importantes?"
Jarvis: "Você tem 3 e-mails não lidos marcados como importantes."

Você: "Leia o primeiro"
Jarvis: "E-mail de João Silva, assunto: Proposta de projeto..."
```

### Casa Inteligente (a implementar)
```
Você: "Acenda as luzes da sala"
Jarvis: "Luzes da sala acesas."

Você: "Qual a temperatura da casa?"
Jarvis: "A temperatura atual é 22°C."
```

## Dicas de Uso

### 1. Seja Natural
```
✅ "Me lembre de comprar leite"
✅ "Que horas são?"
✅ "Como está o tempo?"

❌ "CRIAR_LEMBRETE: comprar leite"
❌ "GET_TIME()"
```

### 2. Contexto Importa
```
Você: "Anote: reunião importante amanhã"
Jarvis: "Anotado."

Você: "A que horas?"
Jarvis: "Você não especificou o horário. A que horas é a reunião?"
```

### 3. Correções
```
Você: "Me lembre de ligar para João"
Jarvis: "Lembrete criado."

Você: "Na verdade, é para ligar para Maria"
Jarvis: "Entendido. Atualizei o lembrete para ligar para Maria."
```

### 4. Comandos Compostos
```
Você: "Me lembre de comprar leite e também anote que preciso ir ao banco"
Jarvis: "Entendido. Criei um lembrete para comprar leite e anotei que você precisa ir ao banco."
```

## Atalhos Personalizados

### Atalho: "Resumo do Dia"
```
Você: "Hey Siri, resumo do dia"
Jarvis: "Bom dia! Hoje é [data]. Você tem [X] compromissos: [lista]. Lembretes pendentes: [lista]."
```

### Atalho: "Status"
```
Você: "Hey Siri, status"
Jarvis: "Todos os sistemas operacionais. Última conversa: [tempo]. Lembretes ativos: [número]."
```

### Atalho: "Boa Noite"
```
Você: "Hey Siri, boa noite"
Jarvis: "Boa noite! Amanhã você tem [compromissos]. Durma bem!"
```

## Personalização

### Modificar Personalidade

Edite `main.py` na Oracle VM:

```python
# Linha ~50
full_prompt = f"""Você é Jarvis, um assistente pessoal [PERSONALIDADE].

Características:
- [Característica 1]
- [Característica 2]
- [Característica 3]

Contexto relevante:
{context}

Usuário: {prompt}

Jarvis:"""
```

**Exemplos de personalidade:**

**Formal:**
```python
"""Você é Jarvis, um assistente pessoal formal e profissional.

Características:
- Sempre use tratamento formal
- Seja conciso e direto
- Priorize eficiência
```

**Casual:**
```python
"""Você é Jarvis, um assistente pessoal descontraído e amigável.

Características:
- Use linguagem casual
- Seja conversacional
- Adicione humor quando apropriado
```

**Técnico:**
```python
"""Você é Jarvis, um assistente pessoal técnico e detalhista.

Características:
- Forneça explicações técnicas
- Use terminologia precisa
- Seja detalhado nas respostas
```

## Comandos de Sistema

### Ver Histórico
```bash
# Via API
curl -X GET https://seu-dominio.com/history \
  -H "X-Api-Key: SUA_KEY"
```

### Limpar Histórico
```bash
# Na Oracle VM
psql -U assistant -d personal_kb
DELETE FROM conversations WHERE timestamp < NOW() - INTERVAL '30 days';
\q
```

### Backup Manual
```bash
# Na Oracle VM
~/backup.sh
```

## Troubleshooting de Comandos

### "Não entendi"
```
Problema: Jarvis não entende o comando
Solução: Reformule de forma mais clara

❌ "Faz aquilo que eu te pedi ontem"
✅ "Me lembre do que conversamos ontem sobre o projeto"
```

### "Erro ao processar"
```
Problema: Erro interno
Solução: Verifique logs

# Na VM
sudo journalctl -u jarvis -n 50
```

### Resposta Lenta
```
Problema: Demora muito para responder
Solução: 
1. Verifique RAM: free -h
2. Use modelo menor se necessário
3. Reduza contexto
```

## Exemplos de Fluxos Completos

### Fluxo 1: Planejamento de Dia
```
08:00 - Você: "Bom dia, Jarvis"
        Jarvis: "Bom dia! Hoje você tem 3 compromissos..."

09:00 - Você: "Me lembre de revisar o relatório"
        Jarvis: "Lembrete criado."

12:00 - Você: "Quais meus lembretes?"
        Jarvis: "Você tem 1 lembrete: revisar o relatório."

14:00 - Você: "Anote: ideias para o projeto X"
        Jarvis: "Anotado."

18:00 - Você: "Resuma meu dia"
        Jarvis: "Hoje você teve 3 compromissos, criou 1 lembrete..."
```

### Fluxo 2: Sessão de Trabalho
```
Você: "Vou começar uma sessão de trabalho focado"
Jarvis: "Entendido. Boa sessão de trabalho!"

Você: "Timer de 25 minutos"
Jarvis: "Timer iniciado."

[25 minutos depois]
Jarvis: "Timer finalizado. Hora de fazer uma pausa."

Você: "Anote: completei a tarefa X"
Jarvis: "Anotado."
```

### Fluxo 3: Brainstorming
```
Você: "Preciso de ideias para um projeto de app"
Jarvis: "Claro! Que tipo de app você está pensando?"

Você: "Um app de produtividade"
Jarvis: "Aqui estão algumas ideias: 1) App de pomodoro com gamificação..."

Você: "Anote a ideia 2"
Jarvis: "Anotado: [ideia 2]"
```

## Próximos Passos

1. Experimente os comandos básicos
2. Crie seus próprios atalhos personalizados
3. Ajuste a personalidade do Jarvis
4. Adicione integrações customizadas

---

**Dica:** Quanto mais você usar, melhor o Jarvis entenderá seu contexto e preferências!
