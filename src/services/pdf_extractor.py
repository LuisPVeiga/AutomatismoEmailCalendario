"""
Serviço de extração de dados de PDFs
Responsável por extrair valores, datas e referências de PDFs

Suporta:
- PDFs com texto nativo (via pdfplumber)
- PDFs escaneados com OCR (via pytesseract + pdf2image, se tesseract estiver instalado)
- Padrões regex por tipo de conta (luz, agua, gas, comunicacoes, seguros)
- Referências Multibanco (entidade + referência) — padrão em Portugal
"""

import io
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Importado aqui para evitar import circular — usado apenas em _extract_entidade_from_text
_KNOWN_PROVIDERS_LAZY: Optional[Dict] = None


def _get_known_providers() -> Dict:
    global _KNOWN_PROVIDERS_LAZY
    if _KNOWN_PROVIDERS_LAZY is None:
        from src.config import KNOWN_PROVIDERS
        _KNOWN_PROVIDERS_LAZY = KNOWN_PROVIDERS
    return _KNOWN_PROVIDERS_LAZY

try:
    import pdfplumber
except ImportError:
    raise ImportError("Instale pdfplumber: pip install pdfplumber")

# OCR — opcional. Só usado se tesseract estiver presente no sistema.
_OCR_AVAILABLE = False
try:
    import pytesseract
    from pdf2image import convert_from_bytes
    pytesseract.get_tesseract_version()
    _OCR_AVAILABLE = True
except Exception:
    pass  # OCR gracefully disabled


# ---------------------------------------------------------------------------
# Padrões regex compilados (por categoria)
# ---------------------------------------------------------------------------

# Valores em euros — mais específica para mais genérica; suporta formato PT (1.234,56) e EN (1,234.56)
# Grupo de captura sempre apanha o número completo includindo separador de milhar
_NUM_PT = r"\d{1,3}(?:\.\d{3})*,\d{2}"   # 1.234,56
_NUM_EN = r"\d{1,3}(?:,\d{3})*\.\d{2}"   # 1,234.56
_NUM_SIMPLE = r"\d+[,.]\d{2}"             # 45,99 ou 45.99

_VALOR_PATTERNS: List[re.Pattern] = [p for p in (re.compile(r, re.IGNORECASE) for r in [
    rf"total\s*a\s*pagar\s*[:\-]?\s*€?\s*({_NUM_PT}|{_NUM_EN}|{_NUM_SIMPLE})",
    rf"valor\s*(?:total|a\s*pagar|fatura)\s*[:\-]?\s*€?\s*({_NUM_PT}|{_NUM_EN}|{_NUM_SIMPLE})",
    rf"montante\s*(?:total|a\s*pagar)?\s*[:\-]?\s*€?\s*({_NUM_PT}|{_NUM_EN}|{_NUM_SIMPLE})",
    rf"imp[oô]rte?\s*(?:total)?\s*[:\-]?\s*€?\s*({_NUM_PT}|{_NUM_EN}|{_NUM_SIMPLE})",
    # [^\S\n]* permite espaços mas NÃO newlines — evita capturar o número da linha seguinte ao €
    rf"\b({_NUM_PT}|{_NUM_EN}|{_NUM_SIMPLE})[^\S\n]*€",
    rf"\b({_NUM_PT}|{_NUM_EN}|{_NUM_SIMPLE})[^\S\n]*eur\b",
])]

