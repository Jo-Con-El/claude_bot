#!/usr/bin/env python3
"""
Claude Telegram Bot
Conecta Telegram con la API de Anthropic (Claude).
Mantiene historial de conversación por usuario.

Uso:
    python bot.py

Requisitos:
    pip install anthropic python-telegram-bot
"""

import logging
import asyncio

from telegram import Update, constants
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from anthropic import Anthropic

from config import (
    TELEGRAM_TOKEN,
    ANTHROPIC_API_KEY,
    ALLOWED_USERS,
    MAX_HISTORY,
    SYSTEM_PROMPT,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Cliente Anthropic ─────────────────────────────────────────────────────────
client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Historial por usuario: { user_id: [ {"role": ..., "content": ...}, ... ] }
history: dict[int, list[dict]] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_allowed(user_id: int) -> bool:
    return not ALLOWED_USERS or user_id in ALLOWED_USERS


def get_history(user_id: int) -> list[dict]:
    return history.setdefault(user_id, [])


def add_message(user_id: int, role: str, content: str) -> None:
    msgs = get_history(user_id)
    msgs.append({"role": role, "content": content})
    # Recortar para no exceder el límite configurado
    if len(msgs) > MAX_HISTORY * 2:
        history[user_id] = msgs[-(MAX_HISTORY * 2):]


def ask_claude(user_id: int, user_text: str) -> str:
    """Llama a la API de Claude de forma síncrona y devuelve la respuesta."""
    add_message(user_id, "user", user_text)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=get_history(user_id),
        )
        reply = response.content[0].text
        add_message(user_id, "assistant", reply)
        return reply
    except Exception:
        # Revertir el mensaje del usuario para no desincronizar el historial
        get_history(user_id).pop()
        raise


def split_message(text: str, limit: int = 4096) -> list[str]:
    """Divide texto largo en chunks que Telegram acepta."""
    if len(text) <= limit:
        return [text]
    return [text[i : i + limit] for i in range(0, len(text), limit)]


# ── Handlers ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_allowed(user.id):
        await update.message.reply_text("⛔ No tienes acceso a este bot.")
        return
    await update.message.reply_text(
        f"👋 Hola, {user.first_name}!\n\n"
        "Soy Claude, tu asistente de IA. Escríbeme lo que necesites.\n\n"
        "Comandos:\n"
        "• /reset — Borra el historial de conversación\n"
        "• /status — Info del bot\n"
        "• /help — Esta ayuda"
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        return
    history.pop(user_id, None)
    await update.message.reply_text("🗑️ Historial borrado. Empezamos de cero.")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        return
    n = len(get_history(user_id))
    await update.message.reply_text(
        f"📊 Mensajes en memoria: {n} / {MAX_HISTORY * 2}\n"
        f"Modelo: claude-sonnet-4-6"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_allowed(user.id):
        await update.message.reply_text("⛔ No tienes acceso a este bot.")
        return

    user_text = update.message.text
    logger.info("Usuario %s (%d): %s", user.username or "?", user.id, user_text[:80])

    # Indicador "escribiendo..." mientras Claude procesa
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=constants.ChatAction.TYPING,
    )

    try:
        reply = await asyncio.to_thread(ask_claude, user.id, user_text)
        for chunk in split_message(reply):
            await update.message.reply_text(chunk)
    except Exception as e:
        logger.exception("Error en handle_message")
        await update.message.reply_text(
            f"❌ Error al contactar con Claude:\n{e}\n\nInténtalo de nuevo."
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("Iniciando bot...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot en marcha. Ctrl+C para detener.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
