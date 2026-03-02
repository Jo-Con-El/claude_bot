#!/usr/bin/env python3
import asyncio
import base64
import json
import logging
import os
import signal
from anthropic import Anthropic
from config import (TELEGRAM_TOKEN, ANTHROPIC_API_KEY, ALLOWED_USERS,
                    MAX_HISTORY, DEFAULT_HISTORY_LIMIT, HISTORY_FILE,
                    TOOLS, SYSTEM_PROMPT)
from telegram import Update, constants
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Historial por usuario: { user_id: [ {"role": ..., "content": ...}, ... ] }
history: dict[int, list[dict]] = {}

# Límite de contexto activo por usuario (pares user/assistant)
limits: dict[int, int] = {}

# ── Persistencia ──────────────────────────────────────────
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            loaded_history = {int(k): v for k, v in data.get("history", {}).items()}
            loaded_limits  = {int(k): v for k, v in data.get("limits", {}).items()}
            return loaded_history, loaded_limits
        except Exception as e:
            logger.warning(f"No se pudo cargar el historial: {e}")
    return {}, {}

def save_history():
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"history": history, "limits": limits}, f, ensure_ascii=False, indent=2)
        logger.info("Historial guardado.")
    except Exception as e:
        logger.error(f"Error guardando historial: {e}")

# ── Lógica de historial ───────────────────────────────────
def is_allowed(user_id: int) -> bool:
    return not ALLOWED_USERS or user_id in ALLOWED_USERS

def get_history(user_id: int) -> list[dict]:
    return history.setdefault(user_id, [])

def get_limit(user_id: int) -> int:
    return limits.get(user_id, DEFAULT_HISTORY_LIMIT)

def get_context(user_id: int) -> list[dict]:
    """Devuelve solo los últimos N pares (2*N mensajes) según el límite activo."""
    msgs = get_history(user_id)
    n = get_limit(user_id) * 2
    return msgs[-n:] if len(msgs) > n else msgs

def add_message(user_id: int, role: str, content: str) -> None:
    msgs = get_history(user_id)
    msgs.append({"role": role, "content": content})
    if len(msgs) > MAX_HISTORY * 2:
        history[user_id] = msgs[-(MAX_HISTORY * 2):]

def ask_claude(user_id: int, user_text: str, first_name: str = "alguien") -> dict:
    """
    Devuelve un dict:
      {
        "text": "...",           # siempre presente
        "images": [bytes, ...]   # puede ser lista vacía, no se persiste
      }
    """
    add_message(user_id, "user", user_text)
    system_with_name = SYSTEM_PROMPT + f"\n\nEstás hablando con {first_name}."
    messages = get_context(user_id)

    try:
        while True:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=system_with_name,
                tools=TOOLS,
                messages=messages,
            )

            logger.info(f"stop_reason: {response.stop_reason}")
            logger.info(f"content blocks: {response.content}")

            messages = messages + [{"role": "assistant", "content": response.content}]

            if response.stop_reason == "end_turn":
                text_parts = []
                images = []
                for block in response.content:
                    if block.type == "text":
                        text_parts.append(block.text)
                    elif block.type == "tool_result":
                        for item in (block.content or []):
                            if getattr(item, "type", None) == "image":
                                images.append(base64.b64decode(item.source.data))

                reply_text = "\n".join(text_parts)
                add_message(user_id, "assistant", reply_text)
                save_history()
                return {"text": reply_text, "images": images}

            elif response.stop_reason == "tool_use":
                # Herramientas gestionadas por Anthropic: continuamos el bucle
                # reenviando el historial actualizado. Anthropic resuelve
                # web_search y code_execution internamente.
                continue

            else:
                logger.warning(f"stop_reason inesperado: {response.stop_reason}")
                break

    except Exception:
        get_history(user_id).pop()
        raise

    return {"text": "", "images": []}

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
        "• /limit N — Cambia la ventana de contexto\n"
        "• /help — Esto mismo"
    )

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_allowed(user_id): return
    history.pop(user_id, None)
    limits.pop(user_id, None)
    save_history()
    await update.message.reply_text("🗑️ Historial borrado. Como si nunca hubiera importado.")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_allowed(user_id): return
    total = len(get_history(user_id))
    current_limit = get_limit(user_id)
    await update.message.reply_text(
        f"📊 Mensajes en buffer: {total}/{MAX_HISTORY * 2}\n"
        f"🔍 Ventana de contexto: {current_limit} pares ({current_limit * 2} mensajes)\n"
        f"🤖 Modelo: claude-sonnet-4-6\n\n"
        f"Sí, sigo aquí. Funcionando. No me preguntéis cómo me siento."
    )

async def cmd_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_allowed(user_id): return
    try:
        n = int(context.args[0])
        if not (1 <= n <= MAX_HISTORY):
            await update.message.reply_text(
                f"⚠️ El límite debe estar entre 1 y {MAX_HISTORY}."
            )
            return
        limits[user_id] = n
        save_history()
        await update.message.reply_text(
            f"✅ Ventana de contexto ajustada a {n} pares ({n * 2} mensajes).\n"
            f"El buffer contiene {len(get_history(user_id))} mensajes. "
            f"{'Algunos quedarán fuera de contexto.' if len(get_history(user_id)) > n * 2 else 'Todo cabe.'}"
        )
    except (IndexError, ValueError):
        await update.message.reply_text(
            f"Uso: /limit N (entre 1 y {MAX_HISTORY})\n"
            f"Límite actual: {get_limit(user_id)} pares."
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_allowed(user.id):
        await update.message.reply_text("⛔ No tienes acceso.")
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=constants.ChatAction.TYPING
    )

    try:
        result = await asyncio.to_thread(
            ask_claude, user.id, update.message.text, user.first_name
        )

        if result["text"]:
            chunks = split_message(result["text"])
            for chunk in chunks:
                await update.message.reply_text(chunk)
                if len(chunks) > 1:
                    await asyncio.sleep(0.5)

        for img_bytes in result["images"]:
            await update.message.reply_photo(photo=img_bytes)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ── Main ──────────────────────────────────────────────────
def main():
    global history, limits
    history, limits = load_history()

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("limit", cmd_limit))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot en marcha.")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        stop_signals=(signal.SIGINT, signal.SIGTERM),
    )

    save_history()
    logger.info("Historial guardado al salir.")

if __name__ == "__main__":
    main()