# Datas de vencimento
_VENCIMENTO_PATTERNS: List[re.Pattern] = [p for p in (re.compile(r, re.IGNORECASE) for r in [
    # Formato ISO YYYY-MM-DD (ex: Setgás "2026-01-09") — antes dos padrões DD/MM
    r"(?:data\s*(?:de\s*)?)?vencimento\s*[:\-]?\s*(\d{4}[\-/]\d{2}[\-/]\d{2})",
    r"(?:data\s*)?limite\s*(?:de\s*pagamento)?\s*[:\-]?\s*(\d{4}[\-/]\d{2}[\-/]\d{2})",
    r"pagar\s*at[eé]\s*(?:ao)?\s*(\d{4}[\-/]\d{2}[\-/]\d{2})",
    # Formato DD/MM/YYYY
    r"(?:data\s*(?:de\s*)?)?vencimento\s*[:\-]?\s*(\d{1,2}[/. -]\d{1,2}[/. -]\d{2,4})",
    r"(?:data\s*)?limite\s*(?:de\s*pagamento)?\s*[:\-]?\s*(\d{1,2}[/. -]\d{1,2}[/. -]\d{2,4})",
    r"pagar\s*at[eé]\s*(?:ao)?\s*(\d{1,2}[/. -]\d{1,2}[/. -]\d{2,4})",
    r"due\s*date\s*[:\-]?\s*(\d{1,2}[/. -]\d{1,2}[/. -]\d{2,4})",
    r"(\d{1,2})\s*de\s*(janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s*de\s*(\d{4})",
    r"d[aá]bili?t\s*a\s*partir\s*de\s*[:\-]?\s*(\d{1,2}[/. -]\d{1,2}[/. -]\d{4})",
    r"(\d{1,2}[/. -]\d{1,2}[/. -]\d{4})",
])]

# Número de fatura / referência documental
_REFERENCIA_PATTERNS: List[re.Pattern] = [p for p in (re.compile(r, re.IGNORECASE) for r in [
    # Padrões altamente específicos primeiro
    r"n[uú]mero\s*(?:de\s*)?fatura\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-\/\.]{2,30})",
    r"n[uú]\s*factura\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-\/\.]{2,30})",
    r"n[uº]\.\s*fatura\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-\/\.]{2,30})",
    r"fatura\s*(?:n[uú]?[º°]?)?\s*[:\-]\s*([A-Z0-9][A-Z0-9\-\/\.]{2,30})",
    r"invoice\s*(?:no|num|number|#)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-\/\.]{2,30})",
    # Prefixos de série comuns em Portugal — antes do genérico
    r"\bFAC[:\- ]\s*([A-Z0-9\-\/\.]{3,20})",
    r"\bFT[:\- ]\s*([A-Z0-9\-\/\.]{3,20})",
    r"\bFR[:\- ]\s*([A-Z0-9\-\/\.]{3,20})",
    r"\bNC[:\- ]\s*([A-Z0-9\-\/\.]{3,20})",
    # Genérico — requer separador ':' ou '-' para evitar falsos positivos
    r"ref(?:er[eê]ncia)?\s+(?:do\s+documento\s*)?[:\-]\s*([A-Z0-9][A-Z0-9\-\/\.]{2,30})",
])]

# Referência Multibanco (entidade 5 dígitos + referência 9 dígitos) — padrão PT
_MULTIBANCO_ENTIDADE_PATTERN = re.compile(r"entidade\s*[:\-]?\s*(\d{5})", re.IGNORECASE)
_MULTIBANCO_REF_PATTERN = re.compile(
    # O carácter 'ê' pode aparecer corrompido como '˚' (U+02DA) em PDFs com encoding buggy
    r"refer.ncia\s*(?:multibanco|mb|pagamento)?\s*[:\-]?\s*(\d{3}\s?\d{3}\s?\d{3})",
    re.IGNORECASE,
)

# Por fornecedor — padrões extra específicos ao tipo de conta
_PROVIDER_PATTERNS: Dict[str, Dict[str, List[re.Pattern]]] = {
    "luz": {
        "valor": [re.compile(r, re.IGNORECASE) for r in [
            rf"energia\s*(?:ativa)?\s*[:\-]?\s*€?\s*({_NUM_PT}|{_NUM_EN}|{_NUM_SIMPLE})",
            rf"total\s*kwh\s*[:\-]?\s*€?\s*({_NUM_PT}|{_NUM_EN}|{_NUM_SIMPLE})",
        ]],
    },
    "agua": {
        "valor": [re.compile(r, re.IGNORECASE) for r in [
            rf"consumo\s*(?:de\s*)?[aá]gua\s*[:\-]?\s*€?\s*({_NUM_PT}|{_NUM_EN}|{_NUM_SIMPLE})",
            rf"saneamento\s*[:\-]?\s*€?\s*({_NUM_PT}|{_NUM_EN}|{_NUM_SIMPLE})",
        ]],
    },
    "gas": {
        "valor": [re.compile(r, re.IGNORECASE) for r in [
            rf"g[aá]s\s*natural\s*[:\-]?\s*€?\s*({_NUM_PT}|{_NUM_EN}|{_NUM_SIMPLE})",
        ]],
    },
    "comunicacoes": {
        "referencia": [re.compile(r, re.IGNORECASE) for r in [
            r"n[uú]mero\s*de\s*cliente\s*[:\-]?\s*([A-Z0-9]{4,20})",
            r"conta\s*[:\-]?\s*([A-Z0-9]{4,20})",
        ]],
    },
    "seguros": {
        "referencia": [re.compile(r, re.IGNORECASE) for r in [
            r"ap[oó]lice\s*[:\-]?\s*([A-Z0-9\-]{4,20})",
            r"n[uú]mero\s*(?:de\s*)?ap[oó]lice\s*[:\-]?\s*([A-Z0-9\-]{4,20})",
        ]],
    },
}

