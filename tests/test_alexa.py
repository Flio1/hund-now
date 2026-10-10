import pytest
import requests

from tools import alexa_control as ac
from tools import alexa_skill as sk
from tools.jarvis_alexa_intent import handle


class FakeResp:
    def __init__(self, status=200, data=None):
        self.status_code, self._d, self.text = status, data, "x"
        self.content = b"1" if data is not None else b""

    def json(self):
        return self._d


class FakeSession:
    def __init__(self, resp):
        self.headers, self.calls, self.resp = {}, [], resp

    def post(self, url, json=None, timeout=0):
        self.calls.append((url, json))
        return self.resp

    def get(self, url, timeout=0):
        return self.resp


def test_ha_speak_and_volume():
    s = FakeSession(FakeResp(200, []))
    b = ac.HomeAssistantBackend("http://ha:8123/", "t", s)
    b.speak("echo", "hi")
    b.volume("echo", 150)
    assert s.calls[0][0].endswith("/api/services/notify/alexa_media")
    assert s.calls[0][1]["target"] == ["media_player.echo"]
    assert s.calls[1][1]["volume_level"] == 1.0


def test_ha_error_and_missing_config():
    with pytest.raises(ac.AlexaError):
        ac.HomeAssistantBackend("", "")
    b = ac.HomeAssistantBackend("http://ha", "t", FakeSession(FakeResp(401)))
    with pytest.raises(ac.AlexaError):
        b.stop("echo")


def test_devices_filter():
    s = FakeSession(FakeResp(200, [{"entity_id": "light.a"}, {"entity_id": "media_player.echo"}]))
    assert ac.HomeAssistantBackend("http://ha", "t", s).devices() == ["media_player.echo"]


def test_remote_backend_missing(monkeypatch):
    monkeypatch.setattr(ac.shutil, "which", lambda _: None)
    with pytest.raises(ac.AlexaError):
        ac.RemoteControlBackend()


def test_skill():
    sk.set_command_handler(lambda c: f"ok {c}")
    ev = {"request": {"type": "IntentRequest", "intent": {"name": "RunCommandIntent", "slots": {"command": {"value": "licht an"}}}}}
    assert sk.lambda_handler(ev)["response"]["outputSpeech"]["text"] == "ok licht an"
    assert sk.lambda_handler({"request": {"type": "LaunchRequest"}})["response"]["shouldEndSession"] is False


def test_jarvis_intent():
    calls = []

    class B:
        def speak(self, d, t): calls.append(("speak", d, t))
        def play(self, d, q): calls.append(("play", d, q))
        def volume(self, d, l): calls.append(("vol", d, l))
        def stop(self, d): calls.append(("stop", d))
        def routine(self, n): calls.append(("routine", n))

    assert handle("alexa sag Hallo Welt", B(), "echo") == "Erledigt."
    assert handle("alexa lautstärke 30", B(), "echo") == "Erledigt."
    assert handle("wie wird das wetter", B()) is None
    assert calls == [("speak", "echo", "Hallo Welt"), ("vol", "echo", 30)]
