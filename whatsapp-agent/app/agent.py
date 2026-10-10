"""Bucle del agente: Claude + herramientas + memoria."""
import anthropic
from . import config, store
from .tools import TOOLS, run_tool

client = anthropic.AsyncAnthropic()
MAX_STEPS = 5


async def reply_to(phone: str, text: str) -> str:
    store.save(phone, "user", text)
    messages = store.load(phone)

    for _ in range(MAX_STEPS):
        resp = await client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=1000,
            system=config.SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        blocks = [b.model_dump(exclude_none=True) for b in resp.content]
        store.save(phone, "assistant", blocks)
        messages.append({"role": "assistant", "content": blocks})

        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text") or "..."

        results = [
            {
                "type": "tool_result",
                "tool_use_id": b.id,
                "content": run_tool(b.name, b.input),
            }
            for b in resp.content
            if b.type == "tool_use"
        ]
        store.save(phone, "user", results)
        messages.append({"role": "user", "content": results})

    return "Lo siento, no pude completar la consulta. ¿Puedes reformularla?"
