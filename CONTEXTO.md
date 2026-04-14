# CONTEXTO TÉCNICO - Automação de Emails para Contas a Pagar

**Última Atualização**: Abril 2026  
**Versão do Projeto**: 1.1.0  
**Status Atual**: ✅ PASSO 8 Completo — Telegram Bot para fotos

---

## 📊 Estado das Funcionalidades

### ✅ Implementado (PASSO 1)

#### `src/config.py`
- Configurações centralizadas
- Variáveis de ambiente (.env)
- Palavras-chave para identificação de contas (agua, luz, gas, comunicacoes, seguros)
- Padrões regex para extração (valor, vencimento, referência)

#### `src/services/gmail_service.py`
- ✅ Autenticação OAuth com Google
- ✅ Leitura de emails não lidos
- ✅ Extração de detalhes do email (subject, sender, body, attachments)
- ✅ Download de anexos
- ✅ Filtro básico de contas a pagar (com PDFs)
- ✅ Marcar emails como lidos

**Métodos principais**:
```python
gmail = GmailService()
emails = gmail.get_unread_emails(max_results=100)
bills = gmail.filter_bills(emails)
```

#### `src/services/state_manager.py`
- ✅ Rastreio de emails processados (JSON)
- ✅ Marcar emails como processados
- ✅ Verificar se email já foi processado
- ✅ Guardar data da última execução

**Métodos principais**:
```python
manager = StateManager()
if not manager.is_processed(email_id):
    manager.mark_as_processed(email_id, data)
```

#### `src/services/pdf_extractor.py`
- ✅ Extração de PDF a partir de bytes
- ✅ Padrões regex para valor (€, formato decimal)
- ✅ Padrões regex para vencimento (DD/MM/YYYY)
- ✅ Padrões regex para referência (FAC2026-001, etc.)
- ✅ Parsing de múltiplos formatos de data
- ⚠️ Não faz OCR (assume PDF com texto)

**Métodos principais**:
```python
extractor = PDFExtractor()
pdf_bytes = gmail.download_attachment(message_id, part_id)
data = extractor.extract_from_file(pdf_bytes)
# Returns: {"valor": 85.50, "vencimento": "2026-05-15", "referencia": "FAC2026-001"}
```

#### `src/services/calendar_service.py`
- ✅ Autenticação Google Calendar API
- ✅ Criação de eventos
- ✅ Notificações automáticas (1 dia antes + mesmo dia)
- ✅ Descrição formatada com emojis
- ✅ Listagem de eventos próximos

**Métodos principais**:
```python
calendar = CalendarService()
event_id = calendar.create_event(
    title="Fatura Luz",
    bill_type="luz",
    valor=85.50,
    vencimento="2026-05-15",
    referencia="FAC001"
)
```

#### `src/services/telegram_service.py`
- ✅ Autenticação com Telegram Bot
- ✅ Envio de mensagens formatadas (HTML)
- ✅ Notificações de contas com emojis
- ✅ Resumo de execução
- ✅ Teste de conexão

**Métodos principais**:
```python
telegram = TelegramService()
telegram.send_bill_notification(
    bill_type="luz",
    valor=85.50,
    vencimento="2026-05-15"
)
telegram.send_summary(10, 3, 250.75, 3)
```

#### `src/services/image_processor.py`
- ✅ Implementado (PASSO 8, revisto Abril 2026)
- ✅ `validate_image(image_bytes)` — valida com PIL
- ✅ `process_from_bytes(image_bytes, bill_type, entidade_nome)` — pré-processamento multi-variante + OCR `por+eng` + delega extração para `PDFExtractor._extract_data()`
- ✅ `process_from_file(image_path)` — delega para `process_from_bytes()`
- ✅ Retorna mesmo formato de `PDFExtractor.extract_from_file()` com `metodo_extracao="ocr_image"` + `_ocr_text` para diagnóstico
- ✅ Pré-processamento multi-variante: `ImageOps.autocontrast` + thresholds variados + escala mínima 1500px; escolhe automaticamente a variante com mais caracteres alfanuméricos reconhecidos
- ✅ Logging via `logger.info` → visível nos logs do bot (`logs/logs.txt` via handler configurado em `bot.py`)

#### Ficheiros de Suporte
- ✅ `requirements.txt` - Dependências Python
- ✅ `.env.example` - Modelo de configurações
- ✅ `.gitignore` - Arquivos a ignorar
- ✅ `README.md` - Guia de utilização
- ✅ `CONTEXTO.md` - Este arquivo

---

### ⏳ Por Implementar

