# Start with: python -m spotlight
import sys
import threading

import keyboard
import webview

from . import config, winutil
from .app import App
from .tray import start_tray


def main():
    if winutil.already_running():
        winutil.tell_running_app_to_show()  # e.g. clicked the pinned icon again
        return

    if sys.stdout is None:  # no console (pythonw / exe): print() goes to the log file instead
        config.APP_DIR.mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = open(config.LOG_FILE, "a", encoding="utf-8", buffering=1)

    winutil.set_app_id()
    app = App()
    cfg = app._cfg
    width, height = config.COMPACT

    # use the saved position if it's still on a screen, otherwise bottom right corner
    x, y = cfg["x"], cfg["y"]
    on_screen = x is not None and any(s.x <= x < s.x + s.width and s.y <= y < s.y + s.height for s in webview.screens)
    if not on_screen:
        screen = webview.screens[0]
        x, y = screen.width - width - 16, screen.height - height - 64

    window = webview.create_window(
        "SpotLight", str(config.UI_DIR / "index.html"), js_api=app,
        width=width, height=height, x=x, y=y,
        frameless=True, easy_drag=False, resizable=False, shadow=False,
        on_top=cfg["always_on_top"], background_color="#07051a",
    )

    def on_shown():
        window.resize(width, height)  # pywebview makes frameless windows a bit too small, fix it
        winutil.round_corners(window.native.Handle.ToInt64())  # native = the windows forms window

    window.events.shown += on_shown
    window.events.moved += app._on_moved

    tray = start_tray(app)
    keyboard.add_hotkey(cfg["hotkey"], app._toggle_visible)
    threading.Thread(target=winutil.wait_for_show, args=(app._show,), daemon=True).start()
    app._start(window)

    webview.start(icon=str(config.ICON))
    tray.stop()


if __name__ == "__main__":
    main()
