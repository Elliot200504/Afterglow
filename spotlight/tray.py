# Tray icon with a right-click menu
import threading

import pystray
from PIL import Image

from . import config


def start_tray(app):
    cfg = app._cfg
    item = pystray.MenuItem
    menu = pystray.Menu(
        item("Show / hide", lambda: app._toggle_visible(), default=True),
        item("Always on top", lambda: app._set_option("always_on_top", not cfg["always_on_top"]),
             checked=lambda _: cfg["always_on_top"]),
        item("Crimson theme", lambda: app._set_option("theme", "default" if cfg["theme"] == "crimson" else "crimson"),
             checked=lambda _: cfg["theme"] == "crimson"),
        item("CRT scanlines", lambda: app._set_option("scanlines", not cfg["scanlines"]),
             checked=lambda _: cfg["scanlines"]),
        item("Log out of Spotify", lambda: app._logout(), enabled=lambda _: app._spotify.linked),
        item("Quit", lambda icon: (icon.stop(), app._window.destroy())),
    )
    icon = pystray.Icon("SpotLight", Image.open(config.ICON), "SpotLight", menu)
    threading.Thread(target=icon.run, daemon=True).start()
    return icon
