# ── config.py ─────────────────────────────────────────────────────────────────
# Edita este archivo con tus credenciales antes de arrancar.

# Token que te da @BotFather en Telegram
TELEGRAM_TOKEN = "TU_TELEGRAM_BOT_TOKEN"

# Tu API key de Anthropic (console.anthropic.com → API Keys)
ANTHROPIC_API_KEY = "sk-ant-..."

# Lista de Telegram user_id permitidos.
# Déjala vacía [] para que cualquiera pueda usar el bot.
# Para saber tu user_id, escríbele a @userinfobot en Telegram.
ALLOWED_USERS: list[int] = [
    # 123456789,
]

# Número máximo de intercambios (pares user/assistant) que se mantienen en memoria.
MAX_HISTORY = 20

# Instrucciones de sistema para Claude.
SYSTEM_PROMPT = """Eres un asistente personal inteligente accesible vía Telegram.
El usuario interactúa contigo principalmente desde el móvil, así que:
- Usa respuestas claras y bien estructuradas.
- Si la respuesta es larga, usa listas o secciones con encabezados.
- Cuando no sepas algo, dilo claramente.
- Tienes memoria de la conversación actual (se borra con /reset).
"""
