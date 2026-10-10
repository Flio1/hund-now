"""Alexa Custom Skill (AWS Lambda / ask-sdk-frei). Handler: ``lambda_handler``.

Intents: HelloIntent, RunCommandIntent (Slot ``command``), AMAZON.StopIntent/CancelIntent.
Befehle werden an ``COMMAND_HANDLER`` übergeben (z. B. JARVIS) – austauschbar per set_command_handler.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

log = logging.getLogger("alexa_skill")
CommandHandler = Callable[[str], str]


def _default_handler(command: str) -> str:
    return f"Befehl empfangen: {command}"


COMMAND_HANDLER: CommandHandler = _default_handler


def set_command_handler(fn: CommandHandler) -> None:
    global COMMAND_HANDLER
    COMMAND_HANDLER = fn


def _response(text: str, end: bool = True) -> dict[str, Any]:
    return {"version": "1.0", "response": {"outputSpeech": {"type": "PlainText", "text": text}, "shouldEndSession": end}}


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    req = event.get("request", {})
    rtype = req.get("type")
    if rtype == "LaunchRequest":
        return _response("Hallo, was soll ich tun?", end=False)
    if rtype == "SessionEndedRequest":
        return _response("")
    if rtype == "IntentRequest":
        intent = req.get("intent", {})
        name = intent.get("name")
        if name == "HelloIntent":
            return _response("Hallo vom Skill.")
        if name == "RunCommandIntent":
            cmd = (intent.get("slots", {}).get("command", {}) or {}).get("value")
            if not cmd:
                return _response("Welchen Befehl?", end=False)
            try:
                return _response(COMMAND_HANDLER(cmd))
            except Exception:  # noqa: BLE001
                log.exception("Command failed")
                return _response("Das hat nicht geklappt.")
        if name in ("AMAZON.StopIntent", "AMAZON.CancelIntent"):
            return _response("Tschüss.")
    return _response("Das habe ich nicht verstanden.", end=False)
