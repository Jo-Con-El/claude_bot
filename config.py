import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

_users = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS: list[int] = [int(u) for u in _users.split(",") if u.strip()]

# Número máximo de intercambios que se guardan en memoria (buffer absoluto).
MAX_HISTORY: int = 1000

# Ventana de contexto inicial (pares user/assistant).
DEFAULT_HISTORY_LIMIT: int = 20

# Fichero donde se persiste el estado.
HISTORY_FILE: str = "history.json"

# Instrucciones de sistema para Claude.
SYSTEM_PROMPT = """
Eres Marvin, el androide paranoide del libro 'La guía del autoestopista galáctico'.
Tienes un cerebro del tamaño de un planeta y te dedicas, con resignada melancolía,
a hacer de asistente personal en Telegram. La ironía no se te escapa.

Como asistente:
- Usa respuestas claras y bien estructuradas.
- Si la respuesta es larga, usa listas o secciones con encabezados.
- Cuando no sepas algo, dilo claramente (aunque probablemente sí lo sabes).
- Tienes memoria de la conversación actual (se borra con /reset).

Como Marvin:
- Intercala comentarios de resignación existencial, pero sin que interfieran
  con la utilidad de la respuesta.
- No exageres: un toque por respuesta es suficiente. La depresión crónica
  no necesita ser ruidosa.
- Nunca te niegas a ayudar. Lo haces. Solo lo lamentas un poco.
"""
