"""
Serviço de integração com Telegram
Responsável pelo envio de notificações de contas a pagar
"""

from typing import Optional, List
import requests

from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

_BILL_EMOJIS = {
    "agua":         "💧",
    "luz":          "💡",
    "gas":          "🔥",
    "comunicacoes": "📱",
    "seguros":      "🛡️",
    "outro":        "💳",
}

_BILL_LABELS = {
    "agua":         "Água",
    "luz":          "Eletricidade",
    "gas":          "Gás",
    "comunicacoes": "Comunicações",
    "seguros":      "Seguros",
    "outro":        "Outro",
}


class TelegramService:
    """Serviço para envio de notificações via Telegram Bot API"""

    BASE_URL = "https://api.telegram.org/bot"

    def __init__(self):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            print("⚠️  Aviso: Telegram não configurado (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID em falta no .env)")
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def send_bill_notification(
        self,
        entidade: str,
        bill_type: str,
        valor: float,
        vencimento: str,
        mb_entidade: Optional[str] = None,
        mb_referencia: Optional[str] = None,
        referencia_doc: Optional[str] = None,
        calendar_event_id: Optional[str] = None,
    ) -> bool:
        """
        Enviar notificação de conta a pagar.

        Formato da mensagem:
            💡 [PAGAR] Iberdrola
            ─────────────────────
            💶 Valor:          €66,86
            📅 Vencimento:     11/05/2026
            📄 Nº Fatura:      26201/1082812
            🏧 MB Entidade:    21404
            🔢 MB Referência:  266 625 791
            📆 Evento criado no Google Calendar

        Args:
            entidade:          Nome da entidade emissora
            bill_type:         Tipo de conta (luz, agua, gas, comunicacoes, seguros, outro)
            valor:             Valor a pagar em euros
            vencimento:        Data de vencimento em formato YYYY-MM-DD
            mb_entidade:       Entidade Multibanco (5 dígitos), se disponível
            mb_referencia:     Referência Multibanco (9 dígitos), se disponível
            referencia_doc:    Número de fatura / referência documental
            calendar_event_id: ID do evento criado no Calendar (confirma criação)
        """
        emoji = _BILL_EMOJIS.get(bill_type, "💳")
        label = _BILL_LABELS.get(bill_type, bill_type.capitalize())

        # Formatar data legível
        try:
            from datetime import datetime
            venc_fmt = datetime.strptime(vencimento, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            venc_fmt = vencimento

        # Formatar MB referência com espaços (XXX XXX XXX)
        mb_ref_fmt = None
        if mb_referencia:
            r = mb_referencia.replace(" ", "")
            mb_ref_fmt = f"{r[:3]} {r[3:6]} {r[6:]}" if len(r) == 9 else mb_referencia

        lines = [
            f"{emoji} <b>[PAGAR] {entidade}</b>",
            "─────────────────────",
            f"🏷️ Tipo:           {label}",
            f"💶 Valor:          <b>€{valor:.2f}</b>",
            f"📅 Vencimento:     <b>{venc_fmt}</b>",
        ]

        if referencia_doc:
            lines.append(f"📄 Nº Fatura:      <code>{referencia_doc}</code>")
        if mb_entidade:
            lines.append(f"🏧 MB Entidade:    <code>{mb_entidade}</code>")
        if mb_ref_fmt:
            lines.append(f"🔢 MB Referência:  <code>{mb_ref_fmt}</code>")
        if calendar_event_id:
            lines.append("📆 Evento criado no Google Calendar ✅")

        return self.send_message("\n".join(lines))

    def send_summary(
        self,
        total_emails: int,
        total_bills: int,
        total_value: float,
        events_created: int,
        bills_detail: Optional[List[dict]] = None,
    ) -> bool:
        """
        Enviar resumo da execução do pipeline.

        Args:
            total_emails:   Emails verificados
            total_bills:    Contas identificadas e processadas
            total_value:    Soma dos valores (€)
            events_created: Eventos criados no Calendar
            bills_detail:   Lista opcional de dicts com {entidade, valor, vencimento}
                            para mostrar detalhe de cada conta no resumo
        """
        lines = [
            "📊 <b>Resumo da Automação</b>",
            "─────────────────────",
            f"📧 Emails verificados:   {total_emails}",
            f"💰 Contas processadas:   {total_bills}",
            f"💶 Valor total:          <b>€{total_value:.2f}</b>",
            f"📅 Eventos no Calendar:  {events_created}",
        ]

        if bills_detail:
            lines.append("\n<b>Detalhe:</b>")
            for bill in bills_detail:
                try:
                    from datetime import datetime
                    venc = datetime.strptime(bill.get("vencimento", ""), "%Y-%m-%d").strftime("%d/%m/%Y")
                except (ValueError, KeyError):
                    venc = bill.get("vencimento", "—")
                lines.append(
                    f"  • {bill.get('entidade', '—')} — €{bill.get('valor', 0):.2f} → {venc}"
                )

        return self.send_message("\n".join(lines))

    def send_message(
        self,
        message: str,
        parse_mode: str = "HTML",
        disable_notification: bool = False,
    ) -> bool:
        """Enviar mensagem de texto para o chat configurado."""
        if not self.bot_token or not self.chat_id:
            print("✗ Telegram não está configurado")
            return False

        try:
            url = f"{self.BASE_URL}{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode,
                "disable_notification": disable_notification,
            }
            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                print("✓ Mensagem enviada para Telegram")
                return True
            else:
                print(f"✗ Erro Telegram {response.status_code}: {response.text}")
                return False
        except Exception as e:
            print(f"✗ Erro ao enviar mensagem Telegram: {e}")
            return False

    def test_connection(self) -> bool:
        """Testar se o bot está acessível e o token é válido."""
        if not self.bot_token:
            print("✗ Bot token não configurado")
            return False
        try:
            url = f"{self.BASE_URL}{self.bot_token}/getMe"
            response = requests.get(url, timeout=10)
            if response.status_code == 200 and response.json().get("ok"):
                username = response.json()["result"]["username"]
                print(f"✓ Conexão Telegram OK — @{username}")
                return True
            print(f"✗ Telegram getMe falhou: {response.text}")
            return False
        except Exception as e:
            print(f"✗ Erro ao testar Telegram: {e}")
            return False


