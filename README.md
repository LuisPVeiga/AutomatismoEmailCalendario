# Automação de Emails para Contas a Pagar

**Versão**: 1.1.0 | **Status**: ✅ PASSOS 1-8 Completos — Pronto para produção

Aplicação Python que automatiza a gestão de contas a pagar (água, luz, gás, comunicações, seguros):

- ✅ Lê emails não lidos do Gmail (até 100 por execução)
- 📋 Filtra e classifica emails com contas a pagar
- 📄 Extrai dados de PDFs em anexo (valor, vencimento, referência)
- 📅 Cria eventos no Google Calendar com notificações
- 💬 Envia notificações via Telegram
- 🔄 Rastreia emails processados para evitar duplicados
- ⏱️ Executa manualmente ou agendado (launchd/cron/Task Scheduler)
- 📷 Bot Telegram recebe fotos de contas em papel → OCR → Calendar

---

## 📋 Progresso

### ✅ Implementado
- **PASSO 1**: Setup e autenticação Gmail
  - Estrutura modular com serviços separados
  - Autenticação OAuth com Google
  - Leitura de emails não lidos
  - Extração de anexos
- **PASSO 2**: Filtrar e classificar emails
  - Scoring de confiança com `classify_email()`
  - +30 fornecedores portugueses em `KNOWN_PROVIDERS`
  - Validação de PDF por extensão + MIME type
  - Detecção de anexos recursiva (multipart aninhado)
- **PASSO 3**: Extração de dados de PDFs
  - Padrões regex por tipo de conta
  - Suporte a formatos PT/EN de números e datas
  - OCR de fallback via pytesseract
  - Extração de referências Multibanco
- **PASSO 4**: Integração Google Calendar
  - Eventos `[Pagar] <entidade>` com cor vermelha
  - Convidados via `CALENDAR_GUESTS` no `.env`
  - Detecção de duplicados
  - Notificações 1 dia antes e no próprio dia
- **PASSO 5**: Notificações Telegram
  - Mensagens formatadas por conta processada
  - Referência Multibanco formatada
- **PASSO 6**: Orquestração completa
  - Pipeline completo com métricas e tratamento de erros
  - Registo de estado para evitar duplicados
- **PASSO 7**: Agendamento automático
  - Scripts para Windows, macOS e Linux
  - Configuração interativa via `schedule_setup.py`

- **PASSO 8**: Telegram Bot para fotos
  - Bot recebe fotos de contas em papel via Telegram
  - OCR com tesseract — pré-processamento multi-variante (autocontrast + thresholds) robusto a papel texturado; selecciona automaticamente a variante com melhor leitura
  - Extrai valor (`Total (€)` robusto a variações OCR como `Total (E)`, valor em coluna separada, etc.)
  - Usa `data do débito` como data de vencimento (ignorando `data de emissão`)
  - Fallback por último recurso: quando OCR não lê nenhum label, recolhe todos os decimais no intervalo válido
  - Extrai vencimento, referência MB usando os mesmos regex dos PDFs
  - Caption da foto usada como nome da entidade → `[Pagar] <entidade>` no Calendar
  - Aceita também PDFs enviados directamente ao bot
  - Quando valor não é encontrado, bot envia o texto OCR bruto para diagnóstico
  - Polling a cada 60 segundos — não requer servidor exposto na internet

---

## � Diagrama de Comunicações

```
╔══════════════════════════════════════════════════════════════════════╗
║                         A TUA MÁQUINA                               ║
║                                                                      ║
║  ┌──────────────────────────────────────────────────────────────┐   ║
║  │  PROCESSO 1 — Pipeline de emails (agendado às 08:00)         │   ║
║  │                                                              │   ║
║  │   launchd/cron ──► main.py                                   │   ║
║  │                        │                                     │   ║
║  │          ┌─────────────┼──────────────┐                      │   ║
║  │          ▼             ▼              ▼                      │   ║
║  │    GmailService   PDFExtractor  CalendarService              │   ║
║  │          │             │              │                      │   ║
║  │          │        StateManager        │                      │   ║
║  │          └─────────────┴──────────────┘                      │   ║
║  │                        │                                     │   ║
║  │                  TelegramService ──────────────────────────► ║── ║─► Telegram
║  └──────────────────────────────────────────────────────────────┘   ║
║                                                                      ║
║  ┌──────────────────────────────────────────────────────────────┐   ║
║  │  PROCESSO 2 — Bot Telegram (contínuo, polling 60s)           │   ║
║  │                                                              │   ║
║  │   bot.py ◄─────── polling getUpdates ◄───────────────────── ║── ║─► Telegram
║  │      │                                                       │   ║
║  │      ├── foto  ──► ImageProcessor (OCR) ──► dados            │   ║
║  │      │                                       │               │   ║
║  │      └── PDF   ──► PDFExtractor      ──► dados               │   ║
║  │                                             │                │   ║
║  │                           ┌────────────────┴──┐             │   ║
║  │                           ▼                   ▼             │   ║
║  │                    CalendarService      TelegramService ──► ║── ║─► Telegram
║  └──────────────────────────────────────────────────────────────┘   ║
╚══════════════════════════════════════════════════════════════════════╝

APIs externas contactadas:

  ┌─────────────────┐    ┌──────────────────────┐    ┌───────────────────┐
  │   Gmail API      │    │  Google Calendar API  │    │  Telegram Bot API │
  │  (Google)        │    │  (Google)             │    │                   │
  │                  │    │                       │    │                   │
  │ · list messages  │    │ · insert event        │    │ · getUpdates      │
  │ · get message    │    │ · list events         │    │ · getFile         │
  │ · get attachment │    │ · delete event        │    │ · sendMessage     │
  │ · modify (read)  │    │                       │    │ · getMe           │
  └─────────────────┘    └──────────────────────┘    └───────────────────┘
        ▲                          ▲                          ▲ ▼
        │            OAuth 2.0     │                  Bot Token│ │ polling
        └──────────────────────────┘                          │ │
                                                        Telemóvel
                                                   (envia foto via Telegram)
```

