#!/usr/bin/env python3
import logging
import asyncio
import json
import signal
import os
from telegram import Update, constants
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from anthropic import Anthropic
from config import TELEGRAM_TOKEN, ANTHROPIC_API_KEY, ALLOWED_USERS, MAX_HISTORY, HISTORY_FILE, SYSTEM_PROMPT

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

client = Anthropic(api_key=ANTHROPIC_API_KEY)
# Historial por usuario: { user_id: [ {"role": ..., "content": ...}, ... ] }
history: dict[int, list[dict]] = {}

# ── Persistencia ──────────────────────────────────────────
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Las claves en JSON son siempre strings; las convertimos a int
            return {int(k): v for k, v in data.items()}
        except Exception as e:
            logger.warning(f"No se pudo cargar el historial: {e}")
    return {}

def save_history():
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        logger.info("Historial guardado.")
    except Exception as e:
        logger.error(f"Error guardando historial: {e}")

# ── Lógica de historial ───────────────────────────────────
def is_allowed(user_id: int) -> bool:
    return not ALLOWED_USERS or user_id in ALLOWED_USERS

def get_history(user_id: int) -> list[dict]:
    return history.setdefault(user_id, [])

def add_message(user_id: int, role: str, content: str) -> None:
    msgs = get_history(user_id)
    msgs.append({"role": role, "content": content})
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
    return [text[i:i+limit] for i in range(0, len(text), limit)] if len(text) > limit else [text]

# ── Handlers ──────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_allowed(user.id):
        await update.message.reply_text("⛔ No tienes acceso a este bot.")
        return
    await update.message.reply_text(
        f"Hola, {user.first_name}. Soy Marvin.\n\n"
        "Tengo un cerebro del tamaño de un planeta y me han asignado "
        "responder mensajes de Telegram. He intentado encontrarle sentido. "
        "No lo tiene.\n\n"
        "• /reset — Borra tu historial\n"
        "• /status — Estado del bot\n"
        "• /help — Esto mismo"
    )

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_allowed(user_id): return
    history.pop(user_id, None)
    save_history()
    await update.message.reply_text("🗑️ Historial borrado. Como si nunca hubiera importado.")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_allowed(user_id): return
    n = len(get_history(user_id))
    await update.message.reply_text(
        f"📊 Mensajes almacenados: {n}/{MAX_HISTORY * 2}\n"
        f"🤖 Modelo: claude-sonnet-4-6\n\n"
        f"Sí, sigo aquí. Funcionando. No me preguntéis cómo me siento."
    )

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_allowed(user.id):
        await update.message.reply_text("⛔ No tienes acceso.")
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    try:
        reply = await asyncio.to_thread(ask_claude, user.id, update.message.text)
for chunk in split_message(reply):
            await update.message.reply_text(chunk)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ── Main ──────────────────────────────────────────────────
def main():
    global history
    history = load_history()

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Guardar al recibir SIGINT (Ctrl+C) o SIGTERM (systemd stop, etc.)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda s, f: (save_history(), exit(0)))

    logger.info("Bot en marcha.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
