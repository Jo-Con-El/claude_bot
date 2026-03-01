# Claude Telegram Bot

Bot de Telegram que conecta con Claude (Anthropic API).
Mantiene historial de conversación por usuario y soporta lista blanca de acceso.

---

## Instalación

```bash
python3 -m venv /src/claude-bot (o cualquier otro directorio)
source /src/claude-bot/bin/activate
pip install -r requirements.txt
```

## Configuración

Renombra `.env.example` a `.env` y rellena:

- `TELEGRAM_TOKEN` → obtenlo hablando con @BotFather en Telegram (`/newbot`)
- `ANTHROPIC_API_KEY` → en console.anthropic.com → API Keys
- `ALLOWED_USERS` → tu user_id (pregúntale a @userinfobot) y el de los demás,
  separado por comas sin espacios. Déjalo vacío para acceso libre.

## Arrancar

```bash
python bot.py
```

## Comandos del bot

| Comando    | Función                                        |
|------------|------------------------------------------------|
| `/start`   | Bienvenida                                     |
| `/reset`   | Borra el historial de conversación             |
| `/limit N` | Cambia la ventana de contexto                  |
| `/status`  | Muestra mensajes en memoria y modelo activo    |
| `/help`    | Ayuda                                          |

---

## Ejecutar como servicio (systemd)

Crea `/etc/systemd/system/claude-bot.service`:

```ini
[Unit]
Description=Claude Telegram Bot
After=network.target

[Service]
User=tu_usuario
WorkingDirectory=/ruta/al/proyecto
ExecStart=/ruta/al/proyecto/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now claude-bot
sudo systemctl status claude-bot
```

---

## Coste estimado

Con `claude-sonnet-4-6` y uso personal esporádico (vuelos, etc.):  
~$0.01–0.05 por conversación. Con 5 € de créditos tienes para meses.

Para reducir costes, cambia el modelo en `bot.py` a `claude-haiku-4-5-20251001`.

---

## Estructura

```
claude-telegram-bot/
├── bot.py           # Lógica principal
├── config.py        # Configuración general, personalidad y demás
├── .env             # Credenciales personales
├── requirements.txt # Dependencias
└── README.md        # Este archivo
```
