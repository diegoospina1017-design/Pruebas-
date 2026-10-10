import os
from dotenv import load_dotenv

load_dotenv()

WA_TOKEN = os.environ.get("WA_TOKEN", "")
WA_PHONE_ID = os.environ.get("WA_PHONE_ID", "")
WA_VERIFY_TOKEN = os.environ.get("WA_VERIFY_TOKEN", "")
WA_APP_SECRET = os.environ.get("WA_APP_SECRET", "")
WA_GRAPH_VERSION = os.environ.get("WA_GRAPH_VERSION", "v21.0")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
DB_PATH = os.environ.get("DB_PATH", "conversations.db")

MAX_HISTORY = 20  # mensajes que se envían a Claude

SYSTEM_PROMPT = """Eres el asistente virtual de WhatsApp de <EMPRESA>.
- Responde en español, de forma breve y clara (WhatsApp es un chat, no un correo).
- No uses formato Markdown complejo; usa texto plano, y *negrita* solo si es necesario.
- Si necesitas datos reales, usa las herramientas disponibles; no inventes.
- Si no puedes ayudar, dilo y ofrece derivar con una persona.
"""