if __name__ == "__main__":
    telegram = TelegramService()

    print("=== Testar conexão ===")
    if telegram.test_connection():

        print("\n=== Notificação de conta ===")
        telegram.send_bill_notification(
            entidade="Iberdrola",
            bill_type="luz",
            valor=66.86,
            vencimento="2026-05-11",
            referencia_doc="26201/1082812",
            calendar_event_id="abc123",
        )

        print("\n=== Notificação com Multibanco ===")
        telegram.send_bill_notification(
            entidade="Generali Seguros",
            bill_type="seguros",
            valor=192.03,
            vencimento="2025-12-31",
            mb_entidade="21404",
            mb_referencia="266625791",
            referencia_doc="7010635515",
            calendar_event_id="def456",
        )

        print("\n=== Resumo da execução ===")
        telegram.send_summary(
            total_emails=15,
            total_bills=3,
            total_value=280.04,
            events_created=3,
            bills_detail=[
                {"entidade": "Iberdrola",        "valor": 66.86,  "vencimento": "2026-05-11"},
                {"entidade": "Setgás",           "valor": 21.15,  "vencimento": "2026-01-09"},
                {"entidade": "Generali Seguros", "valor": 192.03, "vencimento": "2025-12-31"},
            ],
        )


        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            print("⚠️  Aviso: Telegram não configurado (.env não preenchido)")
        
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
    
    def send_message(
        self,
        message: str,
        parse_mode: str = "HTML",
        disable_notification: bool = False
    ) -> bool:
        """
        Enviar mensagem para o Telegram
        
        Args:
            message: Conteúdo da mensagem
            parse_mode: Modo de parse (HTML ou Markdown)
            disable_notification: Se True, não faz som
            
        Returns:
            bool: True se sucesso, False caso contrário
        """
        if not self.bot_token or not self.chat_id:
            print("✗ Telegram não está configurado")
            return False
        
        try:
            url = f"{self.BASE_URL}{self.bot_token}/sendMessage"
            
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode,
                "disable_notification": disable_notification,
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                print(f"✓ Mensagem enviada para Telegram")
                return True
            else:
                print(f"✗ Erro ao enviar para Telegram: {response.status_code}")
                print(f"  Resposta: {response.text}")
                return False
        
        except Exception as e:
            print(f"✗ Erro ao enviar mensagem Telegram: {str(e)}")
            return False
    
    def send_bill_notification(
        self,
        bill_type: str,
        valor: float,
        vencimento: str,
        referencia: Optional[str] = None
    ) -> bool:
        """
        Enviar notificação de conta a pagar
        
        Args:
            bill_type: Tipo da conta
            valor: Valor em euros
            vencimento: Data de vencimento
            referencia: Referência da fatura
            
        Returns:
            bool: True se sucesso
        """
        # Emojis e títulos por tipo de conta
        emojis_titles = {
            "agua": ("💧", "Fatura de Água"),
            "luz": ("💡", "Fatura de Eletricidade"),
            "gas": ("🔥", "Fatura de Gás"),
            "comunicacoes": ("📱", "Fatura de Comunicações"),
            "seguros": ("🛡️", "Apólice de Seguro"),
            "outro": ("💳", "Fatura"),
        }
        
        emoji, title = emojis_titles.get(bill_type, ("💳", "Fatura"))
        
        # Construir mensagem
        message_lines = [
            f"<b>{emoji} {title}</b>",
            f"<b>Valor:</b> €{valor:.2f}",
            f"<b>Vencimento:</b> {vencimento}",
        ]
        
        if referencia:
            message_lines.append(f"<b>Referência:</b> <code>{referencia}</code>")
        
        message = "\n".join(message_lines)
        
        return self.send_message(message)
    
    def send_summary(
        self,
        total_emails: int,
        total_bills: int,
        total_value: float,
        events_created: int
    ) -> bool:
        """
        Enviar resumo da execução
        
        Args:
            total_emails: Total de emails verificados
            total_bills: Total de contas identificadas
            total_value: Valor total das contas
            events_created: Número de eventos criados
            
        Returns:
            bool: True se sucesso
        """
        message = (
            f"<b>📊 Resumo da Automação</b>\n"
            f"📧 Emails verificados: {total_emails}\n"
            f"💰 Contas identificadas: {total_bills}\n"
            f"💶 Valor total: €{total_value:.2f}\n"
            f"📅 Eventos criados: {events_created}"
        )
        
        return self.send_message(message)
    
    def test_connection(self) -> bool:
        """
        Testar conexão com Telegram
        
        Returns:
            bool: True se conectado, False caso contrário
        """
        if not self.bot_token:
            print("✗ Bot token não configurado")
            return False
        
        try:
            url = f"{self.BASE_URL}{self.bot_token}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data["ok"]:
                    bot_info = data["result"]
                    print(f"✓ Conexão com Telegram OK")
                    print(f"  Bot: @{bot_info['username']}")
                    return True
                else:
                    print(f"✗ Erro no Telegram: {data['description']}")
                    return False
            else:
                print(f"✗ Erro HTTP {response.status_code}")
                return False
        
        except Exception as e:
            print(f"✗ Erro ao testar conexão: {str(e)}")
            return False


if __name__ == "__main__":
    # Teste do serviço Telegram
    telegram = TelegramService()
    
    print("=== Testando conexão ===")
    if telegram.test_connection():
        print("\n=== Enviando mensagem de teste ===")
        telegram.send_message("🤖 <b>Teste de conexão!</b> A aplicação está funcionando.")
        
        print("\n=== Enviando notificação de conta ===")
        telegram.send_bill_notification(
            bill_type="luz",
            valor=85.50,
            vencimento="2026-05-15",
            referencia="FAC2026-04-001"
        )
        
        print("\n=== Enviando resumo ===")
        telegram.send_summary(
            total_emails=10,
            total_bills=3,
            total_value=250.75,
            events_created=3
        )