#### ✅ PASSO 2: Filtrar & Classificar Emails
**Responsável**: `gmail_service.py` + `config.py`

- ✅ `classify_email()` com scoring de confiança (fornecedor: +3, keyword: +1, palavra faturação: +2, PDF: +2)
- ✅ `KNOWN_PROVIDERS` com +30 fornecedores portugueses (EDP, MEO, NOS, Vodafone, EPAL, Galp, AXA…)
- ✅ `MIN_CONFIDENCE_SCORE = 3` — threshold configurável
- ✅ `_has_valid_pdf()` valida extensão (.pdf) E MIME type (application/pdf)
- ✅ `_get_attachments()` recursivo — suporta multipart aninhado e usa `attachmentId` correto
- ✅ `filter_bills()` ignora emails já processados, reporta motivos de exclusão
- ✅ Email enriquecido: `bill_type`, `confidence`, `matched_keywords`, `matched_providers`

#### ✅ PASSO 3: Extrair Dados de PDFs
**Responsável**: `pdf_extractor.py`

- ✅ Padrões regex pré-compilados (cache em memória)
- ✅ Padrões específicos por tipo de conta (`_PROVIDER_PATTERNS`): luz, agua, gas, comunicacoes, seguros
- ✅ `_parse_value()` suporta formatos PT (1.234,56), EN (1,234.56) e simples
- ✅ Datas por extenso: "15 de maio de 2026"
- ✅ Validação de intervalo de valor por tipo de conta
- ✅ Extração de referência Multibanco (entidade 5 dígitos + referência 9 dígitos)
- ✅ OCR via pytesseract + pdf2image (graceful — só ativa se tesseract estiver instalado)
- ✅ Campo `metodo_extracao` e `campos_encontrados` no resultado
- ✅ `extract_from_file(pdf_bytes, bill_type)` aceita tipo de conta para aplicar padrões corretos
- ✅ `Total (€)` robusto a variações OCR: aceita `(E)`, `(e)`, sem parênteses, valor na linha seguinte (duas colunas)
- ✅ `data do débito` reconhecida como data de vencimento preferencial (acima de `data de emissão`)
- ✅ `_EMISSAO_LABELS` ignora datas precedidas por labels de emissão (incluindo corrupções OCR como `emissio`)
- ✅ `_extract_value_near_total()` — fallback para layout duas colunas: procura número decimal após linha "Total"
- ✅ `_extract_value_last_resort()` — último recurso quando OCR não lê nenhum label: recolhe todos os decimais no intervalo válido e devolve o maior

#### ✅ PASSO 4: Google Calendar API
**Responsável**: `calendar_service.py`

- ✅ Título do evento: `[PAGAR] <entidade>` (ex: "[PAGAR] Iberdrola")
- ✅ `create_bill_event()` — aceita `entidade, bill_type, valor, vencimento, mb_entidade, mb_referencia, referencia_doc, guests`
- ✅ Convidados configuráveis: param `guests` explícito **ou** `CALENDAR_GUESTS` no `.env` (emails separados por vírgula)
- ✅ Detecção de duplicados — verifica se já existe evento para a mesma entidade e data antes de criar
- ✅ Descrição estruturada: tipo, entidade, valor, vencimento, nº fatura, MB entidade/referência
- ✅ `sendUpdates="all"` — envia convite por email aos convidados quando adicionados
- ✅ Notificações: 1 dia antes + no próprio dia
- ✅ `get_upcoming_events(days)` e `delete_event(id)` mantidos

#### ✅ PASSO 5: Telegram
**Responsável**: `telegram_service.py`

- ✅ `send_bill_notification()` alinhado com output do PASSO 3: `entidade, bill_type, valor, vencimento, mb_entidade, mb_referencia, referencia_doc, calendar_event_id`
- ✅ Formato de mensagem estruturado com emojis, separador e campos condicionais
- ✅ MB Referência formatada com espaços (XXX XXX XXX) para facilitar leitura
- ✅ `send_summary()` com detalhe opcional por conta (entidade, valor, vencimento)
- ✅ `send_message()` genérico mantido para uso livre no pipeline
- ✅ `test_connection()` valida token e mostra username do bot

#### ✅ PASSO 6: Orquestração Completa
**Responsável**: `src/main.py`