# Intervalo de valores aceites por tipo de conta (min €, max €)
_VALUE_RANGES: Dict[str, Tuple[float, float]] = {
    "luz":          (1.0, 2000.0),
    "agua":         (1.0, 500.0),
    "gas":          (1.0, 1000.0),
    "comunicacoes": (1.0, 1000.0),
    "seguros":      (1.0, 5000.0),
    "outro":        (0.01, 10000.0),
}

# Meses em português para parsear datas por extenso
_MONTHS_PT = {
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
    "abril": "04", "maio": "05", "junho": "06",
    "julho": "07", "agosto": "08", "setembro": "09",
    "outubro": "10", "novembro": "11", "dezembro": "12",
}


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------

class PDFExtractor:
    """
    Extrai valor, vencimento, referência e referência multibanco de faturas em PDF.

    Estratégia de extração:
    1. pdfplumber — texto nativo
    2. OCR via pytesseract/pdf2image — apenas se (1) falhar e tesseract estiver instalado
    """

    def __init__(self):
        self.ocr_available = _OCR_AVAILABLE
        if not self.ocr_available:
            print("ℹ  OCR não disponível (tesseract não instalado). Apenas PDFs com texto nativo serão processados.")

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def extract_from_file(
        self,
        pdf_bytes: bytes,
        bill_type: str = "outro",
        entidade_nome: str = "",
    ) -> Optional[Dict]:
        """
        Extrair dados de um PDF fornecido como bytes.

        Args:
            pdf_bytes:     Conteúdo do PDF em bytes.
            bill_type:     Tipo de conta (luz, agua, gas, comunicacoes, seguros, outro).
            entidade_nome: Nome da entidade emissora (vem do email — sender / matched_providers).
                           Se não fornecido, tenta extrair do texto do PDF.

        Returns:
            Dict com os 5 campos principais:
              entidade, valor, vencimento, mb_entidade, mb_referencia
            Mais campos de suporte:
              referencia_doc, metodo_extracao, campos_encontrados
        """
        text = self._extract_text_native(pdf_bytes)
        method = "pdfplumber"

        if not text.strip() and self.ocr_available:
            text = self._extract_text_ocr(pdf_bytes)
            method = "ocr"

        if not text.strip():
            print("✗ PDF sem texto extraível e OCR não disponível/falhou.")
            return None

        result = self._extract_data(text, bill_type)

        # Entidade emissora: preferir o que vem do email; fallback: texto do PDF
        result["entidade"] = entidade_nome or self._extract_entidade_from_text(text)

        result["metodo_extracao"] = method
        result["campos_encontrados"] = sum(
            1 for k in ("valor", "vencimento", "mb_entidade") if result.get(k) is not None
        )
        return result

    def extract_from_path(
        self,
        pdf_path: str,
        bill_type: str = "outro",
        entidade_nome: str = "",
    ) -> Optional[Dict]:
        """Extrair dados de um ficheiro PDF local."""
        try:
            with open(pdf_path, "rb") as f:
                return self.extract_from_file(f.read(), bill_type, entidade_nome)
        except Exception as e:
            print(f"✗ Erro ao abrir PDF {pdf_path}: {e}")
            return None

    # ------------------------------------------------------------------
    # Extração de texto
    # ------------------------------------------------------------------

    def _extract_text_native(self, pdf_bytes: bytes) -> str:
        """Extrai texto via pdfplumber (PDFs com texto embutido)."""
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                parts = []
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        parts.append(t)
                return "\n".join(parts)
        except Exception as e:
            print(f"Aviso pdfplumber: {e}")
            return ""

    def _extract_text_ocr(self, pdf_bytes: bytes) -> str:
        """Extrai texto via OCR (PDFs escaneados). Requer tesseract instalado."""
        try:
            images = convert_from_bytes(pdf_bytes, dpi=200)
            parts = []
            for img in images:
                t = pytesseract.image_to_string(img, lang="por+eng")
                if t:
                    parts.append(t)
            return "\n".join(parts)
        except Exception as e:
            print(f"Aviso OCR: {e}")
            return ""

    # ------------------------------------------------------------------
    # Extração de dados
    # ------------------------------------------------------------------

    def _extract_data(self, text: str, bill_type: str) -> Dict:
        """Orquestra extração de todos os campos a partir do texto completo."""
        valor = self._extract_value(text, bill_type)
        vencimento = self._extract_date(text)
        referencia_doc = self._extract_reference(text, bill_type)
        mb_entidade, mb_referencia = self._extract_multibanco(text)

        return {
            # ---- 5 campos principais ----
            "entidade": "",          # preenchido em extract_from_file após esta chamada
            "valor": valor,
            "vencimento": vencimento,
            "mb_entidade": mb_entidade,
            "mb_referencia": mb_referencia,
            # ---- campos de suporte ----
            "referencia_doc": referencia_doc,
        }

    def _extract_entidade_from_text(self, text: str) -> str:
        """Tenta identificar o nome da entidade emissora no texto do PDF."""
        text_lower = text.lower()
        providers = _get_known_providers()
        for provider, _ in providers.items():
            # Ignorar entradas muito curtas (ex: 'nos ', 'meo') que podem ter falsos positivos
            if len(provider.strip()) >= 4 and provider.strip() in text_lower:
                return provider.strip().title()
        return ""

    # ------------------------------------------------------------------
    # Valor
    # ------------------------------------------------------------------

    def _extract_value(self, text: str, bill_type: str) -> Optional[float]:
        """
        Extrai o valor a pagar.
        Tenta primeiro padrões específicos do tipo de conta, depois os genéricos.
        Valida o intervalo plausível para o tipo de conta.
        """
        min_val, max_val = _VALUE_RANGES.get(bill_type, _VALUE_RANGES["outro"])

        # Padrões específicos do fornecedor/tipo
        provider_patterns = _PROVIDER_PATTERNS.get(bill_type, {}).get("valor", [])
        for pattern in provider_patterns:
            result = self._try_value_pattern(pattern, text, min_val, max_val)
            if result is not None:
                return result

        # Padrões genéricos (ordenados por especificidade)
        for pattern in _VALOR_PATTERNS:
            result = self._try_value_pattern(pattern, text, min_val, max_val)
            if result is not None:
                return result

        return None

    def _try_value_pattern(
        self, pattern: re.Pattern, text: str, min_val: float, max_val: float
    ) -> Optional[float]:
        for match in pattern.finditer(text):
            try:
                raw = match.group(1).strip()
                value = self._parse_value(raw)
                if value is not None and min_val <= value <= max_val:
                    return value
            except (IndexError, ValueError):
                continue
        return None

    @staticmethod
    def _parse_value(raw: str) -> Optional[float]:
        """Converte string de valor (ex: '1.234,56' ou '1234.56') para float."""
        raw = raw.strip().replace(" ", "")
        # Formato PT: 1.234,56
        if re.match(r"^\d{1,3}(\.\d{3})*,\d{2}$", raw):
            return float(raw.replace(".", "").replace(",", "."))
        # Formato EN: 1,234.56
        if re.match(r"^\d{1,3}(,\d{3})*\.\d{2}$", raw):
            return float(raw.replace(",", ""))
        # Simples com vírgula decimal: 45,90
        if re.match(r"^\d+,\d{1,2}$", raw):
            return float(raw.replace(",", "."))
        # Simples com ponto decimal: 45.90
        if re.match(r"^\d+\.\d{1,2}$", raw):
            return float(raw)
        # Inteiro
        if re.match(r"^\d+$", raw):
            return float(raw)
        return None

    # ------------------------------------------------------------------
    # Data de vencimento
    # ------------------------------------------------------------------

    def _extract_date(self, text: str) -> Optional[str]:
        """Extrai data de vencimento e retorna no formato YYYY-MM-DD."""
        for pattern in _VENCIMENTO_PATTERNS:
            for match in pattern.finditer(text):
                try:
                    groups = match.groups()
                    # Padrão por extenso: "15 de maio de 2026"
                    if len(groups) == 3 and not groups[1].isdigit():
                        day, month_pt, year = groups
                        month = _MONTHS_PT.get(month_pt.lower().replace("ç", "c"))
                        if month:
                            parsed = self._parse_date(f"{day}/{month}/{year}")
                            if parsed:
                                return parsed
                    else:
                        parsed = self._parse_date(groups[0])
                        if parsed:
                            return parsed
                except (IndexError, ValueError):
                    continue
        return None

    @staticmethod
    def _parse_date(date_str: str) -> Optional[str]:
        """Parseia string de data em vários formatos e devolve YYYY-MM-DD."""
        date_str = re.sub(r"\s+", "", date_str.strip())
        # normalizar separadores
        date_str = re.sub(r"[. ]", "/", date_str)

        formats = [
            "%d/%m/%Y", "%d/%m/%y",
            "%Y/%m/%d",
            "%d-%m-%Y", "%d-%m-%y",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str, fmt)
                # Rejeitar datas no passado longínquo ou futuro implausível
                year = parsed.year
                if year < 2020 or year > 2035:
                    continue
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    # ------------------------------------------------------------------
    # Referência documental
    # ------------------------------------------------------------------

    def _extract_reference(self, text: str, bill_type: str) -> Optional[str]:
        """Extrai número de fatura / referência documental."""
        provider_patterns = _PROVIDER_PATTERNS.get(bill_type, {}).get("referencia", [])
        for pattern in provider_patterns:
            match = pattern.search(text)
            if match:
                ref = match.group(1).strip().upper()
                if len(ref) >= 3 and re.search(r'\d', ref):
                    return ref

        for pattern in _REFERENCIA_PATTERNS:
            match = pattern.search(text)
            if match:
                ref = match.group(1).strip().upper()
                # Referência válida: mínimo 3 chars E pelo menos um dígito
                if len(ref) >= 3 and re.search(r'\d', ref):
                    return ref
        return None

    # ------------------------------------------------------------------
    # Referência Multibanco
    # ------------------------------------------------------------------

    def _extract_multibanco(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extrai entidade (5 dígitos) e referência multibanco (9 dígitos) se presentes.
        Muito comum em faturas portuguesas.
        """
        entidade = None
        referencia = None

        m = _MULTIBANCO_ENTIDADE_PATTERN.search(text)
        if m:
            entidade = m.group(1)

        m = _MULTIBANCO_REF_PATTERN.search(text)
        if m:
            referencia = re.sub(r"\s", "", m.group(1))  # remover espaços

        return entidade, referencia


# ---------------------------------------------------------------------------
# Bloco de teste
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import glob

    extractor = PDFExtractor()

    # Procurar PDFs na pasta ExemplosPDF/ ou na raiz
    pdf_files = glob.glob("ExemplosPDF/**/*.pdf", recursive=True) + glob.glob("*.pdf")

    if not pdf_files:
        print("Nenhum PDF encontrado. Coloque ficheiros em ExemplosPDF/ para testar.")
    else:
        for path in pdf_files:
            print(f"\n{'='*60}")
            print(f"📄 {path}")
            result = extractor.extract_from_path(path)
            if result:
                print(f"  Método:             {result['metodo_extracao']}")
                print(f"  Campos encontrados: {result['campos_encontrados']}/3")
                valor_str = f"€{result['valor']}" if result['valor'] else '—'
                print(f"  Valor:              {valor_str}")
                print(f"  Vencimento:         {result['vencimento'] or '—'}")
                print(f"  Referência:         {result['referencia'] or '—'}")
                if result["multibanco_entidade"]:
                    print(f"  MB Entidade:        {result['multibanco_entidade']}")
                if result["multibanco_referencia"]:
                    print(f"  MB Referência:      {result['multibanco_referencia']}")
            else:
                print("  ✗ Não foi possível extrair dados")
