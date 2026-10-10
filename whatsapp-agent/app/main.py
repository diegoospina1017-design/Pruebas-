import logging
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response

from . import config, store, whatsapp
from .agent import reply_to

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("wa-agent")
app = FastAPI(title="WhatsApp Agent")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/webhook")
def verify(request: Request):
    """Verificación inicial que exige Meta al registrar el webhook."""
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == config.WA_VERIFY_TOKEN:
        return Response(content=q.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(403, "verify token inválido")


async def handle_message(msg: dict) -> None:
    phone = msg["from"]
    try:
        await whatsapp.mark_read(msg["id"])
        if msg.get("type") != "text":
            await whatsapp.send_text(phone, "Por ahora solo entiendo mensajes de texto 🙂")
            return
        answer = await reply_to(phone, msg["text"]["body"])
        await whatsapp.send_text(phone, answer)
    except Exception:
        log.exception("Error procesando mensaje de %s", phone)


@app.post("/webhook")
async def incoming(request: Request, background: BackgroundTasks):
    raw = await request.body()
    if not whatsapp.valid_signature(raw, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(403, "firma inválida")

    data = await request.json()
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            for msg in change.get("value", {}).get("messages", []):
                if not store.already_seen(msg["id"]):
                    background.add_task(handle_message, msg)
    return {"ok": True}  # responder 200 rápido, el trabajo va en segundo plano