- ✅ Classe `BillAutomation` com `run()` — liga todos os serviços
- ✅ `_process_bill()` — pipeline completo por email: PDF → extração → Calendar → Telegram → estado
- ✅ `_download_pdf()` — descarrega primeiro PDF válido do email (por extensão + MIME)
- ✅ `_resolve_entidade()` — nome via `matched_providers` ou fallback ao remetente
- ✅ Métricas de execução: emails_lidos, contas_encontradas, processadas, eventos_criados, notificacoes_enviadas, erros, valor_total
- ✅ Resumo Telegram com detalhe de cada conta no final
- ✅ Logging duplo: ficheiro `logs/logs.txt` + consola
- ✅ Tratamento de erros por conta (não interrompe o pipeline se uma falhar)
- ✅ `main()` com saída formatada e `sys.exit(1)` em caso de erro fatal

#### ✅ PASSO 7: Agendamento Automático
**Responsável**: `config/run_automation.bat`, `config/run_automation.sh`, `config/schedule_setup.py`

- ✅ `config/run_automation.bat` melhorado — log rotacionado por timestamp em `logs\`, limpeza automática de logs >30 dias
- ✅ `config/run_automation.sh` (macOS/Linux) — mesma lógica, usa `set -euo pipefail`, compativel com cron e launchd
- ✅ `config/schedule_setup.py` — script interativo cross-platform:
  - **Windows**: instala/remove/verifica via `schtasks` (Task Scheduler)
  - **macOS**: instala/remove/verifica via `launchd` (plist em `~/Library/LaunchAgents`)
  - **Linux**: instala/remove/verifica via `crontab`
  - Hora configuravel (padrão 08:00)
  - Comandos: `install`, `remove`, `status` (executar via `python config/schedule_setup.py`)

#### PASSO 8: Telegram Bot para Fotos
**Responsável**: `src/bot.py` + `src/services/image_processor.py`

- ✅ `src/bot.py` — runner do bot com `python-telegram-bot` v20 (async)
- ✅ `handle_photo()` — descarrega foto de maior resolução, chama `ImageProcessor`, cria evento Calendar, responde ao utilizador
- ✅ `handle_document()` — aceita PDFs enviados directamente ao bot, usa `PDFExtractor`
- ✅ Caption da foto usada como `entidade_nome` → título `[Pagar] <entidade>` no Calendar
- ✅ Se sem caption: auto-detecção via `classify_email()` no texto OCR
- ✅ `/start` e `/help` com instruções
- ✅ Polling `poll_interval=60s` — sem servidor exposto na internet
- ✅ Quando valor não é extraído: bot envia o texto OCR bruto de volta ao utilizador para diagnóstico
- ✅ `ImageProcessor` com pré-processamento multi-variante (autocontrast + thresholds) robusto a papel texturado

**Pré-requisito de sistema**: `brew install tesseract tesseract-lang`

**Execução**: `python -m src.bot` (paralelo com o agendamento em `main.py`)

---

## 🏗️ Arquitetura Técnica

### Fluxo Completo (quando terminar)

```
┌─────────────────────────────────────────────────────────────┐
│ Windows Task Scheduler (ou execução manual)                 │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
        ┌────────────────┐
        │  main.py       │ (PASSO 6)
        │  Orquestrador  │
        └────────┬───────┘
                 │
      ┌──────────┼──────────┐
      │          │          │
      ▼          ▼          ▼
  ┌────────┐ ┌─────────┐ ┌──────────┐
  │ Gmail  │ │  PDF    │ │ Calendar │
  │Service │─│Extractor│─│ Service  │
  └────┬───┘ └────┬────┘ └────┬─────┘
       │          │           │
       │    ┌─────▼────┐      │
       │    │ State    │      │
       │    │ Manager  │      │
       │    └──────────┘      │
       │                      │
       └──────────┬───────────┘
                  │
                  ▼
            ┌─────────────┐
            │ Telegram    │
            │ Service     │
            └─────────────┘
