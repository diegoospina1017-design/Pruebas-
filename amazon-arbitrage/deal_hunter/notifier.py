"""
Notifications for HOT BUYS - macOS native and/or Telegram.

Setup macOS (no extra steps - osascript is built-in):
    Notifications work out of the box. The first time you run, macOS will
    ask if you want to allow Terminal/Python to send notifications - say yes.

Setup Telegram (5 minutes):
    1. On Telegram, search for @BotFather and start a chat
    2. Send /newbot, follow prompts to name your bot
    3. BotFather sends you a token like: 1234567890:ABC-DEF1234abcdef
    4. Start a chat with YOUR new bot (search by the name you gave it)
       and send any message like "hi"
    5. Visit: https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
       Look for "chat":{"id":NNNNN}. That number is your chat_id.
    6. Set env vars:
        export TELEGRAM_BOT_TOKEN="1234567890:ABC-DEF1234abcdef"
        export TELEGRAM_CHAT_ID="NNNNN"
       (Add to ~/.zshrc to persist)

If neither is configured, hunter just prints to console as before.
"""

import json
import os
import platform
import shutil
import subprocess
import urllib.parse
import urllib.request
import urllib.error
from typing import List, Optional


def _escape_applescript(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def mac_notify(title: str, body: str, subtitle: str = "") -> bool:
    """Send a macOS notification via osascript. No-op on non-Mac."""
    if platform.system() != "Darwin":
        return False
    if not shutil.which("osascript"):
        return False
    parts = [f'display notification "{_escape_applescript(body)}"',
             f'with title "{_escape_applescript(title)}"']
    if subtitle:
        parts.append(f'subtitle "{_escape_applescript(subtitle)}"')
    parts.append('sound name "Glass"')
    script = " ".join(parts)
    try:
        subprocess.run(["osascript", "-e", script], check=False, timeout=5,
                       capture_output=True)
        return True
    except (subprocess.SubprocessError, OSError):
        return False


def telegram_send(token: str, chat_id: str, text: str, disable_preview: bool = True) -> bool:
    """Send a Telegram message. Supports Markdown."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": "true" if disable_preview else "false",
    }).encode("utf-8")
    try:
        with urllib.request.urlopen(url, data=data, timeout=10) as r:
            response = json.loads(r.read().decode("utf-8"))
            return bool(response.get("ok"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        print(f"  [telegram] HTTP {e.code}: {body}")
        return False
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        print(f"  [telegram] failed: {e}")
        return False


def _format_hot_buy_telegram(d: dict, idx: int) -> str:
    m = d["_target_match"]
    bsr = f"{m['target_bsr']:,}" if m.get("target_bsr") else "?"
    title_short = d["title"][:80].replace("*", "").replace("_", "").replace("[", "(").replace("]", ")")
    return (
        f"*HOT BUY #{idx}*\n"
        f"{title_short}\n\n"
        f"Retailer: *{d.get('retailer') or '?'}*\n"
        f"Deal price: *${d['deal_price']:.2f}*\n"
        f"Your max buy: ${m['target_max_buy']:.2f}  (margin: +${m['margin_vs_max']:.2f})\n"
        f"Sells on Amazon: ${m['target_amazon_price']:.2f}  BSR {bsr}\n"
        f"ASIN: `{m['target_asin']}`\n\n"
        f"[Open deal]({d['url']})"
    )


def notify_hot_buys(hot_buys: List[dict], summary_only: bool = False) -> dict:
    """
    Send notifications about found HOT BUYS via all configured channels.
    Returns dict with status per channel.
    """
    result = {"mac": False, "telegram": False, "count": len(hot_buys)}
    if not hot_buys:
        return result

    top3 = hot_buys[:3]
    summary_lines = []
    for d in top3:
        m = d["_target_match"]
        summary_lines.append(
            f"{m.get('target_brand') or '?'} @ ${d['deal_price']:.2f} "
            f"({d.get('retailer') or '?'}) saves ${m['margin_vs_max']:.2f}"
        )

    body = "\n".join(summary_lines)
    if len(hot_buys) > 3:
        body += f"\n+{len(hot_buys) - 3} more in report.md"

    title = f"{len(hot_buys)} HOT BUY{'S' if len(hot_buys) > 1 else ''} found"
    subtitle = "Deal Hunter"

    result["mac"] = mac_notify(title, body, subtitle)
    if result["mac"]:
        print(f"  [notify] macOS notification sent")

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        header = f"*Deal Hunter:* {len(hot_buys)} HOT BUY{'S' if len(hot_buys) > 1 else ''} found"
        sent = telegram_send(token, chat_id, header)
        if sent and not summary_only:
            for i, d in enumerate(hot_buys[:5], 1):
                if not telegram_send(token, chat_id, _format_hot_buy_telegram(d, i)):
                    break
        result["telegram"] = sent
        if sent:
            print(f"  [notify] Telegram message sent to chat {chat_id}")
    elif token or chat_id:
        print("  [notify] TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID both required for Telegram")

    return result


if __name__ == "__main__":
    print("Testing macOS notification...")
    ok = mac_notify("Test - Deal Hunter", "If you see this, notifications work!", "Setup test")
    print(f"  macOS: {'OK' if ok else 'FAILED or not on Mac'}")

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        print("Testing Telegram...")
        ok = telegram_send(token, chat_id, "*Deal Hunter test* - if you see this, Telegram works!")
        print(f"  Telegram: {'OK' if ok else 'FAILED'}")
    else:
        print("Telegram skipped - set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to test")
