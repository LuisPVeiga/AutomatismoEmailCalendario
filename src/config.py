"""
Configurações de ambiente da aplicação
"""

import os
from dotenv import load_dotenv
import json
from typing import Dict, List

# Carregar variáveis de .env
load_dotenv()

# ==================== CONFIGURAÇÕES GMAIL ====================
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
GMAIL_CREDENTIALS_FILE = "config/credentials.json"
GMAIL_TOKEN_FILE = "config/token.json"

# ==================== CONFIGURAÇÕES GOOGLE CALENDAR ====================
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]
CALENDAR_CREDENTIALS_FILE = "config/credentials.json"
CALENDAR_TOKEN_FILE = "config/calendar_token.json"
CALENDAR_ID = "primary"  # Usar calendário primário

# Convidados padrão para todos os eventos (emails separados por vírgula no .env)
# Ex: CALENDAR_GUESTS=joao@gmail.com,maria@gmail.com
_guests_raw = os.getenv("CALENDAR_GUESTS", "")
CALENDAR_DEFAULT_GUESTS: list = [g.strip() for g in _guests_raw.split(",") if g.strip()]

# ==================== CONFIGURAÇÕES TELEGRAM ====================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")  # Chat ID do canal

# ==================== CONFIGURAÇÕES EMAIL ====================
# Palavras-chave para identificar contas a pagar
BILL_KEYWORDS = {
    "agua": ["água", "aguas", "abastecimento de água", "consumo água", "saneamento", "epal"],
    "luz": ["luz", "eletricidade", "energia elétrica", "kwh", "edp", "consumo elétrico"],
    "gas": ["gás", "gas", "combustivel", "gn", "gás natural", "propano"],
    "comunicacoes": ["comunicações", "telefone", "internet", "telemóvel", "telefónico", "fibra", "banda larga", "dados móveis"],
    "seguros": ["seguro", "apólice", "responsabilidade civil", "sinistro", "prémio"],
}

# Fornecedores conhecidos → tipo de conta
KNOWN_PROVIDERS = {
    # Eletricidade
    "edp": "luz",
    "endesa": "luz",
    "iberdrola": "luz",
    "galp energia": "luz",
    "goldenergy": "luz",
    "repsol": "luz",
    "e.on": "luz",
    "plenitude": "luz",
    # Gás
    "galp": "gas",
    "naturgy": "gas",
    "endesa gas": "gas",
    "sin": "gas",
    # Água
    "epal": "agua",
    "aguas de lisboa": "agua",
    "águas de lisboa": "agua",
    "aguas do algarve": "agua",
    "águas do algarve": "agua",
    "aguas do porto": "agua",
    "águas do porto": "agua",
    "indaqua": "agua",
    "sisar": "agua",
    "aguas de cascais": "agua",
    "águas de cascais": "agua",
    "aguas do tejo": "agua",
    "águas do tejo": "agua",
    # Telecomunicações
    "nos ": "comunicacoes",
    "@nos.pt": "comunicacoes",
    "meo": "comunicacoes",
    "vodafone": "comunicacoes",
    "nowo": "comunicacoes",
    "altice": "comunicacoes",
    "digi": "comunicacoes",
    "claranet": "comunicacoes",
    # Seguros
    "axa": "seguros",
    "fidelidade": "seguros",
    "tranquilidade": "seguros",
    "zurich": "seguros",
    "allianz": "seguros",
    "ageas": "seguros",
    "generali": "seguros",
    "ocidental": "seguros",
    "logo seguros": "seguros",
    "lusitania": "seguros",
    "victoria": "seguros",
}

# Palavras genéricas de faturação (aumentam a confiança)
BILL_GENERIC_KEYWORDS = [
    "fatura", "factura", "recibo", "pagamento", "conta",
    "vencimento", "débito", "cobrança", "aviso de pagamento",
    "notificação", "invoice", "bill", "due date", "referência mbway",
    "referência multibanco", "entidade", "valor a pagar",
]

# Pesos do scoring de classificação
SCORE_WEIGHTS = {
    "has_pdf": 2,         # Bónus por ter PDF
    "keyword_match": 1,   # Por cada keyword identificada
    "provider_match": 3,  # Fornecedor conhecido (subject/sender)
    "bill_word": 2,       # Palavra genérica de faturação
}

