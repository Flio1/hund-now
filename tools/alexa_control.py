"""Alexa-Steuerung über Home Assistant (REST) oder alexa_remote_control.sh (CLI).

Läuft lokal im selben WLAN wie Alexa. Zugangsdaten stehen in
``tools/alexa_config.json`` (siehe ``alexa_config.example.json``) oder in
den Umgebungsvariablen ``HA_URL``, ``HA_TOKEN``, ``ALEXA_BACKEND``.
Nie Passwörter ins Repo einchecken.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Protocol

import requests

log = logging.getLogger("alexa_control")
CONFIG_PATH = Path(__file__).with_name("alexa_config.json")


class AlexaError(RuntimeError):
    """Fehler bei der Kommunikation mit Alexa/Backend."""


class Backend(Protocol):
    def speak(self, device: str, text: str) -> None: ...
    def play(self, device: str, query: str) -> None: ...
    def volume(self, device: str, level: int) -> None: ...
    def stop(self, device: str) -> None: ...
    def routine(self, name: str) -> None: ...
    def devices(self) -> list[str]: ...


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    p = path or CONFIG_PATH
    if p.exists():
        cfg = json.loads(p.read_text(encoding="utf-8"))
    for key, env in (("ha_url", "HA_URL"), ("ha_token", "HA_TOKEN"), ("backend", "ALEXA_BACKEND")):
        if os.environ.get(env):
            cfg[key] = os.environ[env]
    cfg.setdefault("backend", "homeassistant")
    return cfg


class HomeAssistantBackend:
    """Nutzt die HA-Integration `alexa_media_player` (HACS)."""

    def __init__(self, url: str, token: str, session: requests.Session | None = None) -> None:
        if not url or not token:
            raise AlexaError("ha_url und ha_token fehlen (Config oder HA_URL/HA_TOKEN).")
        self.url = url.rstrip("/")
        self.s = session or requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}"})

    def _call(self, domain: str, service: str, data: dict[str, Any]) -> Any:
        r = self.s.post(f"{self.url}/api/services/{domain}/{service}", json=data, timeout=10)
        if r.status_code >= 400:
            raise AlexaError(f"HA {domain}.{service} -> {r.status_code}: {r.text[:200]}")
        return r.json() if r.content else None

    @staticmethod
    def _entity(device: str) -> str:
        return device if device.startswith("media_player.") else f"media_player.{device}"

    def speak(self, device: str, text: str) -> None:
        self._call("notify", "alexa_media", {"message": text, "target": [self._entity(device)], "data": {"type": "tts"}})

    def play(self, device: str, query: str) -> None:
        self._call("media_player", "play_media", {"entity_id": self._entity(device), "media_content_id": query, "media_content_type": "MUSIC"})

    def volume(self, device: str, level: int) -> None:
        self._call("media_player", "volume_set", {"entity_id": self._entity(device), "volume_level": max(0, min(100, level)) / 100})

    def stop(self, device: str) -> None:
        self._call("media_player", "media_stop", {"entity_id": self._entity(device)})

    def routine(self, name: str) -> None:
        self._call("script", "turn_on", {"entity_id": name if name.startswith("script.") else f"script.{name}"})

    def devices(self) -> list[str]:
        r = self.s.get(f"{self.url}/api/states", timeout=10)
        if r.status_code >= 400:
            raise AlexaError(f"HA states -> {r.status_code}")
        return sorted(e["entity_id"] for e in r.json() if e["entity_id"].startswith("media_player."))


class RemoteControlBackend:
    """Wrapper um https://github.com/thorsten-gehrig/alexa-remote-control (alexa_remote_control.sh)."""

    def __init__(self, script: str | None = None) -> None:
        self.script = script or shutil.which("alexa_remote_control.sh") or ""
        if not self.script:
            raise AlexaError("alexa_remote_control.sh nicht gefunden (Config 'script' setzen).")

    def _run(self, *args: str) -> str:
        res = subprocess.run([self.script, *args], capture_output=True, text=True, timeout=30)
        if res.returncode != 0:
            raise AlexaError(f"alexa_remote_control: {res.stderr.strip()[:200]}")
        return res.stdout

    def speak(self, device: str, text: str) -> None:
        self._run("-d", device, "-e", f"speak:{text}")

    def play(self, device: str, query: str) -> None:
        self._run("-d", device, "-e", f"textcommand:spiele {query}")

    def volume(self, device: str, level: int) -> None:
        self._run("-d", device, "-e", f"vol:{max(0, min(100, level))}")

    def stop(self, device: str) -> None:
        self._run("-d", device, "-e", "pause")

    def routine(self, name: str) -> None:
        self._run("-e", f"automation:{name}")

    def devices(self) -> list[str]:
        return [ln.strip() for ln in self._run("-a").splitlines() if ln.strip()]


def make_backend(cfg: dict[str, Any]) -> Backend:
    kind = cfg.get("backend", "homeassistant")
    if kind == "homeassistant":
        return HomeAssistantBackend(cfg.get("ha_url", ""), cfg.get("ha_token", ""))
    if kind == "remote":
        return RemoteControlBackend(cfg.get("script"))
    raise AlexaError(f"Unbekanntes Backend: {kind}")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["speak", "play", "volume", "stop", "routine", "devices"])
    ap.add_argument("value", nargs="?", default="", help="Text / Suchbegriff / Lautstärke / Routinenname")
    ap.add_argument("-d", "--device", default=None)
    a = ap.parse_args(argv)
    cfg = load_config()
    dev = a.device or cfg.get("default_device", "")
    try:
        b = make_backend(cfg)
        if a.action == "devices":
            print("\n".join(b.devices()))
        elif a.action == "routine":
            b.routine(a.value)
        else:
            if not dev:
                raise AlexaError("Gerät fehlt (-d oder default_device).")
            {"speak": lambda: b.speak(dev, a.value), "play": lambda: b.play(dev, a.value),
             "volume": lambda: b.volume(dev, int(a.value)), "stop": lambda: b.stop(dev)}[a.action]()
    except (AlexaError, requests.RequestException, ValueError) as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
