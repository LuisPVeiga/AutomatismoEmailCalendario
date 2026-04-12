"""
Serviço de integração com Google Calendar
Responsável pela criação de eventos no calendário
"""

import os
import pickle
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

try:
    from googleapiclient.discovery import build
except ImportError:
    print("Erro: Instale google-api-python-client com: pip install google-api-python-client")

from src.config import (
    CALENDAR_SCOPES, CALENDAR_CREDENTIALS_FILE, CALENDAR_TOKEN_FILE,
    CALENDAR_ID, CALENDAR_DEFAULT_GUESTS,
)

# Emojis por tipo de conta
_BILL_EMOJIS = {
    "agua": "💧",
    "luz": "💡",
    "gas": "🔥",
    "comunicacoes": "📱",
    "seguros": "🛡️",
    "outro": "💳",
}

_BILL_LABELS = {
    "agua": "Água",
    "luz": "Eletricidade",
    "gas": "Gás",
    "comunicacoes": "Comunicações",
    "seguros": "Seguros",
    "outro": "Outro",
}


class CalendarService:
    """Serviço para criação de eventos no Google Calendar"""

    def __init__(self):
        self.service = None
        self.authenticate()

    def authenticate(self):
        """Autenticar com Google Calendar via OAuth 2.0."""
        creds = None

        if os.path.exists(CALENDAR_TOKEN_FILE):
            with open(CALENDAR_TOKEN_FILE, "rb") as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(CALENDAR_CREDENTIALS_FILE):
                    raise FileNotFoundError(
                        f"Arquivo {CALENDAR_CREDENTIALS_FILE} não encontrado.\n"
                        "Use o mesmo arquivo de credenciais do Gmail."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    CALENDAR_CREDENTIALS_FILE,
                    CALENDAR_SCOPES,
                )
                creds = flow.run_local_server(port=0)

            with open(CALENDAR_TOKEN_FILE, "wb") as token:
                pickle.dump(creds, token)

        self.service = build("calendar", "v3", credentials=creds)
        print("✓ Autenticado com Google Calendar")

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def create_bill_event(
        self,
        entidade: str,
        bill_type: str,
        valor: float,
        vencimento: str,
        mb_entidade: Optional[str] = None,
        mb_referencia: Optional[str] = None,
        referencia_doc: Optional[str] = None,
        guests: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Criar evento de pagamento de conta no calendário.

        Título do evento: [Pagar] <entidade>
        Ex: "[Pagar] Iberdrola"

        Args:
            entidade:       Nome da entidade emissora (Iberdrola, Setgás, etc.)
            bill_type:      Tipo de conta (luz, gas, agua, comunicacoes, seguros, outro)
            valor:          Valor a pagar em euros
            vencimento:     Data de vencimento no formato YYYY-MM-DD
            mb_entidade:    Entidade Multibanco (5 dígitos), se disponível
            mb_referencia:  Referência Multibanco (9 dígitos), se disponível
            referencia_doc: Número de fatura/referência documental
            guests:         Lista de emails de convidados. Se None, usa CALENDAR_DEFAULT_GUESTS.

        Returns:
            str: ID do evento criado, ou None se erro
        """
        # Verificar se já existe evento duplicado nesta data para esta entidade
        existing_id = self._find_duplicate(entidade, vencimento)
        if existing_id:
            print(f"⚠️  Evento já existe para '{entidade}' em {vencimento} (ID: {existing_id}) — ignorado")
            return existing_id

        try:
            emoji = _BILL_EMOJIS.get(bill_type, "💳")
            label = _BILL_LABELS.get(bill_type, bill_type.capitalize())
            title = f"[Pagar] {entidade}"

            # Descrição estruturada
            desc_lines = [
                f"{emoji} Tipo: {label}",
                f"🏢 Entidade: {entidade}",
                f"💶 Valor: €{valor:.2f}",
                f"📅 Vencimento: {datetime.strptime(vencimento, '%Y-%m-%d').strftime('%d/%m/%Y')}",
            ]
            if referencia_doc:
                desc_lines.append(f"📄 Nº Fatura: {referencia_doc}")
            if mb_entidade:
                desc_lines.append(f"🏧 MB Entidade: {mb_entidade}")
            if mb_referencia:
                desc_lines.append(f"🔢 MB Referência: {mb_referencia}")

            description = "\n".join(desc_lines)

            # Convidados: parâmetro explícito → default do .env → nenhum
            attendee_emails = guests if guests is not None else CALENDAR_DEFAULT_GUESTS
            attendees = [{"email": email} for email in attendee_emails]

            # Google Calendar exige end = start + 1 dia para eventos de dia inteiro
            venc_dt = datetime.strptime(vencimento, "%Y-%m-%d")
            end_date = (venc_dt + timedelta(days=1)).strftime("%Y-%m-%d")

            event_body = {
                "summary": title,
                "description": description,
                "colorId": "11",  # Tomato (vermelho)
                "start": {"date": vencimento},
                "end": {"date": end_date},
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "popup", "minutes": 24 * 60},  # 1 dia antes
                        {"method": "popup", "minutes": 0},         # no próprio dia
                    ],
                },
            }

            if attendees:
                event_body["attendees"] = attendees

            created = self.service.events().insert(
                calendarId=CALENDAR_ID,
                body=event_body,
                sendUpdates="all" if attendees else "none",
            ).execute()

            guests_info = f", {len(attendees)} convidado(s)" if attendees else ""
            print(f"✓ Evento criado: {title} — {vencimento}{guests_info} (ID: {created['id']})")
            return created["id"]

        except Exception as e:
            print(f"✗ Erro ao criar evento: {e}")
            return None

    def get_upcoming_events(self, days: int = 30) -> List[Dict]:
        """Obter eventos dos próximos N dias."""
        try:
            now = datetime.utcnow().isoformat() + "Z"
            end = (datetime.utcnow() + timedelta(days=days)).isoformat() + "Z"

            result = self.service.events().list(
                calendarId=CALENDAR_ID,
                timeMin=now,
                timeMax=end,
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            return result.get("items", [])
        except Exception as e:
            print(f"✗ Erro ao obter eventos: {e}")
            return []

    def delete_event(self, event_id: str) -> bool:
        """Apagar um evento pelo seu ID."""
        try:
            self.service.events().delete(
                calendarId=CALENDAR_ID,
                eventId=event_id,
            ).execute()
            print(f"✓ Evento apagado: {event_id}")
            return True
        except Exception as e:
            print(f"✗ Erro ao apagar evento: {e}")
            return False

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _find_duplicate(self, entidade: str, vencimento: str) -> Optional[str]:
        """
        Verifica se já existe um evento '[Pagar] <entidade>' para a data de vencimento.
        Retorna o ID do evento existente ou None.
        """
        try:
            # Pesquisar eventos no dia exato
            time_min = f"{vencimento}T00:00:00Z"
            time_max = f"{vencimento}T23:59:59Z"

            result = self.service.events().list(
                calendarId=CALENDAR_ID,
                timeMin=time_min,
                timeMax=time_max,
                q=f"[Pagar] {entidade}",
                singleEvents=True,
            ).execute()

            items = result.get("items", [])
            expected_title = f"[Pagar] {entidade}".lower()
            for item in items:
                if item.get("summary", "").lower() == expected_title:
                    return item["id"]
        except Exception:
            pass
        return None


if __name__ == "__main__":
    calendar = CalendarService()

    print("\n=== Criar evento de teste ===")
    event_id = calendar.create_bill_event(
        entidade="Iberdrola",
        bill_type="luz",
        valor=66.86,
        vencimento="2026-05-11",
        mb_entidade=None,
        mb_referencia=None,
        referencia_doc="26201/1082812",
        guests=[],  # Sem convidados no teste
    )

    if event_id:
        print(f"\n=== Eventos próximos (30 dias) ===")
        events = calendar.get_upcoming_events(days=30)
        for ev in events:
            start = ev["start"].get("date", ev["start"].get("dateTime", ""))
            print(f"  {start} — {ev['summary']}")
    print("\n=== Eventos próximos (próximos 7 dias) ===")
    events = calendar.get_upcoming_events(days=7)
    for event in events:
        print(f"- {event['summary']} em {event['start'].get('dateTime', event['start'].get('date'))}")
