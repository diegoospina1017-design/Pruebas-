"""Memoria de conversación por número de teléfono (SQLite)."""
import json
import sqlite3
from . import config


def _conn():
    c = sqlite3.connect(config.DB_PATH)
    c.execute(
        "CREATE TABLE IF NOT EXISTS messages ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT, role TEXT, content TEXT)"
    )
    c.execute("CREATE TABLE IF NOT EXISTS seen (msg_id TEXT PRIMARY KEY)")
    return c


def already_seen(msg_id: str) -> bool:
    """Meta reintenta webhooks; evita procesar dos veces el mismo mensaje."""
    with _conn() as c:
        try:
            c.execute("INSERT INTO seen (msg_id) VALUES (?)", (msg_id,))
            return False
        except sqlite3.IntegrityError:
            return True


def load(phone: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT role, content FROM messages WHERE phone=? ORDER BY id DESC LIMIT ?",
            (phone, config.MAX_HISTORY),
        ).fetchall()
    msgs = [{"role": r, "content": json.loads(t)} for r, t in reversed(rows)]
    # La conversación debe empezar con un mensaje de usuario (texto)
    while msgs and not (msgs[0]["role"] == "user" and isinstance(msgs[0]["content"], str)):
        msgs.pop(0)
    return msgs


def save(phone: str, role: str, content) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO messages (phone, role, content) VALUES (?,?,?)",
            (phone, role, json.dumps(content, ensure_ascii=False)),
        )