# Score mínimo para incluir um email como conta a pagar
MIN_CONFIDENCE_SCORE = 3

# Assuntos a ignorar sempre (case-insensitive, correspondência parcial)
SUBJECT_IGNORE_LIST = [
    "cartão continente",
]

# Extensões de ficheiros a processar
VALID_PDF_EXTENSIONS = {".pdf"}

# ==================== CONFIGURAÇÕES DE ESTADO ====================
STATE_FILE = "config/processed_emails.json"
LOGS_FILE = "logs/logs.txt"

# ==================== CONFIGURAÇÕES DE LOGGING ====================
LOG_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ==================== CONFIGURAÇÕES DE EXTRAÇÃO ====================
# Padrões regex para extração de dados de PDFs
# Será expandido conforme necessário
PDF_EXTRACTION_PATTERNS = {
    "valor": r"(€|EUR|\$)?\s*(\d+[.,]\d{2})",
    "vencimento": r"(\d{1,2}[/-]?\d{1,2}[/-]?\d{2,4})",
    "referencia": r"(ref|referência|n\.?\s*facto|invoice|bill|fatura).*?:?\s*([A-Z0-9\-]+)",
}

# ==================== FUNÇÕES AUXILIARES ====================
def classify_email(
    email_subject: str,
    email_body: str = "",
    email_sender: str = "",
    has_pdf: bool = False,
) -> Dict:
    """
    Classifica um email com scoring de confiança.

    Returns:
        Dict com chaves: bill_type, confidence, matched_keywords, matched_providers
    """
    subject_lower = email_subject.lower()
    sender_lower = email_sender.lower()
    full_text = (email_subject + " " + email_body + " " + email_sender).lower()

    score: int = 0
    type_scores: Dict[str, int] = {}
    matched_keywords: List[str] = []
    matched_providers: List[str] = []

    # 1. Fornecedores conhecidos no assunto ou remetente (peso alto)
    for provider, ptype in KNOWN_PROVIDERS.items():
        if provider in sender_lower or provider in subject_lower:
            matched_providers.append(provider)
            w = SCORE_WEIGHTS["provider_match"]
            score += w
            type_scores[ptype] = type_scores.get(ptype, 0) + w

    # 2. Palavras-chave por tipo de conta
    for btype, keywords in BILL_KEYWORDS.items():
        for keyword in keywords:
            if keyword in full_text:
                matched_keywords.append(keyword)
                w = SCORE_WEIGHTS["keyword_match"]
                score += w
                type_scores[btype] = type_scores.get(btype, 0) + w

    # 3. Palavras genéricas de faturação (conta apenas uma vez)
    for word in BILL_GENERIC_KEYWORDS:
        if word in full_text:
            score += SCORE_WEIGHTS["bill_word"]
            break

    # 4. Bónus por ter PDF
    if has_pdf:
        score += SCORE_WEIGHTS["has_pdf"]

    # Determinar tipo com maior pontuação
    bill_type = max(type_scores, key=type_scores.get) if type_scores else "outro"

    return {
        "bill_type": bill_type,
        "confidence": score,
        "matched_keywords": list(set(matched_keywords)),
        "matched_providers": list(set(matched_providers)),
    }


def get_bill_type(email_subject: str, email_body: str = "") -> str:
    """
    Identifica o tipo de conta baseado em palavras-chave.
    Mantido para compatibilidade — usa classify_email internamente.

    Returns:
        str: Tipo de conta identificada ou "outro"
    """
    return classify_email(email_subject, email_body)["bill_type"]


def load_config_file(config_path: str = "config.ini") -> dict:
    """
    Carrega configurações adicionales de arquivo INI (para futuro)
    
    Args:
        config_path: Caminho do arquivo de configuração
        
    Returns:
        dict: Dicionário com configurações
    """
    # Implementar depois se necessário
    return {}


if __name__ == "__main__":
    # Teste de configurações
    print("✓ Configurações carregadas:")
    print(f"  - Telegram Bot Token: {'Configurado' if TELEGRAM_BOT_TOKEN else 'NÃO CONFIGURADO'}")
    print(f"  - Telegram Chat ID: {'Configurado' if TELEGRAM_CHAT_ID else 'NÃO CONFIGURADO'}")
    print(f"  - Estado será salvo em: {STATE_FILE}")