```

### Requisições à API

**Gmail API**:
- `users().messages().list()` - listar emails
- `users().messages().get()` - detalhes do email
- `users().messages().attachments().get()` - descarregar anexo
- `users().messages().modify()` - marcar como lido

**Google Calendar API**:
- `events().insert()` - criar evento
- `events().list()` - listar eventos
- `events().delete()` - deletar evento

**Telegram Bot API**:
- `getUpdates` (polling) — receber fotos e PDFs enviados ao bot
- `getFile` / download — descarregar imagem recebida
- `sendMessage` — enviar mensagem
- `getMe` — testar conexão

---

## 📊 Data Models

### Email Object
```python
{
    "id": "gmail_message_id",
    "subject": "Fatura de Eletricidade",
    "sender": "eletricidade@exemplo.com",
    "date": "2026-04-12",
    "body": "Dear customer...",
    "has_pdf": True,
    "attachments": [
        {
            "filename": "fatura_2026_04.pdf",
            "mime_type": "application/pdf",
            "part_id": "part_id_123"
        }
    ],
    "bill_type": "luz"  # Adicionado após filtro
}
```

### Extracted Bill Data
```python
{
    "valor": 85.50,           # €
    "vencimento": "2026-05-15", # YYYY-MM-DD
    "referencia": "FAC2026001",  # String
    "texto_completo": "..."   # Debug
}
```

### Calendar Event
```python
{
    "summary": "💡 Fatura de Eletricidade",
    "description": "💰 Tipo: Eletricidade\n💶 Valor: €85.50\n📋 Referência: FAC2026001",
    "start": {"date": "2026-05-15"},
    "end": {"date": "2026-05-15"},
    "reminders": {
        "overrides": [
            {"method": "notification", "minutes": 1440},  # 1 dia
            {"method": "notification", "minutes": 0}       # Mesmo dia
        ]
    }
}
```

### State (processed_emails.json)
```python
{
    "emails": {
        "gmail_id_1": {
            "processed_at": "2026-04-12T10:30:00",
            "data": {
                "subject": "Fatura",
                "bill_type": "luz",
                "valor": 85.50
            }
        }
    },
    "last_run": "2026-04-12T10:35:00"
}
```

---

## 🔐 Segurança

### Credenciais
- `config/credentials.json` - OAuth 2.0 do Google (NÃO commitar)
- `config/token.json` - Access token Gmail (NÃO commitar, gerado automaticamente)
- `config/calendar_token.json` - Access token Calendar (NÃO commitar, gerado automaticamente)
- `.env` - Tokens Telegram, convidados Calendar e outras configurações (NÃO commitar)

### Variáveis do `.env`

| Variável | Obrigatório | Descrição |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | Token do bot (obtido no @BotFather) |
| `TELEGRAM_CHAT_ID` | ✅ | ID do canal/grupo Telegram |
| `CALENDAR_GUESTS` | ⭕ | Emails convidados para eventos (separados por vírgula) |
| `ADMIN_EMAIL` | ❌ | Email do administrador (não usado atualmente) |
| `SCHEDULE_TIMES` | ❌ | Horários de execução (ex: `08:00`) |
| `QUIET_HOURS_START` | ❌ | Início de período de silêncio |
| `QUIET_HOURS_END` | ❌ | Fim de período de silêncio |

### Boas Práticas
1. Usar `.env` para todas as chaves sensíveis
2. `.gitignore` configurado para todos os ficheiros sensíveis
3. Reautenticar após alterar scopes: apagar `config/token.json`
4. Logging sem expor dados sensíveis

---

## 🐛 Conhecidas e Limitações

### Limitações Conhecidas
1. **OCR**: PDF Extractor não suporta PDFs escaneados (apenas texto)
2. **Gmail Limit**: Pipeline processa até 100 emails não lidos por execução; Google limita 1.000 requests/dia
3. **Padrões**: Padrões regex podem não capturar todos os formatos
4. **Timezone**: Usa timezone local (não UTC)
5. **Duplicação**: Eventos duplicam se script executar 2x no mesmo dia com mesmo vencimento

### ✅ PASSO 3 — Resolvido
- [x] Extração para PDFs escaneados (OCR opcional)
- [x] Cache de padrões compilados por tipo de conta
- [x] Validação de valores por intervalo por tipo

---

## 📂 Pasta `logs/`

- **`logs/logs.txt`** — log contínuo de execução (sobrescreve entre reinícios, appendado em cada run)
- **`logs/run_YYYYMMDD_HHMMSS.log`** — log por execução gerado pelos scripts `config/run_automation.sh` / `config/run_automation.bat`
- Logs com mais de 30 dias são apagados automaticamente pelos scripts de agendamento
- A pasta `logs/` existe no repositório mas o seu conteúdo está no `.gitignore` (`logs/*.txt`, `logs/*.log`)

---

## 🧪 Testes Implementados

```bash
# Testar todas as ligações (Gmail, Calendar, Telegram)
python -m src.test_connections

# Testar apenas uma ligação
python -m src.test_connections gmail
python -m src.test_connections calendar
python -m src.test_connections telegram
```

---

##  Referências

- [Gmail API Docs](https://developers.google.com/gmail/api)
- [Google Calendar API Docs](https://developers.google.com/calendar/api)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [PDFPlumber Docs](https://github.com/jsvine/pdfplumber)

---

**Desenvolvido por**: Automação Email Calendar Team  
**Python**: 3.10+  
**Ambiente**: Windows + Python venv
