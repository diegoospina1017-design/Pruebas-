"""Cliente mínimo de la WhatsApp Cloud API."""
import hashlib
import hmac
import httpx
from . import config

BASE = f"https://graph.facebook.com/{config.WA_GRAPH_VERSION}/{config.WA_PHONE_ID}"
HEADERS = {"Authorization": f"Bearer {config.WA_TOKEN}"}


def valid_signature(raw_body: bytes, header: str | None) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(config.WA_APP_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


async def send_text(to: str, body: str) -> None:
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.post(
            f"{BASE}/messages",
            headers=HEADERS,
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": body[:4096]},  # límite de WhatsApp
            },
        )
        r.raise_for_status()


async def mark_read(msg_id: str) -> None:
    async with httpx.AsyncClient(timeout=15) as h:
        await h.post(
            f"{BASE}/messages",
            headers=HEADERS,
            json={"messaging_product": "whatsapp", "status": "read", "message_id": msg_id},
        )
