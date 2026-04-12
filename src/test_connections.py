"""
test_connections.py — Testa as três ligações externas do projeto

Uso:
    python -m src.test_connections          # Corre os 3 testes
    python -m src.test_connections gmail    # Só Gmail
    python -m src.test_connections calendar # Só Calendar
    python -m src.test_connections telegram # Só Telegram
"""

import sys
from datetime import datetime, timedelta

PASS = "✅"
FAIL = "❌"
SEP  = "─" * 50


def _header(title: str):
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


# ---------------------------------------------------------------------------
# 1. Gmail
# ---------------------------------------------------------------------------

def test_gmail() -> bool:
    _header("1 / 3 — Gmail")
    try:
        from .services.gmail_service import GmailService

        gmail = GmailService()
        print(f"{PASS}  Autenticação OK")

        emails = gmail.get_unread_emails(max_results=5)
        print(f"{PASS}  Emails não lidos encontrados: {len(emails)}")

        for e in emails[:3]:
            print(f"     • [{e.get('bill_type','—')}] {e['subject'][:60]}")

        return True

    except FileNotFoundError as exc:
        print(f"{FAIL}  credentials.json não encontrado: {exc}")
    except Exception as exc:
        print(f"{FAIL}  Erro: {exc}")
    return False


# ---------------------------------------------------------------------------
# 2. Google Calendar
# ---------------------------------------------------------------------------

def test_calendar() -> bool:
    _header("2 / 3 — Google Calendar")
    try:
        from .services.calendar_service import CalendarService

        calendar = CalendarService()
        print(f"{PASS}  Autenticação OK")

        # Criar evento de teste amanhã
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        event_id = calendar.create_bill_event(
            entidade="Teste Automação",
            bill_type="outro",
            valor=0.01,
            vencimento=tomorrow,
            referencia_doc="TESTE-001",
            guests=[],
        )

        if event_id:
            print(f"{PASS}  Evento de teste criado (ID: {event_id})")
            print(f"     Título: [PAGAR] Teste Automação — {tomorrow}")

            # Apagar logo após criar
            deleted = calendar.delete_event(event_id)
            if deleted:
                print(f"{PASS}  Evento de teste apagado (limpeza OK)")
            return True
        else:
            print(f"{FAIL}  Falha ao criar evento")
    except FileNotFoundError as exc:
        print(f"{FAIL}  credentials.json não encontrado: {exc}")
    except Exception as exc:
        print(f"{FAIL}  Erro: {exc}")
    return False


# ---------------------------------------------------------------------------
# 3. Telegram
# ---------------------------------------------------------------------------

def test_telegram() -> bool:
    _header("3 / 3 — Telegram")
    try:
        from .services.telegram_service import TelegramService

        telegram = TelegramService()

        if not telegram.test_connection():
            print(f"{FAIL}  Bot inacessível (verifica TELEGRAM_BOT_TOKEN no .env)")
            return False

        print(f"{PASS}  Conexão ao bot OK")

        sent = telegram.send_message(
            "🤖 <b>Teste de Ligação</b>\n"
            "─────────────────────\n"
            "A automação de contas a pagar está corretamente configurada.\n"
            f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        )

        if sent:
            print(f"{PASS}  Mensagem de teste enviada com sucesso")
            return True
        else:
            print(f"{FAIL}  Falha ao enviar mensagem (verifica TELEGRAM_CHAT_ID no .env)")
    except Exception as exc:
        print(f"{FAIL}  Erro: {exc}")
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

TESTS = {
    "gmail":    test_gmail,
    "calendar": test_calendar,
    "telegram": test_telegram,
}

def main():
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    print("\n" + "=" * 50)
    print("  Testes de Ligação — Automação Contas a Pagar")
    print("=" * 50)

    if arg != "all" and arg not in TESTS:
        print(f"Argumento inválido: '{arg}'. Opções: gmail, calendar, telegram")
        sys.exit(1)

    to_run = [arg] if arg != "all" else list(TESTS.keys())
    results = {}

    for name in to_run:
        results[name] = TESTS[name]()

    # Resumo
    print(f"\n{'=' * 50}")
    print("  Resumo")
    print("=" * 50)
    all_ok = True
    for name, ok in results.items():
        status = PASS if ok else FAIL
        print(f"  {status}  {name.capitalize()}")
        if not ok:
            all_ok = False

    print()
    if all_ok:
        print("  Tudo pronto — pode correr: python -m src.main")
    else:
        print("  Corrige os erros acima antes de executar o pipeline.")
    print()

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
