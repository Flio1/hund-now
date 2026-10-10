"""JARVIS-Plugin: Alexa-Befehle als Intent.

Einbindung in jarvis_gemini.py:
    from tools.jarvis_alexa_intent import handle
    reply = handle(user_text)   # None = nicht zuständig
Beispiele: "alexa sag Hallo", "alexa spiel Queen", "alexa lautstärke 30", "alexa stopp".
"""
from __future__ import annotations

import re

from tools.alexa_control import AlexaError, load_config, make_backend

_PATTERNS = [
    (re.compile(r"^alexa\s+(?:sag|sage)\s+(.+)$", re.I), "speak"),
    (re.compile(r"^alexa\s+(?:spiel|spiele)\s+(.+)$", re.I), "play"),
    (re.compile(r"^alexa\s+lautst[aä]rke\s+(\d{1,3})$", re.I), "volume"),
    (re.compile(r"^alexa\s+(?:stopp|stop|pause)$", re.I), "stop"),
    (re.compile(r"^alexa\s+routine\s+(.+)$", re.I), "routine"),
]


def handle(text: str, backend=None, device: str | None = None) -> str | None:
    for rx, action in _PATTERNS:
        m = rx.match(text.strip())
        if not m:
            continue
        arg = m.group(1) if m.groups() else ""
        try:
            cfg = load_config()
            b = backend or make_backend(cfg)
            dev = device or cfg.get("default_device", "")
            if action == "speak":
                b.speak(dev, arg)
            elif action == "play":
                b.play(dev, arg)
            elif action == "volume":
                b.volume(dev, int(arg))
            elif action == "stop":
                b.stop(dev)
            else:
                b.routine(arg)
        except AlexaError as exc:
            return f"Alexa-Fehler: {exc}"
        return "Erledigt."
    return None
