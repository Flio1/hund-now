# Alexa-Tools
1. `alexa_control.py` – lokal im WLAN ausführen. `cp alexa_config.example.json alexa_config.json`, Home-Assistant-Token + `alexa_media_player` (HACS) eintragen, dann z. B. `python -m tools.alexa_control speak "Hallo" -d echo_wohnzimmer`. Alternativ `"backend": "remote"` mit alexa_remote_control.sh.
2. `alexa_skill.py` – als AWS-Lambda-Handler im Alexa Developer Console Skill (Intents: HelloIntent, RunCommandIntent mit Slot `command`).
3. `jarvis_alexa_intent.py` – `handle(text)` in JARVIS einhängen ("alexa sag …", "alexa spiel …", "alexa lautstärke 30").
Tests: `python -m pytest tests`
