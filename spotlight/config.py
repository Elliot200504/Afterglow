import json
import os
import sys
from pathlib import Path

APP_DIR = Path(os.environ["APPDATA"]) / "SpotLight"
CONFIG_FILE = APP_DIR / "config.json"
TOKEN_FILE = APP_DIR / "token.json"
LOG_FILE = APP_DIR / "spotlight.log"

# when running as SpotLight.exe the files are unpacked to sys._MEIPASS
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
UI_DIR = BASE_DIR / "ui"
ICON = BASE_DIR / "assets" / "spotlight.ico"

COMPACT = (420, 140)

DEFAULTS = {
    "client_id": "",
    "x": None,
    "y": None,
    "theme": "default",  # or "crimson"
    "scanlines": False,
    "always_on_top": True,
    "hotkey": "ctrl+alt+s",
    "expanded_w": 420,
    "expanded_h": 520,
}


def _load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save(path, data):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_config():
    return {**DEFAULTS, **(_load(CONFIG_FILE) or {})}


def save_config(cfg):
    _save(CONFIG_FILE, cfg)


def load_token():
    return _load(TOKEN_FILE)


def save_token(token):
    _save(TOKEN_FILE, token)


def delete_token():
    TOKEN_FILE.unlink(missing_ok=True)
