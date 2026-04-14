"""
Telegram Bot — recebe fotos e PDFs de contas a pagar,
processa via OCR/extração e cria eventos no Google Calendar.

Execução: python -m src.bot  (paralelo com o agendamento em main.py)
"""

import logging
from typing import Optional

from telegram import Update, Message
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from src.config import TELEGRAM_BOT_TOKEN, classify_email
from src.services.calendar_service import CalendarService
from src.services.image_processor import ImageProcessor
from src.services.pdf_extractor import PDFExtractor
from src.services.telegram_service import TelegramService

logging.basicConfig(
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Handlers de comandos
# ------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Olá! Sou o teu assistente de contas a pagar.\n\n"
        "📸 Envia uma foto de uma conta em papel e extraio automaticamente:\n"
        "   • Valor a pagar\n"
        "   • Data de vencimento\n"
        "   • Referência Multibanco\n"
        "   • Evento no Google Calendar\n\n"
        "💡 <b>Dica:</b> Adiciona o nome da entidade como legenda da foto\n"
        "   (ex: <i>EDP</i>, <i>Água</i>) para um título mais preciso no Calendar.\n\n"
        "📄 Também aceito PDFs enviados directamente.",
        parse_mode="HTML",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "ℹ️ <b>Como usar:</b>\n\n"
        "1. Tira uma foto à conta em papel\n"
        "2. Envia a foto para este chat\n"
        "3. (Opcional) Escreve o nome da entidade como legenda da foto\n"
        "   ex: <i>EDP</i>, <i>NOS</i>, <i>Água Lisboa</i>\n\n"
        "4. Aguarda — evento criado no Google Calendar! ✅\n\n"
        "<b>Comandos:</b>\n"
        "/start — mensagem de boas-vindas\n"
        "/help  — esta ajuda",
        parse_mode="HTML",
    )


# ------------------------------------------------------------------
# Handler de fotos
# ------------------------------------------------------------------

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    caption = (message.caption or "").strip()

    await message.reply_text("⏳ A processar a imagem…")

    # Descarregar foto em maior resolução disponível
    photo_file = await message.photo[-1].get_file()
    image_bytes = bytes(await photo_file.download_as_bytearray())

    entidade_nome = caption
    bill_type = _detect_bill_type_from_caption(caption)

    processor = ImageProcessor()
    data = processor.process_from_bytes(image_bytes, bill_type=bill_type, entidade_nome=entidade_nome)

    if data is None:
        await message.reply_text(
            "❌ Não foi possível processar a imagem.\n"
            "Certifica-te que a foto está nítida e bem iluminada."
        )
        return

    # Se bill_type ainda indeterminado, inferir a partir do texto extraído pelo OCR
    if bill_type == "outro":
        ocr_entity = data.get("entidade", "")
        if ocr_entity:
            classification = classify_email(ocr_entity, "", "")
            bill_type = classification.get("bill_type", "outro")

    await _finalise_bill(message, data, bill_type)


# ------------------------------------------------------------------
# Handler de documentos (PDFs)
# ------------------------------------------------------------------

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    doc = message.document
    caption = (message.caption or "").strip()

    if doc.mime_type != "application/pdf":
        await message.reply_text("⚠️ Só aceito ficheiros PDF ou fotos. Por favor tenta novamente.")
        return

    await message.reply_text("⏳ A processar o PDF…")

    pdf_file = await doc.get_file()
    pdf_bytes = bytes(await pdf_file.download_as_bytearray())

    entidade_nome = caption
    bill_type = _detect_bill_type_from_caption(caption)

    extractor = PDFExtractor()
    data = extractor.extract_from_file(pdf_bytes, bill_type=bill_type, entidade_nome=entidade_nome)

    if data is None:
        await message.reply_text("❌ Não foi possível extrair dados do PDF.")
        return

    await _finalise_bill(message, data, bill_type)


# ------------------------------------------------------------------
# Finalização comum — Calendar + notificação Telegram
# ------------------------------------------------------------------

async def _finalise_bill(message: Message, data: dict, bill_type: str) -> None:
    entidade = data.get("entidade") or "Desconhecida"
    valor = data.get("valor")
    vencimento = data.get("vencimento")
    mb_entidade = data.get("mb_entidade")
    mb_referencia = data.get("mb_referencia")
    referencia_doc = data.get("referencia_doc")

    # Criar evento no Google Calendar (apenas se tiver data de vencimento)
    event_id: Optional[str] = None
    if vencimento:
        try:
            calendar = CalendarService()
            event_id = calendar.create_bill_event(
                entidade=entidade,
                bill_type=bill_type,
                valor=valor or 0.0,
                vencimento=vencimento,
                mb_entidade=mb_entidade,
                mb_referencia=mb_referencia,
                referencia_doc=referencia_doc,
            )
        except Exception as e:
            logger.warning(f"Erro ao criar evento no Calendar para '{entidade}': {e}")

    if valor and vencimento:
        # Notificação completa via TelegramService (vai para o TELEGRAM_CHAT_ID do .env)
        TelegramService().send_bill_notification(
            entidade=entidade,
            bill_type=bill_type,
            valor=valor,
            vencimento=vencimento,
            mb_entidade=mb_entidade,
            mb_referencia=mb_referencia,
            referencia_doc=referencia_doc,
            calendar_event_id=event_id,
        )
    else:
        # Resposta parcial — faltam campos principais
        campos = []
        if valor:
            campos.append(f"💶 Valor: <b>€{valor:.2f}</b>")
        if vencimento:
            campos.append(f"📅 Vencimento: <b>{vencimento}</b>")
        if mb_entidade:
            campos.append(f"🏧 MB Entidade: <code>{mb_entidade}</code>")
        if mb_referencia:
            campos.append(f"🔢 MB Referência: <code>{mb_referencia}</code>")
        if referencia_doc:
            campos.append(f"📄 Nº Fatura: <code>{referencia_doc}</code>")

        if campos:
            body = "\n".join(campos)
            await message.reply_text(
                f"⚠️ Dados parcialmente extraídos para <b>{entidade}</b>:\n\n{body}\n\n"
                "Verifica se a imagem está nítida.",
                parse_mode="HTML",
            )
        else:
            await message.reply_text(
                "⚠️ Não foi possível extrair dados suficientes.\n"
                "Tenta com uma foto mais nítida ou envia o PDF directamente."
            )


# ------------------------------------------------------------------
# Utilitário
# ------------------------------------------------------------------

def _detect_bill_type_from_caption(caption: str) -> str:
    """Infere o tipo de conta a partir da caption enviada com a foto."""
    if not caption:
        return "outro"
    return classify_email(caption, "", "").get("bill_type", "outro")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN não configurado no .env")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document))

    logger.info("🤖 Bot a correr em polling — aguarda fotos e PDFs…")
    app.run_polling(poll_interval=5)


if __name__ == "__main__":
    main()
