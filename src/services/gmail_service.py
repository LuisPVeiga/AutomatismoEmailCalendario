"""
Serviço de integração com Gmail
Responsável por autenticação, leitura e filtro de emails
"""

import os
import pickle
import base64
from typing import List, Dict, Optional
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials as UserCredentials
from google.api_core.gapic_v1 import client_info
import google.auth.exceptions

try:
    from googleapiclient.discovery import build
except ImportError:
    print("Erro: Instale google-api-python-client com: pip install google-api-python-client")

from src.config import (
    GMAIL_SCOPES, GMAIL_CREDENTIALS_FILE, GMAIL_TOKEN_FILE,
    classify_email, get_bill_type,
    MIN_CONFIDENCE_SCORE, VALID_PDF_EXTENSIONS, SUBJECT_IGNORE_LIST,
)
from src.services.state_manager import StateManager


class GmailService:
    """Serviço para autenticação e leitura de emails Gmail"""
    
    def __init__(self):
        """Inicializar o serviço Gmail"""
        self.service = None
        self.state_manager = StateManager()
        self.authenticate()
    
    def authenticate(self):
        """
        Autenticar com Google para acesso ao Gmail
        Usa arquivo credentials.json (OAuth 2.0)
        """
        creds = None
        
        # Carregar token existente se disponível
        if os.path.exists(GMAIL_TOKEN_FILE):
            with open(GMAIL_TOKEN_FILE, "rb") as token:
                creds = pickle.load(token)
        
        # Se não houver token válido, criar novo
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(GMAIL_CREDENTIALS_FILE):
                    raise FileNotFoundError(
                        f"Arquivo {GMAIL_CREDENTIALS_FILE} não encontrado.\n"
                        "Baixe em: https://developers.google.com/gmail/api/quickstart/python"
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    GMAIL_CREDENTIALS_FILE,
                    GMAIL_SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Salvar token para próximas vezes
            with open(GMAIL_TOKEN_FILE, "wb") as token:
                pickle.dump(creds, token)
        
        # Construir serviço Gmail
        self.service = build("gmail", "v1", credentials=creds)
        print("✓ Autenticado com Gmail")
    
    def get_unread_emails(self, max_results: int = 100) -> List[Dict]:
        """
        Obter emails não lidos
        
        Args:
            max_results: Número máximo de emails a retornar
            
        Returns:
            List[Dict]: Lista de emails não lidos com informações básicas
        """
        try:
            results = self.service.users().messages().list(
                userId="me",
                q="is:unread",
                maxResults=max_results
            ).execute()
            
            messages = results.get("messages", [])
            emails = []
            
            for message in messages:
                email_data = self.get_email_details(message["id"])
                if email_data:
                    emails.append(email_data)
            
            print(f"✓ Encontrados {len(emails)} emails não lidos")
            return emails
        
        except Exception as e:
            print(f"✗ Erro ao obter emails não lidos: {str(e)}")
            return []
    
    def get_email_details(self, message_id: str) -> Optional[Dict]:
        """
        Obter detalhes completos de um email
        
        Args:
            message_id: ID do email no Gmail
            
        Returns:
            Dict: Dicionário com detalhes do email ou None se erro
        """
        try:
            message = self.service.users().messages().get(
                userId="me",
                id=message_id,
                format="full"
            ).execute()
            
            headers = message["payload"]["headers"]
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "Sem assunto")
            sender = next((h["value"] for h in headers if h["name"] == "From"), "Desconhecido")
            date = next((h["value"] for h in headers if h["name"] == "Date"), "")
            
            # Extrair corpo do email
            body = self._get_email_body(message["payload"])
            
            # Extrair anexos
            attachments = self._get_attachments(message_id, message["payload"])
            
            email_data = {
                "id": message_id,
                "subject": subject,
                "sender": sender,
                "date": date,
                "body": body,
                "attachments": attachments,
                "has_pdf": any(att["filename"].lower().endswith(".pdf") for att in attachments),
            }
            
            return email_data
        
        except Exception as e:
            print(f"✗ Erro ao obter detalhes do email {message_id}: {str(e)}")
            return None
    
    def _get_email_body(self, payload: Dict) -> str:
        """Extrair corpo do email"""
        try:
            if "parts" in payload:
                # Email com múltiplas partes
                for part in payload["parts"]:
                    if part["mimeType"] == "text/plain":
                        if "data" in part["body"]:
                            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
            else:
                # Email simples
                if "body" in payload and "data" in payload["body"]:
                    return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
        except Exception as e:
            print(f"Aviso: Não foi possível extrair corpo do email: {str(e)}")
        
        return ""
    
    def _get_attachments(self, message_id: str, payload: Dict) -> List[Dict]:
        """Extrair lista de anexos de forma recursiva (suporta multipart aninhado)"""
        attachments = []

        def _extract_parts(parts: list) -> None:
            for part in parts:
                # Descer recursivamente em partes multipart
                if part.get("mimeType", "").startswith("multipart/"):
                    _extract_parts(part.get("parts", []))
                    continue

                filename = part.get("filename", "")
                if filename:
                    body = part.get("body", {})
                    # Gmail usa attachmentId para descarregar, partId para identificar
                    attachment_id = body.get("attachmentId", part.get("partId", ""))
                    attachments.append({
                        "filename": filename,
                        "mime_type": part.get("mimeType", ""),
                        "part_id": attachment_id,
                        "message_id": message_id,
                        "size": body.get("size", 0),
                    })

        try:
            _extract_parts(payload.get("parts", []))
        except Exception as e:
            print(f"Aviso: Erro ao extrair anexos: {str(e)}")

        return attachments
    
    def download_attachment(self, message_id: str, part_id: str) -> Optional[bytes]:
        """
        Descarregar um anexo específico
        
        Args:
            message_id: ID do email
            part_id: ID da parte (anexo)
            
        Returns:
            bytes: Conteúdo do anexo ou None se erro
        """
        try:
            attachment = self.service.users().messages().attachments().get(
                userId="me",
                messageId=message_id,
                id=part_id
            ).execute()
            
            file_data = base64.urlsafe_b64decode(attachment["data"])
            return file_data
        
        except Exception as e:
            print(f"✗ Erro ao descarregar anexo: {str(e)}")
            return None
    
    def _has_valid_pdf(self, email: Dict) -> bool:
        """Verifica se o email tem pelo menos um PDF válido (por extensão ou MIME type)"""
        for att in email.get("attachments", []):
            filename = att.get("filename", "").lower()
            mime_type = att.get("mime_type", "").lower()
            has_pdf_ext = any(filename.endswith(ext) for ext in VALID_PDF_EXTENSIONS)
            has_pdf_mime = mime_type in {"application/pdf", "application/x-pdf"}
            if has_pdf_ext or has_pdf_mime:
                return True
        return False

    def filter_bills(self, emails: List[Dict]) -> List[Dict]:
        """
        Filtrar e classificar emails de contas a pagar com scoring de confiança.

        Cada email aprovado recebe os campos extras:
          - bill_type: tipo de conta identificado
          - confidence: pontuação de confiança
          - matched_keywords: palavras-chave encontradas
          - matched_providers: fornecedores reconhecidos

        Returns:
            List[Dict]: emails classificados com confiança >= MIN_CONFIDENCE_SCORE
        """
        filtered = []
        skipped_no_pdf = 0
        skipped_low_confidence = 0
        skipped_processed = 0

        for email in emails:
            # Ignorar emails já processados
            if self.state_manager.is_processed(email["id"]):
                skipped_processed += 1
                continue

            # Ignorar assuntos na lista negra
            subject_lower = email["subject"].lower()
            if any(term in subject_lower for term in SUBJECT_IGNORE_LIST):
                continue

            # Validar presença de PDF (extensão + MIME type)
            has_valid_pdf = self._has_valid_pdf(email)
            if not has_valid_pdf:
                skipped_no_pdf += 1
                continue

            # Classificar com scoring
            classification = classify_email(
                email_subject=email["subject"],
                email_body=email["body"],
                email_sender=email["sender"],
                has_pdf=True,
            )

            if classification["confidence"] < MIN_CONFIDENCE_SCORE:
                skipped_low_confidence += 1
                continue

            # Enriquecer email com dados de classificação
            email["bill_type"] = classification["bill_type"]
            email["confidence"] = classification["confidence"]
            email["matched_keywords"] = classification["matched_keywords"]
            email["matched_providers"] = classification["matched_providers"]

            filtered.append(email)

        print(f"✓ Filtrados {len(filtered)} emails com contas a pagar")
        if skipped_no_pdf:
            print(f"  ↳ {skipped_no_pdf} ignorado(s): sem PDF válido")
        if skipped_low_confidence:
            print(f"  ↳ {skipped_low_confidence} ignorado(s): confiança insuficiente (< {MIN_CONFIDENCE_SCORE})")
        if skipped_processed:
            print(f"  ↳ {skipped_processed} ignorado(s): já processados anteriormente")

        return filtered
    
    def mark_as_read(self, message_id: str) -> bool:
        """
        Marcar email como lido
        
        Args:
            message_id: ID do email
            
        Returns:
            bool: True se sucesso, False caso contrário
        """
        try:
            self.service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            return True
        except Exception as e:
            print(f"Aviso: Não foi possível marcar como lido: {str(e)}")
            return False


if __name__ == "__main__":
    # Teste do serviço Gmail
    gmail = GmailService()
    
    # Obter emails não lidos
    print("\n=== Obtendo emails não lidos ===")
    unread = gmail.get_unread_emails(max_results=5)
    
    for email in unread:
        print(f"\nAssunto: {email['subject']}")
        print(f"De: {email['sender']}")
        print(f"Tem PDF: {email['has_pdf']}")
        print(f"Anexos: {len(email['attachments'])}")
    
    # Filtrar e classificar contas a pagar
    print("\n=== Filtrando e classificando contas a pagar ===")
    bills = gmail.filter_bills(unread)
    
    for bill in bills:
        print(f"\nTipo: {bill['bill_type']}  |  Confiança: {bill['confidence']}")
        print(f"Assunto: {bill['subject']}")
        print(f"Fornecedores: {bill.get('matched_providers', [])}")
        print(f"Keywords: {bill.get('matched_keywords', [])}")