**Nota de segurança**: A tua máquina nunca está exposta na internet.
Ambos os processos abrem ligações para fora (Google/Telegram) — nunca aceitam ligações de fora.

---

## �🚀 Quickstart

### 1. Clonar e Configurar

```bash
# Clonar repositório (ou apenas extrair a pasta)
cd AutomatismoEmailCalendario

# Criar ambiente virtual
python -m venv venv
venv\Scripts\activate  # Windows
# ou
source venv/bin/activate  # macOS/Linux

# Instalar dependências
pip install -r requirements.txt
```

### 2. Criar Pasta e Ficheiros de Configuração

A pasta `config/` deve existir com os ficheiros de estado e credenciais:

```bash
mkdir config

# Criar ficheiro de estado (emails processados)
echo '{"emails": {}, "last_run": null}' > config/processed_emails.json
```

> Os ficheiros `config/token.json` e `config/calendar_token.json` são gerados automaticamente na primeira autenticação.  
> O ficheiro `config/credentials.json` deve ser descarregado do Google Cloud Console (ver passo seguinte).

### 2. Configurar Credenciais Gmail

1. Ir para [Google Cloud Console](https://console.cloud.google.com/)
2. Criar novo projeto
3. Ativar APIs: **Gmail API** e **Google Calendar API**
4. Criar credenciais **OAuth 2.0** (Desktop Application)
5. Descarregar JSON e salvar como `config/credentials.json`

### 3. Configurar Telegram (Opcional)

1. Criar bot com [@BotFather](https://t.me/botfather)
2. Guardar o **Bot Token**
3. Criar grupo/canal no Telegram
4. Enviar `/start` ao bot para obter **Chat ID**
5. Preencher `.env`:
   ```bash
   cp .env.example .env
   ```
   Editar `.env` com:
   ```
   TELEGRAM_BOT_TOKEN=seu_token
   TELEGRAM_CHAT_ID=seu_chat_id
   ```

### 4. Instalar Tesseract (necessário para OCR de fotos)

```bash
# macOS 14 (Sonoma) ou superior
brew install tesseract tesseract-lang

# macOS 13 (Ventura) ou inferior
# O Homebrew pode falhar com erro de permissões. Corrigir primeiro:
sudo chown -R $(whoami) /usr/local/share/man/man8
chmod u+w /usr/local/share/man/man8
# Depois instalar normalmente:
brew install tesseract tesseract-lang

# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-por

# Windows — descarregar instalador em:
# https://github.com/UB-Mannheim/tesseract/wiki
# (selecionar Portuguese como linguagem adicional)
```

### Testar Ligações

> ⚠️ Executar sempre a partir da **raiz do projeto** (`AutomatismoEmailCalendario/`)

```bash
python -m src.test_connections          # Testa Gmail, Calendar e Telegram
python -m src.test_connections gmail    # Só Gmail
python -m src.test_connections calendar # Só Calendar
python -m src.test_connections telegram # Só Telegram
```

### Correr o Bot Telegram (fotos)

```bash
# Num terminal separado — corre em paralelo com o agendamento
python -m src.bot
```

O bot fica à escuta de fotos e PDFs enviados para o chat configurado no `.env`. Não precisa de servidor exposto — usa polling (o bot contacta o Telegram, não o contrário).

**Como usar o bot:**
1. Abre o Telegram e vai ao chat do bot
2. Envia uma foto de uma conta em papel
3. (Opcional) Adiciona o nome da entidade como legenda (ex: `EDP`, `Água Lisboa`)
4. O bot responde com os dados extraídos e confirma o evento no Calendar

### Agendar Automático (pipeline de emails)

```bash
python config/schedule_setup.py install  # Instalar agendamento diário
python config/schedule_setup.py status   # Ver estado
python config/schedule_setup.py remove   # Remover agendamento
```

---

## 📁 Estrutura do Projeto

```
AutomatismoEmailCalendario/
├── src/
│   ├── services/
│   │   ├── gmail_service.py         # Leitura de emails ✅
│   │   ├── pdf_extractor.py         # Extração de PDFs ✅
│   │   ├── calendar_service.py      # Google Calendar ✅
│   │   ├── telegram_service.py      # Notificações ✅
│   │   ├── state_manager.py         # Rastreio de estado ✅
│   │   └── image_processor.py       # OCR de imagens ✅
│   ├── main.py                      # Orquestração (pipeline emails) ✅
│   ├── bot.py                       # Telegram Bot (fotos/PDFs) ✅
│   ├── test_connections.py          # Testes de ligação ✅
│   ├── config.py                    # Configurações ✅
│   └── __init__.py
├── config/
│   ├── credentials.json             # Credenciais Google (não commitar)
│   ├── token.json                   # Token Gmail (não commitar)
│   ├── calendar_token.json          # Token Calendar (não commitar)
│   ├── processed_emails.json        # Estado de emails processados
│   ├── run_automation.bat           # Script de execução Windows
│   ├── run_automation.sh            # Script de execução macOS/Linux
│   └── schedule_setup.py            # Configuração de agendamento
├── logs/
│   ├── logs.txt                     # Log contínuo da aplicação
│   └── run_YYYYMMDD_HHMMSS.log      # Log por execução (gerado pelos scripts)
├── .env                             # Variáveis de ambiente (não commitar)
├── .env.example                     # Modelo de .env
├── requirements.txt                 # Dependências ✅
├── README.md                        # Esta documentação
├── CONTEXTO.md                      # Detalhes técnicos
└── .gitignore                       # Arquivos a ignorar

```

---

## 🔧 Configuração Detalhada

### Gmail OAuth Setup

1. No Google Cloud Console, criar credenciais:
   - Tipo: OAuth 2.0 Client ID
   - Aplicação: Desktop Application
   - Descarregar como JSON

2. A primeira execução abrirá navegador para autenticação
3. Token será salvo em `config/token.json` para próximas execuções

### Variáveis de Ambiente (.env)

```ini
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxYZ
TELEGRAM_CHAT_ID=-1001234567890
CALENDAR_GUESTS=email1@gmail.com,email2@gmail.com
ADMIN_EMAIL=seu_email@gmail.com
SCHEDULE_TIMES=08:00
QUIET_HOURS_START=22
QUIET_HOURS_END=8
```

---

## 💻 Uso Manual

### Executar uma vez

```bash
python src/main.py
```

Saída esperada (após implementação completa):
```
✓ Autenticado com Gmail
✓ Encontrados 12 emails não lidos (máx. 100)
✓ Filtrados 3 contas a pagar
✓ Extraído: €85.50 (vence 2026-05-15)
✓ Evento criado no Calendar
✓ Notificação enviada ao Telegram
```

### Agendar no Windows (PASSO 7)

```bash
# Utilizar o script incluído
config/run_automation.bat   # Windows
./config/run_automation.sh  # macOS/Linux
```

Depois usar `Task Scheduler` do Windows para agendar execução.

---

## 🛠️ Troubleshooting

### Erro: "config/credentials.json não encontrado"
- Descarregar arquivo de credenciais do Google Cloud Console
- Salvar na pasta `config/` com nome `credentials.json`

### Erro: "Telegram não está configurado"
- Preencher `.env` com `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`
- Ou executar sem Telegram (funciona normalmente)

### Erro: "Permission denied" (Gmail)
- Ir em Google Account Settings
- Verificar se app está autorizado
- Deletar `config/token.json` e fazer login novamente

---

## 📊 Logs e Estado

- **logs/logs.txt**: Log contínuo de execução da aplicação
- **logs/run_YYYYMMDD_HHMMSS.log**: Log por execução gerado pelos scripts de agendamento (limpos automaticamente após 30 dias)
- **config/processed_emails.json**: Emails já processados (evita duplicados)
- **config/token.json**: Token de autenticação Gmail (NÃO commitar)

---

##  Notas Importantes

1. **Segurança**: Nunca commitar `config/credentials.json`, `config/token.json` ou `.env`
2. **Limite de API**: Google tem limites de requisições (1.000/dia para Gmail)
3. **Rastreio**: Emails já processados são registados em `config/processed_emails.json`
4. **Timezone**: Aplicação usa servidor local (ajustar se necessário)
5. **Reautenticar**: Após alterar scopes ou credenciais, apagar `config/token.json` e correr novamente

---

## 📞 Support

Para problemas:
1. Verificar logs em `logs/logs.txt`
2. Verificar se credenciais estão corretas
3. Reautenticar (deletar `config/token.json` e `config/calendar_token.json`)

---

**Última atualização**: Abril 2026
**Desenvolvido para**: macOS / Linux / Windows — Python 3.10+
