"""
Serviço de processamento de imagens
Extrai dados de contas a pagar via OCR (tesseract + Pillow)
"""

import io
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# OCR — opcional, depende de tesseract estar instalado no sistema
_OCR_AVAILABLE = False
try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = '/opt/local/bin/tesseract'
    pytesseract.get_tesseract_version()
    _OCR_AVAILABLE = True
except Exception:
    pass

# Pillow — necessário para pré-processamento da imagem
_PIL_AVAILABLE = False
try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    pass


class ImageProcessor:
    """Serviço para processar imagens via OCR e extrair dados de contas a pagar"""

    def __init__(self):
        self.ocr_available = _OCR_AVAILABLE and _PIL_AVAILABLE
        if not _PIL_AVAILABLE:
            print("⚠️  ImageProcessor: Pillow não instalado — instale com: pip install Pillow")
        elif not _OCR_AVAILABLE:
            print("⚠️  ImageProcessor: tesseract não instalado — OCR desactivado")

    def validate_image(self, image_bytes: bytes) -> bool:
        """
        Validar se os bytes são uma imagem válida.

        Args:
            image_bytes: Conteúdo da imagem

        Returns:
            bool: True se válida
        """
        if not _PIL_AVAILABLE:
            return False
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img.verify()
            return True
        except Exception:
            return False

    def process_from_bytes(
        self,
        image_bytes: bytes,
        bill_type: str = "outro",
        entidade_nome: str = "",
    ) -> Optional[Dict]:
        """
        Processar imagem de bytes e extrair dados de conta.

        Args:
            image_bytes:   Conteúdo da imagem em bytes.
            bill_type:     Tipo de conta (luz, agua, gas, comunicacoes, seguros, outro).
            entidade_nome: Nome da entidade (ex: caption enviada no Telegram).

        Returns:
            Dict no mesmo formato de PDFExtractor.extract_from_file(), ou None se erro.
        """
        if not self.ocr_available:
            print("✗ OCR indisponível — instale: brew install tesseract tesseract-lang && pip install Pillow")
            return None

        try:
            text = self._image_bytes_to_text(image_bytes)
        except Exception as e:
            print(f"✗ Erro OCR: {e}")
            return None

        if not text.strip():
            print("✗ OCR não extraiu texto da imagem.")
            return None

        # Reutilizar lógica de extração do PDFExtractor (evita duplicar regex)
        from src.services.pdf_extractor import PDFExtractor
        extractor = PDFExtractor()
        result = extractor._extract_data(text, bill_type)
        result["entidade"] = entidade_nome or extractor._extract_entidade_from_text(text)
        result["metodo_extracao"] = "ocr_image"
        result["campos_encontrados"] = sum(
            1 for k in ("valor", "vencimento", "mb_entidade") if result.get(k) is not None
        )
        # Incluir texto OCR bruto para diagnóstico (usado pelo bot quando valor não é encontrado)
        result["_ocr_text"] = text
        return result

    def process_from_file(self, image_path: str) -> Optional[Dict]:
        """
        Processar imagem de ficheiro local.

        Args:
            image_path: Caminho da imagem

        Returns:
            Dict: Dados extraídos da imagem ou None
        """
        try:
            with open(image_path, "rb") as f:
                return self.process_from_bytes(f.read())
        except Exception as e:
            print(f"✗ Erro ao abrir imagem {image_path}: {e}")
            return None

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _image_bytes_to_text(self, image_bytes: bytes) -> str:
        """Pré-processa imagem e extrai texto via tesseract.

        Usa adaptive thresholding para eliminar ruído de textura do papel:
        cada pixel é comparado com a média da sua vizinhança local (blur grande),
        não com um valor global — ideal para faturas em papel texturado/granulado.
        """
    def _image_bytes_to_text(self, image_bytes: bytes) -> str:
        """Pré-processa imagem e extrai texto via tesseract."""
        from PIL import ImageFilter, ImageOps

        img_orig = Image.open(io.BytesIO(image_bytes)).convert("L")

        # Garantir resolução mínima para OCR
        if img_orig.width < 1500:
            scale = 1500 / img_orig.width
            img_orig = img_orig.resize(
                (int(img_orig.width * scale), int(img_orig.height * scale)),
                Image.LANCZOS,
            )

        # autocontrast: estica o histograma ignorando os 2% extremos
        # ideal para papel texturado — não precisa de numpy
        img_auto = ImageOps.autocontrast(img_orig, cutoff=2)

        candidates = [
            (img_auto.point(lambda x: 0 if x < 128 else 255), 6, "auto+thresh128 psm6"),
            (img_auto.point(lambda x: 0 if x < 128 else 255), 4, "auto+thresh128 psm4"),
            (img_orig.point(lambda x: 0 if x < 150 else 255), 6, "thresh150 psm6"),
            (img_orig.point(lambda x: 0 if x < 130 else 255), 6, "thresh130 psm6"),
            (img_auto,                                          6, "autocontrast psm6"),
            (img_orig,                                          6, "grayscale psm6"),
        ]

        best_text = ""
        best_score = -1
        for img_variant, psm, desc in candidates:
            try:
                config = f"--psm {psm} -l por+eng"
                text = pytesseract.image_to_string(img_variant, config=config)
                score = sum(1 for c in text if c.isalnum())
                logger.info(f"[OCR] {desc}: score={score} | {repr(text[:100])}")
                if score > best_score:
                    best_score = score
                    best_text = text
            except Exception as e:
                logger.warning(f"[OCR] {desc} falhou: {e}")

        logger.info(f"[OCR] Melhor resultado:\n---\n{best_text}\n---")
        return best_text

        best_text = ""
        best_score = -1
        for img_variant, psm, desc in candidates:
            try:
                config = f"--psm {psm} -l por+eng"
                text = pytesseract.image_to_string(img_variant, config=config)
                score = sum(1 for c in text if c.isalnum())
                logger.info(f"[OCR] {desc}: score={score} | {repr(text[:100])}")
                if score > best_score:
                    best_score = score
                    best_text = text
            except Exception as e:
                logger.warning(f"[OCR] {desc} falhou: {e}")

        logger.info(f"[OCR] Melhor resultado:\n---\n{best_text}\n---")
        return best_text


if __name__ == "__main__":
    processor = ImageProcessor()
    print(f"OCR disponível: {processor.ocr_available}")
