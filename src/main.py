"""
Orquestrador principal — Automação de Contas a Pagar

Fluxo completo:
  1. Autenticar Gmail e obter emails não lidos
  2. Filtrar e classificar emails com contas a pagar (scoring)
  3. Para cada conta:
     a. Descarregar PDF em anexo
     b. Extrair dados (valor, vencimento, MB, entidade)
     c. Criar evento no Google Calendar ([PAGAR] Entidade)
     d. Enviar notificação Telegram
     e. Marcar email como lido e registar no estado
  4. Enviar resumo final via Telegram
  5. Registar logs
"""

import logging
import sys
from datetime import datetime
from typing import List, Dict

from src.config import LOG_FORMAT, LOG_DATE_FORMAT, LOGS_FILE
from src.services import (
    GmailService,
    PDFExtractor,
    CalendarService,
    TelegramService,
    StateManager,
)

# ---------------------------------------------------------------------------
# Logging — ficheiro + consola
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
    handlers=[
        logging.FileHandler(LOGS_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Orquestrador
# ---------------------------------------------------------------------------

class BillAutomation:
    """Orquestra todos os serviços para processar contas a pagar."""

    def __init__(self):
        logger.info("A inicializar serviços...")
        self.gmail    = GmailService()
        self.extractor = PDFExtractor()
        self.calendar = CalendarService()
        self.telegram = TelegramService()
        self.state    = StateManager()

    def run(self, max_emails: int = 100) -> Dict:
        """
        Executar o pipeline completo.

        Returns:
            dict com métricas da execução:
              emails_lidos, contas_encontradas, processadas, eventos_criados,
              notificacoes_enviadas, erros, valor_total, bills_detail
        """
        metrics = {
            "emails_lidos": 0,
            "contas_encontradas": 0,
            "processadas": 0,
            "eventos_criados": 0,
            "notificacoes_enviadas": 0,
            "erros": 0,
            "valor_total": 0.0,
            "bills_detail": [],
        }

        # ── 1. Ler emails ──────────────────────────────────────────────────
        logger.info("A obter emails não lidos...")
        emails = self.gmail.get_unread_emails(max_results=max_emails)
        metrics["emails_lidos"] = len(emails)

        if not emails:
            logger.info("Nenhum email não lido. Pipeline terminado.")
            return metrics

        # ── 2. Filtrar contas a pagar ──────────────────────────────────────
        logger.info("A filtrar contas a pagar...")
        bills = self.gmail.filter_bills(emails)
        metrics["contas_encontradas"] = len(bills)

        if not bills:
            logger.info("Nenhuma conta a pagar identificada.")
            return metrics

        # ── 3. Processar cada conta ────────────────────────────────────────
        for email in bills:
            try:
                self._process_bill(email, metrics)
            except Exception as e:
                metrics["erros"] += 1
                logger.error(f"Erro a processar email {email.get('id')}: {e}", exc_info=True)

        # ── 4. Finalizar ───────────────────────────────────────────────────────
        self.state.set_last_run()

        logger.info(
            f"Pipeline concluído — {metrics['processadas']} contas processadas, "
            f"€{metrics['valor_total']:.2f} total, {metrics['erros']} erros"
        )
        return metrics

    # ------------------------------------------------------------------
    # Processamento individual de uma conta
    # ------------------------------------------------------------------

    def _process_bill(self, email: Dict, metrics: Dict) -> None:
        """Processar uma única conta a pagar de ponta a ponta."""
        email_id   = email["id"]
        bill_type  = email.get("bill_type", "outro")
        entidade   = self._resolve_entidade(email)

        logger.info(f"A processar: '{entidade}' (tipo={bill_type}, email={email_id})")

        # ── a. Descarregar PDF ─────────────────────────────────────────
        pdf_data = self._download_pdf(email)
        if pdf_data is None:
            logger.warning(f"  Sem PDF descarregável — email {email_id} ignorado")
            metrics["erros"] += 1
            return

        # ── b. Extrair dados do PDF ────────────────────────────────────
        extracted = self.extractor.extract_from_file(
            pdf_data,
            bill_type=bill_type,
            entidade_nome=entidade,
        )

        if extracted is None:
            logger.warning(f"  Falha na extração do PDF — email {email_id} ignorado")
            metrics["erros"] += 1
            return

        valor      = extracted.get("valor")
        vencimento = extracted.get("vencimento")

        if not valor or not vencimento:
            logger.warning(
                f"  Dados incompletos (valor={valor}, vencimento={vencimento}) "
                f"— email {email_id} ignorado"
            )
            metrics["erros"] += 1
            return

        logger.info(f"  Extraído: €{valor:.2f} | vencimento {vencimento}")

        # ── c. Criar evento no Calendar ────────────────────────────────
        event_id = self.calendar.create_bill_event(
            entidade=entidade,
            bill_type=bill_type,
            valor=valor,
            vencimento=vencimento,
            mb_entidade=extracted.get("mb_entidade"),
            mb_referencia=extracted.get("mb_referencia"),
            referencia_doc=extracted.get("referencia_doc"),
        )
        if event_id:
            metrics["eventos_criados"] += 1

        # ── d. Notificação Telegram ────────────────────────────────────
        sent = self.telegram.send_bill_notification(
            entidade=entidade,
            bill_type=bill_type,
            valor=valor,
            vencimento=vencimento,
            mb_entidade=extracted.get("mb_entidade"),
            mb_referencia=extracted.get("mb_referencia"),
            referencia_doc=extracted.get("referencia_doc"),
            calendar_event_id=event_id,
        )
        if sent:
            metrics["notificacoes_enviadas"] += 1

        # ── e. Marcar como lido e registar estado ──────────────────────
        self.gmail.mark_as_read(email_id)
        self.state.mark_as_processed(email_id, {
            "subject":   email.get("subject"),
            "entidade":  entidade,
            "bill_type": bill_type,
            "valor":     valor,
            "vencimento": vencimento,
            "event_id":  event_id,
        })

        # ── Métricas ───────────────────────────────────────────────────
        metrics["processadas"] += 1
        metrics["valor_total"] += valor
        metrics["bills_detail"].append({
            "entidade":  entidade,
            "valor":     valor,
            "vencimento": vencimento,
        })

    # ------------------------------------------------------------------
    # Auxiliares
    # ------------------------------------------------------------------

    def _download_pdf(self, email: Dict) -> bytes | None:
        """Descarrega o primeiro PDF válido do email."""
        for att in email.get("attachments", []):
            filename  = att.get("filename", "").lower()
            mime_type = att.get("mime_type", "").lower()
            is_pdf = filename.endswith(".pdf") or mime_type in (
                "application/pdf", "application/x-pdf"
            )
            if is_pdf:
                data = self.gmail.download_attachment(
                    att["message_id"], att["part_id"]
                )
                if data:
                    return data
        return None

    def _resolve_entidade(self, email: Dict) -> str:
        """Determina o nome da entidade a partir dos dados do email."""
        # 1. Fornecedores reconhecidos pelo classificador
        providers = email.get("matched_providers", [])
        if providers:
            return providers[0].strip().title()
        # 2. Fallback: nome do remetente (parte antes do @)
        sender = email.get("sender", "")
        if "<" in sender:
            sender = sender.split("<")[0].strip()
        return sender or "Desconhecido"


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main():
    print("\n" + "=" * 60)
    print("🤖  Automação de Contas a Pagar")
    print(f"⏰  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 60 + "\n")

    try:
        automation = BillAutomation()
        metrics = automation.run()

        print("\n" + "=" * 60)
        print("✅  Pipeline concluído")
        print(f"   📧 Emails lidos:        {metrics['emails_lidos']}")
        print(f"   💰 Contas encontradas:  {metrics['contas_encontradas']}")
        print(f"   ✔️  Processadas:         {metrics['processadas']}")
        print(f"   📅 Eventos no Calendar: {metrics['eventos_criados']}")
        print(f"   💬 Notificações Telegram:{metrics['notificacoes_enviadas']}")
        print(f"   💶 Valor total:         €{metrics['valor_total']:.2f}")
        if metrics["erros"]:
            print(f"   ⚠️  Erros:              {metrics['erros']}")
        print("=" * 60 + "\n")

    except KeyboardInterrupt:
        print("\n⏹️  Automação interrompida pelo utilizador.")
    except Exception as e:
        logger.error(f"Erro fatal: {e}", exc_info=True)
        print(f"\n❌  Erro fatal: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

